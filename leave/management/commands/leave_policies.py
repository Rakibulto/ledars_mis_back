from django.core.management.base import BaseCommand
from leave.models import LeavePolicy, LeaveGroup

class Command(BaseCommand):
    help = 'Seed unique Leave Policies per group, skipping duplicates within group'

    def handle(self, *args, **kwargs):
        general_leave_types = [
            ("Medical Leave", 0),
            ("Casual Leave", 1),
            ("Maternity Leave", 30),
            ("Paternity Leave", 7),
            ("Annual Leave", 10),
            ("Compensatory Leave", 0),
            ("Duty Leave / On-Duty", 1),
            ("Bereavement Leave", 0),
            ("Emergency Leave", 0),
        ]

        teacher_leave_types = [
            ("Medical Leave", 0),
            ("Casual Leave", 1),
            ("Maternity Leave", 30),
            ("Paternity Leave", 7),
            ("Bereavement Leave", 0),
            ("Duty Leave / On-Duty", 1),
            ("Study Leave", 1),
        ]

        group_policy_map = {
            'General Staff (Probation)': general_leave_types,
            'General Staff (Regular)': general_leave_types,
            'Teachers (Probation)': teacher_leave_types,
            'Teachers (Regular)': teacher_leave_types,
        }

        for group_name, leave_types in group_policy_map.items():
            try:
                group = LeaveGroup.objects.get(name=group_name)
            except LeaveGroup.DoesNotExist:
                self.stdout.write(self.style.ERROR(f"LeaveGroup '{group_name}' not found."))
                continue

            for leave_name, apply_days in leave_types:
                # Check if a policy with same name already exists for this group
                existing_policies = LeavePolicy.objects.filter(
                    leave_type_name=leave_name,
                    leave_groups=group
                )

                if existing_policies.exists():
                    self.stdout.write(self.style.WARNING(
                        f"Policy '{leave_name}' already exists for '{group_name}' — skipped."
                    ))
                    continue

                validity_days = 30 if leave_name == "Compensatory Leave" else 0

                policy = LeavePolicy.objects.create(
                    leave_type_name=leave_name,
                    apply_before_days=apply_days,
                    gender="any",
                    effective_from="joining",
                    total_leave_days=1,
                    max_days_per_request=30,
                    min_days_per_request=1,
                    allow_half_day=True,
                    count_holidays=False,
                    count_weekends=False,
                    is_active=True,
                    validity=validity_days
                )
                policy.leave_groups.add(group)

                self.stdout.write(self.style.SUCCESS(
                    f"Created '{leave_name}' policy for '{group_name}'"
                ))
