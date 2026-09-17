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

    # Promociones 
    path('promociones/', views.lista_promociones, name='lista_promociones'),
    path('promociones/crear/', views.crear_promocion, name='crear_promocion'),
    path('promociones/editar/<int:idpromocion>/', views.editar_promocion, name='editar_promocion'),
    path('promociones/eliminar/<int:idpromocion>/', views.eliminar_promocion, name='eliminar_promocion'),

    # Panel de Administración - Inicio
    path('panel/', panel_inicio, name='panel_inicio'),
    path('pedido/<int:idpedido>/toggle_pagado/', views.toggle_pagado, name='toggle_pagado'),

    # Panel - Categorías
    path('panel/categorias/', views.categoria_lista, name='categoria_lista'),
    path('panel/categorias/crear/', views.categoria_crear, name='categoria_crear'),
    path('panel/categorias/<int:idcategoria>/editar/', views.categoria_editar, name='categoria_editar'),
    path('panel/categorias/<int:idcategoria>/eliminar/', views.categoria_eliminar, name='categoria_eliminar'),

    # Panel - Opciones (Grupos + sus opciones inline)
    path('panel/opciones/', views.grupo_lista, name='grupo_lista'),
    path('panel/opciones/crear/', views.grupo_crear, name='grupo_crear'),
    path('panel/opciones/<int:idgrupo>/editar/', views.grupo_editar, name='grupo_editar'),
    path('panel/opciones/<int:idgrupo>/eliminar/', views.grupo_eliminar, name='grupo_eliminar'),

    # Panel - Productos
    path('panel/productos/', views.producto_lista, name='producto_lista'),
    path('panel/productos/crear/', views.producto_crear, name='producto_crear'),
    path('panel/productos/<int:idproducto>/editar/', views.producto_editar, name='producto_editar'),
    path('panel/productos/<int:idproducto>/eliminar/', views.producto_eliminar, name='producto_eliminar'),

    # Panel - Recetas e Insumos de la Receta
    path('panel/recetas/', views.lista_recetas, name='lista_recetas'),
    path('panel/recetas/producto/<int:idproducto>/', views.gestionar_receta, name='gestionar_receta'),
    path('panel/recetas/insumo/eliminar/<int:idrecetainsumo>/', views.eliminar_insumo_receta, name='eliminar_insumo_receta'),

    # Panel - Pedidos / Tickets (Nuevas rutas añadidas para solucionar el error)
    path('panel/pedidos/<int:idpedido>/ticket/', views.ver_ticket, name='ver_ticket'),
    path('panel/pedidos/<int:idpedido>/imprimir/', views.imprimir_ticket, name='imprimir_ticket'),
    path('panel/pedidos/<int:idpedido>/estado/', views.cambiar_estado_pedido, name='cambiar_estado_pedido'),
]