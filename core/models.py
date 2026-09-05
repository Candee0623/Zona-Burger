from django.db import models
from PIL import Image
import os
from django.core.files.base import ContentFile
import io
from django_ckeditor_5.fields import CKEditor5Field

class Categoria(models.Model):
    id = models.AutoField(db_column='Id', primary_key=True)  # Field name made lowercase.
    nombre = models.CharField(db_column='Nombre', max_length=50, db_collation='Modern_Spanish_CI_AS', blank=True, null=True)  # Field name made lowercase.

    class Meta:
        managed = False
        db_table = 'Categoria'


class CategoriaProducto(models.Model):
    idcategoria = models.AutoField(db_column='IdCategoria', primary_key=True)  # Field name made lowercase.
    nombre = models.CharField(db_column='Nombre', max_length=100, db_collation='Modern_Spanish_CI_AS')  # Field name made lowercase.

    class Meta:
        managed = False
        db_table = 'CategoriaProducto'


class Cliente(models.Model):
    idcliente = models.AutoField(db_column='IdCliente', primary_key=True)  # Field name made lowercase.
    nombre = models.CharField(db_column='Nombre', max_length=100, db_collation='Modern_Spanish_CI_AS')  # Field name made lowercase.
    apellido = models.CharField(db_column='Apellido', max_length=100, db_collation='Modern_Spanish_CI_AS')  # Field name made lowercase.
    telefono = models.CharField(db_column='Telefono', max_length=30, db_collation='Modern_Spanish_CI_AS', blank=True, null=True)  # Field name made lowercase.

    class Meta:
        managed = False
        db_table = 'Cliente'


class Compras(models.Model):
    idcompra = models.AutoField(db_column='IdCompra', primary_key=True)  # Field name made lowercase.
    fecha = models.DateTimeField(db_column='Fecha')  # Field name made lowercase.
    preciototal = models.DecimalField(db_column='PrecioTotal', max_digits=10, decimal_places=2)  # Field name made lowercase.
    idempleado = models.ForeignKey('Empleado', models.DO_NOTHING, db_column='IdEmpleado', blank=True, null=True)  # Field name made lowercase.

    class Meta:
        managed = False
        db_table = 'Compras'


class DetalleCompra(models.Model):
    iddetallecompra = models.AutoField(db_column='IdDetalleCompra', primary_key=True)  # Field name made lowercase.
    idcompra = models.ForeignKey(Compras, models.DO_NOTHING, db_column='IdCompra', blank=True, null=True)  # Field name made lowercase.
    idinsumo = models.ForeignKey('Insumo', models.DO_NOTHING, db_column='IdInsumo', blank=True, null=True)  # Field name made lowercase.
    cantidad = models.DecimalField(db_column='Cantidad', max_digits=10, decimal_places=2)  # Field name made lowercase.
    costounitario = models.DecimalField(db_column='CostoUnitario', max_digits=10, decimal_places=2)  # Field name made lowercase.

    class Meta:
        managed = False
        db_table = 'DetalleCompra'


class DetallePedido(models.Model):
    iddetallepedido = models.AutoField(db_column='IdDetallePedido', primary_key=True)  # Field name made lowercase.
    idpedido = models.ForeignKey('Pedido', models.DO_NOTHING, db_column='IdPedido', blank=True, null=True)  # Field name made lowercase.
    idproducto = models.ForeignKey('Producto', models.DO_NOTHING, db_column='IdProducto', blank=True, null=True)  # Field name made lowercase.
    cantidad = models.IntegerField(db_column='Cantidad')  # Field name made lowercase.
    preciounitario = models.DecimalField(db_column='PrecioUnitario', max_digits=10, decimal_places=2)  # Field name made lowercase.

    class Meta:
        managed = False
        db_table = 'DetallePedido'


class Direccion(models.Model):
    iddireccion = models.AutoField(db_column='IdDireccion', primary_key=True)  # Field name made lowercase.
    idcliente = models.ForeignKey(Cliente, models.DO_NOTHING, db_column='IdCliente', blank=True, null=True)  # Field name made lowercase.
    calle = models.CharField(db_column='Calle', max_length=150, db_collation='Modern_Spanish_CI_AS')  # Field name made lowercase.
    numero = models.CharField(db_column='Numero', max_length=20, db_collation='Modern_Spanish_CI_AS')  # Field name made lowercase.
    piso = models.CharField(db_column='Piso', max_length=10, db_collation='Modern_Spanish_CI_AS', blank=True, null=True)  # Field name made lowercase.
    localidad = models.CharField(db_column='Localidad', max_length=100, db_collation='Modern_Spanish_CI_AS')  # Field name made lowercase.

    class Meta:
        managed = False
        db_table = 'Direccion'


