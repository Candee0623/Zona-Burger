from django.contrib import admin
from django.urls import path
from core.views import index
from core import views

urlpatterns = [
    path('admin/', admin.site.urls),
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
]
