from django.contrib import admin
from django.urls import path
from core.views import bienvenida
from core import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('',bienvenida, name='index'),
    path('menu/', views.menu, name='menu'),
    path('producto/<int:idproducto>/', views.detalleProducto, name='detalleProducto')
]
