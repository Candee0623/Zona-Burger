import secrets
from datetime import time
from decimal import Decimal

from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand, CommandError
from django.core.management.color import no_style
from django.db import connection, transaction

from core.models import (
    Empleado,
    EstadoNegocio,
    EstadoPedido,
    EstadoProducto,
    Horario,
    MedioPago,
    Negocio,
    RedesSociales,
    Rol,
    ZonasEntrega,
)

NEGOCIO_NOMBRE = "Zona Burger"
NEGOCIO_TELEFONO = "+54 9 11 5261-7656"
INSTAGRAM_URL = "https://www.instagram.com/zonaburgerrr/"

ADMINISTRADORES = [
    ("Mathias", "Valdez", "Mathiasvaldez732@gmail.com"),
    ("Luciana", "Garcete", "garceteluciana07@gmail.com"),
]

# (día, abierto, apertura, cierre)
HORARIOS = [
    ("Lunes", 1, time(20, 0), time(23, 30)),
    ("Martes", 0, None, None),
    ("Miércoles", 0, None, None),
    ("Jueves", 0, None, None),
    ("Viernes", 1, time(20, 0), time(23, 30)),
    ("Sábado", 1, time(20, 0), time(23, 30)),
    ("Domingo", 1, time(20, 0), time(23, 30)),
]

ZONAS = [("Piedrabuena", Decimal("0.00"))]


