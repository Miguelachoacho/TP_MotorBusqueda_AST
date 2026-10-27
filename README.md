# Motor de búsqueda de funciones similares vía AST

Trabajo Práctico grupal — **Lenguajes Formales y Autómatas 2026** (UCSE).

Dado un conjunto de archivos fuente en Python, la herramienta extrae todas las funciones, las
representa mediante su Árbol de Sintaxis Abstracta (AST) normalizado y permite buscar cuáles son
estructuralmente similares a una función dada. Es una versión reducida del principio que usan
herramientas de detección de código duplicado como SonarQube o PMD/CPD.

**Integrantes:** Demaria Angelo; Giordano Mateo; Quiroga Santiago

## Requisitos

- Python 3.9 o superior (la herramienta usa solo la biblioteca estándar).
- `pytest` únicamente para correr los tests: `pip install -r requirements.txt`.

## Organización del código

| Archivo | Fase | Responsabilidad |
|---|---|---|
| `extraccion.py` | 1 | Recorre un directorio, parsea cada `.py` con `ast.parse` y extrae las `FunctionDef` / `AsyncFunctionDef` (nombre, archivo, línea, subárbol). Usa `ast.NodeVisitor`. |
| `normalizacion.py` | 2 | Reemplaza variables/parámetros por `VAR1, VAR2…`, literales por `LIT` y el nombre de la función por `FUNC`. Usa `ast.NodeTransformer`. |
| `similitud.py` | 3 | Serializa el AST a tokens (recorrido pre-order), implementa Levenshtein normalizado y Jaccard sobre n-gramas, y el motor top-K. |
| `buscar_similares.py` | 4 | CLI (`argparse`). |
| `tests/` | 4 | Suite `pytest` (55 tests): casos positivos, negativos, unitarios y de CLI. |
| `scripts/calibracion.py` | — | Experimento que justifica el umbral, el n-grama y la métrica (resultados en `docs/resultados_calibracion.md`). |
| `ejemplos/repo_demo/` | — | Mini repositorio con clones Tipo 2, Tipo 3 y Tipo 4 para probar la herramienta. |
| `docs/` | — | Informe (máx. 2 páginas) y documento completo del TP. |

## Uso

```bash
# Por archivo + nombre de función
python buscar_similares.py --dir ./mi_repo --funcion archivo.py:mi_funcion --top 5

# Método de una clase (nombre calificado) o función por línea, si el nombre es ambiguo
python buscar_similares.py --dir ./mi_repo --funcion modelos.py:Cliente.guardar
python buscar_similares.py --dir ./mi_repo --funcion modelos.py:guardar@42

# Pegando el código de la función objetivo (o "-" para leerlo de stdin)
python buscar_similares.py --dir ./mi_repo --codigo "def f(a, b): return a + b"
cat mi_funcion.py | python buscar_similares.py --dir ./mi_repo --codigo -

# Elegir métrica, n-grama y umbral
python buscar_similares.py --dir ./mi_repo --funcion a.py:f --metrica levenshtein
python buscar_similares.py --dir ./mi_repo --funcion a.py:f --metrica jaccard --n 2 --umbral 0.65
```

Opciones: `--top K` (defecto 5) · `--metrica {levenshtein,jaccard}` (defecto `jaccard`) ·
`--n N` (tamaño de n-grama, defecto 3) · `--umbral U` (defecto 0.75).

### Ejemplo con el repositorio de demostración

```text
$ python buscar_similares.py --dir ejemplos/repo_demo --funcion ventas.py:calcular_descuento --top 3
FUNCIÓN OBJETIVO : calcular_descuento (ejemplos/repo_demo/ventas.py:4)
MÉTRICA          : JACCARD (n=3) | umbral de duplicado: 0.75
#   | SCORE   | ESTADO     | FUNCIÓN CANDIDATA (ARCHIVO:LÍNEA)
1   | 1.0000  | DUPLICADO  | aplicar_rebaja (ejemplos/repo_demo/facturacion.py:5)
2   | 0.6667  | distinta   | calcular_descuento_validado (ejemplos/repo_demo/facturacion.py:14)
3   | 0.1579  | distinta   | factorial_recursivo (ejemplos/repo_demo/utilidades.py:31)
```

## Decisiones principales

- **Métrica por defecto:** Jaccard sobre trigramas (n = 3). Levenshtein normalizado está disponible
  y es complementario (tolera mejor un bloque insertado; Jaccard tolera mejor líneas reordenadas).
- **Umbral de "candidata a duplicado":** 0.75 (conservador: prioriza no generar falsas alarmas).
  Es configurable con `--umbral`. La evidencia empírica está en `docs/resultados_calibracion.md`.
- **Normalización:** además de variables, literales y nombre propio, se descartan docstrings y
  anotaciones de tipo, y se conservan los nombres nativos (`len`, `range`, …) y los nombres de
  atributos/métodos (`.append`, `.upper`, …).

## Tests

```bash
pytest -v
```

## Limitaciones conocidas

No detecta clones **semánticos** (Tipo 4: mismo resultado con otro algoritmo) ni funciones
renombradas atributo por atributo; compara solo funciones individuales. Ver el informe en `docs/`.
