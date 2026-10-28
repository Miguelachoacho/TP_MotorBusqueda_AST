"""Módulo de ejemplo: contiene clones de funciones de ventas.py."""


# Clon Tipo 2: mismo algoritmo con otros nombres y otros literales.
def aplicar_rebaja(monto, tasa_rebaja):
    limite = 500
    if monto > limite:
        descuento = monto * (tasa_rebaja / 100)
        return monto - descuento
    return monto


# Clon Tipo 3: se agregó una validación al principio.
def calcular_descuento_validado(precio, pct):
    if precio < 0:
        raise ValueError("precio negativo")
    minimo = 200
    if precio > minimo:
        rebaja = precio * (pct / 100)
        return precio - rebaja
    return precio


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


# Clon Tipo 3: mismas validaciones en otro orden.
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
