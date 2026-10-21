from django.contrib.auth.hashers import make_password, identify_hasher
from django.contrib import admin
from django.utils.html import format_html

from .models import (
    Rol,
    Empleado,
    EstadoNegocio,
    UltimaModificacion,
    Negocio,
    Horario,
    ZonasEntrega,
    RedesSociales,
    CategoriaProducto,
    EstadoStock,
    EstadoProducto,
    Producto,
    Extras,
    ProductoExtras,
    GrupoOpcion,
    Opcion,
    ProductoGrupoOpcion,
    Insumo,
    AjusteStock,
    Compras,
    Lote,
    DetalleCompra,
    Receta,
    RecetaInsumo,
    MedioPago,
    Cliente,
    Direccion,
    EstadoPedido,
    Pedido,
    DetallePedido,
    Promocion,
    TipoBeneficio,
    ProductoPromocion,
    MovimientoStock,
    Permiso,
    RolPermiso,
    RegistroAuditoria,
)


# ==========================================================
# CONFIGURACIÓN GENERAL DEL ADMINISTRADOR
# ==========================================================

admin.site.site_header = "Zona Burger - Administración"
admin.site.site_title = "Zona Burger"
admin.site.index_title = "Panel de administración"


# ==========================================================
# MIXIN DE ACCIONES
# ==========================================================

class AccionesAdminMixin:
    """Agrega un botón para editar cada registro."""

    @admin.display(description="Acciones")
    def acciones(self, obj):
        url = (
            f"/admin/{obj._meta.app_label}/"
            f"{obj._meta.model_name}/{obj.pk}/change/"
        )
        return format_html(
            '<a class="btn-editar-tabla" href="{}">Editar</a>',
            url,
        )


# ==========================================================
# ROLES, EMPLEADOS Y PERMISOS
# ==========================================================

@admin.register(Rol)
class RolAdmin(AccionesAdminMixin, admin.ModelAdmin):
    list_display = ("idrol", "nombrerol", "acciones")
    list_display_links = ("idrol",)
    search_fields = ("nombrerol",)
    list_filter = ("nombrerol",)


@admin.register(Empleado)
class EmpleadoAdmin(AccionesAdminMixin, admin.ModelAdmin):
    list_display = (
        "id_empleado",
        "nombre",
        "apellido",
        "idrol",
        "correo",
        "activo",
        "fecha_creacion",
        "last_login",
        "acciones",
    )
    list_display_links = ("id_empleado",)
    search_fields = ("nombre", "apellido", "correo")
    list_filter = ("activo", "idrol", "fecha_creacion")
    autocomplete_fields = ("idrol",)
    readonly_fields = ("fecha_creacion", "last_login")
    
    def save_model(self, request, obj, form, change):
        # Si lo cargado no es un hash válido, lo hashea antes de guardar.
        try:
            identify_hasher(obj.contrasena)
        except ValueError:
            obj.contrasena = make_password(obj.contrasena)
        super().save_model(request, obj, form, change)


class RolPermisoInline(admin.TabularInline):
    model = RolPermiso
    extra = 0
    autocomplete_fields = ("idpermiso",)


@admin.register(Permiso)
class PermisoAdmin(AccionesAdminMixin, admin.ModelAdmin):
    list_display = (
        "idpermiso",
        "codigo",
        "modulo",
        "accion",
        "descripcion",
        "acciones",
    )
    list_display_links = ("idpermiso",)
    search_fields = ("codigo", "modulo", "accion", "descripcion")
    list_filter = ("modulo", "accion")
    ordering = ("modulo", "accion")


@admin.register(RolPermiso)
class RolPermisoAdmin(AccionesAdminMixin, admin.ModelAdmin):
    list_display = ("idrolpermiso", "idrol", "idpermiso", "acciones")
    list_display_links = ("idrolpermiso",)
    search_fields = ("idrol__nombrerol", "idpermiso__codigo")
    list_filter = ("idrol", "idpermiso")
    autocomplete_fields = ("idrol", "idpermiso")


