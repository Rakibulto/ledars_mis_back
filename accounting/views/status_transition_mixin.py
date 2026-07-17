from django.utils import timezone
from rest_framework.decorators import action
from rest_framework.response import Response


class StatusTransitionMixin:
    """Generic status transition endpoint for transaction viewsets."""

    status_field_name = "status"

    def _get_status_choices(self, instance):
        return list(getattr(instance.__class__, "STATUS_CHOICES", []) or [])

    def _get_status_display_map(self, instance):
        return {
            str(value).lower(): label
            for value, label in self._get_status_choices(instance)
        }

    def _get_status_code_map(self, instance):
        return {
            str(value).lower(): value
            for value, _label in self._get_status_choices(instance)
        }

    def _get_auto_update_fields(self, instance):
        update_fields = [self.status_field_name]
        for field in instance._meta.fields:
            if getattr(field, "auto_now", False) and field.name not in update_fields:
                update_fields.append(field.name)
        return update_fields

    def _get_legal_status_transitions(self, instance):
        choices = self._get_status_choices(instance)
        status_map = self._get_status_code_map(instance)
        current_value = getattr(instance, self.status_field_name, None)
        current_key = str(current_value).lower() if current_value is not None else ""
        current_index = next(
            (
                index
                for index, (value, _label) in enumerate(choices)
                if str(value).lower() == current_key
            ),
            None,
        )

        if instance.__class__.__name__ == "Bill":
            if current_key == "pending":
                return [status_map[key] for key in ("draft", "approved", "cancelled") if key in status_map]
            if current_key == "overdue":
                return [status_map[key] for key in ("approved", "cancelled") if key in status_map]
            if current_key in {"paid", "cancelled"}:
                return []
            if current_key == "draft":
                return [status_map[key] for key in ("pending", "cancelled") if key in status_map]

        if instance.__class__.__name__ == "CustomerInvoice":
            if current_key == "draft":
                return [status_map[key] for key in ("sent", "cancelled") if key in status_map]
            if current_key == "sent":
                return [
                    status_map[key]
                    for key in ("posted", "cancelled")
                    if key in status_map
                ]
            if current_key == "posted":
                return [status_map[key] for key in ("paid", "cancelled") if key in status_map]
            if current_key == "partial":
                return [status_map[key] for key in ("paid", "cancelled") if key in status_map]
            if current_key == "overdue":
                return [status_map[key] for key in ("sent", "cancelled") if key in status_map]
            if current_key in {"paid", "cancelled"}:
                return []

        if current_key in {"cancelled", "voided"}:
            return []

        transitions = []

        if current_key == "overdue":
            if "sent" in status_map:
                transitions.append(status_map["sent"])
            for terminal_key in ("cancelled", "voided"):
                if terminal_key in status_map:
                    transitions.append(status_map[terminal_key])
            return list(dict.fromkeys(transitions))

        if current_key in {"paid", "posted", "reconciled"}:
            for terminal_key in ("cancelled", "voided"):
                if terminal_key in status_map:
                    transitions.append(status_map[terminal_key])
            return list(dict.fromkeys(transitions))

        if current_index is not None:
            next_index = current_index + 1
            if next_index < len(choices):
                transitions.append(choices[next_index][0])

        for terminal_key in ("cancelled", "voided"):
            if terminal_key in status_map and status_map[terminal_key] not in transitions:
                transitions.append(status_map[terminal_key])

        return list(dict.fromkeys(transitions))

    def _append_status_chatter(self, instance, old_status, new_status):
        chatter = getattr(instance, "chatter", None)
        if chatter is None or not hasattr(chatter, "create"):
            return

        display_map = self._get_status_display_map(instance)
        old_label = display_map.get(str(old_status).lower(), old_status)
        new_label = display_map.get(str(new_status).lower(), new_status)

        try:
            chatter.create(
                author="System",
                message=f"Status changed from {old_label} to {new_label}",
                message_type="system",
                time_label=timezone.now().strftime("%d %b, %H:%M"),
            )
        except Exception:
            return

    @action(detail=True, methods=["patch"], url_path="status")
    def status(self, request, pk=None):
        instance = self.get_object()
        new_status = request.data.get("status")
        if not new_status:
            return Response({"error": "status is required."}, status=400)

        status_map = self._get_status_code_map(instance)
        normalized_status = str(new_status).lower()
        if normalized_status not in status_map:
            return Response({"error": "Invalid status."}, status=400)

        legal_transitions = self._get_legal_status_transitions(instance)
        target_status = status_map[normalized_status]
        current_status = getattr(instance, self.status_field_name)
        if target_status == current_status:
            serializer = self.get_serializer(instance)
            return Response(serializer.data)

        legal_normalized = {str(value).lower() for value in legal_transitions}
        if normalized_status not in legal_normalized:
            return Response(
                {
                    "error": (
                        f"Transition from {current_status} to {target_status} is not allowed."
                    )
                },
                status=400,
            )

        setattr(instance, self.status_field_name, target_status)
        instance.save(update_fields=self._get_auto_update_fields(instance))
        self._append_status_chatter(instance, current_status, target_status)

        serializer = self.get_serializer(instance)
        return Response(serializer.data)