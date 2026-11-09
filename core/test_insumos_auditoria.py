"""INS-004/005 (eliminar insumo) y SEG-030 (auditoría)."""
from decimal import Decimal

from django.contrib.auth.hashers import make_password
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.models import (
    Compras, DetalleCompra, Empleado, Insumo, Producto, Receta, RecetaInsumo,
    RegistroAuditoria, Rol,
)
from core.permisos_config import sincronizar_permisos
from core.stock_service import registrar_ingreso_lote

BACKEND = 'core.auth_backend.EmpleadoAuthBackend'


class BaseTest(TestCase):
    def setUp(self):
        rol = Rol.objects.create(nombrerol='Administrador')
        sincronizar_permisos()
        self.admin = Empleado.objects.create(
            nombre='Ana', apellido='Pérez', correo='ana@zonaburger.com',
            contrasena=make_password('ClaveSegura123'), idrol=rol, activo=True,
        )
        self.client.force_login(self.admin, backend=BACKEND)

    def insumo(self, nombre='Sal'):
        return Insumo.objects.create(
            nombreinsumo=nombre, unidadmedidaingreso='kg', unidadmedidaegreso='g',
            stockactual=Decimal('0'),
        )


class EliminarInsumoTests(BaseTest):
    def test_elimina_insumo_sin_uso_al_confirmar(self):
        ins = self.insumo()
        registrar_ingreso_lote(ins, Decimal('1'))
        resp = self.client.post(reverse('stock_eliminar', args=[ins.pk]))
        self.assertRedirects(resp, reverse('stock_lista'))
        self.assertFalse(Insumo.objects.filter(pk=ins.pk).exists())
        self.assertTrue(RegistroAuditoria.objects.filter(accion='INSUMO_ELIMINAR').exists())

    def test_cancelar_mantiene_el_insumo(self):
        ins = self.insumo()
        resp = self.client.get(reverse('stock_eliminar', args=[ins.pk]))  # solo pide confirmación
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(Insumo.objects.filter(pk=ins.pk).exists())

    def test_no_elimina_insumo_usado_en_receta(self):
        ins = self.insumo()
        prod = Producto.objects.create(nombre='Burger', precio=Decimal('100'))
        receta = Receta.objects.create(idproducto=prod)
        RecetaInsumo.objects.create(idreceta=receta, idinsumo=ins,
                                    cantidadinsumo=Decimal('10'), unidadmedida='g')
        self.client.post(reverse('stock_eliminar', args=[ins.pk]))
        self.assertTrue(Insumo.objects.filter(pk=ins.pk).exists())

    def test_no_elimina_insumo_con_compras(self):
        ins = self.insumo()
        compra = Compras.objects.create(fecha=timezone.now(), preciototal=Decimal('10'))
        DetalleCompra.objects.create(idcompra=compra, idinsumo=ins, cantidad=Decimal('1'),
                                     costounitario=Decimal('10'))
        self.client.post(reverse('stock_eliminar', args=[ins.pk]))
        self.assertTrue(Insumo.objects.filter(pk=ins.pk).exists())


class AuditoriaTests(BaseTest):
    def test_la_pantalla_lista_usuario_fecha_ip_y_descripcion(self):
        RegistroAuditoria.objects.create(
            idempleado=self.admin, accion='USUARIO_EDITAR',
            descripcion='Empleado x modificado', ip='10.0.0.5',
        )
        resp = self.client.get(reverse('auditoria_lista'))
        self.assertContains(resp, 'USUARIO_EDITAR')
        self.assertContains(resp, 'Empleado x modificado')
        self.assertContains(resp, '10.0.0.5')
        self.assertContains(resp, 'ana@zonaburger.com')

    def test_filtra_por_accion(self):
        RegistroAuditoria.objects.create(accion='LOGIN', descripcion='a', ip='1.1.1.1')
        RegistroAuditoria.objects.create(accion='LOGOUT', descripcion='b', ip='1.1.1.1')
        resp = self.client.get(reverse('auditoria_lista'), {'accion': 'LOGOUT'})
        self.assertEqual([r.accion for r in resp.context['pagina']], ['LOGOUT'])
