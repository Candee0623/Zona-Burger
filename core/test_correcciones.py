"""Pruebas de las correcciones: DEF-031, INS-003, REP-008, DEF-037, permisos y auditoría."""
from decimal import Decimal

from django.contrib.auth.hashers import make_password
from django.test import TestCase
from django.urls import reverse

from core.models import (
    Empleado, Insumo, Permiso, RegistroAuditoria, Rol, RolPermiso,
)
from core.permisos_config import sincronizar_permisos
from core.stock_service import (
    StockCambiadoError, ajustar_stock_insumo, registrar_ingreso_lote,
)

BACKEND = 'core.auth_backend.EmpleadoAuthBackend'


def empleado(rol, correo):
    return Empleado.objects.create(
        nombre='Ana', apellido='Pérez', correo=correo,
        contrasena=make_password('ClaveSegura123'), idrol=rol, activo=True,
    )


class PermisosYBotonesTests(TestCase):
    def setUp(self):
        sincronizar_permisos()
        self.admin = empleado(Rol.objects.create(nombrerol='Administrador'), 'admin@zb.com')

    def test_catalogo_incluye_eliminar_insumo_y_auditoria(self):
        self.assertTrue(Permiso.objects.filter(codigo='stock.eliminar').exists())
        self.assertTrue(Permiso.objects.filter(codigo='auditoria.ver').exists())

    def test_administrador_ve_los_permisos_aunque_la_base_este_vacia(self):
        Permiso.objects.all().delete()
        permisos = self.admin.obtener_permisos()
        self.assertIn('stock.eliminar', permisos)
        self.assertIn('auditoria.ver', permisos)

    def test_stock_muestra_boton_eliminar_al_administrador(self):
        Insumo.objects.create(nombreinsumo='Sal', unidadmedidaingreso='kg',
                              unidadmedidaegreso='g')
        self.client.force_login(self.admin, backend=BACKEND)
        resp = self.client.get(reverse('stock_lista'))
        self.assertContains(resp, 'Eliminar')

    def test_menu_muestra_auditoria_al_administrador(self):
        self.client.force_login(self.admin, backend=BACKEND)
        resp = self.client.get(reverse('stock_lista'))
        self.assertContains(resp, reverse('auditoria_lista'))

    def test_rol_sin_permiso_no_ve_boton_ni_menu(self):
        rol = Rol.objects.create(nombrerol='Cajero')
        RolPermiso.objects.create(idrol=rol, idpermiso=Permiso.objects.get(codigo='stock.ver'))
        Insumo.objects.create(nombreinsumo='Sal', unidadmedidaingreso='kg',
                              unidadmedidaegreso='g')
        self.client.force_login(empleado(rol, 'caja@zb.com'), backend=BACKEND)
        resp = self.client.get(reverse('stock_lista'))
        self.assertNotContains(resp, reverse('auditoria_lista'))
        self.assertNotContains(resp, '>\n                                        Eliminar')


class AuditoriaFiltroTests(TestCase):
    def setUp(self):
        sincronizar_permisos()
        self.admin = empleado(Rol.objects.create(nombrerol='Administrador'), 'admin@zb.com')
        self.client.force_login(self.admin, backend=BACKEND)

    def test_desplegable_con_nombres_legibles(self):
        resp = self.client.get(reverse('auditoria_lista'))
        self.assertContains(resp, 'Insumo eliminado')
        self.assertContains(resp, 'Inicio de sesión')

    def test_filtro_exacto_no_mezcla_login_con_login_fallido(self):
        RegistroAuditoria.objects.create(accion='LOGIN', descripcion='a', ip='1.1.1.1')
        RegistroAuditoria.objects.create(accion='LOGIN_FALLIDO', descripcion='b', ip='1.1.1.1')
        resp = self.client.get(reverse('auditoria_lista'), {'accion': 'LOGIN'})
        self.assertEqual([r.accion for r in resp.context['pagina']], ['LOGIN'])


class Def031AjusteSimultaneoTests(TestCase):
    def test_el_segundo_ajuste_no_pisa_al_primero(self):
        insumo = Insumo.objects.create(nombreinsumo='Sal', unidadmedidaingreso='kg',
                                       unidadmedidaegreso='g', stockactual=Decimal('0'))
        registrar_ingreso_lote(insumo, Decimal('10'))
        visto = Decimal('10')  # ambas sesiones abrieron el ajuste viendo 10
        ajustar_stock_insumo(insumo.pk, Decimal('7'), 'sesión A', None, stock_esperado=visto)
        with self.assertRaises(StockCambiadoError):
            ajustar_stock_insumo(insumo.pk, Decimal('3'), 'sesión B', None, stock_esperado=visto)
        insumo.refresh_from_db()
        self.assertEqual(insumo.stockactual, Decimal('7'))


class Ins003Tests(TestCase):
    def setUp(self):
        sincronizar_permisos()
        admin = empleado(Rol.objects.create(nombrerol='Administrador'), 'admin@zb.com')
        self.client.force_login(admin, backend=BACKEND)

    def test_rechaza_numeros_en_la_unidad_de_ingreso(self):
        self.client.post(reverse('stock_crear'), {
            'nombreinsumo': 'Harina', 'unidadmedidaingreso': 'kg2',
            'unidadmedidaegreso': 'g', 'stockactual': '0', 'stockminimo': '1',
        })
        self.assertFalse(Insumo.objects.filter(nombreinsumo='Harina').exists())

    def test_los_codigos_son_unicos_y_automaticos(self):
        a = Insumo.objects.create(nombreinsumo='A', unidadmedidaingreso='kg', unidadmedidaegreso='g')
        b = Insumo.objects.create(nombreinsumo='B', unidadmedidaingreso='kg', unidadmedidaegreso='g')
        self.assertNotEqual(a.codigo, b.codigo)


class ReportesPermisosTests(TestCase):
    URLS = ['exportar_resumen_pdf', 'exportar_resumen_excel', 'exportar_productos_pdf',
            'exportar_productos_excel', 'exportar_dinero_pdf', 'exportar_dinero_excel']

    def setUp(self):
        sincronizar_permisos()

    def test_sin_permiso_no_se_descarga_nada(self):
        rol = Rol.objects.create(nombrerol='Cajero')
        self.client.force_login(empleado(rol, 'caja@zb.com'), backend=BACKEND)
        for nombre in self.URLS:
            resp = self.client.get(reverse(nombre))
            self.assertNotEqual(resp.status_code, 200, nombre)
            self.assertNotIn('attachment', resp.headers.get('Content-Disposition', ''), nombre)

    def test_solo_exportar_sin_ver_tampoco_descarga(self):
        rol = Rol.objects.create(nombrerol='Contador')
        RolPermiso.objects.create(idrol=rol, idpermiso=Permiso.objects.get(codigo='reportes.exportar'))
        self.client.force_login(empleado(rol, 'cont@zb.com'), backend=BACKEND)
        resp = self.client.get(reverse('exportar_resumen_pdf'))
        self.assertNotEqual(resp.status_code, 200)