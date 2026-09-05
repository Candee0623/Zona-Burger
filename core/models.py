from django.db import models
from PIL import Image
import os
from django.core.files.base import ContentFile
import io
from django_ckeditor_5.fields import CKEditor5Field

class Rol(models.Model):
    idrol = models.AutoField(db_column='IdRol', primary_key=True)
    nombrerol = models.CharField(db_column='NombreRol', max_length=50, db_collation='Modern_Spanish_CI_AS', blank=True, null=True)

    def __str__(self):
        return self.nombrerol or f"Rol {self.idrol}"

    class Meta:
        db_table = 'Rol'

class Empleado(models.Model):
    idempleado = models.AutoField(db_column='IdEmpleado', primary_key=True)
    nombre = models.CharField(db_column='Nombre', max_length=100, db_collation='Modern_Spanish_CI_AS')
    apellido = models.CharField(db_column='Apellido', max_length=100, db_collation='Modern_Spanish_CI_AS')
    idrol = models.ForeignKey(Rol, models.DO_NOTHING, db_column='IdRol', blank=True, null=True)
    contrasena = models.CharField(db_column='Contrasena', max_length=255, db_collation='Modern_Spanish_CI_AS')

    def __str__(self):
        return f"{self.nombre} {self.apellido}"

    class Meta:
        db_table = 'Empleado'

class EstadoNegocio(models.Model):
    idestado = models.AutoField(db_column='IdEstado', primary_key=True)
    idmodificacion = models.ForeignKey('UltimaModificacion', models.DO_NOTHING, db_column='IdModificacion', blank=True, null=True)
    descripcion = models.CharField(db_column='Descripcion', max_length=250, db_collation='Modern_Spanish_CI_AS', blank=True, null=True)

    def __str__(self):
        return self.descripcion or f"Estado {self.idestado}"

    class Meta:
        db_table = 'EstadoNegocio'

class UltimaModificacion(models.Model):
    idmodificacion = models.AutoField(db_column='IdModificacion', primary_key=True)
    fecha = models.DateTimeField(db_column='Fecha')
    idempleado = models.ForeignKey(Empleado, models.DO_NOTHING, db_column='IdEmpleado', blank=True, null=True)
    descripcioncambio = models.CharField(db_column='DescripcionCambio', max_length=250, db_collation='Modern_Spanish_CI_AS', blank=True, null=True)
    idnegocio = models.IntegerField(db_column='IdNegocio', blank=True, null=True)

    class Meta:
        db_table = 'UltimaModificacion'

class Negocio(models.Model):
    idnegocio = models.AutoField(db_column='IdNegocio', primary_key=True)
    idempleado = models.ForeignKey(Empleado, models.DO_NOTHING, db_column='IdEmpleado', blank=True, null=True)
    idredsocial = models.ForeignKey('RedesSociales', models.DO_NOTHING, db_column='IdRedSocial', blank=True, null=True)
    nombre = models.CharField(db_column='Nombre', max_length=100, db_collation='Modern_Spanish_CI_AS')
    telefono = models.CharField(db_column='Telefono', max_length=30, db_collation='Modern_Spanish_CI_AS')
    idestado = models.ForeignKey(EstadoNegocio, models.DO_NOTHING, db_column='IdEstado', blank=True, null=True)
    idzona = models.ForeignKey('ZonasEntrega', models.DO_NOTHING, db_column='IdZona', blank=True, null=True)

    def __str__(self):
        return self.nombre

    class Meta:
        db_table = 'Negocio'

class Horario(models.Model):
    idhorario = models.AutoField(db_column='IdHorario', primary_key=True)
    idnegocio = models.ForeignKey(Negocio, models.DO_NOTHING, db_column='IdNegocio', blank=True, null=True)
    diasemana = models.CharField(db_column='DiaSemana', max_length=20, db_collation='Modern_Spanish_CI_AS', blank=True, null=True)
    horaapertura = models.TimeField(db_column='HoraApertura', blank=True, null=True)
    horacierre = models.TimeField(db_column='HoraCierre', blank=True, null=True)
    estaabierto = models.IntegerField(db_column='EstaAbierto', blank=True, null=True)

    class Meta:
        db_table = 'Horario'

