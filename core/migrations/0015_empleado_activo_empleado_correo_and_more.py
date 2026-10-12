
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0014_remove_compras_idempleado_and_more'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.AddField(
                    model_name='empleado',
                    name='activo',
                    field=models.BooleanField(
                        db_column='Activo',
                        default=True,
                    ),
                ),
                migrations.AddField(
                    model_name='empleado',
                    name='correo',
                    field=models.CharField(
                        blank=True,
                        db_column='Correo',
                        max_length=254,
                        null=True,
                    ),
                ),
                migrations.AddField(
                    model_name='insumo',
                    name='descontar_stock_automaticamente',
                    field=models.BooleanField(
                        db_column='DescontarStockAutomaticamente',
                        default=False,
                    ),
                ),
                migrations.AddField(
                    model_name='recetainsumo',
                    name='unidadmedida',
                    field=models.CharField(
                        db_column='UnidadMedida',
                        default='unidad',
                        max_length=20,
                    ),
                ),
                migrations.AlterField(
                    model_name='recetainsumo',
                    name='es_removible',
                    field=models.BooleanField(default=False),
                ),
            ],
        ),
    ]
