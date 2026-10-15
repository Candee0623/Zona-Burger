from core.models import Permiso, Rol, RolPermiso


PERMISOS_SISTEMA = [
    # Pedidos
    {
        "codigo": "pedidos.ver",
        "modulo": "Pedidos",
        "accion": "Ver",
        "descripcion": "Consultar pedidos e historial de ventas",
    },
    {
        "codigo": "pedidos.cambiar_estado",
        "modulo": "Pedidos",
        "accion": "Cambiar estado",
        "descripcion": "Modificar el estado de un pedido (preparación, enviado, cancelado, etc.)",
    },
    {
        "codigo": "pedidos.marcar_pagado",
        "modulo": "Pedidos",
        "accion": "Marcar pago",
        "descripcion": "Cambiar el estado de pago del pedido",
    },
    {
        "codigo": "pedidos.imprimir",
        "modulo": "Pedidos",
        "accion": "Imprimir ticket",
        "descripcion": "Generar e imprimir tickets de pedidos",
    },

    # Menú y Productos
    {
        "codigo": "productos.ver",
        "modulo": "Productos",
        "accion": "Ver",
        "descripcion": "Consultar lista de productos del menú",
    },
    {
        "codigo": "productos.crear",
        "modulo": "Productos",
        "accion": "Crear",
        "descripcion": "Crear nuevos productos en el menú",
    },
    {
        "codigo": "productos.editar",
        "modulo": "Productos",
        "accion": "Editar",
        "descripcion": "Modificar datos y precios de productos",
    },
    {
        "codigo": "productos.eliminar",
        "modulo": "Productos",
        "accion": "Eliminar",
        "descripcion": "Eliminar productos del menú",
    },
    {
        "codigo": "recetas.administrar",
        "modulo": "Productos",
        "accion": "Gestionar recetas",
        "descripcion": "Asignar insumos y cantidades a las recetas de productos",
    },

    # Categorías
    {
        "codigo": "categorias.ver",
        "modulo": "Categorías",
        "accion": "Ver",
        "descripcion": "Consultar categorías de productos",
    },
    {
        "codigo": "categorias.crear",
        "modulo": "Categorías",
        "accion": "Crear",
        "descripcion": "Crear nuevas categorías de productos",
    },
    {
        "codigo": "categorias.editar",
        "modulo": "Categorías",
        "accion": "Editar",
        "descripcion": "Editar nombres de categorías",
    },
    {
        "codigo": "categorias.eliminar",
        "modulo": "Categorías",
        "accion": "Eliminar",
        "descripcion": "Eliminar categorías",
    },

    # Opciones
    {
        "codigo": "opciones.ver",
        "modulo": "Opciones",
        "accion": "Ver",
        "descripcion": "Consultar grupos y opciones de personalización",
    },
    {
        "codigo": "opciones.crear",
        "modulo": "Opciones",
        "accion": "Crear",
        "descripcion": "Crear grupos y opciones",
    },
    {
        "codigo": "opciones.editar",
        "modulo": "Opciones",
        "accion": "Editar",
        "descripcion": "Editar grupos y opciones",
    },
    {
        "codigo": "opciones.eliminar",
        "modulo": "Opciones",
        "accion": "Eliminar",
        "descripcion": "Eliminar grupos y opciones",
    },

    # Extras
    {
        "codigo": "extras.ver",
        "modulo": "Extras",
        "accion": "Ver",
        "descripcion": "Consultar extras de productos",
    },
    {
        "codigo": "extras.crear",
        "modulo": "Extras",
        "accion": "Crear",
        "descripcion": "Crear nuevos extras",
    },
    {
        "codigo": "extras.editar",
        "modulo": "Extras",
        "accion": "Editar",
        "descripcion": "Editar extras existentes",
    },
    {
        "codigo": "extras.eliminar",
        "modulo": "Extras",
        "accion": "Eliminar",
        "descripcion": "Eliminar extras",
    },

    # Stock
    {
        "codigo": "stock.ver",
        "modulo": "Stock",
        "accion": "Ver",
        "descripcion": "Consultar insumos y stock actual",
    },
    {
        "codigo": "stock.crear",
        "modulo": "Stock",
        "accion": "Crear insumo",
        "descripcion": "Registrar nuevos insumos en el inventario",
    },
    {
        "codigo": "stock.editar",
        "modulo": "Stock",
        "accion": "Editar insumo",
        "descripcion": "Modificar datos de insumos existentes",
    },
    {
        "codigo": "stock.ajustar",
        "modulo": "Stock",
        "accion": "Ajustar stock",
        "descripcion": "Realizar ajustes manuales en los niveles de stock",
    },
    {
        "codigo": "stock.compras",
        "modulo": "Stock",
        "accion": "Registrar compras",
        "descripcion": "Cargar ingresos de insumos por compras",
    },

    # Reportes
    {
        "codigo": "reportes.ver",
        "modulo": "Reportes",
        "accion": "Ver reportes",
        "descripcion": "Consultar reportes de ventas, productos y recaudación",
    },
    {
        "codigo": "reportes.exportar",
        "modulo": "Reportes",
        "accion": "Exportar",
        "descripcion": "Exportar resúmenes a Excel y PDF",
    },

    # Promociones
    {
        "codigo": "promociones.ver",
        "modulo": "Promociones",
        "accion": "Ver",
        "descripcion": "Consultar promociones y cupones",
    },
    {
        "codigo": "promociones.crear",
        "modulo": "Promociones",
        "accion": "Crear",
        "descripcion": "Crear nuevas promociones",
    },
    {
        "codigo": "promociones.editar",
        "modulo": "Promociones",
        "accion": "Editar",
        "descripcion": "Modificar promociones y cupones",
    },
    {
        "codigo": "promociones.eliminar",
        "modulo": "Promociones",
        "accion": "Eliminar",
        "descripcion": "Eliminar promociones",
    },
    {
        "codigo": "tipos_beneficio.administrar",
        "modulo": "Promociones",
        "accion": "Tipos de beneficio",
        "descripcion": "Crear, editar o eliminar tipos de beneficios promocionales",
    },

    # Negocio (Abrir / Cerrar)
    {
        "codigo": "negocio.ver",
        "modulo": "Negocio",
        "accion": "Ver estado",
        "descripcion": "Consultar el estado de apertura del local y registros de cambio",
    },
    {
        "codigo": "negocio.abrir",
        "modulo": "Negocio",
        "accion": "Abrir local",
        "descripcion": "Abrir el local manualmente fuera de horario",
    },
    {
        "codigo": "negocio.cerrar",
        "modulo": "Negocio",
        "accion": "Cerrar local",
        "descripcion": "Cerrar el local manualmente suspendiendo compras",
    },
    {
        "codigo": "negocio.automatico",
        "modulo": "Negocio",
        "accion": "Modo automático",
        "descripcion": "Restablecer apertura/cierre automático según horarios",
    },

    # Horarios
    {
        "codigo": "horarios.ver",
        "modulo": "Horarios",
        "accion": "Ver",
        "descripcion": "Consultar los horarios de atención cargados",
    },
    {
        "codigo": "horarios.administrar",
        "modulo": "Horarios",
        "accion": "Administrar",
        "descripcion": "Crear, modificar y eliminar horarios de atención",
    },

    # Zonas de Entrega
    {
        "codigo": "zonas.ver",
        "modulo": "Zonas de entrega",
        "accion": "Ver",
        "descripcion": "Consultar zonas y costos de envío",
    },
    {
        "codigo": "zonas.administrar",
        "modulo": "Zonas de entrega",
        "accion": "Administrar",
        "descripcion": "Crear, modificar y eliminar zonas de entrega y tarifas",
    },

    # Usuarios
    {
        "codigo": "usuarios.ver",
        "modulo": "Usuarios",
        "accion": "Ver",
        "descripcion": "Consultar la lista de usuarios del panel",
    },
    {
        "codigo": "usuarios.crear",
        "modulo": "Usuarios",
        "accion": "Crear",
        "descripcion": "Registrar nuevos usuarios en el sistema",
    },
    {
        "codigo": "usuarios.editar",
        "modulo": "Usuarios",
        "accion": "Editar",
        "descripcion": "Modificar datos y credenciales de usuarios",
    },
    {
        "codigo": "usuarios.activar_desactivar",
        "modulo": "Usuarios",
        "accion": "Activar / Desactivar",
        "descripcion": "Habilitar o suspender cuentas de usuario",
    },
    {
        "codigo": "usuarios.eliminar",
        "modulo": "Usuarios",
        "accion": "Eliminar",
        "descripcion": "Eliminar cuentas de usuario",
    },

    # Roles y Permisos
    {
        "codigo": "roles.ver",
        "modulo": "Roles",
        "accion": "Ver",
        "descripcion": "Consultar los roles existentes",
    },
    {
        "codigo": "roles.crear",
        "modulo": "Roles",
        "accion": "Crear",
        "descripcion": "Crear nuevos roles",
    },
    {
        "codigo": "roles.editar",
        "modulo": "Roles",
        "accion": "Editar",
        "descripcion": "Modificar el nombre de roles existentes",
    },
    {
        "codigo": "roles.eliminar",
        "modulo": "Roles",
        "accion": "Eliminar",
        "descripcion": "Eliminar roles que no estén en uso",
    },
    {
        "codigo": "roles.asignar_permisos",
        "modulo": "Roles",
        "accion": "Asignar permisos",
        "descripcion": "Configurar qué acciones puede realizar cada rol",
    },
]


def sincronizar_permisos():
    """
    Sincroniza todos los permisos del catálogo en la base de datos
    y asegura que el rol 'Administrador' tenga todos los permisos asignados.
    """
    permisos_instancias = []
    for datos in PERMISOS_SISTEMA:
        permiso, _ = Permiso.objects.update_or_create(
            codigo=datos["codigo"],
            defaults={
                "modulo": datos["modulo"],
                "accion": datos["accion"],
                "descripcion": datos["descripcion"],
            },
        )
        permisos_instancias.append(permiso)

    # Rol Administrador: asegurar asignación de todos los permisos
    admin_rol = Rol.objects.filter(nombrerol__iexact="Administrador").first()
    if admin_rol:
        for permiso in permisos_instancias:
            RolPermiso.objects.get_or_create(idrol=admin_rol, idpermiso=permiso)