class ZonasEntrega(models.Model):
    idzona = models.AutoField(db_column='IdZona', primary_key=True)
    nombre = models.CharField(db_column='Nombre', max_length=50, db_collation='Modern_Spanish_CI_AS', blank=True, null=True)
    costoenvio = models.DecimalField(db_column='CostoEnvio', max_digits=10, decimal_places=2, blank=True, null=True, default=0.00)
    idnegocio = models.IntegerField(db_column='IdNegocio', blank=True, null=True)

    def __str__(self):
        return f"{self.nombre} (${self.costoenvio})"

    class Meta:
        db_table = 'ZonasEntrega'

class RedesSociales(models.Model):
    idredsocial = models.AutoField(db_column='IdRedSocial', primary_key=True)
    plataforma = models.CharField(db_column='Plataforma', max_length=50, db_collation='Modern_Spanish_CI_AS', blank=True, null=True)
    enlace = models.CharField(db_column='Enlace', max_length=250, db_collation='Modern_Spanish_CI_AS', blank=True, null=True)
    idnegocio = models.IntegerField(db_column='IdNegocio', blank=True, null=True)

    def __str__(self):
        return self.plataforma or f"Red {self.idredsocial}"

    class Meta:
        db_table = 'RedesSociales'

class Categoria(models.Model):
    id = models.AutoField(db_column='Id', primary_key=True)
    nombre = models.CharField(db_column='Nombre', max_length=50, db_collation='Modern_Spanish_CI_AS', blank=True, null=True)

    class Meta:
        db_table = 'Categoria'

class CategoriaProducto(models.Model):
    idcategoria = models.AutoField(db_column='IdCategoria', primary_key=True)
    nombre = models.CharField(db_column='Nombre', max_length=100, db_collation='Modern_Spanish_CI_AS')

    def __str__(self):
        return self.nombre

    class Meta:
        db_table = 'CategoriaProducto'

class EstadoStock(models.Model):
    idestado = models.AutoField(db_column='IdEstado', primary_key=True)
    descripcion = models.CharField(db_column='Descripcion', max_length=10, db_collation='Modern_Spanish_CI_AS', blank=True, null=True)
    nivelcritico = models.DecimalField(db_column='NivelCritico', max_digits=10, decimal_places=2, blank=True, null=True)

    def __str__(self):
        return self.descripcion or f"Estado {self.idestado}"

    class Meta:
        db_table = 'EstadoStock'

class EstadoProducto(models.Model):
    idestado = models.AutoField(db_column='IdEstado', primary_key=True)
    descripcion = models.CharField(db_column='Descripcion', max_length=50, db_collation='Modern_Spanish_CI_AS')

    def __str__(self):
        return self.descripcion

    class Meta:
        db_table = 'EstadoProducto'

