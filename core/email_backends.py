"""
Envío de correo por API HTTPS.

Render (plan gratuito) bloquea los puertos SMTP 25, 465 y 587, así que Gmail
por SMTP no funciona ahí: la conexión simplemente se queda esperando y el
correo nunca sale. Las APIs de envío usan HTTPS (puerto 443), que no está
bloqueado.

Se activa desde las variables de entorno, sin tocar el código de las vistas:

    EMAIL_BACKEND=core.email_backends.ApiEmailBackend
    EMAIL_API_PROVIDER=brevo        (o "resend")
    EMAIL_API_KEY=<clave de la API>
    DEFAULT_FROM_EMAIL=Zona Burger <correo-verificado@dominio.com>
"""

import logging
from email.utils import parseaddr

import requests
from django.core.mail.backends.base import BaseEmailBackend

logger = logging.getLogger(__name__)

PROVEEDORES = ('brevo', 'resend')


class ErrorEnvioCorreo(Exception):
    """El proveedor rechazó el correo o no se pudo contactar."""


class ApiEmailBackend(BaseEmailBackend):

    def __init__(
        self,
        provider='brevo',
        api_key='',
        timeout=10,
        fail_silently=False,
        **kwargs,
    ):
        super().__init__(**kwargs)

        self.provider = (provider or '').strip().lower()
        self.api_key = (api_key or '').strip()
        self.timeout = timeout
        self.fail_silently = fail_silently

        if self.provider not in PROVEEDORES:
            raise ValueError(
                f'EMAIL_API_PROVIDER inválido: "{provider}". '
                f'Usá uno de: {", ".join(PROVEEDORES)}.'
            )

    def send_messages(self, email_messages):
        enviados = 0

        for mensaje in email_messages or []:
            try:
                self._enviar(mensaje)
                enviados += 1
            except Exception:
                if not self.fail_silently:
                    raise
                logger.exception('No se pudo enviar el correo por API.')

        return enviados

    # Armado de la petición

    @staticmethod
    def _contenidos(mensaje):
        texto = mensaje.body or ''
        html = ''

        for contenido, tipo in getattr(mensaje, 'alternatives', None) or []:
            if tipo == 'text/html':
                html = contenido
                break

        # Si el cuerpo principal ya es HTML, se usa como tal.
        if not html and getattr(mensaje, 'content_subtype', 'plain') == 'html':
            html, texto = texto, ''

        return texto, html

    def _enviar(self, mensaje):
        if not self.api_key:
            raise ErrorEnvioCorreo(
                'Falta EMAIL_API_KEY: no hay clave para el envío por API.'
            )

        destinatarios = [d for d in (mensaje.to or []) if d]
        if not destinatarios:
            raise ErrorEnvioCorreo('El correo no tiene destinatarios.')

        if getattr(mensaje, 'attachments', None):
            logger.warning(
                'El envío por API no incluye adjuntos; se enviará sin ellos.'
            )

        texto, html = self._contenidos(mensaje)

        if self.provider == 'brevo':
            url, cabeceras, datos = self._peticion_brevo(
                mensaje, destinatarios, texto, html
            )
        else:
            url, cabeceras, datos = self._peticion_resend(
                mensaje, destinatarios, texto, html
            )

        try:
            respuesta = requests.post(
                url, headers=cabeceras, json=datos, timeout=self.timeout
            )
        except requests.RequestException as error:
            raise ErrorEnvioCorreo(
                f'No se pudo contactar a {self.provider}: {error}'
            ) from error

        if not 200 <= respuesta.status_code < 300:
            raise ErrorEnvioCorreo(
                f'{self.provider} rechazó el correo '
                f'(HTTP {respuesta.status_code}): {respuesta.text[:300]}'
            )

    def _peticion_brevo(self, mensaje, destinatarios, texto, html):
        nombre, correo = parseaddr(mensaje.from_email)

        sender = {'email': correo}
        if nombre:
            sender['name'] = nombre

        datos = {
            'sender': sender,
            'to': [{'email': d} for d in destinatarios],
            'subject': mensaje.subject,
        }

        if html:
            datos['htmlContent'] = html
        if texto:
            datos['textContent'] = texto

        if mensaje.reply_to:
            datos['replyTo'] = {'email': parseaddr(mensaje.reply_to[0])[1]}

        cabeceras = {
            'api-key': self.api_key,
            'accept': 'application/json',
            'content-type': 'application/json',
        }

        return 'https://api.brevo.com/v3/smtp/email', cabeceras, datos

    def _peticion_resend(self, mensaje, destinatarios, texto, html):
        datos = {
            'from': mensaje.from_email,
            'to': destinatarios,
            'subject': mensaje.subject,
        }

        if html:
            datos['html'] = html
        if texto:
            datos['text'] = texto

        if mensaje.reply_to:
            datos['reply_to'] = list(mensaje.reply_to)

        cabeceras = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json',
        }

        return 'https://api.resend.com/emails', cabeceras, datos
