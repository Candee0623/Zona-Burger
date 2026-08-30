from django.db import models
from django.contrib.auth.models import AbstractUser

class Rol(models.Model):
    idrol = models.AutoField(db_column='IdRol', primary_key=True)
    nombrerol = models.CharField(db_column='NombreRol', max_length=50, db_collation='Modern_Spanish_CI_AS')

    def __str__(self):
        return self.nombrerol

    class Meta:
        db_table = 'Rol'

class Empleado(models.Model):
    idempleado = models.AutoField(db_column='IdEmpleado', primary_key=True)
    nombre = models.CharField(db_column='Nombre', max_length=100, db_collation='Modern_Spanish_CI_AS')
    apellido = models.CharField(db_column='Apellido', max_length=100, db_collation='Modern_Spanish_CI_AS')
    rol = models.ForeignKey(Rol, models.DO_NOTHING, db_column='IdRol')
    contrasena = models.CharField(db_column='Contrasena', max_length=255, db_collation='Modern_Spanish_CI_AS')
    idnegocio = models.ForeignKey('Negocio', models.DO_NOTHING, db_column='IdNegocio', blank=True, null=True)

    def __str__(self):
        return f"{self.nombre} {self.apellido} ({self.rol})"

    class Meta:
        db_table = 'Empleado'

class EstadoNegocio(models.Model):
    idestado = models.AutoField(db_column='IdEstado', primary_key=True)
    descripcion = models.CharField(db_column='Descripcion', max_length=100, db_collation='Modern_Spanish_CI_AS')

    def __str__(self):
        return self.descripcion

    class Meta:
        db_table = 'EstadoNegocio'

class UltimaModificacion(models.Model):
    idmodificacion = models.AutoField(db_column='IdModificacion', primary_key=True)
    fecha = models.DateTimeField(db_column='Fecha')
    empleado = models.ForeignKey(Empleado, models.DO_NOTHING, db_column='IdEmpleado')
    idestado = models.ForeignKey(EstadoNegocio, models.DO_NOTHING, db_column='IdEstado')
    descripcioncambio = models.CharField(db_column='DescripcionCambio', max_length=255, db_collation='Modern_Spanish_CI_AS', blank=True, null=True)

    class Meta:
        db_table = 'UltimaModificacion'

class Negocio(models.Model):
    idnegocio = models.AutoField(db_column='IdNegocio', primary_key=True)
    nombre = models.CharField(db_column='Nombre', max_length=100, db_collation='Modern_Spanish_CI_AS')
    telefono = models.CharField(db_column='Telefono', max_length=30, db_collation='Modern_Spanish_CI_AS', blank=True, null=True)
    idestado = models.ForeignKey(EstadoNegocio, models.DO_NOTHING, db_column='IdEstado', default=1)

    def __str__(self):
        return self.nombre

    class Meta:
        db_table = 'Negocio'

class Horario(models.Model):
    idhorario = models.AutoField(db_column='IdHorario', primary_key=True)
    idnegocio = models.ForeignKey(Negocio, models.DO_NOTHING, db_column='IdNegocio', blank=True, null=True)
    diasemana = models.CharField(db_column='DiaSemana', max_length=50, db_collation='Modern_Spanish_CI_AS')
    horaapertura = models.TimeField(db_column='HoraApertura')
    horacierre = models.TimeField(db_column='HoraCierre')

    def __str__(self):
        return f"{self.diasemana}: {self.horaapertura} - {self.horacierre}"

    class Meta:
        db_table = 'Horario'

class ZonasEntrega(models.Model):
    idzona = models.AutoField(db_column='IdZona', primary_key=True)
    nombre = models.CharField(db_column='Nombre', max_length=100, db_collation='Modern_Spanish_CI_AS')
    costoEnvio = models.DecimalField(db_column='CostoEnvio', max_digits=10, decimal_places=2, default=0.00)
    idnegocio = models.ForeignKey(Negocio, models.DO_NOTHING, db_column='IdNegocio', blank=True, null=True)

    def __str__(self):
        return f"{self.nombre} (${self.costoenvio})"

    class Meta:
        db_table = 'ZonasEntrega'

