from datetime import timedelta
from decimal import Decimal

from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from .models import (
    DetallePedido, Insumo, Lote, MovimientoStock, Pedido, Producto, Receta,
    RecetaInsumo,
)
from .stock_service import (
    ajustar_stock_insumo, calcular_consumo_carrito, dar_baja_lote,
    descontar_stock_pedido, registrar_ingreso_lote, reintegrar_stock_pedido,
)
from .unidades import factor_conversion


class ConversionUnidadesTests(SimpleTestCase):
    def test_masa_y_volumen(self):
        self.assertEqual(factor_conversion('g', 'kg'), Decimal('0.001'))
        self.assertEqual(factor_conversion('Kilos', 'gramos'), Decimal('1000'))
        self.assertEqual(factor_conversion('ml', 'litro'), Decimal('0.001'))

    def test_no_convertibles(self):
        self.assertIsNone(factor_conversion('bolsa', 'unidad'))
        self.assertIsNone(factor_conversion('kg', 'litro'))


class StockUnidadesYLotesTests(TestCase):
    def setUp(self):
        self.carne = Insumo.objects.create(
            nombreinsumo='Carne', unidadmedidaingreso='kg', unidadmedidaegreso='g',
            stockactual=Decimal('0'), descontar_stock_automaticamente=True,
        )
        self.producto = Producto.objects.create(nombre='Hamburguesa', precio=Decimal('100'))
        receta = Receta.objects.create(idproducto=self.producto)
        RecetaInsumo.objects.create(
            idreceta=receta, idinsumo=self.carne,
            cantidadinsumo=Decimal('150'), unidadmedida='g',
        )
        hoy = timezone.localdate()
        # Lote que vence más tarde (ingresa primero) y lote que vence antes.
        self.lote_tarde = registrar_ingreso_lote(self.carne, Decimal('2'), hoy + timedelta(days=30))
        self.lote_pronto = registrar_ingreso_lote(self.carne, Decimal('1'), hoy + timedelta(days=3))
        self.carne.refresh_from_db()

    def _vender(self, cantidad):
        carrito = {'1': {'producto_id': self.producto.pk, 'cantidad': cantidad}}
        consumo = calcular_consumo_carrito(carrito)
        pedido = Pedido.objects.create(total=Decimal('100'))
        descontar_stock_pedido(pedido, consumo)
        return pedido, consumo

    def test_descuenta_en_kilos_aunque_la_receta_sea_en_gramos(self):
        pedido, consumo = self._vender(2)
        self.assertEqual(consumo[self.carne.pk]['cantidad'], Decimal('0.3000'))
        self.carne.refresh_from_db()
        self.assertEqual(self.carne.stockactual, Decimal('2.7000'))

    def test_descuenta_primero_del_lote_que_vence_antes(self):
        self._vender(2)
        self.lote_pronto.refresh_from_db()
        self.lote_tarde.refresh_from_db()
        self.assertEqual(self.lote_pronto.cantidadactual, Decimal('0.7000'))
        self.assertEqual(self.lote_tarde.cantidadactual, Decimal('2.0000'))

    def test_cancelar_reintegra_al_mismo_lote(self):
        pedido, _ = self._vender(2)
        reintegrar_stock_pedido(pedido)
        self.lote_pronto.refresh_from_db()
        self.carne.refresh_from_db()
        self.assertEqual(self.lote_pronto.cantidadactual, Decimal('1.0000'))
        self.assertEqual(self.carne.stockactual, Decimal('3.0000'))

    def test_ajuste_hacia_arriba_crea_lote_y_hacia_abajo_descuenta(self):
        ajustar_stock_insumo(self.carne.pk, Decimal('4'), 'Conteo', timezone.localdate() + timedelta(days=10))
        self.assertEqual(Lote.objects.filter(idinsumo=self.carne).count(), 3)
        ajustar_stock_insumo(self.carne.pk, Decimal('3.5'), 'Pérdida')
        self.carne.refresh_from_db()
        self.assertEqual(self.carne.stockactual, Decimal('3.5000'))
        total_lotes = sum(l.cantidadactual for l in Lote.objects.filter(idinsumo=self.carne))
        self.assertEqual(total_lotes, Decimal('3.5000'))

    def test_baja_de_lote(self):
        dar_baja_lote(self.lote_pronto.pk, 'Vencido')
        self.carne.refresh_from_db()
        self.assertEqual(self.carne.stockactual, Decimal('2.0000'))
        self.assertTrue(
            MovimientoStock.objects.filter(idlote=self.lote_pronto, tipomovimiento='BAJA_LOTE').exists()
        )

    def test_detalle_pedido_guarda_nombre_del_producto(self):
        pedido = Pedido.objects.create(total=Decimal('100'))
        detalle = DetallePedido.objects.create(
            idpedido=pedido, idproducto=self.producto, cantidad=1, preciounitario=Decimal('100'),
        )
        self.assertEqual(detalle.nombreproducto, 'Hamburguesa')
        DetallePedido.objects.filter(pk=detalle.pk).update(idproducto=None)
        detalle.refresh_from_db()
        self.assertEqual(detalle.nombre_mostrado, 'Hamburguesa')