class Command(BaseCommand):
    help = (
        "Carga los datos iniciales de Zona Burger en una base PostgreSQL vacía "
        "(estados, medios de pago, negocio, horarios, zona, rol y administradores). "
        "Se puede ejecutar más de una vez sin duplicar datos."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--password",
            help="Contraseña inicial para los administradores nuevos. "
                 "Si no se indica, se genera una distinta para cada uno.",
        )

    def handle(self, *args, **options):
        if connection.vendor != "postgresql":
            raise CommandError(
                f"Este comando está pensado para PostgreSQL (base actual: {connection.vendor})."
            )

        try:
            with transaction.atomic():
                self.stdout.write("Cargando datos iniciales de Zona Burger...")
                self.cargar_estados_producto()
                self.cargar_estados_pedido()
                self.cargar_estados_negocio()
                self.cargar_medios_pago()
                self.cargar_rol_administrador()
                negocio = self.cargar_negocio()
                self.cargar_zonas_entrega(negocio)
                self.cargar_horarios(negocio)
                self.cargar_instagram(negocio)
                credenciales = self.cargar_administradores(options.get("password"))
                self.reiniciar_secuencias()
        except CommandError:
            raise
        except Exception as e:
            raise CommandError(f"No se pudieron cargar los datos iniciales: {e}")

        # Permisos del sistema (se asignan al rol Administrador).
        from core.permisos_config import sincronizar_permisos
        resultado = sincronizar_permisos()
        self.stdout.write(f"  - Permisos sincronizados: {resultado['total']} en total.")

        self.stdout.write(self.style.SUCCESS("\nDatos iniciales cargados correctamente."))

        if credenciales:
            self.stdout.write(self.style.WARNING(
                "\nContraseñas iniciales (se muestran una sola vez; cada administrador "
                "debe cambiarla al ingresar o usar 'Recuperar contraseña'):"
            ))
            for correo, clave in credenciales:
                self.stdout.write(f"  {correo}  ->  {clave}")

    # ---------- catálogos ----------

    def cargar_estados_producto(self):
        # La aplicación usa estos IDs fijos: 1 = Activo, 2 = Oculto, 3 = Eliminado.
        self.stdout.write("  - Estados de producto...")
        for idestado, descripcion in {1: "Activo", 2: "Oculto", 3: "Eliminado"}.items():
            estado, _ = EstadoProducto.objects.get_or_create(
                idestado=idestado, defaults={"descripcion": descripcion}
            )
            if estado.descripcion != descripcion:
                raise CommandError(
                    f"EstadoProducto {idestado} existe como '{estado.descripcion}' "
                    f"y debería ser '{descripcion}'. Revisá la tabla."
                )

    def cargar_estados_pedido(self):
        self.stdout.write("  - Estados de pedido...")
        for descripcion in ["Pendiente", "En Preparación", "En proceso",
                            "Enviado", "Entregado", "Cancelado"]:
            EstadoPedido.objects.get_or_create(descripcion=descripcion)

    def cargar_estados_negocio(self):
        # Modos del local usados por el botón abrir / cerrar / automático.
        self.stdout.write("  - Estados del local...")
        for descripcion in ["Automático", "Abierto manual", "Cerrado manual"]:
            EstadoNegocio.objects.get_or_create(descripcion=descripcion)

    def cargar_medios_pago(self):
        self.stdout.write("  - Medios de pago...")
        for nombre in ["Efectivo", "Transferencia"]:
            MedioPago.objects.get_or_create(nombremetodo=nombre)

    def cargar_rol_administrador(self):
        self.stdout.write("  - Rol Administrador...")
        if not Rol.objects.filter(nombrerol__iexact="Administrador").exists():
            Rol.objects.create(nombrerol="Administrador")

    # ---------- negocio ----------

    def cargar_negocio(self):
        self.stdout.write("  - Negocio...")
        negocio = Negocio.objects.first()
        automatico = EstadoNegocio.objects.get(descripcion="Automático")
        if negocio is None:
            return Negocio.objects.create(
                nombre=NEGOCIO_NOMBRE, telefono=NEGOCIO_TELEFONO, idestado=automatico
            )
        negocio.nombre = NEGOCIO_NOMBRE
        negocio.telefono = NEGOCIO_TELEFONO
        if negocio.idestado is None:
            negocio.idestado = automatico
        negocio.save()
        return negocio

    def cargar_zonas_entrega(self, negocio):
        self.stdout.write("  - Zona de entrega...")
        for nombre, costo in ZONAS:
            zona, creada = ZonasEntrega.objects.get_or_create(
                nombre=nombre,
                defaults={"costoenvio": costo, "idnegocio": negocio.idnegocio},
            )
            if not creada and zona.idnegocio != negocio.idnegocio:
                zona.idnegocio = negocio.idnegocio
                zona.save(update_fields=["idnegocio"])
        if negocio.idzona_id is None:
            negocio.idzona = ZonasEntrega.objects.get(nombre=ZONAS[0][0])
            negocio.save(update_fields=["idzona"])

    def cargar_horarios(self, negocio):
        self.stdout.write("  - Horarios...")
        for dia, abierto, apertura, cierre in HORARIOS:
            Horario.objects.get_or_create(
                idnegocio=negocio,
                diasemana=dia,
                defaults={
                    "estaabierto": abierto,
                    "horaapertura": apertura,
                    "horacierre": cierre,
                },
            )

    def cargar_instagram(self, negocio):
        self.stdout.write("  - Instagram...")
        red = RedesSociales.objects.filter(plataforma__iexact="Instagram").first()
        if red is None:
            red = RedesSociales.objects.create(
                plataforma="Instagram", enlace=INSTAGRAM_URL, idnegocio=negocio.idnegocio
            )
        else:
            red.enlace = INSTAGRAM_URL
            red.idnegocio = negocio.idnegocio
            red.save(update_fields=["enlace", "idnegocio"])
        if negocio.idredsocial_id != red.idredsocial:
            negocio.idredsocial = red
            negocio.save(update_fields=["idredsocial"])

    def cargar_administradores(self, password_fija):
        self.stdout.write("  - Administradores...")
        rol = Rol.objects.get(nombrerol__iexact="Administrador")
        credenciales = []
        for nombre, apellido, correo in ADMINISTRADORES:
            if Empleado.objects.filter(correo__iexact=correo).exists():
                continue
            clave = password_fija or secrets.token_urlsafe(9)
            Empleado.objects.create(
                nombre=nombre,
                apellido=apellido,
                correo=correo,
                contrasena=make_password(clave),
                idrol=rol,
                activo=True,
            )
            credenciales.append((correo, clave))
        return credenciales

    def reiniciar_secuencias(self):
        # Se insertaron IDs fijos (estados de producto): se alinea la secuencia
        # para que los próximos registros no choquen.
        modelos = [EstadoProducto]
        with connection.cursor() as cursor:
            for sql in connection.ops.sequence_reset_sql(no_style(), modelos):
                cursor.execute(sql)