# ==========================================================
# ESTADOS Y AUDITORÍA
# ==========================================================

@admin.register(EstadoNegocio)
class EstadoNegocioAdmin(AccionesAdminMixin, admin.ModelAdmin):
    list_display = ("idestado", "descripcion", "acciones")
    list_display_links = ("idestado",)
    search_fields = ("descripcion",)
    list_filter = ("descripcion",)


@admin.register(UltimaModificacion)
class UltimaModificacionAdmin(AccionesAdminMixin, admin.ModelAdmin):
    list_display = (
        "idmodificacion",
        "fecha",
        "idempleado",
        "idnegocio",
        "descripcioncambio",
        "idestado",
        "acciones",
    )
    list_display_links = ("idmodificacion",)
    list_filter = ("fecha", "idestado")
    search_fields = (
        "idempleado__nombre",
        "idempleado__apellido",
        "descripcioncambio",
    )


@admin.register(RegistroAuditoria)
class RegistroAuditoriaAdmin(admin.ModelAdmin):
    list_display = (
        "idauditoria",
        "fecha",
        "idempleado",
        "accion",
        "descripcion",
        "ip",
    )
    list_display_links = ("idauditoria",)
    list_filter = ("accion", "fecha")
    search_fields = (
        "accion",
        "descripcion",
        "ip",
        "idempleado__nombre",
        "idempleado__apellido",
    )
    readonly_fields = (
        "fecha",
        "idempleado",
        "accion",
        "descripcion",
        "ip",
    )


# ==========================================================
# NEGOCIO, HORARIOS Y ENTREGA
# ==========================================================

@admin.register(Negocio)
class NegocioAdmin(AccionesAdminMixin, admin.ModelAdmin):
    list_display = (
        "idnegocio",
        "nombre",
        "telefono",
        "idempleado",
        "idestado",
        "idzona",
        "acciones",
    )
    list_display_links = ("idnegocio",)
    list_filter = ("idestado",)
    search_fields = ("nombre", "telefono")


@admin.register(Horario)
class HorarioAdmin(AccionesAdminMixin, admin.ModelAdmin):
    list_display = (
        "idhorario",
        "idnegocio",
        "diasemana",
        "horaapertura",
        "horacierre",
        "estaabierto",
        "acciones",
    )
    list_display_links = ("idhorario",)
    list_filter = ("idnegocio", "diasemana", "estaabierto")
    search_fields = ("diasemana", "idnegocio__nombre")


@admin.register(ZonasEntrega)
class ZonasEntregaAdmin(AccionesAdminMixin, admin.ModelAdmin):
    list_display = (
        "idzona",
        "nombre",
        "costoenvio",
        "idnegocio",
        "acciones",
    )
    list_display_links = ("idzona",)
    list_filter = ("costoenvio",)
    search_fields = ("nombre",)


@admin.register(RedesSociales)
class RedesSocialesAdmin(AccionesAdminMixin, admin.ModelAdmin):
    list_display = (
        "idredsocial",
        "plataforma",
        "enlace",
        "idnegocio",
        "acciones",
    )
    list_display_links = ("idredsocial",)
    list_filter = ("plataforma",)
    search_fields = ("plataforma", "enlace")


# ==========================================================
# CATEGORÍAS, PRODUCTOS Y OPCIONES
# ==========================================================

@admin.register(CategoriaProducto)
class CategoriaAdmin(AccionesAdminMixin, admin.ModelAdmin):
    list_display = ("idcategoria", "nombre", "acciones")
    list_display_links = ("idcategoria",)
    search_fields = ("nombre",)
    list_filter = ("nombre",)


class OpcionInline(admin.TabularInline):
    model = Opcion
    extra = 1
    fields = (
        "nombre",
        "precioadicional",
        "idinsumo",
        "cantidad_insumo",
    )
    autocomplete_fields = ("idinsumo",)


