import random
from datetime import date, datetime, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from core.models import (
    Cliente, Direccion, Pedido, DetallePedido,
    Producto, EstadoPedido, MedioPago,
)

NOMBRES = ["Lucía", "Martín", "Sofía", "Mateo", "Valentina", "Tomás", "Camila", "Nicolás"]
APELLIDOS = ["Gómez", "Rodríguez", "Fernández", "López", "Díaz", "Pérez", "Sosa", "Romero"]
CALLES = ["San Martín", "Belgrano", "Rivadavia", "Sarmiento", "Mitre", "Urquiza"]


class Command(BaseCommand):
    help = "Carga pedidos inventados (históricos) para probar reportes."

    def add_arguments(self, parser):
        parser.add_argument("--cantidad", type=int, default=5)
        parser.add_argument("--desde", type=str, required=True,
                            help="Fecha más antigua, formato AAAA-MM-DD (ej: 2026-08-03)")
        parser.add_argument("--hasta", type=str, default=None,
                            help="Fecha más reciente, AAAA-MM-DD (por defecto: ayer)")

    def handle(self, *args, **opts):
        productos = list(Producto.objects.filter(idestadoproducto_id=1))
        estado = EstadoPedido.objects.filter(descripcion="Entregado").first()
        medios = list(MedioPago.objects.all())

        if not productos or not estado or not medios:
            self.stderr.write("Faltan productos activos, el estado 'Entregado' o medios de pago.")
            return

        desde = date.fromisoformat(opts["desde"])
        hasta = date.fromisoformat(opts["hasta"]) if opts["hasta"] else date.today() - timedelta(days=1)
        if desde > hasta:
            self.stderr.write("--desde no puede ser posterior a --hasta.")
            return
        rango_dias = (hasta - desde).days

        with transaction.atomic():
            for _ in range(opts["cantidad"]):
                cliente = Cliente.objects.create(
                    nombre=random.choice(NOMBRES),
                    apellido=random.choice(APELLIDOS),
                    telefono="11" + str(random.randint(10000000, 99999999)),
                )
                Direccion.objects.create(
                    idcliente=cliente,
                    calle=random.choice(CALLES),
                    numero=str(random.randint(100, 2500)),
                    localidad="Ejemplo",
                )
                pedido = Pedido.objects.create(
                    idcliente=cliente,
                    idmediopago=random.choice(medios),
                    idestadopedido=estado,
                    total=Decimal("0"),
                    pagado=True,
                    stock_descontado=True,  # no toca el stock actual
                )
                total = Decimal("0")
                for prod in random.sample(productos, k=min(len(productos), random.randint(1, 3))):
                    cant = random.randint(1, 3)
                    DetallePedido.objects.create(
                        idpedido=pedido, idproducto=prod,
                        cantidad=cant, preciounitario=prod.precio,
                    )
                    total += prod.precio * cant

                dia = desde + timedelta(days=random.randint(0, rango_dias))
                fecha = timezone.make_aware(datetime(
                    dia.year, dia.month, dia.day,
                    random.randint(19, 23), random.randint(0, 59),
                ))
                # fecha_creacion es auto_now_add: hay que corregirla con update()
                Pedido.objects.filter(pk=pedido.pk).update(total=total, fecha_creacion=fecha)

        self.stdout.write(self.style.SUCCESS(f"Listo: {opts['cantidad']} pedidos de ejemplo creados."))