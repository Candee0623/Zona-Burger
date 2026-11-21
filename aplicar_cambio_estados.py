"""
Quita el estado "En Preparación" (queda solo "En proceso").

Uso, desde la carpeta del proyecto (donde está manage.py):
    python aplicar_cambio_estados.py

Es seguro correrlo dos veces: lo que ya está cambiado se saltea.
"""
import os
import sys

MIGRACION = '''import unicodedata

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
'''

CAMBIOS = {
    'core/views.py': [
        (
            "    nombres_estados = [\n"
            "        'Pendiente',\n"
            "        'En Preparación',\n"
            "        'En proceso',\n",
            "    nombres_estados = [\n"
            "        'Pendiente',\n"
            "        'En proceso',\n",
        ),
        (
            "    'pendiente': {'en preparacion', 'en proceso', 'cancelado'},\n"
            "    'en preparacion': {'en proceso', 'enviado', 'entregado', 'cancelado'},\n"
            "    'en proceso': {'en preparacion', 'enviado', 'entregado', 'cancelado'},\n",
            "    'pendiente': {'en proceso', 'cancelado'},\n"
            "    'en proceso': {'enviado', 'entregado', 'cancelado'},\n",
        ),
    ],
    'core/management/commands/cargar_datos_iniciales.py': [
        (
            'for descripcion in ["Pendiente", "En Preparación", "En proceso",\n'
            '                            "Enviado", "Entregado", "Cancelado"]:',
            'for descripcion in ["Pendiente", "En proceso",\n'
            '                            "Enviado", "Entregado", "Cancelado"]:',
        ),
    ],
    'core/templates/panel/inicioPanel.html': [
        (
            '{% elif item.estado.descripcion == "En preparación" or '
            'item.estado.descripcion == "Preparando" %}',
            '{% elif item.estado.descripcion == "En proceso" %}',
        ),
        (
            '{% elif pedido.idestadopedido.descripcion == "En preparación" or '
            'pedido.idestadopedido.descripcion == "Preparando" %}',
            '{% elif pedido.idestadopedido.descripcion == "En proceso" %}',
        ),
    ],
}


def aplicar(ruta, reemplazos):
    if not os.path.exists(ruta):
        print(f'  [X] No encuentro {ruta}. ¿Estás en la carpeta del proyecto?')
        return False

    with open(ruta, 'r', encoding='utf-8', newline='') as f:
        original = f.read()

    usa_crlf = '\r\n' in original
    texto = original.replace('\r\n', '\n')
    ok = True

    for viejo, nuevo in reemplazos:
        if viejo in texto:
            texto = texto.replace(viejo, nuevo)
            print(f'  [OK] {ruta}: cambio aplicado')
        elif nuevo in texto:
            print(f'  [--] {ruta}: ya estaba cambiado')
        else:
            print(f'  [X] {ruta}: no encontré este texto, hacelo a mano:')
            print('      ' + viejo.strip().splitlines()[0][:90])
            ok = False

    if usa_crlf:
        texto = texto.replace('\n', '\r\n')

    if texto != original:
        with open(ruta, 'w', encoding='utf-8', newline='') as f:
            f.write(texto)

    return ok


def main():
    if not os.path.exists('manage.py'):
        print('Ejecutalo desde la carpeta del proyecto (donde está manage.py).')
        sys.exit(1)

    todo_ok = True
    for ruta, reemplazos in CAMBIOS.items():
        todo_ok = aplicar(ruta, reemplazos) and todo_ok

    destino = 'core/migrations/0006_unificar_estado_en_proceso.py'
    if os.path.exists(destino):
        print(f'  [--] {destino}: ya existe')
    elif not os.path.exists('core/migrations/0005_alter_cliente_apellido.py'):
        print('  [X] No existe core/migrations/0005_alter_cliente_apellido.py.')
        print('      Creá primero esa migración (la del apellido) y volvé a correr esto.')
        todo_ok = False
    else:
        with open(destino, 'w', encoding='utf-8', newline='\n') as f:
            f.write(MIGRACION)
        print(f'  [OK] {destino}: creado')

    print()
    print('Listo. Revisá con: git status' if todo_ok else
          'Terminó con avisos [X]: corregí esos puntos a mano.')


if __name__ == '__main__':
    main()