@admin.register(GrupoOpcion)
class GrupoOpcionAdmin(AccionesAdminMixin, admin.ModelAdmin):
    list_display = (
        "idgrupo",
        "nombre",
        "minselecciones",
        "maxselecciones",
        "acciones",
    )
    list_display_links = ("idgrupo",)
    search_fields = ("nombre",)
    list_filter = ("minselecciones", "maxselecciones")
    inlines = (OpcionInline,)


@admin.register(Extras)
class ExtrasAdmin(AccionesAdminMixin, admin.ModelAdmin):
    list_display = ("idextra", "nombre", "precio", "acciones")
    list_display_links = ("idextra",)
    search_fields = ("nombre",)
    list_filter = ("precio",)


class ProductoGrupoOpcionInline(admin.TabularInline):
    model = ProductoGrupoOpcion
    extra = 1
    autocomplete_fields = ("idgrupo",)


class ProductoExtrasInline(admin.TabularInline):
    model = ProductoExtras
    extra = 1
    autocomplete_fields = ("idextra",)


@admin.register(Producto)
class ProductoAdmin(AccionesAdminMixin, admin.ModelAdmin):
    list_display = (
        "idproducto",
        "nombre",
        "precio",
        "idcategoria",
        "idestadostock",
        "idestadoproducto",
        "idnegocio",
        "acciones",
    )
    list_display_links = ("idproducto",)
    list_filter = (
        "idcategoria",
        "idestadostock",
        "idestadoproducto",
        "idnegocio",
    )
    search_fields = ("nombre", "descripcion")
    inlines = (
        ProductoGrupoOpcionInline,
        ProductoExtrasInline,
    )


@admin.register(Opcion)
class OpcionAdmin(AccionesAdminMixin, admin.ModelAdmin):
    list_display = (
        "idopcion",
        "nombre",
        "idgrupo",
        "precioadicional",
        "idinsumo",
        "cantidad_insumo",
        "acciones",
    )
    list_display_links = ("idopcion",)
    search_fields = ("nombre", "idgrupo__nombre")
    list_filter = ("idgrupo",)
    autocomplete_fields = ("idgrupo", "idinsumo")


@admin.register(ProductoExtras)
class ProductoExtrasAdmin(AccionesAdminMixin, admin.ModelAdmin):
    list_display = (
        "idproductoextra",
        "idproducto",
        "idextra",
        "acciones",
    )
    list_display_links = ("idproductoextra",)
    list_filter = ("idproducto", "idextra")
    autocomplete_fields = ("idproducto", "idextra")


@admin.register(ProductoGrupoOpcion)
class ProductoGrupoOpcionAdmin(AccionesAdminMixin, admin.ModelAdmin):
    list_display = (
        "idproductogrupo",
        "idproducto",
        "idgrupo",
        "acciones",
    )
    list_display_links = ("idproductogrupo",)
    list_filter = ("idproducto", "idgrupo")
    autocomplete_fields = ("idproducto", "idgrupo")


# ==========================================================
# INVENTARIO, INSUMOS Y MOVIMIENTOS DE STOCK
# ==========================================================

@admin.register(EstadoStock)
class EstadoStockAdmin(AccionesAdminMixin, admin.ModelAdmin):
    list_display = (
        "idestado",
        "descripcion",
        "nivelcritico",
        "acciones",
    )
    list_display_links = ("idestado",)
    list_filter = ("nivelcritico",)
    search_fields = ("descripcion",)


@admin.register(EstadoProducto)
class EstadoProductoAdmin(AccionesAdminMixin, admin.ModelAdmin):
    list_display = ("idestado", "descripcion", "acciones")
    list_display_links = ("idestado",)
    search_fields = ("descripcion",)
    list_filter = ("descripcion",)


