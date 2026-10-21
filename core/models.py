from decimal import Decimal
from django.db import models
from PIL import Image
import os
from django.core.files.base import ContentFile
import io
from django_ckeditor_5.fields import CKEditor5Field


class Rol(models.Model):
    idrol = models.AutoField(db_column='IdRol', primary_key=True)
    nombrerol = models.CharField(db_column='NombreRol', max_length=50, blank=True, null=True)
 
    def __str__(self):
        return self.nombrerol or f"Rol {self.idrol}"
 
    class Meta:
        db_table = 'Rol'


class Empleado(models.Model):
    id_empleado = models.AutoField(
        primary_key=True,
        db_column='IdEmpleado'
    )
    nombre = models.CharField(
        max_length=100,
        db_column='Nombre'
    )
    apellido = models.CharField(
        max_length=100,
        db_column='Apellido'
    )
    idrol = models.ForeignKey(
        Rol,
        models.DO_NOTHING,
        db_column='IdRol',
        null=True,
        blank=True,
        related_name='empleados'
    )
    contrasena = models.CharField(
        max_length=255,
        db_column='Contrasena'
    )
    correo = models.EmailField(
        max_length=255,
        db_column='CorreoElectronico'
    )
    activo = models.BooleanField(
        db_column='Activo',
        default=True
    )
    fecha_creacion = models.DateTimeField(
        db_column='FechaCreacion',
        auto_now_add=True,
        null=True,
        blank=True
    )
    token_recuperacion = models.CharField(
        db_column='TokenRecuperacion',
        max_length=128,
        null=True,
        blank=True
    )
    token_expiracion = models.DateTimeField(
        db_column='TokenExpiracion',
        null=True,
        blank=True
    )
    last_login = models.DateTimeField(
        db_column='UltimoLogin',
        null=True,
        blank=True
    )

    @property
    def ultimo_login(self):
        return self.last_login

    @ultimo_login.setter
    def ultimo_login(self, value):
        self.last_login = value

    @property
    def id_rol(self):
        return self.idrol_id

    @id_rol.setter
    def id_rol(self, value):
        self.idrol_id = value

    @property
    def is_authenticated(self):
        return True

    @property
    def is_anonymous(self):
        return False

    @property
    def is_active(self):
        return bool(self.activo)

    @property
    def is_staff(self):
        return (
            self.is_active
            and self.idrol is not None
            and (self.idrol.nombrerol or "").strip().lower() == "administrador"
        )

    @property
    def is_superuser(self):
        return self.is_staff

    def get_session_auth_hash(self):
        import hashlib
        return hashlib.sha256((self.contrasena or '').encode()).hexdigest()

    def get_session_auth_fallback_hash(self):
        return []

    def get_username(self):
        return self.correo or self.nombre

    def has_perm(self, perm, obj=None):
        if not self.is_active:
            return False

        if self.is_superuser:
            return True

        return False

    def has_module_perms(self, app_label):
        return self.is_active and self.is_staff

    def __str__(self):
        return f"{self.nombre} {self.apellido}".strip() or self.correo

    def get_all_permissions(self, obj=None):
            if not self.is_active:
                return set()

            if self.is_superuser:
                return set()

            return set()

    def tiene_permiso(self, codigo):
        if not self.activo:
            return False
        if not self.idrol:
            return False
        if (self.idrol.nombrerol or '').strip().lower() == 'administrador':
            return True
        return RolPermiso.objects.filter(idrol=self.idrol, idpermiso__codigo=codigo).exists()

    def tiene_algun_permiso(self, codigos):
        if not self.activo:
            return False
        if not self.idrol:
            return False
        if (self.idrol.nombrerol or '').strip().lower() == 'administrador':
            return True
        return RolPermiso.objects.filter(idrol=self.idrol, idpermiso__codigo__in=codigos).exists()

    def obtener_permisos(self):
        if not self.activo or not self.idrol:
            return set()
        if (self.idrol.nombrerol or '').strip().lower() == 'administrador':
            return set(Permiso.objects.values_list('codigo', flat=True))
        return set(
            RolPermiso.objects.filter(idrol=self.idrol).values_list('idpermiso__codigo', flat=True)
        )

    class Meta:
        db_table = 'Empleado'


class EstadoNegocio(models.Model):
    idestado = models.AutoField(db_column='IdEstado', primary_key=True)
    descripcion = models.CharField(db_column='Descripcion', max_length=250, blank=True, null=True)

    def __str__(self):
        return self.descripcion or f"Estado {self.idestado}"

    class Meta:
        db_table = 'EstadoNegocio'


