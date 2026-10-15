from functools import wraps
from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from urllib.parse import quote


def es_ajax_o_json(request):
    return (
        request.headers.get('x-requested-with') == 'XMLHttpRequest'
        or 'application/json' in request.headers.get('Accept', '')
        or request.content_type == 'application/json'
    )


def panel_login_requerido(view_func):
    """
    Exige que el usuario esté autenticado con una cuenta activa de Empleado
    para acceder a la vista administrativa.
    """
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not getattr(request.user, 'is_authenticated', False) or not getattr(request.user, 'is_active', False):
            if es_ajax_o_json(request):
                return JsonResponse({
                    'status': 'error',
                    'message': 'Sesión no iniciada o cuenta inactiva. Por favor iniciá sesión.'
                }, status=401)
            next_url = quote(request.get_full_path())
            return redirect(f"{reverse('panel_login')}?next={next_url}")
        return view_func(request, *args, **kwargs)
    return _wrapped


def requiere_permiso(codigo):
    """
    Controla que el usuario tenga un permiso específico asignado a través de su rol
    para ejecutar la acción solicitada.
    Si no tiene permiso, la solicitud es rechazada en el servidor.
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            # Primero garantizar autenticación
            if not getattr(request.user, 'is_authenticated', False) or not getattr(request.user, 'is_active', False):
                if es_ajax_o_json(request):
                    return JsonResponse({'status': 'error', 'message': 'Sesión no iniciada.'}, status=401)
                next_url = quote(request.get_full_path())
                return redirect(f"{reverse('panel_login')}?next={next_url}")

            # Validar permiso en Empleado
            tiene = False
            if hasattr(request.user, 'tiene_permiso'):
                tiene = request.user.tiene_permiso(codigo)
            elif getattr(request.user, 'is_superuser', False):
                tiene = True

            if not tiene:
                if es_ajax_o_json(request):
                    return JsonResponse({
                        'status': 'error',
                        'message': 'No tenés permiso para ejecutar esta acción.',
                        'codigo_requerido': codigo
                    }, status=403)

                messages.error(request, 'No tenés permiso para realizar esta acción.')
                referer = request.META.get('HTTP_REFERER')
                if referer and url_has_allowed_host_and_scheme(referer, allowed_hosts={request.get_host()}):
                    return redirect(referer)
                return redirect('panel_inicio')

            return view_func(request, *args, **kwargs)
        return _wrapped
    return decorator


def requiere_algun_permiso(codigos):
    """
    Controla que el usuario tenga al menos uno de los permisos dados.
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            if not getattr(request.user, 'is_authenticated', False) or not getattr(request.user, 'is_active', False):
                if es_ajax_o_json(request):
                    return JsonResponse({'status': 'error', 'message': 'Sesión no iniciada.'}, status=401)
                next_url = quote(request.get_full_path())
                return redirect(f"{reverse('panel_login')}?next={next_url}")

            tiene = False
            if hasattr(request.user, 'tiene_algun_permiso'):
                tiene = request.user.tiene_algun_permiso(codigos)
            elif getattr(request.user, 'is_superuser', False):
                tiene = True

            if not tiene:
                if es_ajax_o_json(request):
                    return JsonResponse({
                        'status': 'error',
                        'message': 'No tenés permiso para ejecutar esta acción.',
                        'codigos_requeridos': codigos
                    }, status=403)

                messages.error(request, 'No tenés permiso para realizar esta acción.')
                referer = request.META.get('HTTP_REFERER')
                if referer and url_has_allowed_host_and_scheme(referer, allowed_hosts={request.get_host()}):
                    return redirect(referer)
                return redirect('panel_inicio')

            return view_func(request, *args, **kwargs)
        return _wrapped
    return decorator