@admin.register(Insumo)
class InsumoAdmin(AccionesAdminMixin, admin.ModelAdmin):
    list_display = (
        "idinsumo",
        "codigo",
        "nombreinsumo",
        "unidadmedidaingreso",
        "unidadmedidaegreso",
        "stockactual",
        "stockminimo",
        "descontar_stock_automaticamente",
        "acciones",
    )
    list_display_links = ("idinsumo",)
    list_filter = (
        "unidadmedidaingreso",
        "unidadmedidaegreso",
        "descontar_stock_automaticamente",
    )
    search_fields = ("codigo", "nombreinsumo")


@admin.register(AjusteStock)
class AjusteStockAdmin(AccionesAdminMixin, admin.ModelAdmin):
    list_display = (
        "idajuste",
        "idinsumo",
        "cantidadanterior",
        "cantidadnueva",
        "motivo",
        "fecha",
        "acciones",
    )
    list_display_links = ("idajuste",)
    list_filter = ("fecha",)
    search_fields = ("idinsumo__nombreinsumo", "motivo")
    readonly_fields = ("fecha",)


@admin.register(Lote)
class LoteAdmin(AccionesAdminMixin, admin.ModelAdmin):
    list_display = (
        "idlote",
        "codigo",
        "idinsumo",
        "fechaingreso",
        "fechavencimiento",
        "cantidadinicial",
        "cantidadactual",
        "acciones",
    )
    list_display_links = ("idlote",)
    list_filter = ("fechaingreso", "fechavencimiento")
    search_fields = ("codigo", "idinsumo__nombreinsumo")


@admin.register(MovimientoStock)
class MovimientoStockAdmin(AccionesAdminMixin, admin.ModelAdmin):
    list_display = (
        "idmovimiento",
        "tipomovimiento",
        "idinsumo",
        "cantidad",
        "idpedido",
        "fecha",
        "descripcion",
        "acciones",
    )
    list_display_links = ("idmovimiento",)
    list_filter = ("tipomovimiento", "fecha")
    search_fields = (
        "idinsumo__nombreinsumo",
        "descripcion",
    )
    readonly_fields = ("fecha",)


# ==========================================================
# COMPRAS Y RECETAS
# ==========================================================

@admin.register(Compras)
class ComprasAdmin(AccionesAdminMixin, admin.ModelAdmin):
    list_display = (
        "idcompra",
        "fecha",
        "preciototal",
        "acciones",
    )
    list_display_links = ("idcompra",)
    list_filter = ("fecha",)
    ordering = ("-fecha",)


@admin.register(DetalleCompra)
class DetalleCompraAdmin(AccionesAdminMixin, admin.ModelAdmin):
    list_display = (
        "iddetallecompra",
        "idcompra",
        "idinsumo",
        "cantidad",
        "costounitario",
        "acciones",
    )
    list_display_links = ("iddetallecompra",)
    search_fields = ("idinsumo__nombreinsumo",)
    list_filter = ("idcompra", "idinsumo")


@admin.register(Receta)
class RecetaAdmin(AccionesAdminMixin, admin.ModelAdmin):
    list_display = (
        "idreceta",
        "idproducto",
        "idinsumo",
        "acciones",
    )
    list_display_links = ("idreceta",)
    list_filter = ("idproducto",)
    search_fields = ("idproducto__nombre",)


@admin.register(RecetaInsumo)
class RecetaInsumoAdmin(AccionesAdminMixin, admin.ModelAdmin):
    list_display = (
        "idrecetainsumo",
        "idreceta",
        "idinsumo",
        "cantidadinsumo",
        "unidadmedida",
        "es_removible",
        "acciones",
    )
    list_display_links = ("idrecetainsumo",)
    list_filter = ("unidadmedida", "es_removible")
    search_fields = ("idinsumo__nombreinsumo",)


# ==========================================================
# MEDIOS DE PAGO Y CLIENTES
# ==========================================================

