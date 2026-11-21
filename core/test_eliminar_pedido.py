"""Eliminar pedidos desde el panel (permiso, confirmación, stock y auditoría)."""
from decimal import Decimal

from django.contrib.auth.hashers import make_password
from django.test import TestCase
from django.urls import reverse

from core.models import (
    Cliente, DetallePedido, Empleado, Insumo, MovimientoStock, Pedido,
    Permiso, RegistroAuditoria, Rol, RolPermiso,
)
from core.permisos_config import sincronizar_permisos

BACKEND = 'core.auth_backend.EmpleadoAuthBackend'


def crear_empleado(rol, correo):
    return Empleado.objects.create(
        nombre='Ana', apellido='Pérez', correo=correo,
        contrasena=make_password('ClaveSegura123'), idrol=rol, activo=True,
    )


class EliminarPedidoTests(TestCase):
    def setUp(self):
        rol = Rol.objects.create(nombrerol='Administrador')
        sincronizar_permisos()
        self.admin = crear_empleado(rol, 'admin@zonaburger.com')
        self.client.force_login(self.admin, backend=BACKEND)

        cliente = Cliente.objects.create(nombre='Lucía', apellido='Gómez', telefono='1122334455')
        self.pedido = Pedido.objects.create(idcliente=cliente, total=Decimal('1000'))
        DetallePedido.objects.create(
            idpedido=self.pedido, cantidad=2, preciounitario=Decimal('500'),
            nombreproducto='Burger',
        )
        self.url = reverse('eliminar_pedido', args=[self.pedido.pk])

    def con_stock_descontado(self):
        insumo = Insumo.objects.create(
            nombreinsumo='Carne', unidadmedidaingreso='kg', unidadmedidaegreso='g',
            stockactual=Decimal('8'),
        )
        MovimientoStock.objects.create(
            idinsumo=insumo, cantidad=Decimal('2'), idpedido=self.pedido,
            tipomovimiento=MovimientoStock.TIPO_DESCUENTO,
        )
        self.pedido.stock_descontado = True
        self.pedido.save()
        return insumo

    def test_get_pide_confirmacion_y_no_borra(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(Pedido.objects.filter(pk=self.pedido.pk).exists())

    def test_numero_incorrecto_no_borra(self):
        resp = self.client.post(self.url, {'confirmacion': '999'})
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(Pedido.objects.filter(pk=self.pedido.pk).exists())

    def test_confirmando_borra_pedido_detalles_y_audita(self):
        resp = self.client.post(self.url, {'confirmacion': str(self.pedido.pk)})
        self.assertRedirects(resp, reverse('historial_pedidos'))
        self.assertFalse(Pedido.objects.exists())
        self.assertFalse(DetallePedido.objects.exists())
        self.assertTrue(RegistroAuditoria.objects.filter(accion='PEDIDO_ELIMINAR').exists())

    def test_acepta_el_numero_con_numeral(self):
        self.client.post(self.url, {'confirmacion': f'#{self.pedido.pk}'})
        self.assertFalse(Pedido.objects.exists())

    def test_con_stock_descontado_obliga_a_elegir(self):
        self.con_stock_descontado()
        resp = self.client.post(self.url, {'confirmacion': str(self.pedido.pk)})
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(Pedido.objects.filter(pk=self.pedido.pk).exists())

    def test_devolver_stock_lo_reintegra_y_borra_todo(self):
        insumo = self.con_stock_descontado()
        self.client.post(self.url, {'confirmacion': str(self.pedido.pk), 'devolver_stock': 'si'})
        insumo.refresh_from_db()
        self.assertEqual(insumo.stockactual, Decimal('10'))
        self.assertFalse(Pedido.objects.exists())
        self.assertFalse(MovimientoStock.objects.exists())

    def test_no_devolver_stock_lo_deja_como_esta(self):
        insumo = self.con_stock_descontado()
        self.client.post(self.url, {'confirmacion': str(self.pedido.pk), 'devolver_stock': 'no'})
        insumo.refresh_from_db()
        self.assertEqual(insumo.stockactual, Decimal('8'))
        self.assertFalse(Pedido.objects.exists())

    def test_solo_borra_el_pedido_indicado(self):
        otro = Pedido.objects.create(total=Decimal('50'))
        self.client.post(self.url, {'confirmacion': str(self.pedido.pk)})
        self.assertEqual(list(Pedido.objects.values_list('pk', flat=True)), [otro.pk])

    def test_pedido_inexistente_da_404(self):
        resp = self.client.get(reverse('eliminar_pedido', args=[9999]))
        self.assertEqual(resp.status_code, 404)

    def test_sin_permiso_no_puede_ni_ver_ni_borrar(self):
        cajero = Rol.objects.create(nombrerol='Cajero')
        RolPermiso.objects.create(idrol=cajero, idpermiso=Permiso.objects.get(codigo='historial.ver'))
        self.client.force_login(crear_empleado(cajero, 'cajero@zonaburger.com'), backend=BACKEND)

        self.assertEqual(self.client.get(self.url).status_code, 302)
        self.client.post(self.url, {'confirmacion': str(self.pedido.pk)})
        self.assertTrue(Pedido.objects.filter(pk=self.pedido.pk).exists())

    def test_boton_solo_aparece_con_permiso(self):
        detalle = reverse('detalle_historial_pedido', args=[self.pedido.pk])
        self.assertContains(self.client.get(detalle), self.url)

        cajero = Rol.objects.create(nombrerol='Cajero')
        RolPermiso.objects.create(idrol=cajero, idpermiso=Permiso.objects.get(codigo='historial.ver'))
        self.client.force_login(crear_empleado(cajero, 'cajero@zonaburger.com'), backend=BACKEND)
        self.assertNotContains(self.client.get(detalle), self.url)
