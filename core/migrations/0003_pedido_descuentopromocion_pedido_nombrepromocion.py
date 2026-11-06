from django.db import migrations, models


def completar_nombre_promocion(apps, schema_editor):
    """Pedidos históricos: copia el nombre de la promoción si todavía existe."""
    Pedido = apps.get_model('core', 'Pedido')
    Promocion = apps.get_model('core', 'Promocion')

    nombres = dict(
        Promocion.objects.exclude(palabraclave__isnull=True)
        .values_list('idpromocion', 'palabraclave')
    )

    for pedido in Pedido.objects.filter(idpromocion__isnull=False, nombrepromocion__isnull=True):
        nombre = nombres.get(pedido.idpromocion)
        if nombre:
            pedido.nombrepromocion = nombre[:100]
            pedido.save(update_fields=['nombrepromocion'])


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0002_detallepedido_nombreproducto_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='pedido',
            name='nombrepromocion',
            field=models.CharField(blank=True, db_column='NombrePromocion', max_length=100, null=True),
        ),
        migrations.AddField(
            model_name='pedido',
            name='descuentopromocion',
            field=models.DecimalField(blank=True, db_column='DescuentoPromocion', decimal_places=2, max_digits=10, null=True),
        ),
        migrations.RunPython(completar_nombre_promocion, migrations.RunPython.noop),
    ]