@admin.register(MedioPago)
class MedioPagoAdmin(AccionesAdminMixin, admin.ModelAdmin):
    list_display = ("idmediopago", "nombremetodo", "acciones")
    list_display_links = ("idmediopago",)
    search_fields = ("nombremetodo",)
    list_filter = ("nombremetodo",)


@admin.register(Cliente)
class ClienteAdmin(AccionesAdminMixin, admin.ModelAdmin):
    list_display = (
        "idcliente",
        "nombre",
        "apellido",
        "telefono",
        "acciones",
    )
    list_display_links = ("idcliente",)
    search_fields = ("nombre", "apellido", "telefono")
    list_filter = ("apellido",)


@admin.register(Direccion)
class DireccionAdmin(AccionesAdminMixin, admin.ModelAdmin):
    list_display = (
        "iddireccion",
        "idcliente",
        "calle",
        "numero",
        "piso",
        "localidad",
        "acciones",
    )
    list_display_links = ("iddireccion",)
    list_filter = ("localidad", "idcliente")
    search_fields = (
        "calle",
        "localidad",
        "idcliente__nombre",
        "idcliente__apellido",
    )


# ==========================================================
# PEDIDOS Y ESTADOS
# ==========================================================

@admin.register(EstadoPedido)
class EstadoPedidoAdmin(AccionesAdminMixin, admin.ModelAdmin):
    list_display = ("idestado", "descripcion", "acciones")
    list_display_links = ("idestado",)
    search_fields = ("descripcion",)
    list_filter = ("descripcion",)


@admin.register(Pedido)
class PedidoAdmin(AccionesAdminMixin, admin.ModelAdmin):
    list_display = (
        "idpedido",
        "idcliente",
        "idmediopago",
        "idestadopedido",
        "total",
        "fecha_creacion",
        "pagado",
        "stock_descontado",
        "acciones",
    )
    list_display_links = ("idpedido",)
    list_filter = (
        "idestadopedido",
        "idmediopago",
        "pagado",
        "stock_descontado",
        "fecha_creacion",
    )
    search_fields = (
        "idcliente__nombre",
        "idcliente__apellido",
    )
    readonly_fields = ("fecha_creacion",)


@admin.register(DetallePedido)
class DetallePedidoAdmin(AccionesAdminMixin, admin.ModelAdmin):
    list_display = (
        "iddetallepedido",
        "idpedido",
        "idproducto",
        "cantidad",
        "preciounitario",
        "observaciones",
        "acciones",
    )
    list_display_links = ("iddetallepedido",)
    list_filter = ("idpedido", "idproducto")
    search_fields = (
        "idproducto__nombre",
        "observaciones",
    )


# ==========================================================
# PROMOCIONES
# ==========================================================

@admin.register(TipoBeneficio)
class TipoBeneficioAdmin(admin.ModelAdmin):
    list_display = ("idtipobeneficio", "codigo", "nombre", "comportamiento")
    list_display_links = ("idtipobeneficio",)
    search_fields = ("codigo", "nombre", "descripcion")
    list_filter = ("comportamiento",)


@admin.register(Promocion)
class PromocionAdmin(admin.ModelAdmin):
    list_display = (
        "idpromocion",
        "palabraclave",
        "get_tipo_beneficio",
        "valor",
        "fechainicio",
        "fechafin",
        "activo",
    )
    list_display_links = ("idpromocion",)
    list_filter = ("activo", "fechainicio", "fechafin")
    search_fields = ("palabraclave",)

    @admin.display(description="Tipo de beneficio")
    def get_tipo_beneficio(self, obj):
        return getattr(obj, "tipobeneficio", None) or "Sin asignar"


@admin.register(ProductoPromocion)
class ProductoPromocionAdmin(AccionesAdminMixin, admin.ModelAdmin):
    list_display = (
        "idproductopromocion",
        "idproducto",
        "idpromocion",
        "acciones",
    )
    list_display_links = ("idproductopromocion",)
    list_filter = ("idproducto", "idpromocion")
