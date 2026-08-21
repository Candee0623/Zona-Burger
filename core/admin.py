from django.contrib import admin
from .models import Categoria, Producto, GrupoOpcion, Opcion, ProductoGrupoOpcion

@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ('idcategoria', 'nombre')
    search_fields = ('nombre',)

# 1. Inline para agregar opciones dentro del Grupo de Opciones
class OpcionInline(admin.TabularInline):
    model = Opcion
    extra = 1

@admin.register(GrupoOpcion)
class GrupoOpcionAdmin(admin.ModelAdmin):
    list_display = ('idgrupo', 'nombre', 'min_selecciones', 'max_selecciones')
    search_fields = ('nombre',)
    inlines = [OpcionInline]  # Aquí administras las opciones de este grupo


# 2. Inline para asociar grupos directamente al Producto
class ProductoGrupoOpcionInline(admin.TabularInline):
    model = ProductoGrupoOpcion
    extra = 1
    autocomplete_fields = ['idgrupo'] # Buscador rápido para el grupo

@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = ('idproducto', 'nombre', 'precio', 'idcategoria')
    list_filter = ('idcategoria',)
    search_fields = ('nombre', 'descripcion')
    inlines = [ProductoGrupoOpcionInline]  # Aquí administras qué grupos tiene este producto


# Nota: Opcion y ProductoGrupoOpcion ya NO se registran aquí individualmente, 
# por lo que desaparecen del menú principal del admin para no hacer ruido, 
# pero siguen funcionando por debajo gracias a los Inlines.
