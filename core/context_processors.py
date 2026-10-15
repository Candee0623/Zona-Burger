from core.models import Negocio


def panel_auth_context(request):
    """
    Context processor para poner a disposición del panel y vistas públicas:
    - usuario_actual: Usuario autenticado (instancia de Empleado).
    - permisos_usuario: Conjunto de códigos de permisos asignados para consultas O(1) en plantillas.
    - es_administrador: True si el usuario tiene rol de Administrador.
    """
    user = getattr(request, 'user', None)
    permisos = set()
    es_admin = False

    if user and getattr(user, 'is_authenticated', False) and getattr(user, 'is_active', False):
        if hasattr(user, 'idrol') and user.idrol and (user.idrol.nombrerol or '').strip().lower() == 'administrador':
            es_admin = True

        if hasattr(user, 'obtener_permisos'):
            permisos = user.obtener_permisos()
        elif es_admin:
            from core.models import Permiso
            permisos = set(Permiso.objects.values_list('codigo', flat=True))

    return {
        'usuario_actual': user if (user and getattr(user, 'is_authenticated', False)) else None,
        'permisos_usuario': permisos,
        'es_administrador': es_admin,
    }
