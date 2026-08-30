from django.contrib import admin
from django.urls import path
from core.views import index
from core import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.index, name='index'),
    path('menu/', views.menu, name='menu'),
    path('producto/<int:idproducto>/', views.detalleProducto, name='detalleProducto'),
    path('checkout/', views.procesar_checkout, name='checkout'),
    path('checkout/exito/', views.pedido_exitoso, name='pedido_exitoso'),
]