class Empleado(models.Model):
    idempleado = models.AutoField(db_column='IdEmpleado', primary_key=True)  # Field name made lowercase.
    nombre = models.CharField(db_column='Nombre', max_length=100, db_collation='Modern_Spanish_CI_AS')  # Field name made lowercase.
    apellido = models.CharField(db_column='Apellido', max_length=100, db_collation='Modern_Spanish_CI_AS')  # Field name made lowercase.
    idrol = models.ForeignKey('Rol', models.DO_NOTHING, db_column='IdRol', blank=True, null=True)  # Field name made lowercase.
    contrasena = models.CharField(db_column='Contrasena', max_length=255, db_collation='Modern_Spanish_CI_AS')  # Field name made lowercase.

    class Meta:
        managed = False
        db_table = 'Empleado'


class EstadoNegocio(models.Model):
    idestado = models.AutoField(db_column='IdEstado', primary_key=True)  # Field name made lowercase.
    idmodificacion = models.ForeignKey('Ultimamodificacion', models.DO_NOTHING, db_column='IdModificacion')  # Field name made lowercase.
    descripcion = models.CharField(db_column='Descripcion', max_length=250, db_collation='Modern_Spanish_CI_AS', blank=True, null=True)  # Field name made lowercase.

    class Meta:
        managed = False
        db_table = 'EstadoNegocio'


class EstadoPedido(models.Model):
    idestado = models.AutoField(db_column='IdEstado', primary_key=True)  # Field name made lowercase.
    descripcion = models.CharField(db_column='Descripcion', max_length=50, db_collation='Modern_Spanish_CI_AS')  # Field name made lowercase.

    class Meta:
        managed = False
        db_table = 'EstadoPedido'


class EstadoProducto(models.Model):
    idestado = models.AutoField(db_column='IdEstado', primary_key=True)  # Field name made lowercase.
    descripcion = models.CharField(db_column='Descripcion', max_length=50, db_collation='Modern_Spanish_CI_AS')  # Field name made lowercase.

    class Meta:
        managed = False
        db_table = 'EstadoProducto'


class EstadoStock(models.Model):
    idestado = models.AutoField(db_column='IdEstado', primary_key=True)  # Field name made lowercase.
    descripcion = models.CharField(db_column='Descripcion', max_length=10, db_collation='Modern_Spanish_CI_AS', blank=True, null=True)  # Field name made lowercase.
    nivelcritico = models.DecimalField(db_column='NivelCritico', max_digits=10, decimal_places=2, blank=True, null=True)  # Field name made lowercase.

    class Meta:
        managed = False
        db_table = 'EstadoStock'


class Extras(models.Model):
    idextra = models.AutoField(db_column='IdExtra', primary_key=True)  # Field name made lowercase.
    nombre = models.CharField(db_column='Nombre', max_length=100, db_collation='Modern_Spanish_CI_AS')  # Field name made lowercase.
    precio = models.DecimalField(db_column='Precio', max_digits=10, decimal_places=2)  # Field name made lowercase.

    class Meta:
        managed = False
        db_table = 'Extras'


class GrupoOpcion(models.Model):
    idgrupo = models.AutoField(db_column='IdGrupo', primary_key=True)  # Field name made lowercase.
    nombre = models.CharField(db_column='Nombre', max_length=100, db_collation='Modern_Spanish_CI_AS')  # Field name made lowercase.
    minselecciones = models.IntegerField(db_column='MinSelecciones', blank=True, null=True)  # Field name made lowercase.
    maxselecciones = models.IntegerField(db_column='MaxSelecciones', blank=True, null=True)  # Field name made lowercase.

    class Meta:
        managed = False
        db_table = 'GrupoOpcion'