class RedesSociales(models.Model):
    idredsocial = models.AutoField(db_column='IdRedSocial', primary_key=True)
    plataforma = models.CharField(db_column='Plataforma', max_length=50, blank=True, null=True)
    enlace = models.CharField(db_column='Enlace', max_length=250, blank=True, null=True)
    idnegocio = models.IntegerField(db_column='IdNegocio', blank=True, null=True)

    def __str__(self):
        return self.plataforma or f"Red {self.idredsocial}"

    class Meta:
        db_table = 'RedesSociales'


class ZonasEntrega(models.Model):
    idzona = models.AutoField(db_column='IdZona', primary_key=True)
    nombre = models.CharField(db_column='Nombre', max_length=50, blank=True, null=True)
    costoenvio = models.DecimalField(db_column='CostoEnvio', max_digits=10, decimal_places=2, blank=True, null=True, default=0.00)
    idnegocio = models.IntegerField(db_column='IdNegocio', blank=True, null=True)

    def __str__(self):
        return f"{self.nombre} (${self.costoenvio})"

    class Meta:
        db_table = 'ZonasEntrega'


class Negocio(models.Model):
    idnegocio = models.AutoField(db_column='IdNegocio', primary_key=True)
    idempleado = models.ForeignKey(Empleado, models.DO_NOTHING, db_column='IdEmpleado', blank=True, null=True)
    idredsocial = models.ForeignKey(RedesSociales, models.DO_NOTHING, db_column='IdRedSocial', blank=True, null=True)
    nombre = models.CharField(db_column='Nombre', max_length=100)
    telefono = models.CharField(db_column='Telefono', max_length=30)
    idestado = models.ForeignKey(EstadoNegocio, models.DO_NOTHING, db_column='IdEstado', blank=True, null=True)
    idzona = models.ForeignKey(ZonasEntrega, models.DO_NOTHING, db_column='IdZona', blank=True, null=True)

    def __str__(self):
        return self.nombre

    class Meta:
        db_table = 'Negocio'


class UltimaModificacion(models.Model):
    idmodificacion = models.AutoField(db_column='IdModificacion', primary_key=True)
    fecha = models.DateTimeField(db_column='Fecha')
    idempleado = models.ForeignKey(Empleado, models.DO_NOTHING, db_column='IdEmpleado', blank=True, null=True)
    descripcioncambio = models.CharField(db_column='DescripcionCambio', max_length=250, blank=True, null=True)
    idnegocio = models.IntegerField(db_column='IdNegocio', blank=True, null=True)
    idestado = models.ForeignKey('EstadoNegocio', models.DO_NOTHING, db_column='IdEstado', blank=True, null=True)

    class Meta:
        db_table = 'UltimaModificacion'


class Horario(models.Model):
    idhorario = models.AutoField(db_column='IdHorario', primary_key=True)
    idnegocio = models.ForeignKey(Negocio, models.DO_NOTHING, db_column='IdNegocio', blank=True, null=True)
    diasemana = models.CharField(db_column='DiaSemana', max_length=20, blank=True, null=True)
    horaapertura = models.TimeField(db_column='HoraApertura', blank=True, null=True)
    horacierre = models.TimeField(db_column='HoraCierre', blank=True, null=True)
    estaabierto = models.IntegerField(db_column='EstaAbierto', blank=True, null=True)

    class Meta:
        db_table = 'Horario'


class CategoriaProducto(models.Model):
    idcategoria = models.AutoField(db_column='IdCategoria', primary_key=True)
    nombre = models.CharField(db_column='Nombre', max_length=100)

    def __str__(self):
        return self.nombre

    class Meta:
        db_table = 'CategoriaProducto'


class EstadoStock(models.Model):
    idestado = models.AutoField(db_column='IdEstado', primary_key=True)
    descripcion = models.CharField(db_column='Descripcion', max_length=10, blank=True, null=True)
    nivelcritico = models.DecimalField(db_column='NivelCritico', max_digits=10, decimal_places=2, blank=True, null=True)

    def __str__(self):
        return self.descripcion or f"Estado {self.idestado}"

    class Meta:
        db_table = 'EstadoStock'


