from decimal import Decimal
from django.test import TestCase
from .models import (
    Insumo, Producto, CategoriaProducto, EstadoStock, EstadoProducto,
    GrupoOpcion, Opcion, Receta, RecetaInsumo, Cliente, MedioPago,
    EstadoPedido, Pedido, DetallePedido, MovimientoStock
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
