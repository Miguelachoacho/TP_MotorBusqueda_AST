"""Fase 3 - Serialización y métricas de similitud.

1. Serializa un AST normalizado a una secuencia lineal de tokens (recorrido pre-order).
2. Compara dos secuencias con (a) similitud de Levenshtein normalizada o
   (b) similitud de Jaccard sobre n-gramas.
3. Expone el motor de búsqueda top-K (comparación todos-contra-uno, O(n) por consulta).
"""

import ast
from dataclasses import dataclass
from typing import List, Set, Tuple

from extraccion import FuncionExtraida
from normalizacion import normalizar_funcion

# Umbral a partir del cual dos funciones son "candidatas a duplicado".
# Justificación empírica en el informe (scripts/calibracion.py).
UMBRAL_DUPLICADO: float = 0.75

# Tamaño de n-grama por defecto para Jaccard (justificado en el informe).
N_GRAMA_DEFECTO: int = 3

# Nodos de contexto (Load/Store/Del) que se omiten: no aportan estructura y duplican la longitud.
NODOS_IGNORADOS = (ast.Load, ast.Store, ast.Del)

# Atributo de cada tipo de nodo que viaja junto al tipo en el token ("Name" -> "Name:VAR1").
ATRIBUTO_ETIQUETA = {
    ast.FunctionDef: "name",
    ast.AsyncFunctionDef: "name",
    ast.ClassDef: "name",
    ast.arg: "arg",
    ast.Name: "id",
    ast.Constant: "value",
    ast.Attribute: "attr",     # nombres de API (append, upper...) cambian el significado
    ast.keyword: "arg",
    ast.alias: "name",
    ast.ExceptHandler: "name",
}


class SerializadorPreOrder(ast.NodeVisitor):
    """Genera la secuencia de tokens de un AST con un recorrido pre-order.

    Pre-order: primero se registra el nodo actual y recién después se visitan sus hijos
    de izquierda a derecha. Se logra sobrescribiendo ``generic_visit``: el token se agrega
    *antes* de llamar a ``super().generic_visit`` (que es quien desciende a los hijos).
    """

    def __init__(self) -> None:
        self.tokens: List[str] = []

    def generic_visit(self, node: ast.AST) -> None:
        if isinstance(node, NODOS_IGNORADOS):
            return
        self.tokens.append(self._token_de(node))
        super().generic_visit(node)

    @staticmethod
    def _token_de(node: ast.AST) -> str:
        tipo = type(node).__name__
        if isinstance(node, (ast.Global, ast.Nonlocal)):
            return f"{tipo}:{','.join(node.names)}"
        atributo = ATRIBUTO_ETIQUETA.get(type(node))
        valor = getattr(node, atributo) if atributo else None
        if valor is None and not isinstance(node, ast.Constant):
            return tipo                      # ej.: "except:" sin nombre, "**kwargs" en keyword
        return f"{tipo}:{valor}"


def serializar_ast(nodo_ast: ast.AST) -> List[str]:
    """Convierte un AST (normalizado) en una lista lineal de tokens en pre-orden."""
    serializador = SerializadorPreOrder()
    serializador.visit(nodo_ast)
    return serializador.tokens


def tokens_de_funcion(funcion: FuncionExtraida) -> List[str]:
    """Pipeline completo para una función: normalizar y serializar."""
    return serializar_ast(normalizar_funcion(funcion.nodo_ast))


# ---------------------------------------------------------------------------
# Métrica 1: distancia de edición (Levenshtein) normalizada
# ---------------------------------------------------------------------------
def distancia_levenshtein(seq1: List[str], seq2: List[str]) -> int:
    """Mínimo de inserciones, eliminaciones y sustituciones para transformar seq1 en seq2.

    Programación dinámica con dos filas (memoria O(min(n, m)) en lugar de O(n*m)).
    """
    if len(seq1) < len(seq2):
        seq1, seq2 = seq2, seq1
    anterior = list(range(len(seq2) + 1))
    for i, a in enumerate(seq1, start=1):
        actual = [i]
        for j, b in enumerate(seq2, start=1):
            costo = 0 if a == b else 1
            actual.append(min(anterior[j] + 1,          # eliminación
                              actual[j - 1] + 1,        # inserción
                              anterior[j - 1] + costo))  # sustitución / coincidencia
        anterior = actual
    return anterior[-1]


