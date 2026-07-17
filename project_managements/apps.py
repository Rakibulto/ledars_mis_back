from django.apps import AppConfig


class ProjectManagementsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "project_managements"

    def ready(self):
        import project_managements.signals  # noqa: F401
