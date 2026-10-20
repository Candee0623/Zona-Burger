import math
import re
import unicodedata
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)

# Ubicación base del negocio (Zona Burger - Villa Lugano / Piedrabuena, CABA)
NEGOCIO_BASE_LAT = -34.6785
NEGOCIO_BASE_LON = -58.4940

# Radio máximo de cobertura directa aproximada desde la base (en km).
# Superada esta distancia o fuera de las zonas definidas, se clasifica como "Envío a coordinar".
RADIO_MAXIMO_COBERTURA_KM = 3.8

# Definiciones geográficas y alias para barrios y zonas de la zona de cobertura:
ZONAS_GEOGRAFICAS_CONFIG = {
    'piedrabuena': {
        'nombre_clave': 'piedrabuena',
        'aliases': [
            'piedrabuena',
            'piedra buena',
            'luis piedrabuena',
            'comandante luis piedrabuena',
            'barrio piedrabuena',
            'barrio comandante luis piedrabuena',
            'barrio luis piedrabuena',
        ],
        'calles': [
            'goleta santa cruz',
            'rio gallegos',
            '2 de abril',
            '2 de abril de 1982',
            'viedma',
            'costanera',
            'canada de gomez',
            'cañada de gomez',
        ],
        'centro': (-34.6785, -58.4940),
        'radio_km': 0.95,
        'bbox': (-34.6870, -34.6710, -58.5030, -58.4850),  # lat_min, lat_max, lon_min, lon_max
    },
    'pirelli': {
        'nombre_clave': 'pirelli',
        'aliases': [
            'pirelli',
            'barrio pirelli',
            'general savio',
            'savio',
            'barrio savio',
            'barrio general savio',
            'barrio general de division manuel nicolas savio',
            'lugano 1 y 2',
            'lugano 1 y ii',
            'lugano i y ii',
            'lugano 1',
            'lugano 2',
            'lugano i',
            'lugano ii',
            'copello',
        ],
        'calles': [
            'soldado de la frontera',
            'ana diaz',
            'cafayate',
            'oliden',
            'larrazabal',
            'chilavert',
        ],
        'centro': (-34.6853, -58.4680),
        'radio_km': 1.15,
        'bbox': (-34.6940, -34.6760, -58.4800, -58.4540),
    },
    'los perales': {
        'nombre_clave': 'los perales',
        'aliases': [
            'los perales',
            'perales',
            'dorrego',
            'manuel dorrego',
            'barrio manuel dorrego',
            'barrio los perales',
        ],
        'calles': [
            'justo suarez',
            'tellier',
        ],
        'centro': (-34.6600, -58.5030),
        'radio_km': 0.85,
        'bbox': (-34.6680, -34.6530, -58.5120, -58.4930),
    },
    'la oculta': {
        'nombre_clave': 'la oculta',
        'aliases': [
            'la oculta',
            'oculta',
            'ciudad oculta',
            'villa 15',
            'barrio 15',
        ],
        'calles': [
            'crisostomo alvarez',
            'hubac',
        ],
        'centro': (-34.6680, -58.4890),
        'radio_km': 0.80,
        'bbox': (-34.6750, -34.6620, -58.4980, -58.4800),
    },
}


def normalizar_texto(texto):
    """
    Normaliza una cadena de texto para comparación:
    - Convierte a minúsculas
    - Remueve tildes / diacríticos (á -> a, é -> e, etc.)
    - Quita espacios iniciales y finales
    - Reduce múltiples espacios contiguos a un único espacio
    """
    if not texto:
        return ''
    # Convertir a cadena y normalizar unicode
    s = str(texto).strip().lower()
    s_nfd = unicodedata.normalize('NFD', s)
    s_sin_tildes = ''.join(c for c in s_nfd if unicodedata.category(c) != 'Mn')
    # Reemplazar caracteres especiales y consolidar espacios
    s_limpia = re.sub(r'[\s\-_,./]+', ' ', s_sin_tildes).strip()
    return s_limpia


