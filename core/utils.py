import logging
import time

logger = logging.getLogger(__name__)


def obtener_ip_cliente(request):
    if not request:
        return None
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()[:50]
    return request.META.get('REMOTE_ADDR', '')[:50]


def registrar_auditoria(request, accion, descripcion):
    """
    Registra operaciones críticas en la tabla RegistroAuditoria sin almacenar secretos ni contraseñas.
    """
    try:
        from core.models import RegistroAuditoria, Empleado
        user = getattr(request, 'user', None)
        empleado = user if isinstance(user, Empleado) else None
        ip = obtener_ip_cliente(request)

        RegistroAuditoria.objects.create(
            idempleado=empleado,
            accion=accion[:100],
            descripcion=descripcion[:500],
            ip=ip,
        )
    except Exception as e:
        logger.exception("Error al registrar evento de auditoría '%s': %s", accion, e)


# ============================================================
# CÓDIGO DE BARRAS CODE 128 (VECTORIAL SVG)
# ============================================================

PATRONES_CODE128 = [
    '212222', '222122', '222221', '121223', '121322', '131222', '122213', '122312', '132212', '221213',
    '221312', '231212', '112232', '122132', '122231', '113222', '123122', '123221', '223211', '221132',
    '221231', '213212', '223112', '312131', '311222', '321122', '321221', '312212', '322112', '322211',
    '212123', '212321', '232121', '111323', '131123', '131321', '112313', '132113', '132311', '211313',
    '231113', '231311', '112133', '112331', '132131', '113123', '113321', '133121', '313121', '211331',
    '231131', '213113', '213311', '213131', '311123', '311321', '331121', '312113', '312311', '332111',
    '314111', '221411', '431111', '111224', '111422', '121124', '121421', '141122', '141221', '112214',
    '112412', '122114', '122411', '142112', '142211', '241211', '221114', '413111', '241112', '134111',
    '111242', '121142', '121241', '114212', '124112', '124211', '411212', '421112', '421211', '212141',
    '214121', '412121', '111143', '111341', '131141', '114113', '114311', '411113', '411311', '113141',
    '114131', '311141', '411131', '211412', '211214', '211232', '2331112'
]


def generar_codigo_barras_svg(codigo, alto=60, ancho_modulo=2):
    """
    Genera un código de barras en formato SVG estándar Code 128 (Subset B)
    para su visualización nítida e impresión en etiquetas de lotes y comandas.
    """
    if not codigo:
        codigo = "LOTE"

    codigo_limpio = str(codigo).strip()
    # Filtrar caracteres válidos ASCII para Code 128 Subset B (32 a 126)
    caracteres = [c for c in codigo_limpio if 32 <= ord(c) <= 126]
    if not caracteres:
        caracteres = list("LOTE")

    valores = [ord(c) - 32 for c in caracteres]
    checksum = (104 + sum((i + 1) * val for i, val in enumerate(valores))) % 103

    codigos_completos = [104] + valores + [checksum, 106]
    secuencia_barras = ''.join(PATRONES_CODE128[c] for c in codigos_completos)

    total_modulos = sum(int(d) for d in secuencia_barras)
    ancho_total = total_modulos * ancho_modulo

    rects = []
    pos_x = 0
    for idx, digito in enumerate(secuencia_barras):
        ancho_barra = int(digito) * ancho_modulo
        if idx % 2 == 0:  # barra negra
            rects.append(f'<rect x="{pos_x}" y="0" width="{ancho_barra}" height="{alto}" fill="#000000"/>')
        pos_x += ancho_barra

    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {ancho_total} {alto}" '
        f'width="{ancho_total}" height="{alto}" style="display:block;margin:0 auto;max-width:100%;height:auto;">'
        + ''.join(rects) +
        '</svg>'
    )
    return svg


# ============================================================
# PROTECCIÓN CONTRA ATAQUES DE FUERZA BRUTA EN LOGIN
# ============================================================

from django.core.cache import cache

MAX_INTENTOS_LOGIN = 5
TIEMPO_BLOQUEO_SEGUNDOS = 900  # 15 minutos


def _clave_intento_login(identificador, ip):
    id_norm = (identificador or '').strip().lower()
    ip_norm = (ip or '').strip()
    return f"login_fails:{ip_norm}:{id_norm}"


def verificar_bloqueo_fuerza_bruta(identificador, ip):
    """
    Verifica si una cuenta o IP superó el límite de intentos fallidos.
    Retorna (esta_bloqueado, segundos_restantes reales).
    """
    clave = _clave_intento_login(identificador, ip)
    datos = cache.get(clave)

    if not datos or datos.get('intentos', 0) < MAX_INTENTOS_LOGIN:
        return False, 0

    hasta = datos.get('bloqueado_hasta')

    # Registros viejos sin hora de fin: se asume el bloqueo completo
    if hasta is None:
        return True, TIEMPO_BLOQUEO_SEGUNDOS

    restantes = int(hasta - time.time())

    if restantes <= 0:
        cache.delete(clave)
        return False, 0

    return True, restantes


def registrar_intento_fallido_login(identificador, ip):
    """
    Incrementa el contador de intentos fallidos y, al llegar al máximo,
    guarda el momento en que termina el bloqueo.
    """
    clave = _clave_intento_login(identificador, ip)
    datos = cache.get(clave, {'intentos': 0})
    datos['intentos'] = datos.get('intentos', 0) + 1

    if datos['intentos'] >= MAX_INTENTOS_LOGIN and 'bloqueado_hasta' not in datos:
        datos['bloqueado_hasta'] = time.time() + TIEMPO_BLOQUEO_SEGUNDOS

    cache.set(clave, datos, timeout=TIEMPO_BLOQUEO_SEGUNDOS)
    return datos['intentos']


def limpiar_intentos_fallidos_login(identificador, ip):
    """
    Limpia los intentos fallidos tras un login exitoso.
    """
    clave = _clave_intento_login(identificador, ip)
    cache.delete(clave)