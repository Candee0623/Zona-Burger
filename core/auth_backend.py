import logging
from django.contrib.auth.backends import BaseBackend
from django.contrib.auth.hashers import check_password
from core.models import Empleado

logger = logging.getLogger(__name__)


class EmpleadoAuthBackend(BaseBackend):
    """
    Backend de autenticación personalizado para Zona Burger.
    Permite iniciar sesión utilizando correo electrónico o nombre de usuario
    y contraseña con hash seguro de Django.
    Valida que la cuenta esté activa.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        if not username or not password:
            return None

        identificador = username.strip().lower()

        # Permitir login por correo electrónico o por nombre
        empleado = (
            Empleado.objects.filter(correo__iexact=identificador).first()
            or Empleado.objects.filter(nombre__iexact=username.strip()).first()
        )

        if not empleado:
            logger.warning("Intento de login fallido: usuario/correo no encontrado '%s'", identificador)
            return None

        # Verificar si la cuenta está activa
        if not getattr(empleado, 'activo', True):
            logger.warning("Intento de login con cuenta inactiva: '%s'", identificador)
            return None

        # Validar contraseña almacenada con hash seguro
        if check_password(password, empleado.contrasena):
            return empleado

        logger.warning("Intento de login fallido: contraseña incorrecta para '%s'", identificador)
        return None

    def get_user(self, user_id):
        try:
            empleado = Empleado.objects.select_related('idrol').get(pk=user_id)
            # Si la cuenta fue desactivada mientras la sesión seguía abierta, invalidar sesión
            if not getattr(empleado, 'activo', True):
                return None
            return empleado
        except Empleado.DoesNotExist:
            return None
