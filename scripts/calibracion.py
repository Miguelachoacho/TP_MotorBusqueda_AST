"""Calibración empírica del umbral, del tamaño de n-grama y de la métrica.

Mide, sobre un corpus real (por defecto, los primeros módulos de la biblioteca estándar):

  * FALSOS POSITIVOS: qué fracción de pares de funciones *no relacionadas* (elegidas al
    azar) alcanza cada umbral.
  * RECALL: qué fracción de *clones sintéticos* (una función real a la que se le aplican
    ediciones: sentencias intercambiadas, eliminadas o insertadas) alcanza cada umbral.

Uso:
    python scripts/calibracion.py [--dir RUTA] [--max-archivos 40] [--pares 1500] [--semilla 7]
"""

import argparse
import ast
import copy
import math
import random
import statistics
import sys
import sysconfig
from pathlib import Path
from typing import Callable, Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from extraccion import FuncionExtraida, extraer_funciones_de_archivo  # noqa: E402
from similitud import (  # noqa: E402
    calcular_similitud, serializar_ast,
)
from normalizacion import normalizar_funcion  # noqa: E402

UMBRALES = [0.5, 0.6, 0.7, 0.75, 0.8, 0.9]
CONFIGURACIONES = [("levenshtein", 3), ("jaccard", 2), ("jaccard", 3), ("jaccard", 4), ("jaccard", 5)]
FRACCIONES_EDICION = [0.1, 0.2, 0.3, 0.5]


def tokens(nodo: ast.AST) -> List[str]:
    return serializar_ast(normalizar_funcion(nodo))


def listas_de_sentencias(nodo: ast.AST) -> List[List[ast.stmt]]:
    """Todas las listas de sentencias (cuerpos, else, finally) de una función."""
    listas = []
    for n in ast.walk(nodo):
        for campo in ("body", "orelse", "finalbody"):
            valor = getattr(n, campo, None)
            if isinstance(valor, list) and valor and isinstance(valor[0], ast.stmt):
                listas.append(valor)
    return listas


def mutar(nodo, fraccion: float, rng: random.Random):
    """Copia de la función con ~fraccion de sus sentencias editadas (swap / delete / insert)."""
    copia = copy.deepcopy(nodo)
    total = sum(len(l) for l in listas_de_sentencias(copia))
    ediciones = max(1, round(total * fraccion))
    for _ in range(ediciones):
        listas = [l for l in listas_de_sentencias(copia) if len(l) >= 2]
        if not listas:
            break
        lista = rng.choice(listas)
        operacion = rng.choice(["swap", "delete", "insert"])
        i = rng.randrange(len(lista) - 1)
        if operacion == "swap":
            lista[i], lista[i + 1] = lista[i + 1], lista[i]
        elif operacion == "delete":
            del lista[i]
        else:
            lista.insert(i, copy.deepcopy(rng.choice(lista)))
    return ast.fix_missing_locations(copia)


def percentil(valores: List[float], p: float) -> float:
    ordenados = sorted(valores)
    return ordenados[min(len(ordenados) - 1, math.ceil(p * len(ordenados)) - 1)]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", default=sysconfig.get_paths()["stdlib"])
    ap.add_argument("--max-archivos", type=int, default=40)
    ap.add_argument("--pares", type=int, default=1500)
    ap.add_argument("--clones", type=int, default=150)
    ap.add_argument("--semilla", type=int, default=7)
    args = ap.parse_args()
    rng = random.Random(args.semilla)

    funciones: List[FuncionExtraida] = []
    for archivo in sorted(Path(args.dir).glob("*.py"))[: args.max_archivos]:
        funciones.extend(extraer_funciones_de_archivo(archivo))
    # Se descartan funciones triviales (< 20 tokens) y gigantes (> 250) para acotar el costo.
    corpus = [(f, tokens(f.nodo_ast)) for f in funciones]
    corpus = [(f, t) for f, t in corpus if 20 <= len(t) <= 250 and len(listas_de_sentencias(f.nodo_ast)) > 0]
    print(f"Corpus: {len(corpus)} funciones de los primeros {args.max_archivos} módulos de {args.dir}")
    print(f"Tokens por función: mediana={statistics.median(len(t) for _, t in corpus):.0f}\n")

    # ---- Falsos positivos: pares al azar ---------------------------------------------
    pares = [rng.sample(range(len(corpus)), 2) for _ in range(args.pares)]
    print(f"## Pares NO relacionados ({args.pares} pares al azar): fracción que supera cada umbral")
    encabezado = "| Métrica | mediana | p95 | máx | " + " | ".join(f">={u}" for u in UMBRALES) + " |"
    print(encabezado)
    print("|" + "---|" * (4 + len(UMBRALES)))
    for metrica, n in CONFIGURACIONES:
        scores = [calcular_similitud(corpus[i][1], corpus[j][1], metrica, n) for i, j in pares]
        fila = [f"{statistics.median(scores):.3f}", f"{percentil(scores, 0.95):.3f}", f"{max(scores):.3f}"]
        fila += [f"{sum(s >= u for s in scores) / len(scores):.1%}" for u in UMBRALES]
        etiqueta = metrica if metrica == "levenshtein" else f"jaccard n={n}"
        print(f"| {etiqueta} | " + " | ".join(fila) + " |")

    # ---- Recall: clones sintéticos ------------------------------------------------------
    candidatas = [(f, t) for f, t in corpus if sum(len(l) for l in listas_de_sentencias(f.nodo_ast)) >= 4]
    muestra = rng.sample(candidatas, min(args.clones, len(candidatas)))
    for fraccion in FRACCIONES_EDICION:
        print(f"\n## Clones con ~{fraccion:.0%} de sentencias editadas ({len(muestra)} clones): fracción detectada")
        print("| Métrica | mediana | " + " | ".join(f">={u}" for u in UMBRALES) + " |")
        print("|" + "---|" * (2 + len(UMBRALES)))
        clones = [(t, tokens(mutar(f.nodo_ast, fraccion, rng))) for f, t in muestra]
        for metrica, n in CONFIGURACIONES:
            scores = [calcular_similitud(a, b, metrica, n) for a, b in clones]
            fila = [f"{statistics.median(scores):.3f}"] + [f"{sum(s >= u for s in scores) / len(scores):.0%}" for u in UMBRALES]
            etiqueta = metrica if metrica == "levenshtein" else f"jaccard n={n}"
            print(f"| {etiqueta} | " + " | ".join(fila) + " |")


if __name__ == "__main__":
    main()
