"""Tests de la Fase 3 (serialización, métricas y motor de búsqueda).

Incluye los casos exigidos por la consigna: 2 positivos (clones con variables renombradas
y con líneas reordenadas) y 2 negativos (funciones claramente distintas).
"""

import pytest

from extraccion import extraer_funciones_de_codigo, extraer_funciones_de_directorio
from similitud import (
    UMBRAL_DUPLICADO,
    buscar_similares,
    calcular_similitud,
    comparar_funciones,
    distancia_levenshtein,
    generar_ngramas,
    serializar_ast,
    similitud_jaccard,
    similitud_levenshtein,
    tokens_de_funcion,
)
from normalizacion import normalizar_funcion


def una_funcion(codigo: str, archivo: str = "memoria.py"):
    return extraer_funciones_de_codigo(codigo, nombre_archivo=archivo)[0]


# ---------------------------------------------------------------------------
# Serialización pre-order
# ---------------------------------------------------------------------------
def test_serializacion_pre_order_de_una_funcion_simple():
    funcion = una_funcion("def g(x):\n    return x + 5\n")
    tokens = serializar_ast(normalizar_funcion(funcion.nodo_ast))
    assert tokens == [
        "FunctionDef:FUNC", "arguments", "arg:VAR1",
        "Return", "BinOp", "Name:VAR1", "Add", "Constant:LIT",
    ]


def test_el_nombre_de_nodo_sin_atributo_no_agrega_sufijo():
    tokens = tokens_de_funcion(una_funcion("def g(x):\n    if x:\n        pass\n"))
    assert "If" in tokens and "Pass" in tokens


def test_los_nombres_de_api_si_forman_parte_del_token():
    # .upper() y .lower() son operaciones distintas: no deben serializarse igual.
    a = tokens_de_funcion(una_funcion("def f(s):\n    return s.upper()\n"))
    b = tokens_de_funcion(una_funcion("def f(s):\n    return s.lower()\n"))
    assert "Attribute:upper" in a and a != b


# ---------------------------------------------------------------------------
# Métricas: pruebas unitarias
# ---------------------------------------------------------------------------
def test_levenshtein_casos_conocidos():
    assert distancia_levenshtein(list("kitten"), list("sitting")) == 3
    assert distancia_levenshtein(["a", "b", "c"], ["a", "c"]) == 1
    assert distancia_levenshtein([], ["a", "b"]) == 2
    assert distancia_levenshtein(["a"], ["a"]) == 0


def test_similitud_levenshtein_rango_y_casos_borde():
    assert similitud_levenshtein(["a", "b"], ["a", "b"]) == 1.0
    assert similitud_levenshtein(["a", "b"], ["c", "d"]) == 0.0
    assert similitud_levenshtein([], []) == 1.0
    assert similitud_levenshtein(["a", "b", "c", "d"], ["a", "b", "c", "x"]) == pytest.approx(0.75)


def test_ngramas():
    assert generar_ngramas(["A", "B", "C", "D"], n=3) == {("A", "B", "C"), ("B", "C", "D")}
    assert generar_ngramas(["A", "B"], n=3) == {("A", "B")}      # más corta que n
    assert generar_ngramas([], n=3) == set()


def test_similitud_jaccard_casos_conocidos():
    assert similitud_jaccard(["A", "B", "C", "D"], ["A", "B", "C", "D"]) == 1.0
    assert similitud_jaccard(["A", "B", "C"], ["X", "Y", "Z"]) == 0.0
    # n-gramas: {ABC, BCD} vs {ABC, BCE} -> intersección 1, unión 3
    assert similitud_jaccard(list("ABCD"), list("ABCE")) == pytest.approx(1 / 3)


def test_las_metricas_son_simetricas_y_estan_en_rango():
    a = tokens_de_funcion(una_funcion("def f(x):\n    for i in x:\n        print(i)\n"))
    b = tokens_de_funcion(una_funcion("def g(x):\n    while x:\n        x = x - 1\n"))
    for metrica in ("levenshtein", "jaccard"):
        ab, ba = calcular_similitud(a, b, metrica), calcular_similitud(b, a, metrica)
        assert ab == pytest.approx(ba)
        assert 0.0 <= ab <= 1.0


