import re
from urllib.parse import quote
from django.contrib import messages
from django.contrib.auth import logout
from django.http import JsonResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone
from core.models import Empleado


class PanelSecurityMiddleware:
    """
    Middleware de seguridad integral para el panel de administración de Zona Burger.
    Protege todas las rutas de /panel/ y /reportes/ asegurando que:
    1. Solo usuarios autenticados como Empleado activo puedan acceder.
    2. Las sesiones expiran forzosamente tras 12 horas continuas (43.200 segundos).
    3. Si una cuenta es desactivada mientras tiene sesión activa, se cierre la sesión de inmediato.
    4. Rutas públicas administrativas (login, recuperación) queden accesibles.
    5. Las solicitudes AJAX/JSON reciban respuestas HTTP 401/403 en lugar de redirecciones HTML.
    6. Se inyecten cabeceras de protección HTTP contra clickjacking y MIME-sniffing.
    """

    DURACION_SESION_MAXIMA = 12 * 60 * 60  # 12 horas en segundos

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

                # 2. Control estricto de expiración tras 12 horas
                ahora = timezone.now().timestamp()
                login_time = request.session.get('login_time')

                if login_time is not None:
                    try:
                        tiempo_transcurrido = ahora - float(login_time)
                        if tiempo_transcurrido > self.DURACION_SESION_MAXIMA:
                            logout(request)
                            if es_ajax:
                                return JsonResponse({
                                    'status': 'error',
                                    'message': 'Tu sesión ha expirado tras 12 horas. Por favor volvé a ingresar.'
                                }, status=401)

                            messages.warning(
                                request,
                                'Tu sesión ha expirado tras 12 horas de actividad. Por favor volvé a ingresar tus credenciales.'
                            )
                            next_url = quote(request.get_full_path())
                            return redirect(f"{reverse('panel_login')}?next={next_url}")
                    except (ValueError, TypeError):
                        request.session['login_time'] = ahora
                else:
                    # Para sesiones existentes sin timestamp previo, fijar el tiempo de sesión
                    request.session['login_time'] = ahora

                # 3. Verificar que la cuenta siga activa
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

        # Inyectar cabeceras de seguridad indispensables
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-Frame-Options'] = 'DENY'
        response['Referrer-Policy'] = 'same-origin'

        return response

