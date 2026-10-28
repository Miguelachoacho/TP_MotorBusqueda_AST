"""Módulo de ejemplo: cálculos de precios."""


def calcular_descuento(precio_base, porcentaje):
    """Aplica un descuento si el precio supera un mínimo."""
    tope_minimo = 1000
    if precio_base > tope_minimo:
        ahorro = precio_base * (porcentaje / 100)
        return precio_base - ahorro
    return precio_base


def sumar_pares(numeros):
    acumulador = 0
    for n in numeros:
        if n % 2 == 0:
            acumulador = acumulador + n
        else:
            acumulador = acumulador - 1
    return acumulador


def saludar(nombre):
    return f"Hola {nombre}"