def similitud_levenshtein(seq1: List[str], seq2: List[str]) -> float:
    """1 - distancia / longitud_máxima  ->  rango [0.0, 1.0] (1.0 = secuencias idénticas)."""
    if not seq1 and not seq2:
        return 1.0
    return 1.0 - distancia_levenshtein(seq1, seq2) / max(len(seq1), len(seq2))


# ---------------------------------------------------------------------------
# Métrica 2: Jaccard sobre n-gramas
# ---------------------------------------------------------------------------
def generar_ngramas(secuencia: List[str], n: int = N_GRAMA_DEFECTO) -> Set[Tuple[str, ...]]:
    """Conjunto de ventanas deslizantes de n tokens consecutivos."""
    if not secuencia:
        return set()
    if len(secuencia) < n:               # función más corta que n: se usa la secuencia entera
        return {tuple(secuencia)}
    return {tuple(secuencia[i:i + n]) for i in range(len(secuencia) - n + 1)}


def similitud_jaccard(seq1: List[str], seq2: List[str], n: int = N_GRAMA_DEFECTO) -> float:
    """|A ∩ B| / |A ∪ B| sobre los conjuntos de n-gramas de ambas secuencias."""
    if not seq1 and not seq2:
        return 1.0
    a, b = generar_ngramas(seq1, n), generar_ngramas(seq2, n)
    union = len(a | b)
    return len(a & b) / union if union else 0.0


METRICAS = ("levenshtein", "jaccard")


def calcular_similitud(seq1: List[str], seq2: List[str], metrica: str = "jaccard",
                       n_grama: int = N_GRAMA_DEFECTO) -> float:
    if metrica == "levenshtein":
        return similitud_levenshtein(seq1, seq2)
    if metrica == "jaccard":
        return similitud_jaccard(seq1, seq2, n=n_grama)
    raise ValueError(f"Métrica desconocida '{metrica}'. Opciones: {', '.join(METRICAS)}.")


# ---------------------------------------------------------------------------
# Motor de búsqueda top-K
# ---------------------------------------------------------------------------
@dataclass
class ResultadoComparacion:
    """Resultado de comparar una función candidata contra la función objetivo."""

    funcion_candidata: FuncionExtraida
    score: float
    es_duplicado: bool


def _es_la_misma(a: FuncionExtraida, b: FuncionExtraida) -> bool:
    return (a is b) or (a.archivo, a.linea, a.nombre_calificado) == (b.archivo, b.linea, b.nombre_calificado)


def buscar_similares(
    funcion_objetivo: FuncionExtraida,
    universo_funciones: List[FuncionExtraida],
    metrica: str = "jaccard",
    top_k: int = 5,
    n_grama: int = N_GRAMA_DEFECTO,
    umbral: float = UMBRAL_DUPLICADO,
) -> List[ResultadoComparacion]:
    """Devuelve las ``top_k`` funciones del universo más similares a la objetivo.

    La función objetivo se excluye del ranking. Se normaliza y serializa cada función una
    sola vez por consulta; el costo es lineal en la cantidad de funciones del universo.
    """
    tokens_objetivo = tokens_de_funcion(funcion_objetivo)
    resultados: List[ResultadoComparacion] = []

    for candidata in universo_funciones:
        if _es_la_misma(candidata, funcion_objetivo):
            continue
        tokens = tokens_de_funcion(candidata)
        score = calcular_similitud(tokens_objetivo, tokens, metrica, n_grama)
        resultados.append(ResultadoComparacion(candidata, round(score, 4), score >= umbral))

    resultados.sort(key=lambda r: r.score, reverse=True)
    return resultados[:max(top_k, 0)]


def comparar_funciones(f1: FuncionExtraida, f2: FuncionExtraida, metrica: str = "jaccard",
                       n_grama: int = N_GRAMA_DEFECTO) -> float:
    """Similitud entre dos funciones puntuales (atajo útil para tests y experimentos)."""
    return calcular_similitud(tokens_de_funcion(f1), tokens_de_funcion(f2), metrica, n_grama)