class RedesSociales(models.Model):
    idredsocial = models.AutoField(db_column='IdRedSocial', primary_key=True)
    plataforma = models.CharField(db_column='Plataforma', max_length=50, db_collation='Modern_Spanish_CI_AS')
    enlace = models.CharField(db_column='Enlace', max_length=255, db_collation='Modern_Spanish_CI_AS')
    idnegocio = models.ForeignKey(Negocio, models.DO_NOTHING, db_column='IdNegocio', blank=True, null=True)

    def __str__(self):
        return self.plataforma

    class Meta:
        db_table = 'RedesSociales'

class Categoria(models.Model):
    idcategoria = models.AutoField(db_column='IdCategoria', primary_key=True)
    nombre = models.CharField(db_column='Nombre', max_length=100, db_collation='Modern_Spanish_CI_AS')

    def __str__(self):
        return self.nombre

    class Meta:
        db_table = 'Categoria'

class EstadoStock(models.Model):
    idestado = models.AutoField(db_column='IdEstado', primary_key=True)
    descripcion = models.CharField(db_column='Descripcion', max_length=100, db_collation='Modern_Spanish_CI_AS')
    nivelcritico = models.IntegerField(db_column='NivelCritico', default=5)

    def __str__(self):
        return self.descripcion

    class Meta:
        db_table = 'EstadoStock'

class EstadoProducto(models.Model):
    idestado = models.AutoField(db_column='IdEstado', primary_key=True)
    descripcion = models.CharField(db_column='Descripcion', max_length=100, db_collation='Modern_Spanish_CI_AS')

    def __str__(self):
        return self.descripcion

    class Meta:
        db_table = 'EstadoProducto'

class Producto(models.Model):
    idproducto = models.AutoField(db_column='IdProducto', primary_key=True)
    idnegocio = models.ForeignKey(Negocio, models.DO_NOTHING, db_column='IdNegocio', blank=True, null=True)
    idcategoria = models.ForeignKey(Categoria, models.DO_NOTHING, db_column='IdCategoria')
    estadostock = models.ForeignKey(EstadoStock, models.DO_NOTHING, db_column='IdEstadoStock', blank=True, null=True)
    estadoproducto = models.ForeignKey(EstadoProducto, models.DO_NOTHING, db_column='IdEstadoProducto', blank=True, null=True)
    nombre = models.CharField(db_column='Nombre', max_length=100, db_collation='Modern_Spanish_CI_AS')
    descripcion = models.CharField(db_column='Descripcion', max_length=255, db_collation='Modern_Spanish_CI_AS', blank=True, null=True)
    precio = models.DecimalField(db_column='Precio', max_digits=10, decimal_places=2)
    imagen = models.CharField(db_column='Imagen', max_length=255, db_collation='Modern_Spanish_CI_AS', blank=True, null=True)

    def __str__(self):
        return self.nombre

    class Meta:
        db_table = 'Producto'

class Extras(models.Model):
    idextra = models.AutoField(db_column='IdExtra', primary_key=True)
    nombre = models.CharField(db_column='Nombre', max_length=100, db_collation='Modern_Spanish_CI_AS')
    precio = models.DecimalField(db_column='Precio', max_digits=10, decimal_places=2, default=0.00)

    def __str__(self):
        return f"{self.nombre} (+${self.precio})"

    class Meta:
        db_table = 'Extras'

class ProductoExtras(models.Model):
    idProducto = models.AutoField(primary_key=True)
    idproducto = models.ForeignKey(Producto, models.DO_NOTHING, db_column='IdProducto')
    idextra = models.ForeignKey(Extras, models.DO_NOTHING, db_column='IdExtra')

    class Meta:
        db_table = 'ProductoExtras'
        unique_together = (('idproducto', 'idextra'),)

