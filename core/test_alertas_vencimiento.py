"""STK-013: alertas de vencimiento próximo y evaluación diaria."""
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.hashers import make_password
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.models import Empleado, Insumo, Rol
from core.permisos_config import sincronizar_permisos
from core.stock_service import registrar_ingreso_lote

BACKEND = 'core.auth_backend.EmpleadoAuthBackend'


class AlertasVencimientoTests(TestCase):
    def setUp(self):
        rol = Rol.objects.create(nombrerol='Administrador')
        sincronizar_permisos()
        self.empleado = Empleado.objects.create(
            nombre='Ana', apellido='Pérez', correo='ana@zonaburger.com',
            contrasena=make_password('ClaveSegura123'), idrol=rol, activo=True,
        )
        self.client.force_login(self.empleado, backend=BACKEND)
        self.insumo = Insumo.objects.create(
            nombreinsumo='Queso', unidadmedidaingreso='kg', unidadmedidaegreso='g',
            stockactual=Decimal('0'),
        )
        self.hoy = timezone.localdate()

    def _alertas(self, fecha=None):
        if fecha is None:
            return self.client.get(reverse('stock_lista'))
        with patch('django.utils.timezone.localdate', return_value=fecha):
            return self.client.get(reverse('stock_lista'))

    def test_sin_lotes_informa_que_no_hay_alertas(self):
        resp = self._alertas()
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(list(resp.context['lotes_por_vencer']), [])
        self.assertContains(resp, 'No hay alertas de vencimiento')

    def test_lote_que_vence_pronto_se_lista_con_datos(self):
        lote = registrar_ingreso_lote(self.insumo, Decimal('2'), self.hoy + timedelta(days=3))
        resp = self._alertas()
        self.assertEqual(list(resp.context['lotes_por_vencer']), [lote])
        self.assertContains(resp, 'Queso')
        self.assertContains(resp, lote.codigo)
        self.assertContains(resp, (self.hoy + timedelta(days=3)).strftime('%d/%m/%Y'))
        self.assertNotContains(resp, 'No hay alertas de vencimiento')

    def test_lote_lejano_no_genera_alerta(self):
        registrar_ingreso_lote(self.insumo, Decimal('2'), self.hoy + timedelta(days=30))
        resp = self._alertas()
        self.assertEqual(list(resp.context['lotes_por_vencer']), [])
        self.assertContains(resp, 'No hay alertas de vencimiento')

    def test_limite_de_7_dias(self):
        dentro = registrar_ingreso_lote(self.insumo, Decimal('1'), self.hoy + timedelta(days=7))
        registrar_ingreso_lote(self.insumo, Decimal('1'), self.hoy + timedelta(days=8))
        self.assertEqual(list(self._alertas().context['lotes_por_vencer']), [dentro])

    def test_recalculo_al_avanzar_la_fecha_un_dia(self):
        # Vence en 8 días: hoy no alerta, mañana sí (queda a 7 días).
        lote = registrar_ingreso_lote(self.insumo, Decimal('1'), self.hoy + timedelta(days=8))
        self.assertEqual(list(self._alertas().context['lotes_por_vencer']), [])
        manana = self.hoy + timedelta(days=1)
        self.assertEqual(list(self._alertas(manana).context['lotes_por_vencer']), [lote])

    def test_al_vencer_pasa_a_vencidos_y_sale_de_proximos(self):
        lote = registrar_ingreso_lote(self.insumo, Decimal('1'), self.hoy)
        self.assertEqual(list(self._alertas().context['lotes_por_vencer']), [lote])
        resp = self._alertas(self.hoy + timedelta(days=1))
        self.assertEqual(list(resp.context['lotes_por_vencer']), [])
        self.assertEqual(list(resp.context['lotes_vencidos']), [lote])

    def test_lote_sin_cantidad_no_alerta(self):
        lote = registrar_ingreso_lote(self.insumo, Decimal('1'), self.hoy + timedelta(days=2))
        lote.cantidadactual = Decimal('0')
        lote.save()
        self.assertEqual(list(self._alertas().context['lotes_por_vencer']), [])

    def test_formulario_de_compra_ofrece_fecha_de_vencimiento(self):
        resp = self.client.get(reverse('registrar_compra_insumo'))
        self.assertContains(resp, 'name="fechavencimiento"')
