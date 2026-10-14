import decimal
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0016_permiso_alter_empleado_options_rolpermiso'),
    ]

    operations = [
        migrations.AddField(
            model_name='opcion',
            name='idinsumo',
            field=models.ForeignKey(
                blank=True,
                db_column='IdInsumo',
                null=True,
                on_delete=django.db.models.deletion.DO_NOTHING,
                related_name='opciones',
                to='core.insumo',
            ),
        ),
        migrations.AddField(
            model_name='opcion',
            name='cantidad_insumo',
            field=models.DecimalField(
                db_column='CantidadInsumo',
                decimal_places=2,
                default=decimal.Decimal('1.00'),
                max_digits=10,
            ),
        ),
        migrations.AddField(
            model_name='pedido',
            name='stock_descontado',
            field=models.BooleanField(
                db_column='StockDescontado',
                default=False,
            ),
        ),
        migrations.CreateModel(
            name='MovimientoStock',
            fields=[
                ('idmovimiento', models.AutoField(db_column='IdMovimiento', primary_key=True, serialize=False)),
                ('cantidad', models.DecimalField(db_column='Cantidad', decimal_places=2, max_digits=10)),
                ('fecha', models.DateTimeField(auto_now_add=True, db_column='Fecha')),
                ('tipomovimiento', models.CharField(db_column='TipoMovimiento', max_length=50)),
                ('descripcion', models.CharField(blank=True, db_column='Descripcion', max_length=250, null=True)),
                ('idinsumo', models.ForeignKey(db_column='IdInsumo', on_delete=django.db.models.deletion.DO_NOTHING, related_name='movimientos', to='core.insumo')),
                ('idpedido', models.ForeignKey(blank=True, db_column='IdPedido', null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='movimientos_stock', to='core.pedido')),
            ],
            options={
                'db_table': 'MovimientoStock',
            },
        ),
    ]
