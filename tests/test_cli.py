"""Tests de la Fase 4 (interfaz de línea de comandos)."""

import io
from pathlib import Path

import pytest

import buscar_similares as cli
from extraccion import extraer_funciones_de_codigo

REPO_DEMO = str(Path(__file__).resolve().parent.parent / "ejemplos" / "repo_demo")

CLON_PEGADO = """
def f(precio, pct):
    minimo = 300
    if precio > minimo:
        rebaja = precio * (pct / 100)
        return precio - rebaja
    return precio
"""


def ejecutar(capsys, *argumentos):
    codigo = cli.main(list(argumentos))
    salida = capsys.readouterr()
    return codigo, salida.out, salida.err


def test_busca_por_archivo_y_nombre_y_encuentra_el_clon(capsys):
    codigo, out, _ = ejecutar(capsys, "--dir", REPO_DEMO, "--funcion", "ventas.py:calcular_descuento", "--top", "3")
    assert codigo == 0
    lineas = [l for l in out.splitlines() if l.startswith("1 ")]
    assert "aplicar_rebaja" in lineas[0] and "DUPLICADO" in lineas[0] and "1.0000" in lineas[0]
    assert out.count("\n1 ") + out.count("\n2 ") + out.count("\n3 ") == 3          # --top 3
    assert "\n4 " not in out


def test_acepta_codigo_pegado_como_objetivo(capsys):
    codigo, out, _ = ejecutar(capsys, "--dir", REPO_DEMO, "--codigo", CLON_PEGADO, "--top", "2")
    assert codigo == 0
    assert "(<codigo>:" in out
    primera = [l for l in out.splitlines() if l.startswith("1 ")][0]
    assert "DUPLICADO" in primera


def test_acepta_codigo_pegado_por_stdin(capsys, monkeypatch):
    monkeypatch.setattr("sys.stdin", io.StringIO(CLON_PEGADO))
    codigo, out, _ = ejecutar(capsys, "--dir", REPO_DEMO, "--codigo", "-", "--top", "1")
    assert codigo == 0 and "DUPLICADO" in out


def test_metrica_levenshtein_seleccionable(capsys):
    codigo, out, _ = ejecutar(capsys, "--dir", REPO_DEMO, "--funcion", "facturacion.py:validar_operacion",
                              "--metrica", "levenshtein", "--top", "1")
    assert codigo == 0 and "LEVENSHTEIN" in out and "chequear_compra" in out


def test_funcion_inexistente_informa_error(capsys):
    codigo, _, err = ejecutar(capsys, "--dir", REPO_DEMO, "--funcion", "ventas.py:no_existe")
    assert codigo == 1 and "No se encontró" in err


def test_formato_invalido_informa_error(capsys):
    codigo, _, err = ejecutar(capsys, "--dir", REPO_DEMO, "--funcion", "ventas.py")
    assert codigo == 1 and "Formato inválido" in err


def test_directorio_inexistente_informa_error(capsys):
    codigo, _, err = ejecutar(capsys, "--dir", "/no/existe", "--funcion", "a.py:f")
    assert codigo == 1 and "no existe" in err


def test_codigo_pegado_invalido_informa_error(capsys):
    codigo, _, err = ejecutar(capsys, "--dir", REPO_DEMO, "--codigo", "def mal(:")
    assert codigo == 1 and "no es Python válido" in err


def test_codigo_pegado_sin_funciones_informa_error(capsys):
    codigo, _, err = ejecutar(capsys, "--dir", REPO_DEMO, "--codigo", "x = 1")
    assert codigo == 1 and "no define ninguna función" in err


def test_nombre_ambiguo_lista_las_alternativas_y_se_resuelve_con_nombre_calificado(tmp_path, capsys):
    (tmp_path / "modelos.py").write_text(
        "class A:\n    def guardar(self):\n        return 1\n\n"
        "class B:\n    def guardar(self):\n        return 2\n", encoding="utf-8")

    codigo, _, err = ejecutar(capsys, "--dir", str(tmp_path), "--funcion", "modelos.py:guardar")
    assert codigo == 1 and "ambigua" in err and "A.guardar" in err and "B.guardar" in err

    codigo, out, _ = ejecutar(capsys, "--dir", str(tmp_path), "--funcion", "modelos.py:B.guardar")
    assert codigo == 0 and "B.guardar" in out


def test_la_ruta_se_compara_por_componentes_no_por_texto():
    funciones = extraer_funciones_de_codigo("def f(): pass\n", nombre_archivo="src/utils.py")
    assert cli.encontrar_funcion_objetivo("tils.py:f", funciones) == []
    assert cli.encontrar_funcion_objetivo("utils.py:f", funciones) == funciones
    assert cli.encontrar_funcion_objetivo("src/utils.py:f", funciones) == funciones
    assert cli.encontrar_funcion_objetivo("./src/utils.py:f", funciones) == funciones


def test_argumentos_invalidos_terminan_con_error_de_argparse(capsys):
    with pytest.raises(SystemExit):
        cli.main(["--dir", REPO_DEMO, "--funcion", "ventas.py:saludar", "--top", "0"])
    with pytest.raises(SystemExit):                      # --funcion y --codigo son excluyentes
        cli.main(["--dir", REPO_DEMO, "--funcion", "ventas.py:saludar", "--codigo", "def f(): pass"])
