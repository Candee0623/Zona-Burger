from django.db import models

class Categoria(models.Model):
    idcategoria = models.AutoField(db_column='IdCategoria', primary_key=True)
    nombre = models.CharField(db_column='Nombre', max_length=100, db_collation='Modern_Spanish_CI_AS')

    def __str__(self):
        return self.nombre

    class Meta:
        db_table = 'Categoria'


class Extras(models.Model):
    idextra = models.AutoField(db_column='IdExtra', primary_key=True)
    nombre = models.CharField(db_column='Nombre', max_length=100, db_collation='Modern_Spanish_CI_AS')
    precio = models.DecimalField(db_column='Precio', max_digits=10, decimal_places=2, default=0.00)

    def __str__(self):
        return f"{self.nombre} (+${self.precio})"

    class Meta:
        db_table = 'Extras'


class Producto(models.Model):
    idproducto = models.AutoField(db_column='IdProducto', primary_key=True)
    nombre = models.CharField(db_column='Nombre', max_length=100, db_collation='Modern_Spanish_CI_AS')
    descripcion = models.CharField(db_column='Descripcion', max_length=255, db_collation='Modern_Spanish_CI_AS', blank=True, null=True)
    precio = models.DecimalField(db_column='Precio', max_digits=10, decimal_places=2)
    imagen = models.CharField(db_column='Imagen', max_length=255, db_collation='Modern_Spanish_CI_AS', blank=True, null=True)
    idcategoria = models.ForeignKey(Categoria, models.DO_NOTHING, db_column='IdCategoria')

    extras = models.ManyToManyField(
        Extras,
        through='ProductoExtras',
        through_fields=('idproducto', 'idextra'),
        related_name='productos'
    )

    def __str__(self):
        return self.nombre

    class Meta:
        db_table = 'Producto'


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
    nombre = models.CharField(db_column='Nombre', max_length=100, db_collation='Modern_Spanish_CI_AS')
    precio_adicional = models.DecimalField(db_column='PrecioAdicional', max_digits=10, decimal_places=2, default=0.00)

    def __str__(self):
        return f"{self.nombre}"

    class Meta:
        db_table = 'Opcion'


class ProductoGrupoOpcion(models.Model):
    id = models.AutoField(db_column='IdProductoGrupo', primary_key=True)
    idproducto = models.ForeignKey(Producto, models.DO_NOTHING, db_column='IdProducto')
    idgrupo = models.ForeignKey(GrupoOpcion, models.DO_NOTHING, db_column='IdGrupo')

    def __str__(self):
        return f"{self.idgrupo.nombre} - {self.idproducto.nombre}"

    class Meta:
        db_table = 'ProductoGrupoOpcion'
        unique_together = (('idproducto', 'idgrupo'),)