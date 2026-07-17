from django.apps import AppConfig


class InventoryConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'inventory'

    def ready(self):
        import inventory.signals  # noqa: F401
        self._configure_sqlite_wal()

    @staticmethod
    def _configure_sqlite_wal():
        """Connect WAL-mode PRAGMA handler for SQLite once the app is ready."""
        from django.db.backends.signals import connection_created

        def _apply_wal(sender, connection, **kwargs):
            if connection.vendor == 'sqlite':
                with connection.cursor() as cursor:
                    cursor.execute('PRAGMA journal_mode=WAL;')
                    cursor.execute('PRAGMA synchronous=NORMAL;')
                    cursor.execute('PRAGMA busy_timeout=20000;')

        connection_created.connect(_apply_wal, weak=False)

