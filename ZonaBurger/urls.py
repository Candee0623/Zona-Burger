from core import views
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('ckeditor5/', include('django_ckeditor_5.urls')),
    path('', views.index, name='index'),
    path('menu/', views.menu, name='menu'),
    path('producto/<int:idproducto>/', views.detalleProducto, name='detalleProducto'),
    path('carrito/agregar/<int:idproducto>/', views.agregar_al_carrito, name='agregar_al_carrito'),
    path('carrito/', views.ver_carrito, name='ver_carrito'),
    path('carrito/editar/<str:item_id>/', views.editar_item_carrito, name='editar_item_carrito'),
    path('carrito/actualizar/<str:item_id>/<str:accion>/', views.actualizar_cantidad_carrito, name='actualizar_cantidad_carrito'),
    path('carrito/eliminar/<str:item_id>/', views.eliminar_del_carrito, name='eliminar_del_carrito'),
    path('checkout/', views.procesar_checkout, name='checkout'),
    path('checkout/exito/', views.pedido_exitoso, name='pedido_exitoso'),
    path('promociones/', views.lista_promociones, name='lista_promociones'),
    path('promociones/crear/', views.crear_promocion, name='crear_promocion'),
    path('promociones/editar/<int:idpromocion>/', views.editar_promocion, name='editar_promocion'),
    path('promociones/eliminar/<int:idpromocion>/', views.eliminar_promocion, name='eliminar_promocion'),
]