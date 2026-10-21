from django.core.management.base import BaseCommand
from core.models import Permiso

# código: descripción
PERMISOS = {
    # Pedidos
    'pedidos.ver': 'Ver pedidos y tickets',
    'pedidos.cambiar_estado': 'Cambiar el estado de un pedido',
    'pedidos.marcar_pagado': 'Marcar pedidos como pagados',
    'pedidos.imprimir': 'Imprimir tickets',
    # Historial de pedidos
    'historial.ver': 'Ver el historial de pedidos',
    # Categorías
    'categorias.ver': 'Ver categorías',
    'categorias.crear': 'Crear categorías',
    'categorias.editar': 'Editar categorías',
    'categorias.eliminar': 'Eliminar categorías',
    # Opciones
    'opciones.ver': 'Ver grupos de opciones',
    'opciones.crear': 'Crear grupos de opciones',
    'opciones.editar': 'Editar grupos de opciones',
    'opciones.eliminar': 'Eliminar grupos de opciones',
    # Productos
    'productos.ver': 'Ver productos',
    'productos.crear': 'Crear productos',
    'productos.editar': 'Editar productos',
    'productos.eliminar': 'Eliminar o restaurar productos',
    # Extras
    'extras.ver': 'Ver extras',
    'extras.crear': 'Crear extras',
    'extras.editar': 'Editar extras',
    'extras.eliminar': 'Eliminar extras',
    # Recetas
    'recetas.administrar': 'Administrar recetas',
    # Promociones
    'promociones.ver': 'Ver promociones',
    'promociones.crear': 'Crear promociones',
    'promociones.editar': 'Editar promociones',
    'promociones.eliminar': 'Eliminar promociones',
    'tipos_beneficio.administrar': 'Administrar tipos de beneficio',
    # Stock
    'stock.ver': 'Ver stock, lotes y etiquetas',
    'stock.crear': 'Crear insumos',
    'stock.editar': 'Editar insumos',
    'stock.compras': 'Registrar compras de insumos',
    'stock.ajustar': 'Ajustar stock',
    # Usuarios
    'usuarios.ver': 'Ver usuarios',
    'usuarios.crear': 'Crear usuarios',
    'usuarios.editar': 'Editar usuarios',
    'usuarios.eliminar': 'Eliminar usuarios',
    'usuarios.activar_desactivar': 'Activar o desactivar usuarios',
    # Roles
    'roles.ver': 'Ver roles',
    'roles.crear': 'Crear roles',
    'roles.editar': 'Editar roles y sus permisos',
    'roles.eliminar': 'Eliminar roles',
    # Horarios
    'horarios.ver': 'Ver horarios',
    'horarios.crear': 'Crear horarios',
    'horarios.editar': 'Editar horarios',
    'horarios.eliminar': 'Eliminar horarios',
    # Zonas de entrega
    'zonas.ver': 'Ver zonas de entrega',
    'zonas.crear': 'Crear zonas de entrega',
    'zonas.editar': 'Editar zonas de entrega',
    'zonas.eliminar': 'Eliminar zonas de entrega',
    # Reportes
    'reportes.ver': 'Ver reportes',
    'reportes.exportar': 'Exportar reportes a Excel y PDF',
    # Estado del negocio
    'negocio.ver': 'Ver el estado del negocio',
    'negocio.abrir': 'Abrir el local manualmente',
    'negocio.cerrar': 'Cerrar el local manualmente',
    'negocio.automatico': 'Volver al modo automático del local',
}


class Command(BaseCommand):
    help = 'Crea o actualiza los permisos del sistema.'

    def handle(self, *args, **options):
        creados = 0
        for codigo, descripcion in PERMISOS.items():
            modulo, accion = codigo.split('.', 1)
            _, nuevo = Permiso.objects.update_or_create(
                codigo=codigo,
                defaults={
                    'modulo': modulo,
                    'accion': accion,
                    'descripcion': descripcion,
                },
            )
            creados += nuevo
        self.stdout.write(self.style.SUCCESS(
            f'{creados} permisos nuevos, {len(PERMISOS)} en total.'
        ))