class Producto(models.Model):
    idproducto = models.AutoField(db_column='IdProducto', primary_key=True)
    nombre = models.CharField(db_column='Nombre', max_length=100, db_collation='Modern_Spanish_CI_AS')
    descripcion = CKEditor5Field('Descripcion', config_name='extends', db_column='Descripcion', blank=True, null=True)
    precio = models.DecimalField(db_column='Precio', max_digits=10, decimal_places=2)
    imagen = models.ImageField(db_column='Imagen', upload_to='productos/', max_length=2000, blank=True, null=True)
    idcategoria = models.ForeignKey(CategoriaProducto, models.DO_NOTHING, db_column='IdCategoria', blank=True, null=True)
    idestadostock = models.ForeignKey(EstadoStock, models.DO_NOTHING, db_column='IdEstadoStock', blank=True, null=True)
    idestadoproducto = models.ForeignKey(EstadoProducto, models.DO_NOTHING, db_column='IdEstadoProducto', blank=True, null=True)
    idnegocio = models.ForeignKey(Negocio, models.DO_NOTHING, db_column='IdNegocio', blank=True, null=True)

    def __str__(self):
        return self.nombre

    def save(self, *args, **kwargs):
        if not self.imagen:
            super().save(*args, **kwargs)
            return

        try:
            img = Image.open(self.imagen)
            if img.mode in ('RGBA', 'P'):
                img = img.convert('RGB')
            max_size = (800, 800)
            img.thumbnail(max_size, Image.Resampling.LANCZOS)
            buffer = io.BytesIO()
            img.save(buffer, format='WEBP', quality=80, method=6)
            buffer.seek(0)
            file_name = os.path.basename(str(self.imagen))
            file_name_without_ext = os.path.splitext(file_name)[0]
            self.imagen.save(f"{file_name_without_ext}.webp", ContentFile(buffer.read()), save=False)
        except Exception:
            pass

        super().save(*args, **kwargs)

    class Meta:
        db_table = 'Producto'

class Extras(models.Model):
    idextra = models.AutoField(db_column='IdExtra', primary_key=True)
    nombre = models.CharField(db_column='Nombre', max_length=100, db_collation='Modern_Spanish_CI_AS')
    precio = models.DecimalField(db_column='Precio', max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.nombre} (${self.precio})"

    class Meta:
        db_table = 'Extras'

class ProductoExtras(models.Model):
    idproductoextra = models.AutoField(db_column='IdProductoExtra', primary_key=True)
    idproducto = models.ForeignKey(Producto, models.DO_NOTHING, db_column='IdProducto')
    idextra = models.ForeignKey(Extras, models.DO_NOTHING, db_column='IdExtra')

    class Meta:
        db_table = 'ProductoExtras'

class GrupoOpcion(models.Model):
    idgrupo = models.AutoField(db_column='IdGrupo', primary_key=True)
    nombre = models.CharField(db_column='Nombre', max_length=100, db_collation='Modern_Spanish_CI_AS')
    minselecciones = models.IntegerField(db_column='MinSelecciones', blank=True, null=True)
    maxselecciones = models.IntegerField(db_column='MaxSelecciones', blank=True, null=True)

    def __str__(self):
        return self.nombre

    class Meta:
        db_table = 'GrupoOpcion'

class Opcion(models.Model):
    idopcion = models.AutoField(db_column='IdOpcion', primary_key=True)
    idgrupo = models.ForeignKey(GrupoOpcion, models.DO_NOTHING, db_column='IdGrupo', blank=True, null=True)
    nombre = models.CharField(db_column='Nombre', max_length=100, db_collation='Modern_Spanish_CI_AS')
    precioadicional = models.DecimalField(db_column='PrecioAdicional', max_digits=10, decimal_places=2, blank=True, null=True)

    def __str__(self):
        return self.nombre

    class Meta:
        db_table = 'Opcion'

class ProductoGrupoOpcion(models.Model):
    idproductogrupo = models.AutoField(db_column='IdProductoGrupo', primary_key=True)
    idproducto = models.ForeignKey(Producto, models.DO_NOTHING, db_column='IdProducto', blank=True, null=True)
    idgrupo = models.ForeignKey(GrupoOpcion, models.DO_NOTHING, db_column='IdGrupo', blank=True, null=True)

    class Meta:
        db_table = 'ProductoGrupoOpcion'

