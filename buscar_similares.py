"""Fase 4 - Interfaz de línea de comandos.

Ejemplos:
    python buscar_similares.py --dir ./mi_repo --funcion archivo.py:mi_funcion --top 5
    python buscar_similares.py --dir ./mi_repo --funcion modulo.py:Clase.metodo --metrica levenshtein
    python buscar_similares.py --dir ./mi_repo --codigo "def f(a, b): return a + b"
    cat mi_funcion.py | python buscar_similares.py --dir ./mi_repo --codigo -
"""

import argparse
import sys
from pathlib import Path
from typing import List, Optional, Sequence
from extraccion import FuncionExtraida, extraer_funciones_de_codigo, extraer_funciones_de_directorio
from similitud import METRICAS, N_GRAMA_DEFECTO, UMBRAL_DUPLICADO, buscar_similares


def _coincide_archivo(ruta_funcion: str, ruta_buscada: str) -> bool:
    """True si ``ruta_buscada`` es un sufijo (por componentes) de ``ruta_funcion``.

    Comparar por componentes evita falsos aciertos como "tils.py" con "utils.py".
    """
    partes_funcion = Path(ruta_funcion).parts
    partes_buscadas = Path(ruta_buscada).parts
    if not partes_buscadas or len(partes_buscadas) > len(partes_funcion):
        return False
    return partes_funcion[-len(partes_buscadas):] == partes_buscadas


def encontrar_funcion_objetivo(especificacion: str, universo: List[FuncionExtraida]) -> List[FuncionExtraida]:
    """Resuelve 'archivo.py:nombre' en las funciones que coinciden (puede haber 0, 1 o varias).

    Formatos aceptados para la parte del nombre:
        nombre            -> cualquier función con ese nombre (incluye métodos)
        Clase.metodo      -> nombre calificado
        nombre@123        -> la que empieza en la línea 123
    """
    if ":" not in especificacion:
        raise ValueError(f"Formato inválido '{especificacion}'. Use 'archivo.py:nombre_funcion'.")
    ruta_buscada, nombre_buscado = especificacion.rsplit(":", maxsplit=1)
    nombre_buscado, _, linea_texto = nombre_buscado.partition("@")
    linea = int(linea_texto) if linea_texto.isdigit() else None

    en_archivo = [f for f in universo if _coincide_archivo(f.archivo, ruta_buscada)]
    exactas = [f for f in en_archivo if f.nombre_calificado == nombre_buscado]
    candidatas = exactas or [f for f in en_archivo if f.nombre == nombre_buscado]
    if linea is not None:
        candidatas = [f for f in candidatas if f.linea == linea]
    return candidatas


def obtener_funcion_pegada(codigo: str) -> Optional[FuncionExtraida]:
    """Primera función definida en un fragmento de código pegado (None si no define ninguna)."""
    funciones = extraer_funciones_de_codigo(codigo)
    return funciones[0] if funciones else None


def configurar_argumentos(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Motor de búsqueda de funciones Python estructuralmente similares (vía AST).",
        epilog="Si hay varias coincidencias, use 'archivo.py:Clase.metodo' o 'archivo.py:nombre@linea'.",
    )
    parser.add_argument("--dir", required=True, help="Directorio o repositorio local a analizar.")
    objetivo = parser.add_mutually_exclusive_group(required=True)
    objetivo.add_argument("--funcion", help="Función objetivo con formato 'archivo.py:nombre_funcion'.")
    objetivo.add_argument("--codigo", help="Código de la función objetivo pegado como texto ('-' lee de stdin).")
    parser.add_argument("--top", type=int, default=5, help="Cantidad de resultados a mostrar (defecto: 5).")
    parser.add_argument("--metrica", choices=METRICAS, default="jaccard",
                        help="Métrica de similitud (defecto: jaccard).")
    parser.add_argument("--n", type=int, default=N_GRAMA_DEFECTO,
                        help=f"Tamaño de n-grama para Jaccard (defecto: {N_GRAMA_DEFECTO}).")
    parser.add_argument("--umbral", type=float, default=UMBRAL_DUPLICADO,
                        help=f"Umbral de 'candidata a duplicado' (defecto: {UMBRAL_DUPLICADO}).")
    args = parser.parse_args(argv)
    if args.top < 1 or args.n < 1:
        parser.error("--top y --n deben ser enteros positivos.")
    if not 0.0 <= args.umbral <= 1.0:
        parser.error("--umbral debe estar entre 0 y 1.")
    return args


def _error(mensaje: str) -> int:
    print(f"[Error] {mensaje}", file=sys.stderr)
    return 1


def _resolver_objetivo(args: argparse.Namespace, universo: List[FuncionExtraida]) -> Optional[FuncionExtraida]:
    """Devuelve la función objetivo o None (habiendo informado el motivo por stderr)."""
    if args.codigo is not None:
        codigo = sys.stdin.read() if args.codigo == "-" else args.codigo
        try:
            objetivo = obtener_funcion_pegada(codigo)
        except SyntaxError as error:
            _error(f"El código pegado no es Python válido: {error}")
            return None
        if objetivo is None:
            _error("El código pegado no define ninguna función (use 'def nombre(...):').")
        return objetivo

    try:
        coincidencias = encontrar_funcion_objetivo(args.funcion, universo)
    except ValueError as error:
        _error(str(error))
        return None
    if not coincidencias:
        _error(f"No se encontró la función '{args.funcion}' dentro de '{args.dir}'.")
        return None
    if len(coincidencias) > 1:
        detalle = "\n".join(f"  - {f.nombre_calificado} ({f.archivo}:{f.linea})" for f in coincidencias)
        _error(f"'{args.funcion}' es ambigua; coincide con:\n{detalle}\n"
               "Use 'archivo.py:Clase.metodo' o 'archivo.py:nombre@linea'.")
        return None
    return coincidencias[0]


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = configurar_argumentos(argv)

    try:
        universo = extraer_funciones_de_directorio(args.dir)
    except ValueError as error:
        return _error(str(error))
    if not universo:
        print(f"No se encontraron funciones Python en '{args.dir}'.")
        return 0

    objetivo = _resolver_objetivo(args, universo)
    if objetivo is None:
        return 1

    resultados = buscar_similares(objetivo, universo, metrica=args.metrica, top_k=args.top,
                                  n_grama=args.n, umbral=args.umbral)

    ancho = 78
    detalle_metrica = args.metrica.upper() + (f" (n={args.n})" if args.metrica == "jaccard" else "")
    print("=" * ancho)
    print(f"FUNCIÓN OBJETIVO : {objetivo.nombre_calificado} ({objetivo.archivo}:{objetivo.linea})")
    print(f"MÉTRICA          : {detalle_metrica} | umbral de duplicado: {args.umbral}")
    print(f"FUNCIONES EN REPO: {len(universo)} analizadas")
    print("=" * ancho)
    if not resultados:
        print("No hay otras funciones en el repositorio para comparar.")
        return 0

    print(f"{'#':<3} | {'SCORE':<7} | {'ESTADO':<10} | FUNCIÓN CANDIDATA (ARCHIVO:LÍNEA)")
    print("-" * ancho)
    for i, r in enumerate(resultados, start=1):
        c = r.funcion_candidata
        estado = "DUPLICADO" if r.es_duplicado else "distinta"
        print(f"{i:<3} | {r.score:<7.4f} | {estado:<10} | {c.nombre_calificado} ({c.archivo}:{c.linea})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