class Horario(models.Model):
    idhorario = models.AutoField(db_column='IdHorario', primary_key=True)  # Field name made lowercase.
    idnegocio = models.ForeignKey('Negocio', models.DO_NOTHING, db_column='IdNegocio', blank=True, null=True)  # Field name made lowercase.
    diasemana = models.CharField(db_column='DiaSemana', max_length=20, db_collation='Modern_Spanish_CI_AS', blank=True, null=True)  # Field name made lowercase.
    horaapertura = models.TimeField(db_column='HoraApertura', blank=True, null=True)  # Field name made lowercase.
    horacierre = models.TimeField(db_column='HoraCierre', blank=True, null=True)  # Field name made lowercase.
    estaabierto = models.IntegerField(db_column='EstaAbierto', blank=True, null=True)  # Field name made lowercase.

    class Meta:
        managed = False
        db_table = 'Horario'


class Insumo(models.Model):
    idinsumo = models.AutoField(db_column='IdInsumo', primary_key=True)  # Field name made lowercase.
    nombreinsumo = models.CharField(db_column='NombreInsumo', max_length=100, db_collation='Modern_Spanish_CI_AS')  # Field name made lowercase.
    unidadmedidaingreso = models.CharField(db_column='UnidadMedidaIngreso', max_length=30, db_collation='Modern_Spanish_CI_AS')  # Field name made lowercase.
    unidadmedidaegreso = models.CharField(db_column='UnidadMedidaEgreso', max_length=30, db_collation='Modern_Spanish_CI_AS')  # Field name made lowercase.
    stockactual = models.DecimalField(db_column='StockActual', max_digits=10, decimal_places=2)  # Field name made lowercase.

    class Meta:
        managed = False
        db_table = 'Insumo'


class MedioPago(models.Model):
    idmediopago = models.AutoField(db_column='IdMedioPago', primary_key=True)  # Field name made lowercase.
    nombremetodo = models.CharField(db_column='NombreMetodo', max_length=50, db_collation='Modern_Spanish_CI_AS')  # Field name made lowercase.

    class Meta:
        managed = False
        db_table = 'MedioPago'


class Negocio(models.Model):
    idnegocio = models.AutoField(db_column='IdNegocio', primary_key=True)  # Field name made lowercase.
    idempleado = models.ForeignKey(Empleado, models.DO_NOTHING, db_column='IdEmpleado', blank=True, null=True)  # Field name made lowercase.
    idredsocial = models.ForeignKey('Redessociales', models.DO_NOTHING, db_column='IdRedSocial', blank=True, null=True)  # Field name made lowercase.
    nombre = models.CharField(db_column='Nombre', max_length=100, db_collation='Modern_Spanish_CI_AS')  # Field name made lowercase.
    telefono = models.CharField(db_column='Telefono', max_length=30, db_collation='Modern_Spanish_CI_AS')  # Field name made lowercase.
    idestado = models.ForeignKey(EstadoNegocio, models.DO_NOTHING, db_column='IdEstado', blank=True, null=True)  # Field name made lowercase.
    idzona = models.ForeignKey('Zonasentrega', models.DO_NOTHING, db_column='IdZona', blank=True, null=True)  # Field name made lowercase.

    class Meta:
        managed = False
        db_table = 'Negocio'


class Opcion(models.Model):
    idopcion = models.AutoField(db_column='IdOpcion', primary_key=True)  # Field name made lowercase.
    idgrupo = models.ForeignKey(GrupoOpcion, models.DO_NOTHING, db_column='IdGrupo', blank=True, null=True)  # Field name made lowercase.
    nombre = models.CharField(db_column='Nombre', max_length=100, db_collation='Modern_Spanish_CI_AS')  # Field name made lowercase.
    precioadicional = models.DecimalField(db_column='PrecioAdicional', max_digits=10, decimal_places=2, blank=True, null=True)  # Field name made lowercase.

    class Meta:
        managed = False
        db_table = 'Opcion'


