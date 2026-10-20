from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from core.models import (
    Cliente,
    Direccion,
    EstadoPedido,
    MedioPago,
    Negocio,
    Pedido,
    Producto,
    CategoriaProducto,
    EstadoProducto,
    EstadoStock,
    ZonasEntrega,
)
from core.geo_zonas import (
    detectar_zona_entrega,
    normalizar_texto,
    texto_sin_espacios,
    calcular_distancia_km,
)


class GeoZonasTestCase(TestCase):
    def setUp(self):
        # Configurar Negocio
        self.negocio = Negocio.objects.create(
            nombre="Zona Burger",
            telefono="1152617656"
        )

        # Configurar Zonas de Entrega
        self.zona_piedrabuena = ZonasEntrega.objects.create(
            nombre="PiedraBuena",
            costoenvio=Decimal("100.00"),
            idnegocio=self.negocio.idnegocio
        )
        self.zona_pirelli = ZonasEntrega.objects.create(
            nombre="Pirelli",
            costoenvio=Decimal("0.00"),
            idnegocio=self.negocio.idnegocio
        )
        self.zona_perales = ZonasEntrega.objects.create(
            nombre="Los Perales",
            costoenvio=Decimal("0.00"),
            idnegocio=self.negocio.idnegocio
        )
        self.zona_oculta = ZonasEntrega.objects.create(
            nombre="La Oculta",
            costoenvio=Decimal("0.00"),
            idnegocio=self.negocio.idnegocio
        )

        self.medio_pago = MedioPago.objects.create(nombremetodo="Efectivo")
        self.estado_pedido = EstadoPedido.objects.create(descripcion="Pendiente")

        self.client = Client()

    def test_01_normalizacion_ignora_mayusculas_minusculas_espacios_y_tildes(self):
        """Verifica que la normalización sea insensible a mayúsculas, minúsculas, espacios y acentos."""
        self.assertEqual(normalizar_texto("  PIEDRABUENA  "), "piedrabuena")
        self.assertEqual(normalizar_texto("Piedra Buena"), "piedra buena")
        self.assertEqual(texto_sin_espacios("  p  i  e  d  r  a  b  u  e  n  a  "), "piedrabuena")
        self.assertEqual(texto_sin_espacios("Pirelli"), "pirelli")
        self.assertEqual(texto_sin_espacios("P I R E L L I"), "pirelli")
        self.assertEqual(normalizar_texto("Bárrio Piedrabuena"), "barrio piedrabuena")

    def test_02_detectar_por_coordenadas_zona_con_tarifa_piedrabuena(self):
        """Si la dirección del cliente está en Piedrabuena, detecta la tarifa de $100.00 y no es gratis."""
        # Goleta Santa Cruz 6850 (Villa Lugano / Piedrabuena)
        lat = -34.6791577
        lon = -58.4918399
        res = detectar_zona_entrega(lat=lat, lon=lon)

        self.assertTrue(res['cobertura'])
        self.assertFalse(res['es_a_coordinar'])
        self.assertFalse(res['es_gratis'])
        self.assertEqual(res['idzona'], self.zona_piedrabuena.idzona)
        self.assertEqual(res['nombre'], "PiedraBuena")
        self.assertEqual(res['costoenvio'], Decimal("100.00"))
        self.assertEqual(res['costoenvio_texto'], "$100.00")

    def test_03_detectar_por_coordenadas_zona_envio_gratis_pirelli(self):
        """Si la dirección está en Pirelli / Savio, detecta envío gratis ($0.00) y suma 0."""
        # Soldado de la Frontera 5000 (Lugano 1 y 2 / Pirelli)
        lat = -34.6872093
        lon = -58.4620085
        res = detectar_zona_entrega(lat=lat, lon=lon)

        self.assertTrue(res['cobertura'])
        self.assertFalse(res['es_a_coordinar'])
        self.assertTrue(res['es_gratis'])
        self.assertEqual(res['idzona'], self.zona_pirelli.idzona)
        self.assertEqual(res['nombre'], "Pirelli")
        self.assertEqual(res['costoenvio'], Decimal("0.00"))
        self.assertEqual(res['costoenvio_texto'], "Envío gratis")

    def test_04_detectar_por_coordenadas_montiel_pirelli(self):
        """Montiel 5200 se ubica en el radio de Pirelli/Savio y se clasifica geográficamente sin depender de la palabra del cliente."""
        lat = -34.6887957
        lon = -58.4769161
        res = detectar_zona_entrega(lat=lat, lon=lon)

        self.assertTrue(res['cobertura'])
        self.assertEqual(res['idzona'], self.zona_pirelli.idzona)
        self.assertTrue(res['es_gratis'])

    def test_05_detectar_lejos_o_fuera_de_cobertura_envio_a_coordinar(self):
        """Si la dirección está lejos (ej. Obelisco a 13km), muestra Envío a coordinar y costo 0."""
        # Obelisco
        lat = -34.6037
        lon = -58.3816
        res = detectar_zona_entrega(lat=lat, lon=lon)

        self.assertFalse(res['cobertura'])
        self.assertTrue(res['es_a_coordinar'])
        self.assertEqual(res['costoenvio'], Decimal("0.00"))
        self.assertEqual(res['costoenvio_texto'], "A coordinar")
        self.assertEqual(res['localidad_guardar'], "A coordinar con el vendedor")

    def test_06_detectar_por_calle_emblematica_sin_escribir_barrio(self):
        """Si el cliente ingresa solo calle y altura sin nombrar el barrio, el sistema identifica la zona cubierta."""
        res = detectar_zona_entrega(calle="Goleta Santa Cruz", numero="6850")
        self.assertTrue(res['cobertura'])
        self.assertEqual(res['idzona'], self.zona_piedrabuena.idzona)
        self.assertEqual(res['costoenvio'], Decimal("100.00"))

    def test_07_detectar_variaciones_de_texto_con_espacios_y_mayusculas(self):
        """Detecta la zona ignorando mayúsculas, minúsculas, espacios y tildes en el nombre de la localidad."""
        res1 = detectar_zona_entrega(localidad="  p i e d r a b u e n a  ")
        self.assertEqual(res1['idzona'], self.zona_piedrabuena.idzona)

        res2 = detectar_zona_entrega(localidad="BARRIO PIRELLI")
        self.assertEqual(res2['idzona'], self.zona_pirelli.idzona)

        res3 = detectar_zona_entrega(localidad="los perales")
        self.assertEqual(res3['idzona'], self.zona_perales.idzona)

    def test_08_api_detectar_zona_endpoint(self):
        """Prueba el endpoint /api/detectar-zona/ retornando JSON completo."""
        response = self.client.get(
            reverse('api_detectar_zona'),
            {'lat': '-34.6791577', 'lon': '-58.4918399'}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['status'], 'success')
        self.assertTrue(data['cobertura'])
        self.assertEqual(data['nombre_zona'], 'PiedraBuena')
        self.assertEqual(data['costo_envio'], 100.0)
        self.assertFalse(data['es_gratis'])

    def test_09_api_detectar_zona_fuera_de_cobertura(self):
        """Prueba el endpoint /api/detectar-zona/ para una coordenada lejana."""
        response = self.client.get(
            reverse('api_detectar_zona'),
            {'lat': '-34.6037', 'lon': '-58.3816'}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['status'], 'success')
        self.assertFalse(data['cobertura'])
        self.assertTrue(data['es_a_coordinar'])
        self.assertEqual(data['costo_envio_texto'], 'A coordinar')

    def test_10_checkout_get_render(self):
        """Verifica que la vista GET /checkout/ renderice correctamente con código 200 sin errores de template."""
        response = self.client.get(reverse('procesar_checkout'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="coord_lat"')
        self.assertContains(response, 'id="coord_lng"')
        self.assertContains(response, 'id="zona-status-banner"')
