from django.apps import AppConfig
from django.db import connections
from django.db.models.signals import post_migrate


def _sincronizar_permisos(sender, using='default', **kwargs):
    from core.models import Permiso, Rol, RolPermiso
    from core.permisos_config import sincronizar_permisos

    tablas = set(connections[using].introspection.table_names())
    necesarias = {Permiso._meta.db_table, Rol._meta.db_table, RolPermiso._meta.db_table}
    if necesarias <= tablas:
        sincronizar_permisos()


class CoreConfig(AppConfig):
    name = 'core'

    def ready(self):
        post_migrate.connect(_sincronizar_permisos, sender=self)
