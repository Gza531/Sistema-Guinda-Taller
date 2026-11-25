"""
Costo del envío a domicilio según la zona de destino.

El negocio cobra el envío con una tabla de tarifas por zona (no hay contrato con un
correo, así que no se cotiza en línea). La zona sale de la provincia y del código
postal que el cliente carga en el checkout:

    Salta Capital     provincia Salta y CP 4400
    Resto de Salta    provincia Salta, otro CP
    NOA               Jujuy, Tucumán, Catamarca o Santiago del Estero
    Resto del país    cualquier otra provincia

En Salta, la localidad y el código postal tienen que coincidir (validar_destino):
el CP 4400 es solo de Salta Capital, y las localidades conocidas tienen su CP.

El costo lo calcula siempre el servidor (el checkout y el endpoint que lo muestra
usan esta misma función). Si el local contrata un correo, se reemplaza
tarifa_envio() por la cotización de su API y el resto del sistema no cambia.
"""

import re
import unicodedata
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

# Localidades principales de Salta con su código postal (los de 4 números).
# Sirven para sugerirlas en el checkout, completar el CP solo y validar que
# coincidan. Una localidad que no está en la lista se acepta con cualquier CP
# de Salta salvo el 4400, que es solo de la Capital.
LOCALIDADES_SALTA = [
    ("Salta", "4400"),
    ("Vaqueros", "4401"),
    ("Cerrillos", "4403"),
    ("Rosario de Lerma", "4405"),
    ("Campo Quijano", "4407"),
    ("San Antonio de los Cobres", "4411"),
    ("Cachi", "4417"),
    ("Molinos", "4419"),
    ("Coronel Moldes", "4421"),
    ("El Carril", "4421"),
    ("La Merced", "4421"),
    ("Chicoana", "4423"),
    ("Cafayate", "4427"),
    ("San Carlos", "4427"),
    ("General Güemes", "4430"),
    ("Campo Santo", "4432"),
    ("San José de Metán", "4440"),
    ("El Galpón", "4444"),
    ("Joaquín V. González", "4448"),
    ("Apolinario Saravia", "4449"),
    ("Las Lajitas", "4449"),
    ("Rosario de la Frontera", "4190"),
    ("San Ramón de la Nueva Orán", "4530"),
    ("Hipólito Yrigoyen", "4533"),
    ("Pichanal", "4534"),
    ("Embarcación", "4550"),
    ("Tartagal", "4561"),
    ("General Mosconi", "4562"),
    ("Aguaray", "4566"),
    ("Salvador Mazza", "4568"),
]

# Otras formas de escribir algunas localidades
ALIAS_SALTA = {
    "salta capital": "Salta",
    "ciudad de salta": "Salta",
    "salta (capital)": "Salta",
    "metan": "San José de Metán",
    "oran": "San Ramón de la Nueva Orán",
    "guemes": "General Güemes",
}

# 4400 o el formato nuevo A4400ABC: se usan los 4 números
RE_CODIGO_POSTAL = re.compile(r"^(?:[A-Za-z])?(\d{4})(?:[A-Za-z]{3})?$")


def numero_postal(codigo_postal):
    """Los 4 números del código postal, o None si el formato no es válido."""
    coincide = RE_CODIGO_POSTAL.match((codigo_postal or "").strip())
    return coincide.group(1) if coincide else None


def _normalizar(texto):
    """'San José de Metán ' → 'san jose de metan' (sin tildes, mayúsculas ni espacios de más)."""
    sin_tildes = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode()
    return " ".join(sin_tildes.lower().split())


_CP_POR_LOCALIDAD = {_normalizar(nombre): cp for nombre, cp in LOCALIDADES_SALTA}


def localidad_conocida(localidad):
    """Nombre oficial de la localidad de Salta, o None si no está en la lista."""
    clave = _normalizar(localidad)
    nombre = ALIAS_SALTA.get(clave)
    if nombre:
        return nombre
    for oficial, _cp in LOCALIDADES_SALTA:
        if _normalizar(oficial) == clave:
            return oficial
    return None


def validar_destino(provincia, localidad, codigo_postal):
    """
    En Salta, que la localidad y el código postal coincidan (de eso depende la
    tarifa). Devuelve un mensaje de error para el código postal, o None si está bien.
    """
    if provincia != "Salta":
        return None

    numero = numero_postal(codigo_postal)
    conocida = localidad_conocida(localidad)

    if conocida:
        esperado = _CP_POR_LOCALIDAD[_normalizar(conocida)]
        if numero != esperado:
            return f"El código postal de {conocida} es {esperado}."
    elif numero == CP_SALTA_CAPITAL:
        return "El código postal 4400 es de Salta Capital. Revisá la localidad o el código postal."
    return None


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


def localidades_salta():
    """Para el checkout: [{"nombre": "Cafayate", "codigo_postal": "4427"}, ...]"""
    return [{"nombre": nombre, "codigo_postal": cp} for nombre, cp in LOCALIDADES_SALTA]


def tabla_tarifas():
    """La tabla completa, para mostrarla en la tienda y en el panel."""
    return [
        {"zona": nombre, "alcance": alcance, "costo": costo}
        for nombre, alcance, costo in TARIFAS.values()
    ]