class GrupoOpcion(models.Model):
    idgrupo = models.AutoField(db_column='IdGrupo', primary_key=True)
    nombre = models.CharField(db_column='Nombre', max_length=100, db_collation='Modern_Spanish_CI_AS')
    min_selecciones = models.IntegerField(db_column='MinSelecciones', default=0)
    max_selecciones = models.IntegerField(db_column='MaxSelecciones', default=1)

    def __str__(self):
        return self.nombre

    class Meta:
        db_table = 'GrupoOpcion'

class Opcion(models.Model):
  idopcion = models.AutoField(db_column='IdOpcion', primary_key=True)
  idgrupo = models.ForeignKey(GrupoOpcion, models.DO_NOTHING, db_column='IdGrupo')
  nombre = models.CharField(
      db_column='Nombre', max_length=100, db_collation='Modern_Spanish_CI_AS'
  )
  precio_adicional = models.DecimalField(
      db_column='PrecioAdicional', max_digits=10, decimal_places=2, default=0.00
  )

  def __str__(self):
    return self.nombre

  class Meta:
    db_table = 'Opcion'
    managed = (
        False  
    )

class ProductoGrupoOpcion(models.Model):
    id = models.AutoField(db_column='IdProductoGrupo', primary_key=True)
    idproducto = models.ForeignKey(Producto, models.DO_NOTHING, db_column='IdProducto')
    idgrupo = models.ForeignKey(GrupoOpcion, models.DO_NOTHING, db_column='IdGrupo')

    class Meta:
        db_table = 'ProductoGrupoOpcion'
        unique_together = (('idproducto', 'idgrupo'),)

class Insumo(models.Model):
    idinsumo = models.AutoField(db_column='IdInsumo', primary_key=True)
    nombreinsumo = models.CharField(db_column='NombreInsumo', max_length=100, db_collation='Modern_Spanish_CI_AS')
    unidadmedida = models.CharField(db_column='UnidadMedida', max_length=30, db_collation='Modern_Spanish_CI_AS')
    stockactual = models.DecimalField(db_column='StockActual', max_digits=10, decimal_places=2, default=0.00)

    def __str__(self):
        return f"{self.nombreinsumo} ({self.unidadmedida})"

    class Meta:
        db_table = 'Insumo'

class Compras(models.Model):
    idcompra = models.AutoField(db_column='IdCompra', primary_key=True)
    insumo = models.ForeignKey(Insumo, models.DO_NOTHING, db_column='IdInsumo')
    fecha = models.DateTimeField(db_column='Fecha')
    cantidad = models.DecimalField(db_column='Cantidad', max_digits=10, decimal_places=2)
    preciototal = models.DecimalField(db_column='PrecioTotal', max_digits=10, decimal_places=2)

    class Meta:
        db_table = 'Compras'

class Receta(models.Model):
    idreceta = models.AutoField(db_column='IdReceta', primary_key=True)
    producto = models.ForeignKey(Producto, models.DO_NOTHING, db_column='IdProducto')
    insumo = models.ForeignKey(Insumo, models.DO_NOTHING, db_column='IdInsumo')
    cantidadinsumo = models.DecimalField(db_column='CantidadInsumo', max_digits=10, decimal_places=2)

    class Meta:
        db_table = 'Receta'

class MedioPago(models.Model):
    idmediopago = models.AutoField(db_column='IdMedioPago', primary_key=True)
    nombremetodo = models.CharField(
        db_column='NombreMetodo',
        max_length=50,
        choices=[
            ('Efectivo', 'Efectivo'),
            ('Transferencia', 'Transferencia')
        ],
        db_collation='Modern_Spanish_CI_AS'
    )

    def __str__(self):
        return self.nombremetodo

    class Meta:
        db_table = 'MedioPago'

