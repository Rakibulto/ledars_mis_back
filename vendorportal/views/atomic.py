from django.db import transaction


class AtomicModelViewSetMixin:
    """Wrap every request in an atomic transaction."""

    @transaction.atomic
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)