class EstadoProducto(models.Model):
    idestado = models.AutoField(db_column='IdEstado', primary_key=True)
    descripcion = models.CharField(db_column='Descripcion', max_length=50)

    def __str__(self):
        return self.descripcion

    class Meta:
        db_table = 'EstadoProducto'


class Producto(models.Model):
    idproducto = models.AutoField(db_column='IdProducto', primary_key=True)
    nombre = models.CharField(db_column='Nombre', max_length=100)
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
            file_name = os.path.splitext(self.imagen.name)[0] + '.webp'
            self.imagen.save(file_name, ContentFile(buffer.read()), save=False)
        except Exception as e:
            print(f"Error al procesar la imagen: {e}")
            
        super().save(*args, **kwargs)

    class Meta:
        db_table = 'Producto'


class Extras(models.Model):
    idextra = models.AutoField(db_column='IdExtra', primary_key=True)
    nombre = models.CharField(db_column='Nombre', max_length=100)
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
    nombre = models.CharField(db_column='Nombre', max_length=100)
    minselecciones = models.IntegerField(db_column='MinSelecciones', blank=True, null=True)
    maxselecciones = models.IntegerField(db_column='MaxSelecciones', blank=True, null=True)

    def __str__(self):
        return self.nombre

    class Meta:
        db_table = 'GrupoOpcion'


class Opcion(models.Model):
    idopcion = models.AutoField(db_column='IdOpcion', primary_key=True)
    idgrupo = models.ForeignKey(GrupoOpcion, models.DO_NOTHING, db_column='IdGrupo', blank=True, null=True)
    nombre = models.CharField(db_column='Nombre', max_length=100)
    precioadicional = models.DecimalField(db_column='PrecioAdicional', max_digits=10, decimal_places=2, blank=True, null=True)
    idinsumo = models.ForeignKey('Insumo', models.DO_NOTHING, db_column='IdInsumo', blank=True, null=True, related_name='opciones')
    cantidad_insumo = models.DecimalField(db_column='CantidadInsumo', max_digits=10, decimal_places=2, default=Decimal('1.00'))

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
    codigo = models.CharField(max_length=50, unique=True, blank=True, null=True)
    nombreinsumo = models.CharField(db_column='NombreInsumo', max_length=100)
    unidadmedidaingreso = models.CharField(db_column='UnidadMedidaIngreso', max_length=30)
    unidadmedidaegreso = models.CharField(db_column='UnidadMedidaEgreso', max_length=30)
    stockactual = models.DecimalField(db_column='StockActual', max_digits=10, decimal_places=2, default=0.00)
    stockminimo = models.DecimalField(max_digits=10, decimal_places=2, default=5.00)
    descontar_stock_automaticamente = models.BooleanField(db_column='DescontarStockAutomaticamente', default=False)

    def save(self, *args, **kwargs):
        es_nuevo = self.pk is None
        if es_nuevo and not self.codigo:
            super().save(*args, **kwargs)
            self.codigo = f"INS-{self.pk:03d}"
            super().save(update_fields=['codigo'])
            return
        super().save(*args, **kwargs)

    def __str__(self):
        return self.nombreinsumo

    class Meta:
        db_table = 'Insumo'


class AjusteStock(models.Model):
    idajuste = models.AutoField(db_column='IdAjuste', primary_key=True)
    idinsumo = models.ForeignKey(Insumo, models.DO_NOTHING, db_column='IdInsumo')
    cantidadanterior = models.DecimalField(db_column='CantidadAnterior', max_digits=10, decimal_places=2)
    cantidadnueva = models.DecimalField(db_column='CantidadNueva', max_digits=10, decimal_places=2)
    motivo = models.CharField(db_column='Motivo', max_length=250)
    fecha = models.DateTimeField(db_column='Fecha', auto_now_add=True)

    def __str__(self):
        return f'Ajuste en {self.idinsumo.nombreinsumo}. Motivo: {self.motivo[:30]}'

    class Meta:
        db_table = 'AjusteStock'


class Compras(models.Model):
    idcompra = models.AutoField(db_column='IdCompra', primary_key=True)
    fecha = models.DateTimeField(db_column='Fecha')
    preciototal = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        db_table = 'Compras'