class Insumo(models.Model):
    idinsumo = models.AutoField(db_column='IdInsumo', primary_key=True)
    nombreinsumo = models.CharField(db_column='NombreInsumo', max_length=100, db_collation='Modern_Spanish_CI_AS')
    unidadmedidaingreso = models.CharField(db_column='UnidadMedidaIngreso', max_length=30, db_collation='Modern_Spanish_CI_AS', blank=True, null=True)
    unidadmedidaegreso = models.CharField(db_column='UnidadMedidaEgreso', max_length=30, db_collation='Modern_Spanish_CI_AS', blank=True, null=True)
    stockactual = models.DecimalField(db_column='StockActual', max_digits=10, decimal_places=2, default=0.00)

    def __str__(self):
        return self.nombreinsumo

    class Meta:
        db_table = 'Insumo'

class Compras(models.Model):
    idcompra = models.AutoField(db_column='IdCompra', primary_key=True)
    fecha = models.DateTimeField(db_column='Fecha')
    preciototal = models.DecimalField(db_column='PrecioTotal', max_digits=10, decimal_places=2)
    idempleado = models.ForeignKey(Empleado, models.DO_NOTHING, db_column='IdEmpleado', blank=True, null=True)

    class Meta:
        db_table = 'Compras'

class DetalleCompra(models.Model):
    iddetallecompra = models.AutoField(db_column='IdDetalleCompra', primary_key=True)
    idcompra = models.ForeignKey(Compras, models.DO_NOTHING, db_column='IdCompra', blank=True, null=True)
    idinsumo = models.ForeignKey(Insumo, models.DO_NOTHING, db_column='IdInsumo', blank=True, null=True)
    cantidad = models.DecimalField(db_column='Cantidad', max_digits=10, decimal_places=2)
    costounitario = models.DecimalField(db_column='CostoUnitario', max_digits=10, decimal_places=2)

    class Meta:
        db_table = 'DetalleCompra'

class Receta(models.Model):
    idreceta = models.AutoField(db_column='IdReceta', primary_key=True)
    idproducto = models.ForeignKey(Producto, models.DO_NOTHING, db_column='IdProducto', blank=True, null=True)
    idinsumo = models.IntegerField(db_column='IdInsumo', blank=True, null=True)

    class Meta:
        db_table = 'Receta'

class RecetaInsumo(models.Model):
    idrecetainsumo = models.IntegerField(db_column='IdRecetaInsumo', primary_key=True)
    idinsumo = models.ForeignKey(Insumo, models.DO_NOTHING, db_column='IdInsumo', blank=True, null=True)
    idreceta = models.ForeignKey(Receta, models.DO_NOTHING, db_column='IdReceta', blank=True, null=True)
    cantidadinsumo = models.IntegerField(db_column='CantidadInsumo')

    class Meta:
        db_table = 'RecetaInsumo'

class MedioPago(models.Model):
    idmediopago = models.AutoField(db_column='IdMedioPago', primary_key=True)
    nombremetodo = models.CharField(db_column='NombreMetodo', max_length=50, db_collation='Modern_Spanish_CI_AS')

    def __str__(self):
        return self.nombremetodo

    class Meta:
        db_table = 'MedioPago'

class Cliente(models.Model):
    idcliente = models.AutoField(db_column='IdCliente', primary_key=True)
    nombre = models.CharField(db_column='Nombre', max_length=100, db_collation='Modern_Spanish_CI_AS')
    apellido = models.CharField(db_column='Apellido', max_length=100, db_collation='Modern_Spanish_CI_AS')
    telefono = models.CharField(db_column='Telefono', max_length=30, db_collation='Modern_Spanish_CI_AS', blank=True, null=True)

    def __str__(self):
        return f"{self.nombre} {self.apellido}"

    class Meta:
        db_table = 'Cliente'

class Direccion(models.Model):
    iddireccion = models.AutoField(db_column='IdDireccion', primary_key=True)
    idcliente = models.ForeignKey(Cliente, models.DO_NOTHING, db_column='IdCliente', blank=True, null=True, related_name='direcciones')
    calle = models.CharField(db_column='Calle', max_length=150, db_collation='Modern_Spanish_CI_AS')
    numero = models.CharField(db_column='Numero', max_length=20, db_collation='Modern_Spanish_CI_AS')
    piso = models.CharField(db_column='Piso', max_length=10, db_collation='Modern_Spanish_CI_AS', blank=True, null=True)
    localidad = models.CharField(db_column='Localidad', max_length=100, db_collation='Modern_Spanish_CI_AS')

    def __str__(self):
        return f"{self.calle} {self.numero}, {self.localidad}"

    class Meta:
        db_table = 'Direccion'

