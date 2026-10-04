from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from core.models import (
    EstadoProducto,
    EstadoPedido,
    MedioPago,
    Negocio,
    ZonasEntrega,
)


class Command(BaseCommand):
    help = "Carga los datos iniciales necesarios para Zona-Burger."

    def handle(self, *args, **options):
        try:
            with transaction.atomic():
                self.stdout.write("Cargando datos iniciales de Zona-Burger...")

                self.cargar_estados_producto()
                self.cargar_estados_pedido()
                self.cargar_medios_pago()
                negocio = self.cargar_negocio()
                self.cargar_zonas_entrega(negocio)

            self.stdout.write(
                self.style.SUCCESS(
                    "\nDatos iniciales cargados correctamente."
                )
            )

        except Exception as e:
            raise CommandError(
                f"No se pudieron cargar los datos iniciales: {e}"
            )

    def cargar_estados_producto(self):
        """
        La aplicación utiliza los IDs:
        1 = Activo
        2 = Oculto
        3 = Eliminado

        SQL Server utiliza IDENTITY, por lo que se habilita
        temporalmente IDENTITY_INSERT para garantizar esos IDs.
        """

        estados = {
            1: "Activo",
            2: "Oculto",
            3: "Eliminado",
        }

        self.stdout.write("  - Verificando estados de producto...")

        with connection.cursor() as cursor:
            tabla = EstadoProducto._meta.db_table

            try:
                cursor.execute(
                    f"SET IDENTITY_INSERT [{tabla}] ON"
                )

                for idestado, descripcion in estados.items():
                    cursor.execute(
                        f"""
                        IF NOT EXISTS (
                            SELECT 1
                            FROM [{tabla}]
                            WHERE [IdEstado] = %s
                        )
                        BEGIN
                            INSERT INTO [{tabla}]
                                ([IdEstado], [Descripcion])
                            VALUES
                                (%s, %s)
                        END
                        """,
                        [idestado, idestado, descripcion],
                    )

                cursor.execute(
                    f"SET IDENTITY_INSERT [{tabla}] OFF"
                )

            except Exception:
                try:
                    cursor.execute(
                        f"SET IDENTITY_INSERT [{tabla}] OFF"
                    )
                except Exception:
                    pass

                raise

        for idestado, descripcion in estados.items():
            estado = EstadoProducto.objects.get(idestado=idestado)

            if estado.descripcion != descripcion:
                raise CommandError(
                    f"El EstadoProducto con ID {idestado} ya existe "
                    f"pero tiene la descripción '{estado.descripcion}' "
                    f"en lugar de '{descripcion}'."
                )

    def cargar_estados_pedido(self):
        estados = [
            "Pendiente",
            "En Preparación",
            "En proceso",
            "Enviado",
            "Entregado",
            "Cancelado",
        ]

        self.stdout.write("  - Verificando estados de pedido...")

        for descripcion in estados:
            EstadoPedido.objects.get_or_create(
                descripcion=descripcion
            )

    def cargar_medios_pago(self):
        medios = [
            "Efectivo",
            "Transferencia",
        ]

        self.stdout.write("  - Verificando medios de pago...")

        for nombre in medios:
            MedioPago.objects.get_or_create(
                nombremetodo=nombre
            )

    def cargar_negocio(self):
        self.stdout.write("  - Verificando negocio...")

        negocio, creado = Negocio.objects.get_or_create(
            nombre="Zona Burger",
            defaults={
                "telefono": "1152617656",
            },
        )

        if not creado and negocio.telefono != "1152617656":
            negocio.telefono = "1152617656"
            negocio.save(update_fields=["telefono"])

        return negocio

    def cargar_zonas_entrega(self, negocio):
        zonas = [
            "Piedra Buena",
            "Pirelli",
            "Los Perales",
            "La Oculta",
        ]

        self.stdout.write("  - Verificando zonas de entrega...")

        for nombre in zonas:
            zona, creado = ZonasEntrega.objects.get_or_create(
                nombre=nombre,
                defaults={
                    "costoenvio": Decimal("0.00"),
                    "idnegocio": negocio.idnegocio,
                },
            )

            if not creado:
                cambios = []

                if zona.idnegocio != negocio.idnegocio:
                    zona.idnegocio = negocio.idnegocio
                    cambios.append("idnegocio")

                if zona.costoenvio is None:
                    zona.costoenvio = Decimal("0.00")
                    cambios.append("costoenvio")

                if cambios:
                    zona.save(update_fields=cambios)