def texto_sin_espacios(texto):
    """Devuelve el texto normalizado completamente sin espacios."""
    return normalizar_texto(texto).replace(' ', '')


def calcular_distancia_km(lat1, lon1, lat2, lon2):
    """
    Calcula la distancia ortodrómica en kilómetros entre dos coordenadas
    utilizando la fórmula de Haversine.
    """
    try:
        lat1, lon1, lat2, lon2 = float(lat1), float(lon1), float(lat2), float(lon2)
    except (ValueError, TypeError):
        return None

    r_tierra = 6371.0  # Radio medio de la Tierra en km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return r_tierra * c


def coordenada_en_bbox(lat, lon, bbox):
    """Comprueba si una coordenada (lat, lon) cae dentro de una bounding box (lat_min, lat_max, lon_min, lon_max)."""
    lat_min, lat_max, lon_min, lon_max = bbox
    return (lat_min <= lat <= lat_max) and (lon_min <= lon <= lon_max)


def coordenada_en_radio(lat, lon, centro, radio_km):
    """Comprueba si una coordenada está dentro del radio_km del centro."""
    d = calcular_distancia_km(lat, lon, centro[0], centro[1])
    return (d is not None) and (d <= radio_km)


def buscar_zona_en_db(clave_o_nombre, zonas_db=None):
    """
    Busca un objeto ZonasEntrega de la base de datos comparando:
    - Nombre exacto o contenido (ignorando mayúsculas, minúsculas, tildes y espacios).
    - Coincidencia con alias conocidos.
    """
    if zonas_db is None:
        try:
            from core.models import ZonasEntrega
            zonas_db = list(ZonasEntrega.objects.all())
        except Exception as e:
            logger.error("Error al consultar ZonasEntrega: %s", e)
            zonas_db = []

    buscado_norm = normalizar_texto(clave_o_nombre)
    buscado_sinesp = texto_sin_espacios(clave_o_nombre)

    if not buscado_norm:
        return None

    # 1. Búsqueda directa por nombre de zona en DB
    for z in zonas_db:
        z_norm = normalizar_texto(z.nombre)
        z_sinesp = texto_sin_espacios(z.nombre)
        if z_norm == buscado_norm or z_sinesp == buscado_sinesp:
            return z

    # 2. Búsqueda por inclusión bidireccional
    for z in zonas_db:
        z_norm = normalizar_texto(z.nombre)
        z_sinesp = texto_sin_espacios(z.nombre)
        if z_norm and (z_norm in buscado_norm or buscado_norm in z_norm):
            return z
        if z_sinesp and (z_sinesp in buscado_sinesp or buscado_sinesp in z_sinesp):
            return z

    # 3. Búsqueda a través de configuración y alias
    for clave_cfg, cfg in ZONAS_GEOGRAFICAS_CONFIG.items():
        aliases_norm = [normalizar_texto(a) for a in cfg.get('aliases', [])]
        aliases_sinesp = [texto_sin_espacios(a) for a in cfg.get('aliases', [])]
        
        coincide_alias = (
            buscado_norm in aliases_norm
            or buscado_sinesp in aliases_sinesp
            or any(a in buscado_norm for a in aliases_norm)
        )

        if coincide_alias:
            # Buscar en la lista de DB la zona que coincida con esta clave de config o sus alias
            for z in zonas_db:
                z_norm = normalizar_texto(z.nombre)
                z_sinesp = texto_sin_espacios(z.nombre)
                if z_norm in aliases_norm or z_sinesp in aliases_sinesp:
                    return z

    return None


