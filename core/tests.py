from decimal import Decimal
from django.contrib.auth.hashers import make_password
from django.test import Client, TestCase
from django.urls import reverse
from .models import (
    Insumo, Producto, CategoriaProducto, EstadoStock, EstadoProducto,
    GrupoOpcion, Opcion, Receta, RecetaInsumo, Cliente, MedioPago,
    EstadoPedido, Pedido, DetallePedido, MovimientoStock, Rol, Empleado
)
from .stock_service import (
    calcular_consumo_carrito,
    verificar_stock_disponible,
    descontar_stock_pedido,
    reintegrar_stock_pedido,
    StockInsuficienteError,
)


class StockOpcionesTestCase(TestCase):
    def setUp(self):
        # 1. Estados base
        self.estado_stock = EstadoStock.objects.create(descripcion='Normal', nivelcritico=5)
        self.estado_prod = EstadoProducto.objects.create(descripcion='Activo')
        self.categoria = CategoriaProducto.objects.create(nombre='Combos')

        # 2. Insumos en stock
        self.insumo_pan = Insumo.objects.create(
            codigo='INS-001',
            nombreinsumo='Pan de Hamburguesa',
            unidadmedidaingreso='unidades',
            unidadmedidaegreso='unidades',
            stockactual=Decimal('50.00'),
            stockminimo=Decimal('10.00'),
            descontar_stock_automaticamente=True,
        )
        self.insumo_sprite = Insumo.objects.create(
            codigo='INS-002',
            nombreinsumo='Sprite 500ml',
            unidadmedidaingreso='unidades',
            unidadmedidaegreso='unidades',
            stockactual=Decimal('20.00'),
            stockminimo=Decimal('5.00'),
            descontar_stock_automaticamente=True,
        )
        self.insumo_cocacola = Insumo.objects.create(
            codigo='INS-003',
            nombreinsumo='Coca-Cola 500ml',
            unidadmedidaingreso='unidades',
            unidadmedidaegreso='unidades',
            stockactual=Decimal('20.00'),
            stockminimo=Decimal('5.00'),
            descontar_stock_automaticamente=True,
        )
        self.insumo_fanta = Insumo.objects.create(
            codigo='INS-004',
            nombreinsumo='Fanta 500ml',
            unidadmedidaingreso='unidades',
            unidadmedidaegreso='unidades',
            stockactual=Decimal('20.00'),
            stockminimo=Decimal('5.00'),
            descontar_stock_automaticamente=True,
        )

        # 3. Producto principal (Combo Hamburguesa)
        self.producto_combo = Producto.objects.create(
            nombre='Combo Hamburguesa Clásica',
            precio=Decimal('5000.00'),
            idcategoria=self.categoria,
            idestadostock=self.estado_stock,
            idestadoproducto=self.estado_prod,
        )

        # 4. Receta del producto (usa 1 pan)
        self.receta = Receta.objects.create(idproducto=self.producto_combo)
        self.receta_insumo = RecetaInsumo.objects.create(
            idreceta=self.receta,
            idinsumo=self.insumo_pan,
            cantidadinsumo=Decimal('1.00'),
            unidadmedida='unidades',
            es_removible=False,
        )

        # 5. Grupo de Opciones: Bebida
        self.grupo_bebidas = GrupoOpcion.objects.create(
            nombre='Bebida',
            minselecciones=1,
            maxselecciones=1,
        )

        # 6. Opciones vinculadas a insumos de inventario
        self.opcion_sprite = Opcion.objects.create(
            idgrupo=self.grupo_bebidas,
            nombre='Sprite',
            precioadicional=Decimal('0.00'),
            idinsumo=self.insumo_sprite,
            cantidad_insumo=Decimal('1.00'),
        )
        self.opcion_cocacola = Opcion.objects.create(
            idgrupo=self.grupo_bebidas,
            nombre='Coca-Cola',
            precioadicional=Decimal('0.00'),
            idinsumo=self.insumo_cocacola,
            cantidad_insumo=Decimal('1.00'),
        )
        self.opcion_fanta = Opcion.objects.create(
            idgrupo=self.grupo_bebidas,
            nombre='Fanta',
            precioadicional=Decimal('0.00'),
            idinsumo=self.insumo_fanta,
            cantidad_insumo=Decimal('1.00'),
        )

        # 7. Opción sin insumo vinculado (ej: opción personalizada o no inventariable)
        self.opcion_sin_insumo = Opcion.objects.create(
            idgrupo=self.grupo_bebidas,
            nombre='Agua del grifo con hielo',
            precioadicional=Decimal('0.00'),
            idinsumo=None,
            cantidad_insumo=Decimal('1.00'),
        )

        # 8. Datos de checkout / pedidos
        self.cliente = Cliente.objects.create(nombre='Juan', apellido='Pérez', telefono='1122334455')
        self.medio_pago = MedioPago.objects.create(nombremetodo='Efectivo')
        self.estado_pendiente = EstadoPedido.objects.create(descripcion='Pendiente')
        self.estado_cancelado = EstadoPedido.objects.create(descripcion='Cancelado')

    def test_01_cliente_selecciona_sprite_descuenta_una_unidad_sprite(self):
        """Escenario 1: Un cliente selecciona una Sprite -> se descuenta una unidad de Sprite."""
        carrito = {
            'item_1': {
                'producto_id': self.producto_combo.pk,
                'cantidad': 1,
                'opciones_ids': [str(self.opcion_sprite.pk)],
                'insumos_quitados_ids': [],
            }
        }
        consumo = calcular_consumo_carrito(carrito)
        self.assertIn(self.insumo_sprite.pk, consumo)
        self.assertEqual(consumo[self.insumo_sprite.pk]['cantidad'], Decimal('1.00'))

        pedido = Pedido.objects.create(
            idcliente=self.cliente,
            idmediopago=self.medio_pago,
            idestadopedido=self.estado_pendiente,
            total=Decimal('5000.00'),
        )

        ok, msg = descontar_stock_pedido(pedido, consumo)
        self.assertTrue(ok)

        self.insumo_sprite.refresh_from_db()
        self.assertEqual(self.insumo_sprite.stockactual, Decimal('19.00'))

        # Insumo de la receta también se descuenta
        self.insumo_pan.refresh_from_db()
        self.assertEqual(self.insumo_pan.stockactual, Decimal('49.00'))

    def test_02_cliente_selecciona_cocacola_no_modifica_sprite(self):
        """Escenario 2: Un cliente selecciona una Coca-Cola: se descuenta Coca-Cola y no se modifica Sprite."""
        stock_inicial_sprite = self.insumo_sprite.stockactual

        carrito = {
            'item_1': {
                'producto_id': self.producto_combo.pk,
                'cantidad': 1,
                'opciones_ids': [str(self.opcion_cocacola.pk)],
                'insumos_quitados_ids': [],
            }
        }
        consumo = calcular_consumo_carrito(carrito)
        self.assertIn(self.insumo_cocacola.pk, consumo)
        self.assertNotIn(self.insumo_sprite.pk, consumo)

        pedido = Pedido.objects.create(
            idcliente=self.cliente,
            idmediopago=self.medio_pago,
            idestadopedido=self.estado_pendiente,
            total=Decimal('5000.00'),
        )

        descontar_stock_pedido(pedido, consumo)

        self.insumo_cocacola.refresh_from_db()
        self.insumo_sprite.refresh_from_db()
        self.assertEqual(self.insumo_cocacola.stockactual, Decimal('19.00'))
        self.assertEqual(self.insumo_sprite.stockactual, stock_inicial_sprite)

    def test_03_pedido_contiene_varias_unidades_respeta_cantidades(self):
        """Escenario 3: Un pedido contiene varias unidades (ej: 2 combos con Sprite): descuenta 2 unidades."""
        carrito = {
            'item_1': {
                'producto_id': self.producto_combo.pk,
                'cantidad': 2,
                'opciones_ids': [str(self.opcion_sprite.pk)],
                'insumos_quitados_ids': [],
            }
        }
        consumo = calcular_consumo_carrito(carrito)
        self.assertEqual(consumo[self.insumo_sprite.pk]['cantidad'], Decimal('2.00'))
        self.assertEqual(consumo[self.insumo_pan.pk]['cantidad'], Decimal('2.00'))

        pedido = Pedido.objects.create(
            idcliente=self.cliente,
            idmediopago=self.medio_pago,
            idestadopedido=self.estado_pendiente,
            total=Decimal('10000.00'),
        )

        descontar_stock_pedido(pedido, consumo)

        self.insumo_sprite.refresh_from_db()
        self.insumo_pan.refresh_from_db()
        self.assertEqual(self.insumo_sprite.stockactual, Decimal('18.00'))
        self.assertEqual(self.insumo_pan.stockactual, Decimal('48.00'))

    def test_04_pedido_procesado_nuevamente_no_duplica_descuento(self):
        """Escenario 4: Un pedido se procesa nuevamente: no se duplica el descuento (idempotencia)."""
        carrito = {
            'item_1': {
                'producto_id': self.producto_combo.pk,
                'cantidad': 1,
                'opciones_ids': [str(self.opcion_sprite.pk)],
                'insumos_quitados_ids': [],
            }
        }
        consumo = calcular_consumo_carrito(carrito)

        pedido = Pedido.objects.create(
            idcliente=self.cliente,
            idmediopago=self.medio_pago,
            idestadopedido=self.estado_pendiente,
            total=Decimal('5000.00'),
        )

        # Primer descuento
        ok1, _ = descontar_stock_pedido(pedido, consumo)
        self.assertTrue(ok1)
        self.insumo_sprite.refresh_from_db()
        self.assertEqual(self.insumo_sprite.stockactual, Decimal('19.00'))

        # Segundo intento de descuento sobre el mismo pedido
        ok2, msg2 = descontar_stock_pedido(pedido, consumo)
        self.assertFalse(ok2)
        self.insumo_sprite.refresh_from_db()
        # Debe mantenerse en 19.00, NO descontar otra vez a 18.00
        self.assertEqual(self.insumo_sprite.stockactual, Decimal('19.00'))

    def test_05_pedido_cancelado_despues_del_descuento_reintegra_stock_una_sola_vez(self):
        """Escenario 5: Un pedido se cancela después del descuento: el stock se reintegra una sola vez."""
        carrito = {
            'item_1': {
                'producto_id': self.producto_combo.pk,
                'cantidad': 1,
                'opciones_ids': [str(self.opcion_sprite.pk)],
                'insumos_quitados_ids': [],
            }
        }
        consumo = calcular_consumo_carrito(carrito)

        pedido = Pedido.objects.create(
            idcliente=self.cliente,
            idmediopago=self.medio_pago,
            idestadopedido=self.estado_pendiente,
            total=Decimal('5000.00'),
        )
        descontar_stock_pedido(pedido, consumo)

        self.insumo_sprite.refresh_from_db()
        self.assertEqual(self.insumo_sprite.stockactual, Decimal('19.00'))

        # Cancelación y primer reintegro
        ok_reintegro, _ = reintegrar_stock_pedido(pedido, motivo='Cliente canceló por WhatsApp')
        self.assertTrue(ok_reintegro)
        self.insumo_sprite.refresh_from_db()
        self.assertEqual(self.insumo_sprite.stockactual, Decimal('20.00'))

        # Segundo intento de cancelación o actualización de estado
        ok_reintegro2, _ = reintegrar_stock_pedido(pedido, motivo='Reintento')
        self.assertFalse(ok_reintegro2)
        self.insumo_sprite.refresh_from_db()
        # Debe permanecer en 20.00, sin duplicar reintegros a 21.00
        self.assertEqual(self.insumo_sprite.stockactual, Decimal('20.00'))

    def test_06_articulo_no_tiene_stock_suficiente_aplica_validacion(self):
        """Escenario 6: Un artículo no tiene stock suficiente: el sistema aplica la regla de validación."""
        self.insumo_sprite.stockactual = Decimal('0.00')
        self.insumo_sprite.save()

        carrito = {
            'item_1': {
                'producto_id': self.producto_combo.pk,
                'cantidad': 1,
                'opciones_ids': [str(self.opcion_sprite.pk)],
                'insumos_quitados_ids': [],
            }
        }
        consumo = calcular_consumo_carrito(carrito)

        # Validación previa informa error
        valido, errores = verificar_stock_disponible(consumo)
        self.assertFalse(valido)
        self.assertTrue(any('Stock insuficiente de Sprite' in e for e in errores))

        # Intento de descuento lanza StockInsuficienteError
        pedido = Pedido.objects.create(
            idcliente=self.cliente,
            idmediopago=self.medio_pago,
            idestadopedido=self.estado_pendiente,
            total=Decimal('5000.00'),
        )
        with self.assertRaises(StockInsuficienteError):
            descontar_stock_pedido(pedido, consumo)

    def test_07_producto_varias_opciones_solo_descuenta_opcion_seleccionada(self):
        """Escenario 7: Un producto tiene varias opciones posibles: solamente se descuenta la opción seleccionada."""
        carrito = {
            'item_1': {
                'producto_id': self.producto_combo.pk,
                'cantidad': 1,
                'opciones_ids': [str(self.opcion_fanta.pk)],
                'insumos_quitados_ids': [],
            }
        }
        consumo = calcular_consumo_carrito(carrito)

        pedido = Pedido.objects.create(
            idcliente=self.cliente,
            idmediopago=self.medio_pago,
            idestadopedido=self.estado_pendiente,
            total=Decimal('5000.00'),
        )
        descontar_stock_pedido(pedido, consumo)

        self.insumo_fanta.refresh_from_db()
        self.insumo_sprite.refresh_from_db()
        self.insumo_cocacola.refresh_from_db()

        self.assertEqual(self.insumo_fanta.stockactual, Decimal('19.00'))
        self.assertEqual(self.insumo_sprite.stockactual, Decimal('20.00'))
        self.assertEqual(self.insumo_cocacola.stockactual, Decimal('20.00'))

    def test_08_opcion_no_vinculada_a_insumo_no_realiza_descuentos_incorrectos(self):
        """Escenario 8: Una opción no está vinculada con ningún insumo de stock: no realiza descuentos incorrectos."""
        carrito = {
            'item_1': {
                'producto_id': self.producto_combo.pk,
                'cantidad': 1,
                'opciones_ids': [str(self.opcion_sin_insumo.pk)],
                'insumos_quitados_ids': [],
            }
        }
        consumo = calcular_consumo_carrito(carrito)

        # Solo debe descontar el pan de la hamburguesa, ninguna bebida
        self.assertIn(self.insumo_pan.pk, consumo)
        self.assertNotIn(self.insumo_sprite.pk, consumo)
        self.assertNotIn(self.insumo_cocacola.pk, consumo)
        self.assertNotIn(self.insumo_fanta.pk, consumo)

        pedido = Pedido.objects.create(
            idcliente=self.cliente,
            idmediopago=self.medio_pago,
            idestadopedido=self.estado_pendiente,
            total=Decimal('5000.00'),
        )
        descontar_stock_pedido(pedido, consumo)

        self.insumo_sprite.refresh_from_db()
        self.insumo_cocacola.refresh_from_db()
        self.insumo_fanta.refresh_from_db()
        self.assertEqual(self.insumo_sprite.stockactual, Decimal('20.00'))
        self.assertEqual(self.insumo_cocacola.stockactual, Decimal('20.00'))
        self.assertEqual(self.insumo_fanta.stockactual, Decimal('20.00'))


