from django.contrib import admin
from .models import (
    Rol, Empleado, EstadoNegocio, UltimaModificacion, Negocio, Horario, 
    ZonasEntrega, RedesSociales, Categoria, EstadoStock, EstadoProducto, 
    Producto, Extras, ProductoExtras, GrupoOpcion, Opcion, ProductoGrupoOpcion, 
    Insumo, Compras, Receta, MedioPago, Cliente, Direccion, EstadoPedido, 
    Pedido, Promocion
)

# --- CONFIGURACIONES AVANZADAS DE PRODUCTOS Y OPCIONES ---

@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ('idcategoria', 'nombre')
    list_display_links = ('idcategoria',)
    search_fields = ('nombre',)
    list_filter = ('nombre',)

class OpcionInline(admin.TabularInline):
    model = Opcion
    extra = 1

@admin.register(GrupoOpcion)
class GrupoOpcionAdmin(admin.ModelAdmin):
    list_display = ('idgrupo', 'nombre', 'min_selecciones', 'max_selecciones')
    list_display_links = ('idgrupo',)
    search_fields = ('nombre',)
    list_filter = ('min_selecciones', 'max_selecciones')
    inlines = [OpcionInline]

@admin.register(Extras)
class ExtrasAdmin(admin.ModelAdmin):
    list_display = ('idextra', 'nombre', 'precio')
    list_display_links = ('idextra',)
    search_fields = ('nombre',)
    list_filter = ('precio',)

class ProductoGrupoOpcionInline(admin.TabularInline):
    model = ProductoGrupoOpcion
    extra = 1
    autocomplete_fields = ['idgrupo']

class ProductoExtrasInline(admin.TabularInline):
    model = ProductoExtras
    extra = 1
    autocomplete_fields = ['idextra']

@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = ('idproducto', 'nombre', 'precio', 'idcategoria')
    list_display_links = ('idproducto',)
    list_filter = ('idcategoria', 'precio')
    search_fields = ('nombre', 'descripcion')
    inlines = [ProductoGrupoOpcionInline, ProductoExtrasInline]


# --- REGISTRO DEL RESTO DE LAS TABLAS DEL SISTEMA ---

@admin.register(Rol)
class RolAdmin(admin.ModelAdmin):
    list_display = ('idrol', 'nombrerol')
    list_display_links = ('idrol',)
    search_fields = ('nombrerol',)
    list_filter = ('nombrerol',)

@admin.register(Empleado)
class EmpleadoAdmin(admin.ModelAdmin):
    list_display = ('idempleado', 'nombre', 'apellido', 'rol')
    list_display_links = ('idempleado',)
    list_filter = ('rol',)
    search_fields = ('nombre', 'apellido', 'rol__nombrerol')

@admin.register(EstadoNegocio)
class EstadoNegocioAdmin(admin.ModelAdmin):
    list_display = ('idestado', 'descripcion')
    list_display_links = ('idestado',)
    search_fields = ('descripcion',)
    list_filter = ('descripcion',)

@admin.register(UltimaModificacion)
class UltimaModificacionAdmin(admin.ModelAdmin):
    list_display = ('idmodificacion', 'fecha', 'empleado', 'idestado')
    list_display_links = ('idmodificacion',)
    list_filter = ('idestado', 'empleado', 'fecha')
    search_fields = ('empleado__nombre', 'empleado__apellido')

@admin.register(Negocio)
class NegocioAdmin(admin.ModelAdmin):
    list_display = ('idnegocio', 'nombre', 'telefono', 'idestado')
    list_display_links = ('idnegocio',)
    list_filter = ('idestado',)
    search_fields = ('nombre', 'telefono')

@admin.register(Horario)
class HorarioAdmin(admin.ModelAdmin):
    list_display = ('idhorario', 'idnegocio', 'diasemana', 'horaapertura', 'horacierre')
    list_display_links = ('idhorario',)
    list_filter = ('idnegocio', 'diasemana')
    search_fields = ('diasemana', 'idnegocio__nombre')

