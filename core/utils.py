import logging

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
