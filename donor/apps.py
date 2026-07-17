from django.apps import AppConfig


class DonorConfig(AppConfig):
    name = 'donor'
    
    def ready(self):
        """Register signal handlers when the app is ready."""
        from .signals import register_signals
        register_signals()
