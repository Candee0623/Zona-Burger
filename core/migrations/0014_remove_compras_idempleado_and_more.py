
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0013_remove_compras_idempleado_lote'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.RemoveField(
                    model_name='compras',
                    name='idempleado',
                ),
                migrations.AlterField(
                    model_name='recetainsumo',
                    name='cantidadinsumo',
                    field=models.DecimalField(
                        db_column='CantidadInsumo',
                        decimal_places=2,
                        default=0,
                        max_digits=10,
                    ),
                ),
                migrations.AlterField(
                    model_name='recetainsumo',
                    name='es_removible',
                    field=models.BooleanField(
                        db_column='es_removible',
                        default=False,
                    ),
                ),
                migrations.AlterField(
                    model_name='recetainsumo',
                    name='idrecetainsumo',
                    field=models.AutoField(
                        db_column='IdRecetaInsumo',
                        primary_key=True,
                        serialize=False,
                    ),
                ),
            ],
        ),
    ]