@admin.register(ZonasEntrega)
class ZonasEntregaAdmin(admin.ModelAdmin):
    list_display = ('idzona', 'nombre', 'costoEnvio', 'idnegocio')
    list_display_links = ('idzona',)
    list_filter = ('idnegocio', 'costoEnvio')
    search_fields = ('nombre', 'idnegocio__nombre')

@admin.register(RedesSociales)
class RedesSocialesAdmin(admin.ModelAdmin):
    list_display = ('idredsocial', 'plataforma', 'enlace', 'idnegocio')
    list_display_links = ('idredsocial',)
    list_filter = ('idnegocio', 'plataforma')
    search_fields = ('plataforma', 'enlace')

@admin.register(EstadoStock)
class EstadoStockAdmin(admin.ModelAdmin):
    list_display = ('idestado', 'descripcion', 'nivelcritico')
    list_display_links = ('idestado',)
    list_filter = ('nivelcritico',)
    search_fields = ('descripcion', 'nivelcritico')

@admin.register(EstadoProducto)
class EstadoProductoAdmin(admin.ModelAdmin):
    list_display = ('idestado', 'descripcion')
    list_display_links = ('idestado',)
    search_fields = ('descripcion',)
    list_filter = ('descripcion',)

@admin.register(Insumo)
class InsumoAdmin(admin.ModelAdmin):
    list_display = ('idinsumo', 'nombreinsumo', 'unidadmedida', 'stockactual')
    list_display_links = ('idinsumo',)
    list_filter = ('unidadmedida', 'stockactual')
    search_fields = ('nombreinsumo', 'unidadmedida')

@admin.register(Compras)
class ComprasAdmin(admin.ModelAdmin):
    list_display = ('idcompra', 'insumo', 'fecha', 'cantidad', 'preciototal')
    list_display_links = ('idcompra',)
    list_filter = ('insumo', 'fecha')
    search_fields = ('insumo__nombreinsumo',)

@admin.register(Receta)
class RecetaAdmin(admin.ModelAdmin):
    list_display = ('idreceta', 'producto', 'insumo', 'cantidadinsumo')
    list_display_links = ('idreceta',)
    list_filter = ('producto', 'insumo')
    search_fields = ('producto__nombre', 'insumo__nombreinsumo')

@admin.register(MedioPago)
class MedioPagoAdmin(admin.ModelAdmin):
    list_display = ('idmediopago', 'nombremetodo')
    list_display_links = ('idmediopago',)
    search_fields = ('nombremetodo',)
    list_filter = ('nombremetodo',)

@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ('idcliente', 'nombre', 'apellido', 'telefono')
    list_display_links = ('idcliente',)
    search_fields = ('nombre', 'apellido', 'telefono')
    list_filter = ('apellido',)

@admin.register(Direccion)
class DireccionAdmin(admin.ModelAdmin):
    list_display = ('iddireccion', 'idcliente', 'calle', 'numero', 'localidad')
    list_display_links = ('iddireccion',)
    list_filter = ('localidad', 'idcliente')
    search_fields = ('calle', 'localidad', 'idcliente__nombre', 'idcliente__apellido')

@admin.register(EstadoPedido)
class EstadoPedidoAdmin(admin.ModelAdmin):
    list_display = ('idestadopedido', 'descripcion')
    list_display_links = ('idestadopedido',)
    search_fields = ('descripcion',)
    list_filter = ('descripcion',)

@admin.register(Pedido)
class PedidoAdmin(admin.ModelAdmin):
    list_display = ('idpedido', 'idcliente', 'idmediopago', 'idestadopedido', 'cantidad')
    list_display_links = ('idpedido',)
    list_filter = ('idestadopedido', 'idmediopago', 'idcliente')
    search_fields = ('idcliente__nombre', 'idcliente__apellido')

@admin.register(Promocion)
class PromocionAdmin(admin.ModelAdmin):
    list_display = ('idpromocion', 'palabraclave', 'tipobeneficio', 'valor', 'activo')
    list_display_links = ('idpromocion',)
    list_filter = ('activo', 'tipobeneficio')
    search_fields = ('palabraclave', 'tipobeneficio')