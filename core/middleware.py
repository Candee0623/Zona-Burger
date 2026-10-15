import re
from urllib.parse import quote
from django.contrib import messages
from django.contrib.auth import logout
from django.http import JsonResponse
from django.shortcuts import redirect
from django.urls import reverse
from core.models import Empleado


class PanelSecurityMiddleware:
    """
    Middleware de seguridad integral para el panel de administración de Zona Burger.
    Protege todas las rutas de /panel/ y /reportes/ asegurando que:
    1. Solo usuarios autenticados como Empleado activo puedan acceder.
    2. Si una cuenta es desactivada mientras tiene sesión activa, se cierre la sesión de inmediato.
    3. Rutas públicas administrativas (login, recuperación) queden accesibles.
    4. Las solicitudes AJAX/JSON reciban respuestas HTTP 401/403 en lugar de redirecciones HTML.
    """

    RUTAS_EXENTAS = [
        r'^/panel/login/?$',
        r'^/panel/logout/?$',
        r'^/panel/recuperar-contrasena/?$',
        r'^/panel/restablecer-contrasena/[^/]+/?$',
    ]

    def __init__(self, get_response):
        self.get_response = get_response
        self._regex_exentas = [re.compile(p) for p in self.RUTAS_EXENTAS]

    def __call__(self, request):
        path = request.path

        # Verificar si la ruta es administrativa
        es_ruta_panel = (
            path.startswith('/panel/')
            or path.startswith('/reportes/')
            or bool(re.match(r'^/pedido/\d+/', path))
        )

        if es_ruta_panel:
            # Comprobar si es una ruta exenta de autenticación
            esta_exenta = any(r.match(path) for r in self._regex_exentas)

            es_ajax = (
                request.headers.get('x-requested-with') == 'XMLHttpRequest'
                or 'application/json' in request.headers.get('Accept', '')
                or getattr(request, 'content_type', '') == 'application/json'
            )

            # Si el usuario ya está autenticado e intenta ir al login, redirigir al panel
            if esta_exenta and path.startswith('/panel/login') and getattr(request.user, 'is_authenticated', False):
                if getattr(request.user, 'is_active', False):
                    return redirect('panel_inicio')

            if not esta_exenta:
                # 1. Verificar autenticación
                if not getattr(request.user, 'is_authenticated', False):
                    if es_ajax:
                        return JsonResponse({
                            'status': 'error',
                            'message': 'Sesión no iniciada. Por favor iniciá sesión.'
                        }, status=401)

                    next_url = quote(request.get_full_path())
                    return redirect(f"{reverse('panel_login')}?next={next_url}")

                # 2. Verificar que la cuenta siga activa
                if not getattr(request.user, 'is_active', True):
                    logout(request)
                    if es_ajax:
                        return JsonResponse({
                            'status': 'error',
                            'message': 'Tu cuenta ha sido desactivada. Contactá al administrador.'
                        }, status=403)

                    messages.error(request, 'Tu cuenta ha sido desactivada. Contactá al administrador.')
                    return redirect('panel_login')

        response = self.get_response(request)
        return response