def test_metrica_desconocida_lanza_error():
    with pytest.raises(ValueError):
        calcular_similitud(["a"], ["a"], metrica="coseno")


# ---------------------------------------------------------------------------
# CASOS POSITIVOS (clones)
# ---------------------------------------------------------------------------
def test_positivo_1_clon_con_variables_literales_y_nombre_renombrados():
    a = una_funcion("""
def calcular_descuento(precio_base, porcentaje):
    tope_minimo = 1000
    if precio_base > tope_minimo:
        ahorro = precio_base * (porcentaje / 100)
        return precio_base - ahorro
    return precio_base
""")
    b = una_funcion("""
def aplicar_rebaja(monto, tasa_rebaja):
    limite = 500
    if monto > limite:
        descuento = monto * (tasa_rebaja / 100)
        return monto - descuento
    return monto
""")
    # Clon Tipo 2: tras normalizar, los árboles son idénticos.
    assert comparar_funciones(a, b, "levenshtein") == 1.0
    assert comparar_funciones(a, b, "jaccard") == 1.0


def test_positivo_2_clon_con_lineas_reordenadas():
    original = una_funcion("""
def validar_operacion(precio, cantidad, stock, limite):
    if precio <= 0:
        return False
    if cantidad <= 0:
        return False
    if cantidad > stock:
        return False
    if precio > limite:
        return False
    subtotal = precio * cantidad
    return subtotal > 100
""")
    reordenada = una_funcion("""
def chequear_compra(costo, unidades, disponible, tope_maximo):
    if unidades > disponible:
        return False
    if costo <= 0:
        return False
    if costo > tope_maximo:
        return False
    if unidades <= 0:
        return False
    total_parcial = costo * unidades
    return total_parcial > 500
""")
    lev = comparar_funciones(original, reordenada, "levenshtein")
    jac = comparar_funciones(original, reordenada, "jaccard")
    assert lev >= UMBRAL_DUPLICADO and jac >= UMBRAL_DUPLICADO
    # Jaccard (insensible al orden global) puntúa mejor el reordenamiento que Levenshtein.
    assert jac > lev


def test_positivo_extra_clon_con_docstring_y_anotaciones_de_tipo():
    sin_extras = una_funcion("def a(xs):\n    t = 0\n    for x in xs:\n        t += x\n    return t\n")
    con_extras = una_funcion(
        'def b(items: list[int]) -> int:\n    """Suma los elementos."""\n    total: int = 0\n'
        "    for it in items:\n        total += it\n    return total\n"
    )
    assert comparar_funciones(sin_extras, con_extras, "levenshtein") == 1.0


# ---------------------------------------------------------------------------
# CASOS NEGATIVOS (funciones claramente distintas)
# ---------------------------------------------------------------------------
def test_negativo_1_bucle_con_acumulador_vs_formateo_de_texto():
    bucle = una_funcion("""
def sumar_pares(numeros):
    acumulador = 0
    for n in numeros:
        if n % 2 == 0:
            acumulador = acumulador + n
        else:
            acumulador = acumulador - 1
    return acumulador
""")
    saludo = una_funcion('def formatear_usuario(nombre):\n    return f"Hola {nombre}"\n')
    for metrica in ("levenshtein", "jaccard"):
        assert comparar_funciones(bucle, saludo, metrica) < UMBRAL_DUPLICADO


def test_negativo_2_try_except_vs_while():
    con_try = una_funcion("""
def obtener_configuracion(diccionario, clave):
    try:
        valor = diccionario[clave]
        return str(valor)
    except KeyError:
        return "valor_por_defecto"
""")
    con_while = una_funcion("""
def contar_pasos_collatz(numero):
    pasos = 0
    while numero > 1:
        if numero % 2 == 0:
            numero = numero // 2
        else:
            numero = numero * 3 + 1
        pasos = pasos + 1
    return pasos
""")
    for metrica in ("levenshtein", "jaccard"):
        assert comparar_funciones(con_try, con_while, metrica) < UMBRAL_DUPLICADO


def test_negativo_extra_metodos_de_api_distintos():
    a = una_funcion("def f(s):\n    return s.upper()\n")
    b = una_funcion("def g(s):\n    return s.lower()\n")
    assert comparar_funciones(a, b, "jaccard") < UMBRAL_DUPLICADO