class Cliente(models.Model):
    idcliente = models.AutoField(db_column='IdCliente', primary_key=True)
    nombre = models.CharField(db_column='Nombre', max_length=100, db_collation='Modern_Spanish_CI_AS')
    apellido = models.CharField(db_column='Apellido', max_length=100, db_collation='Modern_Spanish_CI_AS')
    telefono = models.CharField(db_column='Telefono', max_length=30, db_collation='Modern_Spanish_CI_AS')

    def __str__(self):
        return f"{self.nombre} {self.apellido}"

    class Meta:
        db_table = 'Cliente'

class Direccion(models.Model):
    iddireccion = models.AutoField(db_column='IdDireccion', primary_key=True)
    idcliente = models.ForeignKey(Cliente, models.DO_NOTHING, db_column='IdCliente', related_name='direcciones')
    calle = models.CharField(db_column='Calle', max_length=150, db_collation='Modern_Spanish_CI_AS')
    numero = models.CharField(db_column='Numero', max_length=20, db_collation='Modern_Spanish_CI_AS')
    piso = models.CharField(db_column='Piso', max_length=20, db_collation='Modern_Spanish_CI_AS', blank=True, null=True)
    localidad = models.CharField(db_column='Localidad', max_length=100, db_collation='Modern_Spanish_CI_AS')

    def __str__(self):
        return f"{self.calle} {self.numero}, {self.localidad}"

    class Meta:
        db_table = 'Direccion'

class EstadoPedido(models.Model):
  idestadopedido = models.AutoField(
      db_column='IdEstado', primary_key=True
  )
  descripcion = models.CharField(
      db_column='Descripcion',
      max_length=100,
      db_collation='Modern_Spanish_CI_AS',
  )

  def __str__(self):
    return self.descripcion

  class Meta:
    db_table = 'EstadoPedido'

class Pedido(models.Model):
    idpedido = models.AutoField(db_column='IdPedido', primary_key=True)
    idcliente = models.ForeignKey(Cliente, models.DO_NOTHING, db_column='IdCliente')
    idmediopago = models.ForeignKey(MedioPago, models.DO_NOTHING, db_column='IdMedioPago')
    
    # Forzar el mapeo exacto de la columna física de SQL Server
    idestadopedido = models.ForeignKey(
        EstadoPedido, 
        models.DO_NOTHING, 
        db_column='IdEstadoPedido', 
        to_field='idestadopedido',
        default=1
    )
    
    idpromocion = models.ForeignKey('Promocion', models.DO_NOTHING, db_column='IdPromocion', blank=True, null=True)
    producto = models.ForeignKey(Producto, models.DO_NOTHING, db_column='IdProducto')
    horarioentregadeseado = models.DateTimeField(db_column='HorarioEntregaDeseado', blank=True, null=True)
    justificacioncancelacion = models.CharField(db_column='JustificacionCancelacion', max_length=255, db_collation='Modern_Spanish_CI_AS', blank=True, null=True)
    cantidad = models.IntegerField(db_column='Cantidad', default=1)

    def __str__(self):
        return f"Pedido #{self.idpedido} - {self.idcliente}"

    class Meta:
        db_table = 'Pedido'
        managed = False

class Promocion(models.Model):
    idpromocion = models.AutoField(db_column='IdPromocion', primary_key=True)
    palabraclave = models.CharField(db_column='PalabraClave', max_length=50, db_collation='Modern_Spanish_CI_AS')
    tipobeneficio = models.CharField(db_column='TipoBeneficio', max_length=50, db_collation='Modern_Spanish_CI_AS')
    valor = models.DecimalField(db_column='Valor', max_digits=10, decimal_places=2)
    idproducto = models.ForeignKey(Producto, models.DO_NOTHING, db_column='IdProducto', blank=True, null=True)
    minimocompra = models.DecimalField(db_column='MinimoCompra', max_digits=10, decimal_places=2, default=0.00)
    activo = models.IntegerField(db_column='Activo', default=1)

    def __str__(self):
        return f"{self.palabraclave} ({self.tipobeneficio})"

    class Meta:
        db_table = 'Promocion'