class Lote(models.Model):
    idlote = models.AutoField(db_column='IdLote', primary_key=True)
    codigo = models.CharField(db_column='Codigo', max_length=50, unique=True, blank=True, null=True)
    idinsumo = models.ForeignKey(Insumo, models.DO_NOTHING, db_column='IdInsumo')
    fechaingreso = models.DateTimeField(db_column='FechaIngreso')
    fechavencimiento = models.DateField(db_column='FechaVencimiento', blank=True, null=True)
    cantidadinicial = models.DecimalField(db_column='CantidadInicial', max_digits=10, decimal_places=2)
    cantidadactual = models.DecimalField(db_column='CantidadActual', max_digits=10, decimal_places=2, default=0)

    def save(self, *args, **kwargs):
        es_nuevo = self.pk is None
        if es_nuevo and not self.codigo:
            super().save(*args, **kwargs)
            self.codigo = f'LOT-{self.pk:03d}'
            super().save(update_fields=['codigo'])
            return
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.codigo} - {self.idinsumo.nombreinsumo}'

    class Meta:
        db_table = 'Lote'


class DetalleCompra(models.Model):
    iddetallecompra = models.AutoField(db_column='IdDetalleCompra', primary_key=True)
    idcompra = models.ForeignKey(Compras, models.DO_NOTHING, db_column='IdCompra', blank=True, null=True)
    idinsumo = models.ForeignKey(Insumo, models.DO_NOTHING, db_column='IdInsumo', blank=True, null=True)
    cantidad = models.DecimalField(db_column='Cantidad', max_digits=10, decimal_places=2)
    costounitario = models.DecimalField(max_digits=12, decimal_places=4)

    class Meta:
        db_table = 'DetalleCompra'


class Receta(models.Model):
    idreceta = models.AutoField(db_column='IdReceta', primary_key=True)
    idproducto = models.ForeignKey(Producto, models.DO_NOTHING, db_column='IdProducto', blank=True, null=True)
    idinsumo = models.IntegerField(db_column='IdInsumo', blank=True, null=True)

    class Meta:
        db_table = 'Receta'


class RecetaInsumo(models.Model):
    idrecetainsumo = models.AutoField(db_column='IdRecetaInsumo', primary_key=True)
    idinsumo = models.ForeignKey(Insumo, models.DO_NOTHING, db_column='IdInsumo', blank=True, null=True)
    idreceta = models.ForeignKey(Receta, models.DO_NOTHING, db_column='IdReceta', blank=True, null=True)
    cantidadinsumo = models.DecimalField(db_column='CantidadInsumo', max_digits=10, decimal_places=2, default=0)
    es_removible = models.BooleanField(default=False)
    unidadmedida = models.CharField(db_column='UnidadMedida', max_length=20, default='unidad')

    class Meta:
        db_table = 'RecetaInsumo'


class MedioPago(models.Model):
    idmediopago = models.AutoField(db_column='IdMedioPago', primary_key=True)
    nombremetodo = models.CharField(db_column='NombreMetodo', max_length=50)

    def __str__(self):
        return self.nombremetodo

    class Meta:
        db_table = 'MedioPago'


class Cliente(models.Model):
    idcliente = models.AutoField(db_column='IdCliente', primary_key=True)
    nombre = models.CharField(db_column='Nombre', max_length=100)
    apellido = models.CharField(db_column='Apellido', max_length=100)
    telefono = models.CharField(db_column='Telefono', max_length=30, blank=True, null=True)

    def __str__(self):
        return f"{self.nombre} {self.apellido}"

    class Meta:
        db_table = 'Cliente'


class Direccion(models.Model):
    iddireccion = models.AutoField(db_column='IdDireccion', primary_key=True)
    idcliente = models.ForeignKey(Cliente, models.DO_NOTHING, db_column='IdCliente', blank=True, null=True, related_name='direcciones')
    calle = models.CharField(db_column='Calle', max_length=150)
    numero = models.CharField(db_column='Numero', max_length=20)
    piso = models.CharField(db_column='Piso', max_length=10, blank=True, null=True)
    localidad = models.CharField(db_column='Localidad', max_length=100)

    def __str__(self):
        return f"{self.calle} {self.numero}, {self.localidad}"

    class Meta:
        db_table = 'Direccion'


class EstadoPedido(models.Model):
    idestado = models.AutoField(db_column='IdEstado', primary_key=True)
    descripcion = models.CharField(db_column='Descripcion', max_length=50)

    def __str__(self):
        return self.descripcion

    class Meta:
        db_table = 'EstadoPedido'


