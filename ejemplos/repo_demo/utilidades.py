"""Módulo de ejemplo: funciones sin relación con las de ventas.py / facturacion.py."""


def obtener_configuracion(diccionario, clave):
    try:
        valor = diccionario[clave]
        return str(valor)
    except KeyError:
        return "valor_por_defecto"


def contar_pasos_collatz(numero):
    pasos = 0
    while numero > 1:
        if numero % 2 == 0:
            numero = numero // 2
        else:
            numero = numero * 3 + 1
        pasos = pasos + 1
    return pasos


# Clones Tipo 4 (semánticos): ambas calculan el factorial con algoritmos distintos.
# La herramienta NO los detecta (limitación conocida, ver informe).
def factorial_iterativo(n):
    resultado = 1
    for i in range(2, n + 1):
        resultado = resultado * i
    return resultado


def factorial_recursivo(n):
    if n <= 1:
        return 1
    return n * factorial_recursivo(n - 1)
