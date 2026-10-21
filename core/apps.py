from django.apps import AppConfig


class CoreConfig(AppConfig):
    name = 'core'

    def ready(self):
        from django.db.backends.signals import connection_created

        def configure_sqlite(sender, connection, **kwargs):
            if connection.vendor == 'sqlite':
                try:
                    with connection.cursor() as cursor:
                        cursor.execute("PRAGMA journal_mode = WAL;")
                        cursor.execute("PRAGMA synchronous = NORMAL;")
                        cursor.execute("PRAGMA busy_timeout = 30000;")
                except Exception:
                    pass

        connection_created.connect(configure_sqlite)