# ---------------------------------------------------------------------------
# Limitaciones conocidas (documentadas en el informe)
# ---------------------------------------------------------------------------
def test_limitacion_clones_tipo_4_semanticos_no_se_detectan():
    iterativo = una_funcion(
        "def f(n):\n    r = 1\n    for i in range(2, n + 1):\n        r = r * i\n    return r\n")
    recursivo = una_funcion("def g(n):\n    if n <= 1:\n        return 1\n    return n * g(n - 1)\n")
    assert comparar_funciones(iterativo, recursivo, "levenshtein") < UMBRAL_DUPLICADO
    assert comparar_funciones(iterativo, recursivo, "jaccard") < UMBRAL_DUPLICADO


def test_las_metricas_son_complementarias_ante_un_bloque_insertado():
    # Se agrega una validación al principio: Levenshtein (sensible al orden) lo tolera mejor;
    # Jaccard pierde los n-gramas que cruzan el punto de inserción.
    original = una_funcion(
        "def a(p, q):\n    m = 1000\n    if p > m:\n        r = p * (q / 100)\n        return p - r\n    return p\n")
    con_guarda = una_funcion(
        "def b(p, q):\n    if p < 0:\n        raise ValueError('negativo')\n    m = 200\n"
        "    if p > m:\n        r = p * (q / 100)\n        return p - r\n    return p\n")
    assert comparar_funciones(original, con_guarda, "levenshtein") >= UMBRAL_DUPLICADO
    assert comparar_funciones(original, con_guarda, "jaccard") < UMBRAL_DUPLICADO


# ---------------------------------------------------------------------------
# Motor de búsqueda
# ---------------------------------------------------------------------------
UNIVERSO = """
def objetivo(a, b):
    if a > b:
        return a - b
    return b - a

def clon(x, y):
    if x > y:
        return x - y
    return y - x

def distinta(texto):
    resultado = []
    for letra in texto:
        resultado.append(letra.upper())
    return resultado
"""


def test_ranking_ordenado_excluye_al_objetivo_y_marca_duplicados():
    universo = extraer_funciones_de_codigo(UNIVERSO)
    objetivo = next(f for f in universo if f.nombre == "objetivo")
    ranking = buscar_similares(objetivo, universo, top_k=5)

    assert [r.funcion_candidata.nombre for r in ranking] == ["clon", "distinta"]
    assert ranking[0].score == 1.0 and ranking[0].es_duplicado
    assert not ranking[1].es_duplicado
    assert [r.score for r in ranking] == sorted((r.score for r in ranking), reverse=True)


def test_top_k_limita_la_cantidad_de_resultados():
    universo = extraer_funciones_de_codigo(UNIVERSO)
    objetivo = universo[0]
    assert len(buscar_similares(objetivo, universo, top_k=1)) == 1


def test_umbral_configurable():
    universo = extraer_funciones_de_codigo(UNIVERSO)
    objetivo = next(f for f in universo if f.nombre == "objetivo")
    ranking = buscar_similares(objetivo, universo, umbral=1.1)
    assert not any(r.es_duplicado for r in ranking)


def test_integracion_extremo_a_extremo_sobre_un_directorio(tmp_path):
    (tmp_path / "modulo_a.py").write_text(
        "def calcular_area(base, altura):\n    area = (base * altura) / 2\n    return area\n", encoding="utf-8")
    (tmp_path / "modulo_b.py").write_text(
        "def superficie_triangulo(ancho, alto):\n    resultado = (ancho * alto) / 2\n    return resultado\n\n"
        "def funcion_relleno(x):\n    while x > 0:\n        x = x - 1\n    return x\n", encoding="utf-8")

    universo = extraer_funciones_de_directorio(str(tmp_path))
    assert len(universo) == 3
    objetivo = next(f for f in universo if f.nombre == "calcular_area")

    for metrica in ("levenshtein", "jaccard"):
        ranking = buscar_similares(objetivo, universo, metrica=metrica, top_k=2)
        assert [r.funcion_candidata.nombre for r in ranking] == ["superficie_triangulo", "funcion_relleno"]
        assert ranking[0].score == 1.0 and ranking[0].es_duplicado
        assert not ranking[1].es_duplicado
