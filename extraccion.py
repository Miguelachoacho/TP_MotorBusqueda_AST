"""Fase 1 - Extracción.

Recorre un directorio, parsea cada archivo .py con ``ast.parse`` y extrae todas las
definiciones de funciones (``def`` y ``async def``) junto con su metadata:
nombre original, archivo, línea y subárbol AST.
"""

import ast
import sys
import textwrap
from dataclasses import dataclass
from pathlib import Path
from typing import List, Union

# Una función puede ser síncrona o asíncrona; ambas comparten los atributos que usamos.
NodoFuncion = Union[ast.FunctionDef, ast.AsyncFunctionDef]

# Carpetas que no forman parte del código del repositorio (entornos virtuales, cachés, etc.).
DIRECTORIOS_IGNORADOS = {
    ".git", "__pycache__", ".pytest_cache", ".venv", "venv", "env", "node_modules",
}


@dataclass
class FuncionExtraida:
    """Una función encontrada en el código fuente, con su metadata."""

    nombre: str                 # nombre original (ej.: "visit_FunctionDef")
    archivo: str                # archivo de origen
    linea: int                  # línea donde comienza el "def"
    nodo_ast: NodoFuncion       # subárbol AST de la función
    nombre_calificado: str = ""  # nombre con su contexto (ej.: "Extractor.visit_FunctionDef")

    def __post_init__(self) -> None:
        if not self.nombre_calificado:
            self.nombre_calificado = self.nombre


class ExtractorFunciones(ast.NodeVisitor):
    """Recorre un AST y registra cada FunctionDef / AsyncFunctionDef encontrada.

    Es un ``NodeVisitor`` (solo lectura): no modifica el árbol. Lleva una pila con los
    nombres de las clases y funciones contenedoras para construir el nombre calificado,
    de modo que los métodos homónimos de distintas clases puedan distinguirse.
    """

    def __init__(self, ruta_archivo: str) -> None:
        self.ruta_archivo = ruta_archivo
        self.funciones: List[FuncionExtraida] = []
        self._contexto: List[str] = []

    def _registrar_funcion(self, node: NodoFuncion) -> None:
        calificado = ".".join(self._contexto + [node.name])
        self.funciones.append(
            FuncionExtraida(
                nombre=node.name,
                archivo=self.ruta_archivo,
                linea=node.lineno,
                nodo_ast=node,
                nombre_calificado=calificado,
            )
        )
        # Seguimos descendiendo: así también se encuentran las funciones anidadas.
        self._contexto.append(node.name)
        self.generic_visit(node)
        self._contexto.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._registrar_funcion(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._registrar_funcion(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        # Los métodos son funciones definidas dentro de una clase.
        self._contexto.append(node.name)
        self.generic_visit(node)
        self._contexto.pop()


def extraer_funciones_de_codigo(codigo: str, nombre_archivo: str = "<codigo>") -> List[FuncionExtraida]:
    """Extrae las funciones de un string con código Python.

    Lanza ``SyntaxError`` si el código no es válido (el llamador decide qué hacer).
    """
    arbol = ast.parse(textwrap.dedent(codigo), filename=nombre_archivo)
    extractor = ExtractorFunciones(ruta_archivo=nombre_archivo)
    extractor.visit(arbol)
    return extractor.funciones


def extraer_funciones_de_archivo(ruta_archivo: Path) -> List[FuncionExtraida]:
    """Lee un archivo .py, genera su AST y extrae sus funciones.

    Un archivo ilegible o con errores de sintaxis se informa por stderr y se omite,
    para que un único archivo defectuoso no interrumpa el análisis de todo el repositorio.
    """
    try:
        codigo = ruta_archivo.read_text(encoding="utf-8")
        return extraer_funciones_de_codigo(codigo, nombre_archivo=str(ruta_archivo))
    except (SyntaxError, UnicodeDecodeError, ValueError) as error:
        print(f"[Advertencia] No se pudo parsear {ruta_archivo}: {error}", file=sys.stderr)
        return []


def _es_directorio_ignorado(ruta: Path, raiz: Path) -> bool:
    return any(parte in DIRECTORIOS_IGNORADOS for parte in ruta.relative_to(raiz).parts[:-1])


def extraer_funciones_de_directorio(ruta_directorio: str) -> List[FuncionExtraida]:
    """Recorre recursivamente un directorio y extrae las funciones de todos los .py."""
    directorio = Path(ruta_directorio)
    if not directorio.is_dir():
        raise ValueError(f"La ruta '{ruta_directorio}' no existe o no es un directorio válido.")

    funciones: List[FuncionExtraida] = []
    # sorted(): orden determinista sin importar el sistema operativo.
    for archivo_py in sorted(directorio.rglob("*.py")):
        if _es_directorio_ignorado(archivo_py, directorio):
            continue
        funciones.extend(extraer_funciones_de_archivo(archivo_py))
    return funciones
