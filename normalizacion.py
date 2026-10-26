"""Fase 2 - Normalización.

Transforma el AST de una función para que dos funciones que solo difieren en nombres
de variables, nombres de parámetros, valores literales o nombre propio produzcan
exactamente el mismo árbol.

Reglas aplicadas (cada una está justificada en el informe):
  * Variables y parámetros  -> VAR1, VAR2, ... (misma correspondencia dentro de la función).
  * Literales numéricos / strings / bytes -> "LIT".
  * Nombre de la función (y llamadas recursivas a sí misma) -> "FUNC".
  * Docstrings y anotaciones de tipo se descartan (no alteran el comportamiento).
  * Nombres nativos de Python (len, range, print...) se conservan, salvo que la función
    los redefina localmente (ej.: un parámetro llamado ``sum``).
"""

import ast
import builtins
import copy
from typing import Dict, Set

from extraccion import NodoFuncion

NOMBRES_BUILTINS = set(dir(builtins))


def _recolectar_nombres_ligados(nodo: NodoFuncion) -> Set[str]:
    """Nombres que la función *define* (parámetros, asignaciones, imports, etc.).

    Sirve para distinguir un ``sum`` nativo de un ``sum`` que el programador usó como
    nombre de variable: el segundo debe normalizarse como cualquier otra variable.
    """
    ligados: Set[str] = set()
    for n in ast.walk(nodo):
        if isinstance(n, ast.arg):
            ligados.add(n.arg)
        elif isinstance(n, ast.Name) and isinstance(n.ctx, (ast.Store, ast.Del)):
            ligados.add(n.id)
        elif isinstance(n, ast.ExceptHandler) and n.name:
            ligados.add(n.name)
        elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and n is not nodo:
            ligados.add(n.name)
        elif isinstance(n, ast.alias):
            ligados.add((n.asname or n.name).split(".")[0])
        elif isinstance(n, (ast.Global, ast.Nonlocal)):
            ligados.update(n.names)
    return ligados


class NormalizadorAST(ast.NodeTransformer):
    """``NodeTransformer`` que reemplaza identificadores y literales por tokens genéricos.

    Debe usarse una instancia nueva por cada función: el diccionario de correspondencia
    ``mapa_variables`` es local a la función que se está normalizando.
    """

    def __init__(self, nombres_ligados: Set[str] = frozenset()) -> None:
        self.mapa_variables: Dict[str, str] = {}
        self.contador_variables = 0
        self._nombres_ligados = set(nombres_ligados)
        self._nombre_raiz: str = ""

    # -- utilidades ---------------------------------------------------------
    def _token(self, nombre: str) -> str:
        """Token genérico asociado a un identificador (VARn, FUNC o el mismo nombre nativo)."""
        if self._nombre_raiz and nombre == self._nombre_raiz:
            return "FUNC"  # llamada recursiva a la propia función
        if nombre in NOMBRES_BUILTINS and nombre not in self._nombres_ligados:
            return nombre
        if nombre not in self.mapa_variables:
            self.contador_variables += 1
            self.mapa_variables[nombre] = f"VAR{self.contador_variables}"
        return self.mapa_variables[nombre]

    @staticmethod
    def _quitar_docstring(node: NodoFuncion) -> None:
        cuerpo = node.body
        if (cuerpo and isinstance(cuerpo[0], ast.Expr)
                and isinstance(cuerpo[0].value, ast.Constant)
                and isinstance(cuerpo[0].value.value, str)):
            node.body = cuerpo[1:] or [ast.Pass()]

    # -- funciones ----------------------------------------------------------
    def _visitar_definicion(self, node: NodoFuncion) -> ast.AST:
        if not self._nombre_raiz:        # la primera definición visitada es la función raíz
            self._nombre_raiz = node.name
            node.name = "FUNC"
        else:                            # función anidada: se trata como una variable local
            node.name = self._token(node.name)
        self._quitar_docstring(node)
        node.returns = None
        return self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.AST:
        return self._visitar_definicion(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> ast.AST:
        return self._visitar_definicion(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> ast.AST:
        node.name = self._token(node.name)
        return self.generic_visit(node)

    # -- identificadores ----------------------------------------------------
    def visit_arg(self, node: ast.arg) -> ast.AST:
        """Parámetro en la firma del def (nodo ``ast.arg``, nombre en ``node.arg``)."""
        node.arg = self._token(node.arg)
        node.annotation = None
        return self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> ast.AST:
        """Uso de una variable en el cuerpo (nodo ``ast.Name``, nombre en ``node.id``)."""
        node.id = self._token(node.id)
        return node

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> ast.AST:
        if node.name:
            node.name = self._token(node.name)
        return self.generic_visit(node)

    def visit_Global(self, node: ast.Global) -> ast.AST:
        node.names = [self._token(n) for n in node.names]
        return node

    def visit_Nonlocal(self, node: ast.Nonlocal) -> ast.AST:
        node.names = [self._token(n) for n in node.names]
        return node

    def visit_AnnAssign(self, node: ast.AnnAssign) -> ast.AST:
        """``x: int = 5`` se trata como ``x = 5``; una declaración sin valor se descarta."""
        if node.value is None:
            return ast.copy_location(ast.Pass(), node)
        asignacion = ast.copy_location(ast.Assign(targets=[node.target], value=node.value), node)
        return self.generic_visit(asignacion)

    # -- literales ----------------------------------------------------------
    def visit_Constant(self, node: ast.Constant) -> ast.AST:
        """Números, strings y bytes -> "LIT". True/False/None se conservan (bool es subclase de int)."""
        if isinstance(node.value, (int, float, complex, str, bytes)) and not isinstance(node.value, bool):
            node.value = "LIT"
        return node


def normalizar_funcion(nodo_funcion: NodoFuncion) -> NodoFuncion:
    """Devuelve una copia normalizada del subárbol de una función (el original no se modifica)."""
    copia = copy.deepcopy(nodo_funcion)
    normalizador = NormalizadorAST(_recolectar_nombres_ligados(copia))
    normalizado = normalizador.visit(copia)
    ast.fix_missing_locations(normalizado)
    return normalizado


def previsualizar_codigo_normalizado(nodo_normalizado: NodoFuncion) -> str:
    """Regenera código legible desde un AST normalizado (útil para depurar y para la demo)."""
    return ast.unparse(nodo_normalizado)