class Pedido(models.Model):
    idpedido = models.AutoField(db_column='IdPedido', primary_key=True)
    idcliente = models.ForeignKey('Cliente', models.DO_NOTHING, db_column='IdCliente', blank=True, null=True)
    idmediopago = models.ForeignKey('MedioPago', models.DO_NOTHING, db_column='IdMedioPago', blank=True, null=True)
    idestadopedido = models.ForeignKey('EstadoPedido', models.DO_NOTHING, db_column='IdEstadoPedido', blank=True, null=True)
    horarioentregadeseado = models.TimeField(db_column='HorarioEntregaDeseado', blank=True, null=True)
    justificacioncancelacion = models.CharField(db_column='JustificacionCancelacion', max_length=250, blank=True, null=True)
    idpromocion = models.IntegerField(db_column='IdPromocion', blank=True, null=True)
    total = models.DecimalField(db_column='Total', max_digits=10, decimal_places=2, blank=True, null=True)
    fecha_creacion = models.DateTimeField(db_column='FechaCreacion', auto_now_add=True, blank=True, null=True)
    pagado = models.BooleanField(db_column='Pagado', default=False)
    stock_descontado = models.BooleanField(db_column='StockDescontado', default=False)

    def __str__(self):
        return f"Pedido #{self.idpedido}"

    class Meta:
        db_table = 'Pedido'


class DetallePedido(models.Model):
    iddetallepedido = models.AutoField(db_column='IdDetallePedido', primary_key=True)
    idpedido = models.ForeignKey(Pedido, models.DO_NOTHING, db_column='IdPedido', blank=True, null=True)
    idproducto = models.ForeignKey('Producto', models.DO_NOTHING, db_column='IdProducto', blank=True, null=True)
    cantidad = models.IntegerField(db_column='Cantidad')
    preciounitario = models.DecimalField(db_column='PrecioUnitario', max_digits=10, decimal_places=2)
    observaciones = models.CharField(db_column='Observaciones', max_length=255, blank=True, null=True)

    class Meta:
        db_table = 'DetallePedido'


class MovimientoStock(models.Model):
    TIPO_DESCUENTO = 'DESCUENTO'
    TIPO_REINTEGRO = 'REINTEGRO'
    TIPO_AJUSTE = 'AJUSTE'
    TIPO_COMPRA = 'COMPRA'

    idmovimiento = models.AutoField(db_column='IdMovimiento', primary_key=True)
    idinsumo = models.ForeignKey(Insumo, models.DO_NOTHING, db_column='IdInsumo', related_name='movimientos')
    cantidad = models.DecimalField(db_column='Cantidad', max_digits=10, decimal_places=2)
    idpedido = models.ForeignKey(Pedido, models.DO_NOTHING, db_column='IdPedido', blank=True, null=True, related_name='movimientos_stock')
    fecha = models.DateTimeField(db_column='Fecha', auto_now_add=True)
    tipomovimiento = models.CharField(db_column='TipoMovimiento', max_length=50)
    descripcion = models.CharField(db_column='Descripcion', max_length=250, blank=True, null=True)

    def __str__(self):
        return f"{self.tipomovimiento}: {self.cantidad} de {self.idinsumo.nombreinsumo} (Pedido #{self.idpedido_id})"

    class Meta:
        db_table = 'MovimientoStock'


class TipoBeneficio(models.Model):
    TIPO_PORCENTAJE = 'PORCENTAJE'
    TIPO_MONTO_FIJO = 'MONTO_FIJO'
    TIPO_SIN_VALOR = 'SIN_VALOR'

    OPCIONES_COMPORTAMIENTO = [
        (TIPO_PORCENTAJE, 'Descuento porcentual (%)'),
        (TIPO_MONTO_FIJO, 'Descuento en dinero fijo ($)'),
        (TIPO_SIN_VALOR, 'Sin valor (Ej: 2x1, Producto de regalo)'),
    ]

    idtipobeneficio = models.AutoField(primary_key=True, db_column='IdTipoBeneficio')
    codigo = models.CharField(max_length=50, null=True, blank=True, db_column='Codigo')
    nombre = models.CharField(max_length=100, db_column='Nombre')
    descripcion = models.CharField(max_length=255, blank=True, null=True, db_column='Descripcion')
    comportamiento = models.CharField(
        max_length=50,
        choices=OPCIONES_COMPORTAMIENTO,
        default=TIPO_SIN_VALOR,
        verbose_name="Comportamiento",
        db_column='comportamiento'
    )

    def __str__(self):
        return self.nombre

    class Meta:
        db_table = 'TipoBeneficio'


