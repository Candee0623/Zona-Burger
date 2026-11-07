from django.contrib.auth.hashers import make_password
from django.test import TestCase
from django.urls import reverse

from core.decorators import PERMISOS_EN_VISTAS, requiere_permiso
from core.models import Empleado, Permiso, Rol, RolPermiso
from core.permisos_config import sincronizar_permisos

BACKEND = 'core.auth_backend.EmpleadoAuthBackend'


def crear_empleado(rol, correo='empleado@zonaburger.com'):
    return Empleado.objects.create(
        nombre='Ana',
        apellido='Pérez',
        correo=correo,
        contrasena=make_password('ClaveSegura123'),
        idrol=rol,
        activo=True,
    )


class SincronizacionPermisosTests(TestCase):
    def test_migrar_crea_los_permisos_del_sistema(self):
        self.assertTrue(Permiso.objects.filter(codigo='pedidos.ver').exists())
        self.assertTrue(Permiso.objects.filter(codigo='reportes.exportar').exists())

    def test_se_recrean_si_se_borran_los_datos(self):
        total = Permiso.objects.count()
        Permiso.objects.all().delete()

        resultado = sincronizar_permisos()

        self.assertEqual(Permiso.objects.count(), total)
        self.assertEqual(len(resultado['nuevos']), total)

    def test_no_duplica_ni_pisa_asignaciones_de_roles(self):
        rol = Rol.objects.create(nombrerol='Cajero')
        permiso = Permiso.objects.get(codigo='pedidos.ver')
        RolPermiso.objects.create(idrol=rol, idpermiso=permiso)
        total = Permiso.objects.count()

        sincronizar_permisos()

        self.assertEqual(Permiso.objects.count(), total)
        self.assertTrue(RolPermiso.objects.filter(idrol=rol, idpermiso=permiso).exists())

    def test_administrador_recibe_todos_los_permisos(self):
        admin = Rol.objects.create(nombrerol='Administrador')

        sincronizar_permisos()

        self.assertEqual(
            RolPermiso.objects.filter(idrol=admin).count(),
            Permiso.objects.count(),
        )

    def test_un_permiso_nuevo_en_una_vista_se_detecta_solo(self):
        requiere_permiso('mesas.ver')(lambda request: None)
        self.addCleanup(PERMISOS_EN_VISTAS.pop, 'mesas.ver', None)

        sincronizar_permisos()

        permiso = Permiso.objects.get(codigo='mesas.ver')
        self.assertEqual((permiso.modulo, permiso.accion), ('Mesas', 'Ver'))


class PerfilPermisosTests(TestCase):
    def test_el_perfil_muestra_solo_los_permisos_del_rol(self):
        rol = Rol.objects.create(nombrerol='Cajero')
        for codigo in ('pedidos.ver', 'pedidos.imprimir'):
            RolPermiso.objects.create(idrol=rol, idpermiso=Permiso.objects.get(codigo=codigo))
        empleado = crear_empleado(rol)
        self.client.force_login(empleado, backend=BACKEND)

        respuesta = self.client.get(reverse('panel_perfil'))

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'Ana Pérez')
        self.assertContains(respuesta, 'Cajero')
        self.assertContains(respuesta, 'Imprimir ticket')
        self.assertNotContains(respuesta, 'Eliminar productos')
        self.assertEqual(respuesta.context['total_permisos'], 2)

    def test_el_administrador_ve_todos_los_permisos(self):
        rol = Rol.objects.create(nombrerol='Administrador')
        empleado = crear_empleado(rol, 'admin@zonaburger.com')
        self.client.force_login(empleado, backend=BACKEND)

        respuesta = self.client.get(reverse('panel_perfil'))

        self.assertEqual(respuesta.context['total_permisos'], Permiso.objects.count())

    def test_rol_sin_permisos_lo_aclara(self):
        rol = Rol.objects.create(nombrerol='Pasante')
        empleado = crear_empleado(rol, 'pasante@zonaburger.com')
        self.client.force_login(empleado, backend=BACKEND)

        respuesta = self.client.get(reverse('panel_perfil'))

        self.assertContains(respuesta, 'Tu rol no tiene permisos asignados')


class ProteccionDeVistasTests(TestCase):
    def setUp(self):
        self.rol = Rol.objects.create(nombrerol='Cajero')
        self.empleado = crear_empleado(self.rol, 'cajero@zonaburger.com')
        self.client.force_login(self.empleado, backend=BACKEND)

    def dar(self, *codigos):
        for codigo in codigos:
            RolPermiso.objects.create(idrol=self.rol, idpermiso=Permiso.objects.get(codigo=codigo))

    def test_sin_permiso_no_entra_a_las_pantallas_administrativas(self):
        for nombre in ('rol_lista', 'rol_crear', 'empleado_lista', 'horarios_lista',
                       'zonas_entrega_lista', 'historial_pedidos', 'centro_reportes',
                       'estado_negocio'):
            respuesta = self.client.get(reverse(nombre))
            self.assertEqual(respuesta.status_code, 302, nombre)
            self.assertEqual(respuesta.url, reverse('panel_inicio'), nombre)

    def test_con_permiso_entra(self):
        self.dar('roles.ver', 'usuarios.ver', 'historial.ver')
        for nombre in ('rol_lista', 'empleado_lista', 'historial_pedidos'):
            self.assertEqual(self.client.get(reverse(nombre)).status_code, 200, nombre)

    def test_sin_roles_asignar_permisos_no_cambia_los_permisos_del_rol(self):
        objetivo = Rol.objects.create(nombrerol='Pasante')
        self.dar('roles.editar')
        permiso = Permiso.objects.get(codigo='pedidos.ver')

        self.client.post(
            reverse('rol_editar', args=[objetivo.pk]),
            {'nombrerol': 'Pasante', 'permisos': [permiso.pk]},
        )

        self.assertFalse(RolPermiso.objects.filter(idrol=objetivo).exists())

    def test_con_roles_asignar_permisos_si_los_cambia(self):
        objetivo = Rol.objects.create(nombrerol='Pasante')
        self.dar('roles.editar', 'roles.asignar_permisos')
        permiso = Permiso.objects.get(codigo='pedidos.ver')

        self.client.post(
            reverse('rol_editar', args=[objetivo.pk]),
            {'nombrerol': 'Pasante', 'permisos': [permiso.pk]},
        )

        self.assertTrue(RolPermiso.objects.filter(idrol=objetivo, idpermiso=permiso).exists())

    def test_el_menu_lateral_solo_muestra_lo_permitido(self):
        self.dar('stock.ver')

        respuesta = self.client.get(reverse('panel_inicio'))

        self.assertContains(respuesta, reverse('stock_lista'))
        self.assertNotContains(respuesta, reverse('rol_lista'))


class CorreoRecuperacionTests(TestCase):
    def test_el_correo_tiene_version_html_con_el_enlace(self):
        from django.core import mail

        rol = Rol.objects.create(nombrerol='Cajero')
        empleado = crear_empleado(rol, 'recupera@zonaburger.com')

        self.client.post(reverse('panel_recuperar_contrasena'), {'correo': empleado.correo})

        self.assertEqual(len(mail.outbox), 1)
        mensaje = mail.outbox[0]
        empleado.refresh_from_db()
        self.assertIn(empleado.token_recuperacion, mensaje.body)
        html, tipo = mensaje.alternatives[0]
        self.assertEqual(tipo, 'text/html')
        self.assertIn(empleado.token_recuperacion, html)
        self.assertIn('Restablecer contraseña', html)