def detectar_zona_por_coordenadas(lat, lon, zonas_db=None):
    """
    Detecta la zona de entrega analizando coordenadas geográficas reales.
    Comprueba si cae dentro del bounding box o radio de cobertura de cada zona configurada.
    """
    try:
        lat = float(lat)
        lon = float(lon)
    except (ValueError, TypeError):
        return None

    # Evaluar contra cada zona geográfica configurada
    for clave_zona, cfg in ZONAS_GEOGRAFICAS_CONFIG.items():
        bbox = cfg.get('bbox')
        centro = cfg.get('centro')
        radio_km = cfg.get('radio_km', 1.0)

        cumple_bbox = bbox and coordenada_en_bbox(lat, lon, bbox)
        cumple_radio = centro and coordenada_en_radio(lat, lon, centro, radio_km)

        if cumple_bbox or cumple_radio:
            zona = buscar_zona_en_db(clave_zona, zonas_db)
            if zona:
                return zona

    return None


def detectar_zona_por_texto(calle='', numero='', localidad='', detalles_geocoding=None, zonas_db=None):
    """
    Comprueba si los nombres de calles emblemáticas, barrios o datos de dirección
    coinciden con alguna zona cubierta, ignorando mayúsculas, minúsculas, tildes y espacios.
    """
    if zonas_db is None:
        try:
            from core.models import ZonasEntrega
            zonas_db = list(ZonasEntrega.objects.all())
        except Exception:
            zonas_db = []

    partes_texto = [calle or '', numero or '', localidad or '']
    if detalles_geocoding:
        if isinstance(detalles_geocoding, dict):
            partes_texto.extend([
                detalles_geocoding.get('display_name', ''),
                detalles_geocoding.get('suburb', ''),
                detalles_geocoding.get('neighbourhood', ''),
                detalles_geocoding.get('quarter', ''),
                detalles_geocoding.get('residential', ''),
                detalles_geocoding.get('city_district', ''),
                detalles_geocoding.get('city', ''),
            ])
        elif isinstance(detalles_geocoding, str):
            partes_texto.append(detalles_geocoding)

    texto_completo = ' '.join(partes_texto)
    norm_completo = normalizar_texto(texto_completo)
    sinesp_completo = texto_sin_espacios(texto_completo)

    if not norm_completo:
        return None

    # 1. Comprobar calles emblemáticas y alias de cada configuración geográfica
    for clave_zona, cfg in ZONAS_GEOGRAFICAS_CONFIG.items():
        # Revisar calles emblemáticas
        for calle_emb in cfg.get('calles', []):
            c_norm = normalizar_texto(calle_emb)
            c_sinesp = texto_sin_espacios(calle_emb)
            if c_norm and (c_norm in norm_completo or c_sinesp in sinesp_completo):
                z = buscar_zona_en_db(clave_zona, zonas_db)
                if z:
                    return z

        # Revisar alias
        for alias in cfg.get('aliases', []):
            a_norm = normalizar_texto(alias)
            a_sinesp = texto_sin_espacios(alias)
            if a_norm and (a_norm in norm_completo or a_sinesp in sinesp_completo):
                z = buscar_zona_en_db(clave_zona, zonas_db)
                if z:
                    return z

    # 2. Comprobar directamente los nombres de las zonas cargadas en DB
    for z in zonas_db:
        z_norm = normalizar_texto(z.nombre)
        z_sinesp = texto_sin_espacios(z.nombre)
        if z_norm and (z_norm in norm_completo or z_sinesp in sinesp_completo):
            return z

    return None


