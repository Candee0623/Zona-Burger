import unicodedata

from django.db import migrations


def _norm(texto):
    texto = unicodedata.normalize('NFD', texto or '')
    sin_tildes = ''.join(c for c in texto if unicodedata.category(c) != 'Mn')
    return sin_tildes.strip().lower()


def unificar_estados(apps, schema_editor):
    """
    Elimina el estado "En Preparación": los pedidos que lo tenían pasan a
    "En proceso". Si "En proceso" no existe todavía, se renombra el estado
    viejo para no perder ningún pedido.
    """
    EstadoPedido = apps.get_model('core', 'EstadoPedido')
    Pedido = apps.get_model('core', 'Pedido')

    preparacion = None
    proceso = None
    for estado in EstadoPedido.objects.all():
        nombre = _norm(estado.descripcion)
        if nombre == 'en preparacion':
            preparacion = estado
        elif nombre == 'en proceso':
            proceso = estado

    if preparacion is None:
        return  # Nada que unificar.

    if proceso is None:
        preparacion.descripcion = 'En proceso'
        preparacion.save(update_fields=['descripcion'])
        return

    Pedido.objects.filter(idestadopedido=preparacion).update(idestadopedido=proceso)
    preparacion.delete()


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0005_alter_cliente_apellido'),
    ]

    operations = [
        # Sin reversa: no se puede saber qué pedidos eran "En Preparación".
        migrations.RunPython(unificar_estados, migrations.RunPython.noop),
    ]
