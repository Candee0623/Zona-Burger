from django.contrib import admin
from .models import (
    Categoria,
    Extras,
    GrupoOpcion,
    Opcion,
    Producto,
    ProductoGrupoOpcion,
    ProductoExtras  # <--- Asegúrate de importar tu modelo intermedio
)


@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ('idcategoria', 'nombre')
    search_fields = ('nombre',)


class OpcionInline(admin.TabularInline):
    model = Opcion
    extra = 1


@admin.register(GrupoOpcion)
class GrupoOpcionAdmin(admin.ModelAdmin):
    list_display = ('idgrupo', 'nombre', 'min_selecciones', 'max_selecciones')
    search_fields = ('nombre',)
    inlines = [OpcionInline]


@admin.register(Extras)
class ExtrasAdmin(admin.ModelAdmin):
    list_display = ('idextra', 'nombre', 'precio')
    search_fields = ('nombre',)


class ProductoGrupoOpcionInline(admin.TabularInline):
    model = ProductoGrupoOpcion
    extra = 1
    autocomplete_fields = ['idgrupo']


# --- NUEVO: Inline para relacionar los Extras con el Producto ---
class ProductoExtrasInline(admin.TabularInline):
    model = ProductoExtras
    extra = 1
    autocomplete_fields = ['idextra'] # Opcional si tienes muchos extras


@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = ('idproducto', 'nombre', 'precio', 'idcategoria')
    list_filter = ('idcategoria',)
    search_fields = ('nombre', 'descripcion')
    # Agregamos los dos inlines dentro de la lista
    inlines = [ProductoGrupoOpcionInline, ProductoExtrasInline]