class Promocion(models.Model):
    idpromocion = models.AutoField(
        db_column='IdPromocion',
        primary_key=True
    )
    palabraclave = models.CharField(
        db_column='PalabraClave',
        max_length=50,
        blank=True,
        null=True
    )
    tipobeneficio = models.ForeignKey(
        'TipoBeneficio',
        on_delete=models.DO_NOTHING,
        db_column='IdTipoBeneficio',
        blank=True,
        null=True
    )
    valor = models.DecimalField(
        db_column='Valor',
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True
    )
    fechainicio = models.DateField(
        db_column='FechaInicio',
        blank=True,
        null=True
    )
    fechafin = models.DateField(
        db_column='FechaFin',
        blank=True,
        null=True
    )
    activo = models.IntegerField(
        db_column='Activo',
        blank=True,
        null=True,
        default=1
    )

    def __str__(self):
        return f"{self.palabraclave} ({self.tipobeneficio})"

    @property
    def descripcion_amigable(self):
        tipo = self.tipobeneficio.codigo if self.tipobeneficio else None
        if tipo == 'DESCUENTO_PORCENTAJE':
            return f"Descuento del {int(self.valor)}%" if self.valor else "Descuento porcentual"
        elif tipo == 'DESCUENTO_FIJO':
            return f"Descuento de ${self.valor}" if self.valor else "Descuento fijo"
        elif tipo == 'PRODUCTO_GRATIS':
            return "¡Llevá un Producto Gratis!"
        elif tipo == '2x1':
            return "Promoción 2 x 1"
        elif tipo == '3x2':
            return "Promoción 3 x 2"
        return str(self.tipobeneficio)

    class Meta:
        db_table = 'Promocion'


class ProductoPromocion(models.Model):
    idproductopromocion = models.AutoField(
        db_column='IdProductoPromocion',
        primary_key=True
    )
    idproducto = models.ForeignKey(
        Producto,
        models.DO_NOTHING,
        db_column='IdProducto',
        blank=True,
        null=True
    )
    idpromocion = models.ForeignKey(
        Promocion,
        models.DO_NOTHING,
        db_column='IdPromocion',
        blank=True,
        null=True
    )

    class Meta:
        db_table = 'ProductoPromocion'


class Permiso(models.Model):
    idpermiso = models.AutoField(
        db_column='IdPermiso',
        primary_key=True
    )
    codigo = models.CharField(
        db_column='Codigo',
        max_length=100,
        unique=True
    )
    modulo = models.CharField(
        db_column='Modulo',
        max_length=100
    )
    accion = models.CharField(
        db_column='Accion',
        max_length=50
    )
    descripcion = models.CharField(
        db_column='Descripcion',
        max_length=250,
        blank=True,
        null=True
    )

    def __str__(self):
        return f"{self.modulo} - {self.accion}"

    class Meta:
        db_table = 'Permiso'
        ordering = ['modulo', 'accion']


class RolPermiso(models.Model):
    idrolpermiso = models.AutoField(
        db_column='IdRolPermiso',
        primary_key=True
    )
    idrol = models.ForeignKey(
        Rol,
        models.CASCADE,
        db_column='IdRol',
        related_name='permisos_asignados'
    )
    idpermiso = models.ForeignKey(
        Permiso,
        models.CASCADE,
        db_column='IdPermiso',
        related_name='roles_asignados'
    )

    def __str__(self):
        return f"{self.idrol} - {self.idpermiso}"

    class Meta:
        db_table = 'RolPermiso'
        constraints = [
            models.UniqueConstraint(
                fields=['idrol', 'idpermiso'],
                name='UQ_RolPermiso_Rol_Permiso'
            )
        ]


class RegistroAuditoria(models.Model):
    idauditoria = models.AutoField(primary_key=True, db_column='IdAuditoria')
    fecha = models.DateTimeField(auto_now_add=True, db_column='Fecha')
    idempleado = models.ForeignKey(Empleado, models.SET_NULL, null=True, blank=True, db_column='IdEmpleado')
    accion = models.CharField(max_length=100, db_column='Accion')
    descripcion = models.CharField(max_length=500, db_column='Descripcion')
    ip = models.CharField(max_length=50, null=True, blank=True, db_column='IP')

    def __str__(self):
        return f"[{self.fecha:%Y-%m-%d %H:%M}] {self.accion} - {self.descripcion}"

    class Meta:
        db_table = 'RegistroAuditoria'
        ordering = ['-fecha']