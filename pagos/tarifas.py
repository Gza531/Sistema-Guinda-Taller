"""
Costo del envío a domicilio según la zona de destino.

El negocio cobra el envío con una tabla de tarifas por zona (no hay contrato con un
correo, así que no se cotiza en línea). La zona sale de la provincia y del código
postal que el cliente carga en el checkout:

    Salta Capital     provincia Salta y CP 4400
    Resto de Salta    provincia Salta, otro CP
    NOA               Jujuy, Tucumán, Catamarca o Santiago del Estero
    Resto del país    cualquier otra provincia

El costo lo calcula siempre el servidor (el checkout y el endpoint que lo muestra
usan esta misma función). Si el local contrata un correo, se reemplaza
tarifa_envio() por la cotización de su API y el resto del sistema no cambia.
"""

import re
from decimal import Decimal


# Mismos nombres que la lista del checkout de la tienda (src/utils/checkout.js)
PROVINCIAS = [
    "Buenos Aires", "Ciudad Autónoma de Buenos Aires", "Catamarca", "Chaco",
    "Chubut", "Córdoba", "Corrientes", "Entre Ríos", "Formosa", "Jujuy",
    "La Pampa", "La Rioja", "Mendoza", "Misiones", "Neuquén", "Río Negro",
    "Salta", "San Juan", "San Luis", "Santa Cruz", "Santa Fe",
    "Santiago del Estero", "Tierra del Fuego", "Tucumán",
]

PROVINCIAS_NOA = {"Jujuy", "Tucumán", "Catamarca", "Santiago del Estero"}

CP_SALTA_CAPITAL = "4400"

# zona → (nombre para mostrar, a quién alcanza, costo en pesos)
TARIFAS = {
    "SALTA_CAPITAL": ("Salta Capital", "Código postal 4400", Decimal("3500.00")),
    "SALTA_INTERIOR": ("Resto de Salta", "Otras localidades de Salta", Decimal("6000.00")),
    "NOA": ("NOA", "Jujuy, Tucumán, Catamarca y Santiago del Estero", Decimal("8500.00")),
    "RESTO_DEL_PAIS": ("Resto del país", "Las demás provincias", Decimal("12000.00")),
}

# 4400 o el formato nuevo A4400ABC: se usan los 4 números
RE_CODIGO_POSTAL = re.compile(r"^(?:[A-Za-z])?(\d{4})(?:[A-Za-z]{3})?$")


def numero_postal(codigo_postal):
    """Los 4 números del código postal, o None si el formato no es válido."""
    coincide = RE_CODIGO_POSTAL.match((codigo_postal or "").strip())
    return coincide.group(1) if coincide else None


def zona_de(provincia, codigo_postal):
    if provincia == "Salta":
        if numero_postal(codigo_postal) == CP_SALTA_CAPITAL:
            return "SALTA_CAPITAL"
        return "SALTA_INTERIOR"
    if provincia in PROVINCIAS_NOA:
        return "NOA"
    return "RESTO_DEL_PAIS"


def tarifa_envio(provincia, codigo_postal):
    """{"zona": "Salta Capital", "costo": Decimal("3500.00")} para ese destino."""
    nombre, _alcance, costo = TARIFAS[zona_de(provincia, codigo_postal)]
    return {"zona": nombre, "costo": costo}


def tabla_tarifas():
    """La tabla completa, para mostrarla en la tienda y en el panel."""
    return [
        {"zona": nombre, "alcance": alcance, "costo": costo}
        for nombre, alcance, costo in TARIFAS.values()
    ]
