"""Tests de la Fase 1 (extracción)."""

import pytest

from extraccion import (
    extraer_funciones_de_archivo,
    extraer_funciones_de_codigo,
    extraer_funciones_de_directorio,
)


def test_extrae_nombre_archivo_linea_y_subarbol():
    codigo = "x = 1\n\ndef primera(a):\n    return a\n"
    (funcion,) = extraer_funciones_de_codigo(codigo, nombre_archivo="mod.py")
    assert funcion.nombre == "primera"
    assert funcion.archivo == "mod.py"
    assert funcion.linea == 3
    assert funcion.nodo_ast.name == "primera"


def test_extrae_funciones_async_y_anidadas():
    codigo = (
        "def externa():\n"
        "    def interna():\n"
        "        pass\n"
        "    return interna\n"
        "\n"
        "async def asincrona():\n"
        "    pass\n"
    )
    nombres = [f.nombre for f in extraer_funciones_de_codigo(codigo)]
    assert sorted(nombres) == ["asincrona", "externa", "interna"]


def test_metodos_homonimos_se_distinguen_por_nombre_calificado():
    codigo = (
        "class A:\n"
        "    def guardar(self):\n"
        "        pass\n"
        "class B:\n"
        "    def guardar(self):\n"
        "        pass\n"
    )
    calificados = [f.nombre_calificado for f in extraer_funciones_de_codigo(codigo)]
    assert calificados == ["A.guardar", "B.guardar"]


def test_recorre_directorios_recursivamente_y_en_orden_determinista(tmp_path):
    (tmp_path / "b.py").write_text("def fb(): pass\n", encoding="utf-8")
    (tmp_path / "a.py").write_text("def fa(): pass\n", encoding="utf-8")
    sub = tmp_path / "paquete" / "interno"
    sub.mkdir(parents=True)
    (sub / "c.py").write_text("def fc(): pass\n", encoding="utf-8")
    (tmp_path / "notas.txt").write_text("def no_soy_python(): pass\n", encoding="utf-8")

    nombres = [f.nombre for f in extraer_funciones_de_directorio(str(tmp_path))]
    assert nombres == ["fa", "fb", "fc"]


def test_ignora_directorios_de_entornos_y_caches(tmp_path):
    for carpeta in (".git", "__pycache__", "venv"):
        (tmp_path / carpeta).mkdir()
        (tmp_path / carpeta / "x.py").write_text("def ajena(): pass\n", encoding="utf-8")
    (tmp_path / "propio.py").write_text("def propia(): pass\n", encoding="utf-8")
    assert [f.nombre for f in extraer_funciones_de_directorio(str(tmp_path))] == ["propia"]


def test_archivo_con_error_de_sintaxis_se_omite_sin_detener_el_analisis(tmp_path, capsys):
    (tmp_path / "roto.py").write_text("def mal(:\n    pass\n", encoding="utf-8")
    (tmp_path / "sano.py").write_text("def bien(): pass\n", encoding="utf-8")

    funciones = extraer_funciones_de_directorio(str(tmp_path))

    assert [f.nombre for f in funciones] == ["bien"]
    assert "roto.py" in capsys.readouterr().err


def test_archivo_con_codificacion_invalida_se_omite(tmp_path):
    archivo = tmp_path / "binario.py"
    archivo.write_bytes(b"def f():\n    return '\xff\xfe'\n")
    assert extraer_funciones_de_archivo(archivo) == []


def test_directorio_inexistente_lanza_error():
    with pytest.raises(ValueError):
        extraer_funciones_de_directorio("/ruta/que/no/existe")


def test_codigo_pegado_con_indentacion_comun_es_aceptado():
    codigo = "    def f(x):\n        return x\n"
    assert [f.nombre for f in extraer_funciones_de_codigo(codigo)] == ["f"]
