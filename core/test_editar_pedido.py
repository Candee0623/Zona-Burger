"""Editar pedido desde el panel: extras por producto y cambio de estado."""
from decimal import Decimal

from django.contrib.auth.hashers import make_password
from django.test import TestCase
from django.urls import reverse

from core.models import (
    Cliente, DetallePedido, Empleado, EstadoPedido, Extras, Insumo, MedioPago,
    MovimientoStock, Pedido, Permiso, Producto, ProductoExtras, RegistroAuditoria,
    Rol, RolPermiso,
)
from core.permisos_config import sincronizar_permisos

BACKEND = 'core.auth_backend.EmpleadoAuthBackend'


def crear_empleado(rol, correo):
    return Empleado.objects.create(
        nombre='Ana', apellido='Pérez', correo=correo,
        contrasena=make_password('ClaveSegura123'), idrol=rol, activo=True,
    )


class EditarPedidoExtrasYEstadoTests(TestCase):
    def setUp(self):
        self.rol_admin = Rol.objects.create(nombrerol='Administrador')
        sincronizar_permisos()
        self.admin = crear_empleado(self.rol_admin, 'admin@zonaburger.com')
        self.client.force_login(self.admin, backend=BACKEND)

        self.est = {
            n: EstadoPedido.objects.create(descripcion=n)
            for n in ['Pendiente', 'En proceso', 'Enviado', 'Entregado', 'Cancelado']
        }
        self.efectivo = MedioPago.objects.create(nombremetodo='Efectivo')
        self.burger = Producto.objects.create(nombre='Burger', precio=Decimal('1000'))
        self.queso = Extras.objects.create(nombre='Queso', precio=Decimal('200'))
        self.bacon = Extras.objects.create(nombre='Bacon', precio=Decimal('300'))
        ProductoExtras.objects.create(idproducto=self.burger, idextra=self.queso)
        ProductoExtras.objects.create(idproducto=self.burger, idextra=self.bacon)

        cliente = Cliente.objects.create(nombre='Lucía', apellido='Gómez', telefono='1122334455')
        self.pedido = Pedido.objects.create(
            idcliente=cliente, total=Decimal('1000'), idmediopago=self.efectivo,
            idestadopedido=self.est['Pendiente'],
        )
        self.detalle = DetallePedido.objects.create(
            idpedido=self.pedido, idproducto=self.burger, cantidad=1,
            preciounitario=Decimal('1000'), observaciones='Sin cebolla',
        )
        self.url = reverse('editar_historial_pedido', args=[self.pedido.pk])

    def datos(self, **cambios):
        d = {
            'filas': '1', 'producto_0': str(self.burger.pk), 'cantidad_0': '1',
            'precio_0': '1000.00', 'observaciones_0': 'Sin cebolla', 'extras_0': '',
            'modo_pago': 'unico', 'medio_unico': str(self.efectivo.pk),
            'estado': str(self.est['Pendiente'].pk),
            'estado_esperado': str(self.est['Pendiente'].pk),
        }
        d.update(cambios)
        return d

    # ---------- Extras ----------

    def test_get_muestra_estado_y_extras(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'id="ep-estado"')
        self.assertContains(resp, 'ep-extras-data')
        self.assertContains(resp, 'Queso')
        self.assertTrue(resp.context['puede_cambiar_estado'])

    def test_agregar_extras_suma_texto_y_total(self):
        resp = self.client.post(self.url, self.datos(
            extras_0=f'{self.queso.pk}:2,{self.bacon.pk}:1', precio_0='1700.00',
        ))
        self.assertRedirects(resp, reverse('detalle_historial_pedido', args=[self.pedido.pk]))
        d = DetallePedido.objects.get(idpedido=self.pedido)
        self.assertEqual(
            d.observaciones, 'Sin cebolla, Extra: Queso (x2), Extra: Bacon (x1)'
        )
        self.assertEqual(d.preciounitario, Decimal('1700.00'))
        self.pedido.refresh_from_db()
        self.assertEqual(self.pedido.total, Decimal('1700.00'))

    def test_extras_existentes_se_reconocen_y_se_conservan(self):
        self.detalle.observaciones = 'Sin cebolla, Extra: Queso (x2)'
        self.detalle.save()
        resp = self.client.get(self.url)
        fila = resp.context['filas'][0]
        self.assertEqual(fila['observaciones'], 'Sin cebolla')
        self.assertEqual(fila['extras'], f'{self.queso.pk}:2')
        # Guardar sin tocar nada no cambia el texto.
        self.client.post(self.url, self.datos(
            extras_0=fila['extras'], observaciones_0=fila['observaciones'],
        ))
        d = DetallePedido.objects.get(idpedido=self.pedido)
        self.assertEqual(d.observaciones, 'Sin cebolla, Extra: Queso (x2)')

    def test_quitar_extras(self):
        self.detalle.observaciones = 'Extra: Queso (x1), Sin cebolla'
        self.detalle.save()
        self.client.post(self.url, self.datos(extras_0='', observaciones_0='Sin cebolla'))
        d = DetallePedido.objects.get(idpedido=self.pedido)
        self.assertEqual(d.observaciones, 'Sin cebolla')

    def test_extra_invalido_o_cantidad_fuera_de_rango(self):
        for malo in ['999:1', f'{self.queso.pk}:9', f'{self.queso.pk}:0', 'abc']:
            resp = self.client.post(self.url, self.datos(extras_0=malo))
            self.assertEqual(resp.status_code, 200, malo)
        d = DetallePedido.objects.get(idpedido=self.pedido)
        self.assertEqual(d.observaciones, 'Sin cebolla')

    # ---------- Estado ----------

    def test_cambiar_estado_valido_y_audita(self):
        resp = self.client.post(self.url, self.datos(estado=str(self.est['En proceso'].pk)))
        self.assertEqual(resp.status_code, 302)
        self.pedido.refresh_from_db()
        self.assertEqual(self.pedido.idestadopedido, self.est['En proceso'])
        log = RegistroAuditoria.objects.filter(accion='PEDIDO_EDITAR').first()
        self.assertIn('Pendiente → En proceso', log.descripcion)

    def test_estado_no_permitido_se_rechaza(self):
        # Pendiente -> Entregado no está permitido por las reglas del panel.
        resp = self.client.post(self.url, self.datos(estado=str(self.est['Entregado'].pk)))
        self.assertEqual(resp.status_code, 200)
        self.pedido.refresh_from_db()
        self.assertEqual(self.pedido.idestadopedido, self.est['Pendiente'])

    def test_cancelar_exige_motivo(self):
        resp = self.client.post(self.url, self.datos(estado=str(self.est['Cancelado'].pk)))
        self.assertEqual(resp.status_code, 200)
        self.pedido.refresh_from_db()
        self.assertEqual(self.pedido.idestadopedido, self.est['Pendiente'])

    def test_cancelar_guarda_motivo_y_reintegra_stock(self):
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
        resp = self.client.post(self.url, self.datos(
            estado=str(self.est['Cancelado'].pk), justificacioncancelacion='Cliente no atiende',
            ajustar_stock='1',
        ))
        self.assertEqual(resp.status_code, 302)
        self.pedido.refresh_from_db()
        insumo.refresh_from_db()
        self.assertEqual(self.pedido.idestadopedido, self.est['Cancelado'])
        self.assertEqual(self.pedido.justificacioncancelacion, 'Cliente no atiende')
        self.assertFalse(self.pedido.stock_descontado)
        self.assertEqual(insumo.stockactual, Decimal('10'))

    def test_pedido_cancelado_no_se_edita(self):
        self.pedido.idestadopedido = self.est['Cancelado']
        self.pedido.save()
        resp = self.client.get(self.url)
        self.assertRedirects(resp, reverse('detalle_historial_pedido', args=[self.pedido.pk]))

    def test_pedido_entregado_muestra_estado_bloqueado(self):
        self.pedido.idestadopedido = self.est['Entregado']
        self.pedido.save()
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.context['puede_cambiar_estado'])
        self.assertEqual(len(resp.context['estados']), 1)

    def test_otro_empleado_cambio_el_estado_mientras_se_editaba(self):
        Pedido.objects.filter(pk=self.pedido.pk).update(idestadopedido=self.est['En proceso'])
        resp = self.client.post(self.url, self.datos(estado=str(self.est['Enviado'].pk)))
        self.assertEqual(resp.status_code, 302)
        self.pedido.refresh_from_db()
        self.assertEqual(self.pedido.idestadopedido, self.est['En proceso'])

    def test_sin_permiso_de_estado_no_cambia_el_estado(self):
        rol = Rol.objects.create(nombrerol='Cajero')
        for codigo in ('pedidos.editar',):
            RolPermiso.objects.create(
                idrol=rol, idpermiso=Permiso.objects.get(codigo=codigo),
            )
        cajero = crear_empleado(rol, 'cajero@zonaburger.com')
        self.client.force_login(cajero, backend=BACKEND)
        resp = self.client.get(self.url)
        self.assertFalse(resp.context['puede_estado'])
        self.client.post(self.url, self.datos(estado=str(self.est['En proceso'].pk)))
        self.pedido.refresh_from_db()
        self.assertEqual(self.pedido.idestadopedido, self.est['Pendiente'])

    # ---------- Estado de pago ----------

    def test_marcar_como_pagado_y_audita(self):
        self.assertFalse(self.pedido.pagado)
        self.client.post(self.url, self.datos(pagado='1'))
        self.pedido.refresh_from_db()
        self.assertTrue(self.pedido.pagado)
        log = RegistroAuditoria.objects.filter(accion='PEDIDO_EDITAR').first()
        self.assertIn('Pendiente → Pagado', log.descripcion)

    def test_marcar_como_pendiente(self):
        Pedido.objects.filter(pk=self.pedido.pk).update(pagado=True)
        self.client.post(self.url, self.datos(pagado='0'))
        self.pedido.refresh_from_db()
        self.assertFalse(self.pedido.pagado)

    def test_sin_el_campo_pagado_no_se_toca(self):
        Pedido.objects.filter(pk=self.pedido.pk).update(pagado=True)
        self.client.post(self.url, self.datos())
        self.pedido.refresh_from_db()
        self.assertTrue(self.pedido.pagado)

    def test_sin_permiso_de_pago_no_cambia(self):
        rol = Rol.objects.create(nombrerol='Cajero')
        RolPermiso.objects.create(idrol=rol, idpermiso=Permiso.objects.get(codigo='pedidos.editar'))
        self.client.force_login(crear_empleado(rol, 'c2@zonaburger.com'), backend=BACKEND)
        resp = self.client.get(self.url)
        self.assertFalse(resp.context['puede_pagado'])
        self.client.post(self.url, self.datos(pagado='1'))
        self.pedido.refresh_from_db()
        self.assertFalse(self.pedido.pagado)