class Pedido(models.Model):
    idpedido = models.AutoField(db_column='IdPedido', primary_key=True)  # Field name made lowercase.
    idcliente = models.ForeignKey(Cliente, models.DO_NOTHING, db_column='IdCliente', blank=True, null=True)  # Field name made lowercase.
    idmediopago = models.ForeignKey(MedioPago, models.DO_NOTHING, db_column='IdMedioPago', blank=True, null=True)  # Field name made lowercase.
    idestadopedido = models.ForeignKey(EstadoPedido, models.DO_NOTHING, db_column='IdEstadoPedido', blank=True, null=True)  # Field name made lowercase.
    horarioentregadeseado = models.TimeField(db_column='HorarioEntregaDeseado', blank=True, null=True)  # Field name made lowercase.
    justificacioncancelacion = models.CharField(db_column='JustificacionCancelacion', max_length=250, db_collation='Modern_Spanish_CI_AS', blank=True, null=True)  # Field name made lowercase.
    idpromocion = models.IntegerField(db_column='IdPromocion', blank=True, null=True)  # Field name made lowercase.
    idproducto = models.IntegerField(db_column='IdProducto', blank=True, null=True)  # Field name made lowercase.
    cantidad = models.IntegerField(db_column='Cantidad')  # Field name made lowercase.

    class Meta:
        managed = False
        db_table = 'Pedido'


class Producto(models.Model):
    idproducto = models.IntegerField(db_column='IdProducto', primary_key=True)  # Field name made lowercase.
    nombre = models.CharField(db_column='Nombre', max_length=100, db_collation='Modern_Spanish_CI_AS')  # Field name made lowercase.
    descripcion = models.CharField(db_column='Descripcion', max_length=250, db_collation='Modern_Spanish_CI_AS', blank=True, null=True)  # Field name made lowercase.
    precio = models.DecimalField(db_column='Precio', max_digits=10, decimal_places=2)  # Field name made lowercase.
    imagen = models.CharField(db_column='Imagen', max_length=2000, db_collation='Modern_Spanish_CI_AS', blank=True, null=True)  # Field name made lowercase.
    idcategoria = models.ForeignKey(CategoriaProducto, models.DO_NOTHING, db_column='IdCategoria', blank=True, null=True)  # Field name made lowercase.
    idestadostock = models.ForeignKey(EstadoStock, models.DO_NOTHING, db_column='IdEstadoStock', blank=True, null=True)  # Field name made lowercase.
    idestadoproducto = models.ForeignKey(EstadoProducto, models.DO_NOTHING, db_column='IdEstadoProducto', blank=True, null=True)  # Field name made lowercase.
    idnegocio = models.ForeignKey(Negocio, models.DO_NOTHING, db_column='IdNegocio', blank=True, null=True)  # Field name made lowercase.

    class Meta:
        managed = False
        db_table = 'Producto'


class ProductoExtras(models.Model):
    idproductoextra = models.AutoField(db_column='IdProductoExtra', primary_key=True)
    idproducto = models.ForeignKey(Producto, models.DO_NOTHING, db_column='IdProducto')
    idextra = models.ForeignKey(Extras, models.DO_NOTHING, db_column='IdExtra')

    class Meta:
        managed = False
        db_table = 'ProductoExtras'


class ProductoGrupoOpcion(models.Model):
    idproductogrupo = models.AutoField(db_column='IdProductoGrupo', primary_key=True)  # Field name made lowercase.
    idproducto = models.ForeignKey(Producto, models.DO_NOTHING, db_column='IdProducto', blank=True, null=True)  # Field name made lowercase.
    idgrupo = models.ForeignKey(GrupoOpcion, models.DO_NOTHING, db_column='IdGrupo', blank=True, null=True)  # Field name made lowercase.

    class Meta:
        managed = False
        db_table = 'ProductoGrupoOpcion'


class ProductoPromocion(models.Model):
    idproductopromocion = models.IntegerField(db_column='IdProductoPromocion', blank=True, null=True)  # Field name made lowercase.
    idproducto = models.ForeignKey(Producto, models.DO_NOTHING, db_column='IdProducto', blank=True, null=True)  # Field name made lowercase.
    idpromocion = models.ForeignKey('Promocion', models.DO_NOTHING, db_column='IdPromocion', blank=True, null=True)  # Field name made lowercase.

    class Meta:
        managed = False
        db_table = 'ProductoPromocion'