class TogglePagadoSeguridadTestCase(TestCase):
    def setUp(self):
        self.rol_admin = Rol.objects.create(nombrerol='Administrador')
        self.empleado = Empleado.objects.create(
            nombre='Admin',
            apellido='Test',
            correo='admin@zonaburger.com',
            contrasena=make_password('Password123!'),
            activo=True,
            idrol=self.rol_admin,
        )
        self.estado_pedido = EstadoPedido.objects.create(descripcion='Pendiente')
        self.cliente = Cliente.objects.create(nombre='Juan', apellido='Perez', telefono='12345678')
        self.medio_pago = MedioPago.objects.create(nombremetodo='Efectivo')
        self.pedido = Pedido.objects.create(
            idcliente=self.cliente,
            idestadopedido=self.estado_pedido,
            idmediopago=self.medio_pago,
            total=Decimal('1000.00'),
            pagado=False,
        )
        self.url = reverse('toggle_pagado', kwargs={'idpedido': self.pedido.idpedido})

    def test_get_retorna_405_y_no_cambia_pagado(self):
        self.client.force_login(self.empleado)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 405)
        self.pedido.refresh_from_db()
        self.assertFalse(self.pedido.pagado)

    def test_post_con_permisos_conmuta_pagado(self):
        self.client.force_login(self.empleado)
        response = self.client.post(self.url)
        self.assertIn(response.status_code, [200, 302])
        self.pedido.refresh_from_db()
        self.assertTrue(self.pedido.pagado)

    def test_post_sin_csrf_retorna_403_y_no_cambia_pagado(self):
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.empleado)
        response = csrf_client.post(self.url)
        self.assertEqual(response.status_code, 403)
        self.pedido.refresh_from_db()
        self.assertFalse(self.pedido.pagado)

    def test_reproducir_def_032(self):
        EstadoPedido.objects.get_or_create(pk=1, defaults={'descripcion': 'Pendiente'})
        insumo_1 = Insumo.objects.create(
            codigo='INS-TEST-1', nombreinsumo='Carne',
            unidadmedidaingreso='unidades', unidadmedidaegreso='unidades',
            stockactual=Decimal('10.00'), stockminimo=Decimal('2.00'),
            descontar_stock_automaticamente=True,
        )
        insumo_2 = Insumo.objects.create(
            codigo='INS-TEST-2', nombreinsumo='Cebolla',
            unidadmedidaingreso='unidades', unidadmedidaegreso='unidades',
            stockactual=Decimal('10.00'), stockminimo=Decimal('2.00'),
            descontar_stock_automaticamente=True,
        )
        categoria = CategoriaProducto.objects.create(nombre='Burgers Test')
        producto = Producto.objects.create(
            nombre='Burger Test', precio=Decimal('1000.00'), idcategoria=categoria,
        )
        receta = Receta.objects.create(idproducto=producto)
        RecetaInsumo.objects.create(
            idreceta=receta, idinsumo=insumo_1,
            cantidadinsumo=Decimal('1.00'), unidadmedida='unidades', es_removible=False,
        )
        RecetaInsumo.objects.create(
            idreceta=receta, idinsumo=insumo_2,
            cantidadinsumo=Decimal('1.00'), unidadmedida='unidades', es_removible=True,
        )

        url_agregar = reverse('agregar_al_carrito', kwargs={'idproducto': producto.idproducto})
        resp_add = self.client.post(url_agregar, {
            'cantidad': '1',
            f'sin_insumo_{insumo_2.idinsumo}': str(insumo_2.idinsumo),
        })
        self.assertEqual(resp_add.status_code, 302)

        url_checkout = reverse('procesar_checkout')
        resp_checkout = self.client.post(url_checkout, {
            'nombre': 'Juan',
            'apellido': 'Perez',
            'telefono': '1123456789',
            'calle': 'Calle Falsa',
            'numero': '123',
            'localidad': 'Capital',
            'medio_pago': self.medio_pago.pk,
            'comentario': '',
            'codigo_promocion': '',
        })
        if resp_checkout.status_code == 500:
            print('ERROR 500 CONTENT:', resp_checkout.content.decode('utf-8', errors='ignore')[:1000])
        self.assertIn(resp_checkout.status_code, [200, 302])


