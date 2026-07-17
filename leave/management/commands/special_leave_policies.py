from django.core.management.base import BaseCommand
from leave.models import SpecialLeavePolicy, LeavePolicy, LeaveGroup

class Command(BaseCommand):
    help = 'Seed Special Leave Policies based on leave types and their available policies'

    def handle(self, *args, **kwargs):
        # Define the mapping of leave types to their available policies as per the PDF
        special_leave_mapping = {
            "Medical Leave": [
                "Medical Leave",
                "Bereavement Leave",
                "Emergency Leave",
                "Duty Leave / On-Duty",
                "Compensatory Leave"
            ],
            "Casual Leave": [
                "Casual Leave",
                "Bereavement Leave",
                "Emergency Leave",
                "Duty Leave / On-Duty",
                "Compensatory Leave" "Duty Leave / On-Duty",
            ],
            "Maternity Leave": [
                "Maternity Leave",
                "Bereavement Leave",
                "Emergency Leave",
                "Duty Leave / On-Duty",
                "Compensatory Leave"
            ],
            "Paternity Leave": [
                "Paternity Leave",
                "Bereavement Leave",
                "Emergency Leave",
                "Duty Leave / On-Duty",
                "Compensatory Leave"
            ],
            "Annual Leave": [
                "Annual Leave",
                "Bereavement Leave",
                "Emergency Leave",
                "Duty Leave / On-Duty",
                "Compensatory Leave"
            ],
            "Compensatory Leave": [
                "Compensatory Leave",
                "Bereavement Leave",
                "Emergency Leave",
                "Duty Leave / On-Duty"
            ],
            "Duty Leave / On-Duty": [
                "Duty Leave / On-Duty",
                "Casual Leave",
                "Bereavement Leave",
                "Emergency Leave",
                "Compensatory Leave",
                "Study Leave",
                "Annual Leave",
                "Paternity Leave",
                "Maternity Leave",
                "Medical Leave"
            ],
            "Bereavement Leave": [
                "Bereavement Leave",
                "Emergency Leave",
                "Duty Leave / On-Duty",
                "Compensatory Leave"
            ],
            "Emergency Leave": [
                "Emergency Leave",
                "Bereavement Leave",
                "Duty Leave / On-Duty",
                "Compensatory Leave"
            ],
            "Study Leave": [
                "Study Leave",
                "Bereavement Leave", "Duty Leave / On-Duty",
                "Emergency Leave",
                "Duty Leave / On-Duty",
                "Compensatory Leave"
            ]
        }

        # Iterate through all LeaveGroup objects
        for group in LeaveGroup.objects.all():
            # Get leave policies associated with the current group
            group_policies = LeavePolicy.objects.filter(leave_groups=group)

            for leave_type, available_policy_names in special_leave_mapping.items():
                # Find the LeavePolicy for the current leave_type and group
                try:
                    leave_policy = group_policies.get(leave_type_name=leave_type)
                except LeavePolicy.DoesNotExist:
                    self.stdout.write(self.style.WARNING(
                        f"LeavePolicy '{leave_type}' not found for group '{group.name}'. Skipping."
                    ))
                    continue

                # Check if SpecialLeavePolicy already exists for this leave_policy
                if SpecialLeavePolicy.objects.filter(leave_policy=leave_policy).exists():
                    self.stdout.write(self.style.WARNING(
                        f"SpecialLeavePolicy for '{leave_type}' in group '{group.name}' already exists. Skipping."
                    ))
                    continue

                # Create a new SpecialLeavePolicy
                special_policy = SpecialLeavePolicy.objects.create(
                    leave_policy=leave_policy
                )

                # Add available policies to the SpecialLeavePolicy
                for policy_name in available_policy_names:
                    try:
                        available_policy = group_policies.get(leave_type_name=policy_name)
                        special_policy.available_policies.add(available_policy)
                    except LeavePolicy.DoesNotExist:
                        self.stdout.write(self.style.WARNING(
                            f"Available policy '{policy_name}' not found for group '{group.name}'. Skipping."
                        ))

                self.stdout.write(self.style.SUCCESS(
                    f"Created SpecialLeavePolicy for '{leave_type}' in group '{group.name}' with {special_policy.available_policies.count()} available policies."
                ))