class Promocion(models.Model):
    idpromocion = models.AutoField(db_column='IdPromocion', primary_key=True)  # Field name made lowercase.
    palabraclave = models.CharField(db_column='PalabraClave', max_length=50, db_collation='Modern_Spanish_CI_AS', blank=True, null=True)  # Field name made lowercase.
    tipobeneficio = models.CharField(db_column='TipoBeneficio', max_length=50, db_collation='Modern_Spanish_CI_AS', blank=True, null=True)  # Field name made lowercase.
    valor = models.DecimalField(db_column='Valor', max_digits=10, decimal_places=2, blank=True, null=True)  # Field name made lowercase.
    fechainicio = models.DateField(db_column='FechaInicio', blank=True, null=True)  # Field name made lowercase.
    fechafin = models.DateField(db_column='FechaFin', blank=True, null=True)  # Field name made lowercase.
    activo = models.IntegerField(db_column='Activo', blank=True, null=True)  # Field name made lowercase.

    class Meta:
        managed = False
        db_table = 'Promocion'


class Receta(models.Model):
    idreceta = models.AutoField(db_column='IdReceta', primary_key=True)  # Field name made lowercase.
    idproducto = models.ForeignKey(Producto, models.DO_NOTHING, db_column='IdProducto', blank=True, null=True)  # Field name made lowercase.
    idinsumo = models.IntegerField(db_column='IdInsumo', blank=True, null=True)  # Field name made lowercase.

    class Meta:
        managed = False
        db_table = 'Receta'


class RecetaInsumo(models.Model):
    idrecetainsumo = models.IntegerField(db_column='IdRecetaInsumo', primary_key=True)  # Field name made lowercase.
    idinsumo = models.ForeignKey(Insumo, models.DO_NOTHING, db_column='IdInsumo', blank=True, null=True)  # Field name made lowercase.
    idreceta = models.ForeignKey(Receta, models.DO_NOTHING, db_column='IdReceta', blank=True, null=True)  # Field name made lowercase.
    cantidadinsumo = models.IntegerField(db_column='CantidadInsumo')  # Field name made lowercase.

    class Meta:
        managed = False
        db_table = 'RecetaInsumo'


class RedesSociales(models.Model):
    idredsocial = models.AutoField(db_column='IdRedSocial', primary_key=True)  # Field name made lowercase.
    plataforma = models.CharField(db_column='Plataforma', max_length=50, db_collation='Modern_Spanish_CI_AS', blank=True, null=True)  # Field name made lowercase.
    enlace = models.CharField(db_column='Enlace', max_length=250, db_collation='Modern_Spanish_CI_AS', blank=True, null=True)  # Field name made lowercase.
    idnegocio = models.IntegerField(db_column='IdNegocio', blank=True, null=True)  # Field name made lowercase.

    class Meta:
        managed = False
        db_table = 'RedesSociales'


class Rol(models.Model):
    idrol = models.AutoField(db_column='IdRol', primary_key=True)  # Field name made lowercase.
    nombrerol = models.CharField(db_column='NombreRol', max_length=50, db_collation='Modern_Spanish_CI_AS', blank=True, null=True)  # Field name made lowercase.

    class Meta:
        managed = False
        db_table = 'Rol'


class UltimaModificacion(models.Model):
    idmodificacion = models.AutoField(db_column='IdModificacion', primary_key=True)  # Field name made lowercase.
    fecha = models.DateTimeField(db_column='Fecha')  # Field name made lowercase.
    idempleado = models.ForeignKey(Empleado, models.DO_NOTHING, db_column='IdEmpleado', blank=True, null=True)  # Field name made lowercase.
    descripcioncambio = models.CharField(db_column='DescripcionCambio', max_length=250, db_collation='Modern_Spanish_CI_AS', blank=True, null=True)  # Field name made lowercase.
    idnegocio = models.IntegerField(db_column='IdNegocio', blank=True, null=True)  # Field name made lowercase.

    class Meta:
        managed = False
        db_table = 'UltimaModificacion'


class ZonasEntrega(models.Model):
    idzona = models.AutoField(db_column='IdZona', primary_key=True)  # Field name made lowercase.
    nombre = models.CharField(db_column='Nombre', max_length=50, db_collation='Modern_Spanish_CI_AS', blank=True, null=True)  # Field name made lowercase.
    costoenvio = models.DecimalField(db_column='CostoEnvio', max_digits=10, decimal_places=2, blank=True, null=True)  # Field name made lowercase.
    idnegocio = models.IntegerField(db_column='IdNegocio', blank=True, null=True)  # Field name made lowercase.

    class Meta:
        managed = False
        db_table = 'ZonasEntrega'




