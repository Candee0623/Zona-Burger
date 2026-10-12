
from core.models import Permiso


PERMISOS_SISTEMA = [
    # Roles
    {
        "codigo": "roles.ver",
        "modulo": "Roles",
        "accion": "Ver",
        "descripcion": "Consultar los roles",
    },
    {
        "codigo": "roles.crear",
        "modulo": "Roles",
        "accion": "Crear",
        "descripcion": "Crear roles",
    },
    {
        "codigo": "roles.editar",
        "modulo": "Roles",
        "accion": "Editar",
        "descripcion": "Editar roles",
    },
    {
        "codigo": "roles.eliminar",
        "modulo": "Roles",
        "accion": "Eliminar",
        "descripcion": "Eliminar roles",
    },
    {
        "codigo": "roles.asignar_permisos",
        "modulo": "Roles",
        "accion": "Asignar permisos",
        "descripcion": "Asignar permisos a los roles",
    },
]


def sincronizar_permisos():
    for datos in PERMISOS_SISTEMA:
        Permiso.objects.update_or_create(
            codigo=datos["codigo"],
            defaults={
                "modulo": datos["modulo"],
                "accion": datos["accion"],
                "descripcion": datos["descripcion"],
            },
        )
