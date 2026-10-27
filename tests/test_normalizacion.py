"""Tests de la Fase 2 (normalización)."""

import ast

from extraccion import extraer_funciones_de_codigo
from normalizacion import normalizar_funcion, previsualizar_codigo_normalizado


def normalizada(codigo: str) -> str:
    funcion = extraer_funciones_de_codigo(codigo)[0]
    return previsualizar_codigo_normalizado(normalizar_funcion(funcion.nodo_ast))


def test_ejemplo_del_enunciado_variables_y_literales():
    a = "def calcular_iva(precio):\n    impuesto = 0.21\n    return precio * impuesto + 100\n"
    b = "def obtener_recargo(monto_base):\n    tasa = 0.15\n    return monto_base * tasa + 50\n"
    assert normalizada(a) == normalizada(b)
    assert normalizada(a) == "def FUNC(VAR1):\n    VAR2 = 'LIT'\n    return VAR1 * VAR2 + 'LIT'"


def test_la_correspondencia_se_preserva_dentro_de_la_funcion():
    # La misma variable siempre recibe el mismo VARn; variables distintas, VARn distintos.
    resultado = normalizada("def f(a, b):\n    return a + a + b\n")
    assert resultado == "def FUNC(VAR1, VAR2):\n    return VAR1 + VAR1 + VAR2"


def test_cada_funcion_reinicia_la_numeracion():
    assert normalizada("def f(x):\n    return x\n") == normalizada("def g(totalmente_otro):\n    return totalmente_otro\n")


def test_parametros_y_variables_comparten_correspondencia():
    # ast.arg (firma) y ast.Name (cuerpo) deben mapear al mismo token.
    assert normalizada("def f(base):\n    r = base + 10\n    return r\n") == (
        "def FUNC(VAR1):\n    VAR2 = VAR1 + 'LIT'\n    return VAR2"
    )


def test_booleanos_y_none_no_se_reemplazan_por_lit():
    resultado = normalizada("def f(x):\n    if x is None:\n        return True\n    return 'texto'\n")
    assert "None" in resultado and "True" in resultado and "'LIT'" in resultado


def test_el_nombre_de_la_funcion_no_influye_ni_en_llamadas_recursivas():
    a = "def fact(n):\n    if n <= 1:\n        return 1\n    return n * fact(n - 1)\n"
    b = "def producto(k):\n    if k <= 1:\n        return 1\n    return k * producto(k - 1)\n"
    assert normalizada(a) == normalizada(b)
    assert "FUNC(" in normalizada(a)


def test_nombres_nativos_se_conservan():
    assert "len(VAR1)" in normalizada("def f(lista):\n    return len(lista)\n")


def test_un_nombre_nativo_redefinido_localmente_se_trata_como_variable():
    con_nativo = "def f(datos):\n    sum = 0\n    for d in datos:\n        sum += d\n    return sum\n"
    con_otro = "def g(datos):\n    total = 0\n    for d in datos:\n        total += d\n    return total\n"
    assert normalizada(con_nativo) == normalizada(con_otro)


def test_docstring_y_anotaciones_de_tipo_se_descartan():
    simple = "def f(xs):\n    t = 0\n    return t\n"
    decorada = 'def g(items: list) -> int:\n    """Documentación."""\n    total: int = 0\n    return total\n'
    assert normalizada(simple) == normalizada(decorada)


def test_funcion_con_solo_docstring_queda_con_pass():
    assert normalizada('def f():\n    """Solo doc."""\n') == "def FUNC():\n    pass"


def test_variable_de_except_se_normaliza():
    a = "def f():\n    try:\n        pass\n    except ValueError as error:\n        raise error\n"
    b = "def g():\n    try:\n        pass\n    except ValueError as e:\n        raise e\n"
    assert normalizada(a) == normalizada(b)


def test_funcion_anidada_se_trata_como_variable_local():
    a = "def f(x):\n    def ayuda(y):\n        return y\n    return ayuda(x)\n"
    b = "def g(p):\n    def otra(q):\n        return q\n    return otra(p)\n"
    assert normalizada(a) == normalizada(b)


def test_no_modifica_el_arbol_original():
    funcion = extraer_funciones_de_codigo("def original(valor):\n    return valor + 1\n")[0]
    antes = ast.dump(funcion.nodo_ast)
    normalizar_funcion(funcion.nodo_ast)
    assert ast.dump(funcion.nodo_ast) == antes
    assert funcion.nodo_ast.name == "original"