class EstadoPedido(models.Model):
    idestado = models.AutoField(db_column='IdEstado', primary_key=True)
    descripcion = models.CharField(db_column='Descripcion', max_length=50, db_collation='Modern_Spanish_CI_AS')

    def __str__(self):
        return self.descripcion

    class Meta:
        db_table = 'EstadoPedido'

class Pedido(models.Model):
    idpedido = models.AutoField(db_column='IdPedido', primary_key=True)
    idcliente = models.ForeignKey(Cliente, models.DO_NOTHING, db_column='IdCliente', blank=True, null=True)
    idmediopago = models.ForeignKey(MedioPago, models.DO_NOTHING, db_column='IdMedioPago', blank=True, null=True)
    idestadopedido = models.ForeignKey(EstadoPedido, models.DO_NOTHING, db_column='IdEstadoPedido', blank=True, null=True)
    horarioentregadeseado = models.TimeField(db_column='HorarioEntregaDeseado', blank=True, null=True)
    justificacioncancelacion = models.CharField(db_column='JustificacionCancelacion', max_length=250, db_collation='Modern_Spanish_CI_AS', blank=True, null=True)
    idpromocion = models.IntegerField(db_column='IdPromocion', blank=True, null=True)
    idproducto = models.IntegerField(db_column='IdProducto', blank=True, null=True)
    cantidad = models.IntegerField(db_column='Cantidad')

    def __str__(self):
        return f"Pedido #{self.idpedido}"

    class Meta:
        db_table = 'Pedido'

class DetallePedido(models.Model):
    iddetallepedido = models.AutoField(db_column='IdDetallePedido', primary_key=True)
    idpedido = models.ForeignKey(Pedido, models.DO_NOTHING, db_column='IdPedido', blank=True, null=True)
    idproducto = models.ForeignKey(Producto, models.DO_NOTHING, db_column='IdProducto', blank=True, null=True)
    cantidad = models.IntegerField(db_column='Cantidad')
    preciounitario = models.DecimalField(db_column='PrecioUnitario', max_digits=10, decimal_places=2)

    class Meta:
        db_table = 'DetallePedido'

class Promocion(models.Model):
    idpromocion = models.AutoField(db_column='IdPromocion', primary_key=True)
    palabraclave = models.CharField(db_column='PalabraClave', max_length=50, db_collation='Modern_Spanish_CI_AS', blank=True, null=True)
    tipobeneficio = models.CharField(db_column='TipoBeneficio', max_length=50, db_collation='Modern_Spanish_CI_AS', blank=True, null=True)
    valor = models.DecimalField(db_column='Valor', max_digits=10, decimal_places=2, blank=True, null=True)
    fechainicio = models.DateField(db_column='FechaInicio', blank=True, null=True)
    fechafin = models.DateField(db_column='FechaFin', blank=True, null=True)
    activo = models.IntegerField(db_column='Activo', blank=True, null=True)

    def __str__(self):
        return f"{self.palabraclave} ({self.tipobeneficio})"

    class Meta:
        db_table = 'Promocion'

class ProductoPromocion(models.Model):
    idproductopromocion = models.IntegerField(db_column='IdProductoPromocion', blank=True, null=True)
    idproducto = models.ForeignKey(Producto, models.DO_NOTHING, db_column='IdProducto', blank=True, null=True)
    idpromocion = models.ForeignKey(Promocion, models.DO_NOTHING, db_column='IdPromocion', blank=True, null=True)

    class Meta:
        db_table = 'ProductoPromocion'