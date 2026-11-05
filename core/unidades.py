"""
Conversión de unidades de medida para insumos.

El stock de un insumo se guarda siempre en su *unidad de ingreso* (la que se
usa al comprar, por ejemplo kg), mientras que las recetas y opciones expresan
el consumo en la *unidad de egreso* (por ejemplo g). Este módulo sabe pasar de
una a otra para que, al vender, se descuente lo correcto (150 g = 0,15 kg).

Solo se convierten automáticamente unidades de la misma magnitud (masa,
volumen o conteo). Para el resto (por ejemplo "bolsa" -> "unidad") el insumo
debe indicar su equivalencia manualmente (Insumo.equivalencia_egreso).
"""
import re
import unicodedata
from decimal import Decimal

# magnitud -> {nombre normalizado: factor respecto a la unidad base}
_MAGNITUDES = {
    'masa': {'mg': Decimal('0.001'), 'g': Decimal('1'), 'kg': Decimal('1000')},
    'volumen': {
        'ml': Decimal('1'), 'cl': Decimal('10'), 'l': Decimal('1000'),
    },
    'conteo': {'unidad': Decimal('1'), 'docena': Decimal('12')},
}

# alias escritos por el usuario -> nombre normalizado
_ALIAS = {
    'mg': 'mg', 'miligramo': 'mg', 'miligramos': 'mg',
    'g': 'g', 'gr': 'g', 'grs': 'g', 'gramo': 'g', 'gramos': 'g',
    'kg': 'kg', 'kgs': 'kg', 'kilo': 'kg', 'kilos': 'kg',
    'kilogramo': 'kg', 'kilogramos': 'kg',
    'ml': 'ml', 'mililitro': 'ml', 'mililitros': 'ml', 'cc': 'ml',
    'cl': 'cl', 'centilitro': 'cl', 'centilitros': 'cl',
    'l': 'l', 'lt': 'l', 'lts': 'l', 'litro': 'l', 'litros': 'l',
    'u': 'unidad', 'un': 'unidad', 'uni': 'unidad', 'unid': 'unidad',
    'unidad': 'unidad', 'unidades': 'unidad',
    'pieza': 'unidad', 'piezas': 'unidad',
    'doc': 'docena', 'docena': 'docena', 'docenas': 'docena',
}

# Sugerencias para los formularios (datalist).
UNIDADES_SUGERIDAS = [
    'kg', 'g', 'litro', 'ml', 'unidad', 'docena',
    'paquete', 'bolsa', 'caja', 'lata', 'botella', 'bidón',
]


def _limpiar(texto):
    texto = unicodedata.normalize('NFKD', str(texto or ''))
    texto = ''.join(c for c in texto if not unicodedata.combining(c))
    texto = re.sub(r'[.\s]+', ' ', texto.lower()).strip()
    return texto


def normalizar_unidad(texto):
    """'Kilos' -> 'kg', 'Gramos' -> 'g'. Las desconocidas quedan en minúscula."""
    limpio = _limpiar(texto)
    return _ALIAS.get(limpio, limpio)


def magnitud(texto):
    """Devuelve 'masa', 'volumen', 'conteo' o None si no es una unidad conocida."""
    nombre = normalizar_unidad(texto)
    for nombre_magnitud, unidades in _MAGNITUDES.items():
        if nombre in unidades:
            return nombre_magnitud
    return None


def mismas_unidades(a, b):
    return normalizar_unidad(a) == normalizar_unidad(b)


def factor_conversion(desde, hacia):
    """
    Cuántas unidades `hacia` equivalen a 1 unidad `desde`.
    Ej.: factor_conversion('g', 'kg') -> 0.001
    Devuelve None si no se pueden convertir automáticamente.
    """
    origen = normalizar_unidad(desde)
    destino = normalizar_unidad(hacia)

    if not origen or not destino:
        return None

    if origen == destino:
        return Decimal('1')

    mag_origen = magnitud(origen)
    if mag_origen is None or mag_origen != magnitud(destino):
        return None

    tabla = _MAGNITUDES[mag_origen]
    return tabla[origen] / tabla[destino]


def unidades_compatibles(a, b):
    return factor_conversion(a, b) is not None