def detectar_zona_entrega(calle='', numero='', localidad='', lat=None, lon=None, id_zona_sugerida=None, detalles_geocoding=None, zonas_db=None):
    """
    Función central de detección de zona de entrega:
    1. Utiliza la ubicación geográfica (latitud y longitud) siempre que esté disponible.
    2. Comprueba las calles emblemáticas y alias del barrio o zona.
    3. Compara el texto ignorando mayúsculas, minúsculas, tildes y espacios.
    4. Si está dentro de una zona con tarifa: devuelve el precio y es_gratis=False.
    5. Si el costo es 0: devuelve costo 0 y es_gratis=True.
    6. Si está lejos o fuera de cobertura: devuelve es_a_coordinar=True con costo 0.
    """
    if zonas_db is None:
        try:
            from core.models import ZonasEntrega
            zonas_db = list(ZonasEntrega.objects.all())
        except Exception:
            zonas_db = []

    zona_encontrada = None
    metodo_deteccion = None

    # Paso 1: Ubicación geográfica (coordenadas)
    if lat is not None and lon is not None:
        try:
            lat_f = float(lat)
            lon_f = float(lon)
            zona_encontrada = detectar_zona_por_coordenadas(lat_f, lon_f, zonas_db)
            if zona_encontrada:
                metodo_deteccion = 'coordenadas'
            else:
                # Verificar distancia a la base del negocio
                dist_base = calcular_distancia_km(lat_f, lon_f, NEGOCIO_BASE_LAT, NEGOCIO_BASE_LON)
                if dist_base is not None and dist_base > RADIO_MAXIMO_COBERTURA_KM:
                    # Dirección claramente lejana -> Forzar fuera de cobertura / A coordinar
                    return {
                        'zona': None,
                        'idzona': None,
                        'nombre': 'A coordinar',
                        'costoenvio': Decimal('0.00'),
                        'es_gratis': False,
                        'cobertura': False,
                        'es_a_coordinar': True,
                        'costoenvio_texto': 'A coordinar',
                        'localidad_guardar': 'A coordinar con el vendedor',
                        'mensaje': 'Tu dirección se encuentra fuera de nuestra zona de cobertura habitual. Al confirmar tu pedido nos comunicaremos para coordinar la entrega y el costo de envío.',
                        'distancia_km': round(dist_base, 2),
                        'metodo_deteccion': 'fuera_de_radio',
                    }
        except (ValueError, TypeError):
            pass

    # Paso 2: Análisis por texto (calle, número, localidad y detalles de geocodificación)
    if not zona_encontrada:
        zona_encontrada = detectar_zona_por_texto(
            calle=calle,
            numero=numero,
            localidad=localidad,
            detalles_geocoding=detalles_geocoding,
            zonas_db=zonas_db
        )
        if zona_encontrada:
            metodo_deteccion = 'texto_direccion'

    # Paso 3: Si se recibió un id_zona sugerido por el formulario y no se detectó otra cosa
    if not zona_encontrada and id_zona_sugerida:
        try:
            id_num = int(id_zona_sugerida)
            for z in zonas_db:
                if z.idzona == id_num:
                    zona_encontrada = z
                    metodo_deteccion = 'id_sugerido'
                    break
        except (ValueError, TypeError):
            pass

    # Construir resultado
    if zona_encontrada:
        costo = Decimal(str(zona_encontrada.costoenvio or 0.00))
        es_gratis = (costo == 0)
        costo_texto = 'Envío gratis' if es_gratis else f'${costo:.2f}'

        return {
            'zona': zona_encontrada,
            'idzona': zona_encontrada.idzona,
            'nombre': zona_encontrada.nombre,
            'costoenvio': costo,
            'es_gratis': es_gratis,
            'cobertura': True,
            'es_a_coordinar': False,
            'costoenvio_texto': costo_texto,
            'localidad_guardar': zona_encontrada.nombre,
            'mensaje': (
                f'¡Zona cubierta con Envío Gratuito! ({zona_encontrada.nombre})'
                if es_gratis
                else f'Zona cubierta detectada: {zona_encontrada.nombre} (Costo: {costo_texto})'
            ),
            'metodo_deteccion': metodo_deteccion,
        }
    else:
        # Fuera de cobertura o sin coincidencia
        return {
            'zona': None,
            'idzona': None,
            'nombre': 'A coordinar',
            'costoenvio': Decimal('0.00'),
            'es_gratis': False,
            'cobertura': False,
            'es_a_coordinar': True,
            'costoenvio_texto': 'A coordinar',
            'localidad_guardar': localidad or 'A coordinar con el vendedor',
            'mensaje': 'Dirección fuera del radio de entrega directo. Coordinaremos la entrega y el costo de envío correspondiente al confirmar el pedido.',
            'metodo_deteccion': 'sin_cobertura',
        }
