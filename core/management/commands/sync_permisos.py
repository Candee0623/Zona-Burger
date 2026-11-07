from django.core.management.base import BaseCommand

from core.permisos_config import sincronizar_permisos


class Command(BaseCommand):
    help = 'Crea o actualiza los permisos del sistema a partir de las vistas y el catálogo.'

    def handle(self, *args, **options):
        resultado = sincronizar_permisos()
        self.stdout.write(self.style.SUCCESS(
            f"{len(resultado['nuevos'])} permisos nuevos, {resultado['total']} en total."
        ))
        if resultado['sin_vista']:
            self.stdout.write(self.style.WARNING(
                'Permisos que ninguna vista exige todavía: ' + ', '.join(resultado['sin_vista'])
            ))
        if resultado['sin_uso']:
            self.stdout.write(self.style.WARNING(
                'Permisos en la base que ya no existen en el sistema: ' + ', '.join(resultado['sin_uso'])
            ))
