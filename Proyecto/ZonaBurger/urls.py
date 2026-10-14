
from core import views
from django.contrib import admin
from django.urls import include, path
from core.views import panel_inicio

urlpatterns = [
    # Administración y Librerías de Terceros
    path('admin/', admin.site.urls),
    path('ckeditor5/', include('django_ckeditor_5.urls')),

    # Vistas Públicas / Tienda
    path('', views.index, name='index'),
    path('menu/', views.menu, name='menu'),
    path('menu/actualizaciones/', views.menu_actualizaciones, name='menu_actualizaciones'),
    path('negocio/estado/', views.estado_local_json, name='estado_local_json'),
    path('producto/<int:idproducto>/', views.detalleProducto, name='detalleProducto'),

    # Carrito de Compras
    path('carrito/agregar/<int:idproducto>/', views.agregar_al_carrito, name='agregar_al_carrito'),
    path('carrito/', views.ver_carrito, name='ver_carrito'),
    path('carrito/editar/<str:item_id>/', views.editar_item_carrito, name='editar_item_carrito'),
    path('carrito/actualizar/<str:item_id>/<str:accion>/', views.actualizar_cantidad_carrito, name='actualizar_cantidad_carrito'),
    path('carrito/eliminar/<str:item_id>/', views.eliminar_del_carrito, name='eliminar_del_carrito'),

    # Checkout / Pedidos
    path('checkout/', views.procesar_checkout, name='procesar_checkout'),
    path('pedido-exitoso/', views.pedido_exitoso, name='pedido_exitoso'),
    path('aplicar-promocion/', views.aplicar_promocion, name='aplicar_promocion'),

    # Promociones
    path('panel/promociones/', views.promociones_panel, name='promociones_panel'),
    path('panel/promociones/lista/', views.lista_promociones, name='panel_lista_promociones'),
    path('panel/promociones/crear/', views.crear_promocion, name='panel_crear_promocion'),
    path('panel/promociones/<int:idpromocion>/editar/', views.editar_promocion, name='panel_editar_promocion'),
    path('panel/promociones/<int:idpromocion>/eliminar/', views.eliminar_promocion, name='panel_eliminar_promocion'),

    # Tipos de beneficio
    path('panel/promociones/tipos-beneficio/', views.lista_tipos_beneficio, name='panel_lista_tipos_beneficio'),
    path('panel/promociones/tipos-beneficio/crear/', views.crear_tipo_beneficio, name='panel_crear_tipo_beneficio'),
    path('panel/promociones/tipos-beneficio/<int:pk>/editar/', views.editar_tipo_beneficio, name='panel_editar_tipo_beneficio'),
    path('panel/promociones/tipos-beneficio/<int:pk>/eliminar/', views.eliminar_tipo_beneficio, name='panel_eliminar_tipo_beneficio'),

    # Panel de Administración - Inicio
    path('panel/', panel_inicio, name='panel_inicio'),
    path('pedido/<int:idpedido>/ticket-modal/', views.obtener_ticket_modal, name='obtener_ticket_modal'),
    path('pedido/<int:idpedido>/toggle-pagado/', views.toggle_pagado, name='toggle_pagado'),
    path('pedido/<int:idpedido>/cambiar-estado/', views.actualizar_estado_pedido, name='cambiar_estado'),

    # Historial de pedidos
    path('panel/pedidos/historial/',views.historial_pedidos,name='historial_pedidos'),
    path('panel/pedidos/historial/<int:idpedido>/',views.detalle_historial_pedido,name='detalle_historial_pedido'),

    # Panel - Menú
    path('panel/menu/', views.menu_panel, name='menu_panel'),

    # Menú - Categorías
    path('panel/categorias/', views.categoria_lista, name='categoria_lista'),
    path('panel/categorias/crear/', views.categoria_crear, name='categoria_crear'),
    path('panel/categorias/<int:idcategoria>/editar/', views.categoria_editar, name='categoria_editar'),
    path('panel/categorias/<int:idcategoria>/eliminar/', views.categoria_eliminar, name='categoria_eliminar'),

    # Menú - Opciones
    path('panel/opciones/', views.grupo_lista, name='grupo_lista'),
    path('panel/opciones/crear/', views.grupo_crear, name='grupo_crear'),
    path('panel/opciones/<int:idgrupo>/editar/', views.grupo_editar, name='grupo_editar'),
    path('panel/opciones/<int:idgrupo>/eliminar/', views.grupo_eliminar, name='grupo_eliminar'),

    # Menú - Productos
    path('panel/productos/', views.producto_lista, name='producto_lista'),
    path('panel/productos/crear/', views.producto_crear, name='producto_crear'),
    path('panel/productos/<int:idproducto>/editar/', views.producto_editar, name='producto_editar'),
    path('panel/productos/<int:idproducto>/eliminar/', views.producto_eliminar, name='producto_eliminar'),

    # Menú - Extras
    path('panel/extras/', views.extra_lista, name='extra_lista'),
    path('panel/extras/crear/', views.extra_crear, name='extra_crear'),
    path('panel/extras/<int:idextra>/editar/', views.extra_editar, name='extra_editar'),
    path('panel/extras/<int:idextra>/eliminar/', views.extra_eliminar, name='extra_eliminar'),

    # Stock
    path('panel/stock/', views.stock_lista, name='stock_lista'),
    path('panel/stock/crear/', views.stock_crear, name='stock_crear'),
    path('panel/stock/compras/registrar/', views.registrar_compra_insumo, name='registrar_compra_insumo'),
    path('panel/stock/<int:idinsumo>/ajustar/', views.ajustar_stock, name='ajustar_stock'),
    path('panel/stock/editar/<int:idinsumo>/', views.stock_editar, name='stock_editar'),

    # Recetas - Insumos
    path('panel/receta/insumo/<int:idrecetainsumo>/editar/', views.editar_cantidad_insumo_receta, name='editar_cantidad_insumo_receta'),

    # Reportes
    path("reportes/", views.centro_reportes, name="centro_reportes"),

    path("reportes/ventas/", views.resumen_ventas, name="resumen_ventas"),
    path("reportes/productos/", views.productos_mas_vendidos, name="productos_mas_vendidos"),
    path("reportes/dinero/", views.dinero_recaudado, name="dinero_recaudado"),

    path("reportes/ventas/excel/", views.exportar_resumen_excel, name="exportar_resumen_excel"),
    path("reportes/ventas/pdf/", views.exportar_resumen_pdf, name="exportar_resumen_pdf"),

    path("reportes/productos/excel/", views.exportar_productos_excel, name="exportar_productos_excel"),
    path("reportes/productos/pdf/", views.exportar_productos_pdf, name="exportar_productos_pdf"),

    path("reportes/dinero/excel/", views.exportar_dinero_excel, name="exportar_dinero_excel"),
    path("reportes/dinero/pdf/", views.exportar_dinero_pdf, name="exportar_dinero_pdf"),

    # Usuarios
    path('panel/empleados/', views.empleado_lista, name='empleado_lista'),
    path('panel/empleados/crear/', views.empleado_crear, name='empleado_crear'),
    path('panel/empleados/<int:idempleado>/editar/', views.empleado_editar, name='empleado_editar'),
    path('panel/empleados/<int:idempleado>/eliminar/', views.empleado_eliminar, name='empleado_eliminar'),

    # Roles y permisos
    path('panel/roles/', views.rol_lista, name='rol_lista'),
    path('panel/roles/crear/', views.rol_crear, name='rol_crear'),
    path('panel/roles/<int:idrol>/editar/', views.rol_editar, name='rol_editar'),
    path('panel/roles/<int:idrol>/eliminar/', views.rol_eliminar, name='rol_eliminar'),
    path('panel/roles/<int:idrol>/permisos/', views.rol_permisos, name='rol_permisos'),

    # Productos - Gestión de recetas
    path('panel/recetas/producto/<int:idproducto>/', views.gestionar_receta, name='gestionar_receta'),
    path('panel/recetas/insumo/eliminar/<int:idrecetainsumo>/', views.eliminar_insumo_receta, name='eliminar_insumo_receta'),

    # Panel - Pedidos / Tickets
    path('panel/pedidos/<int:idpedido>/ticket/', views.ver_ticket, name='ver_ticket'),
    path('panel/pedidos/<int:idpedido>/imprimir/', views.imprimir_ticket, name='imprimir_ticket'),
    path('panel/pedidos/<int:idpedido>/estado/', views.cambiar_estado_pedido, name='cambiar_estado_pedido'),

    # Negocio
    path("panel/negocio/apertura/", views.estado_negocio_panel, name="estado_negocio"),
path("panel/negocio/estado/", views.cambiar_estado_local, name="cambiar_estado_local"),

    # Horarios - CRUD
    path('panel/horarios/', views.horarios_lista, name='horarios_lista'),
    path('panel/horarios/crear/', views.horarios_crear, name='horarios_crear'),
    path('panel/horarios/editar/<int:idhorario>/', views.horarios_editar, name='horarios_editar'),
    path('panel/horarios/eliminar/<int:idhorario>/', views.horarios_eliminar, name='horarios_eliminar'),

    # Zonas entrega
    path('panel/zonas-entrega/', views.zonas_entrega_lista, name='zonas_entrega_lista'),
    path('panel/zonas-entrega/crear/', views.zonas_entrega_crear, name='zonas_entrega_crear'),
    path('panel/zonas-entrega/editar/<int:idzona>/', views.zonas_entrega_editar, name='zonas_entrega_editar'),
    path('panel/zonas-entrega/eliminar/<int:idzona>/', views.zonas_entrega_eliminar, name='zonas_entrega_eliminar'),
]