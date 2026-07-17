from django.core.management.base import BaseCommand
from django.contrib.auth.models import Permission
from authentication.models import User, Role
from django.db import transaction


class Command(BaseCommand):
    help = "Seeds permissions for all users with Employee role"

    def handle(self, *args, **options):
        """
        This command assigns specific permissions to all users with 'Employee' role.
        """
        # Employee role permissions
        permissions_code_names = [
            "view_leaverequest",
            "change_leaverequest",
            "add_leaverequest",
            "view_own_attendance",
            "add_attendancedata",
            "view_attendanceadjustmentrequest",
            "add_attendanceadjustmentrequest",
            "change_attendanceadjustmentrequest",
        ]

        try:
            # Get the Employee role
            employee_role = Role.objects.get(name="Employee")
            self.stdout.write(self.style.SUCCESS(f"Found role: {employee_role.name}"))
        except Role.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(
                    "Employee role does not exist. Please create it first."
                )
            )
            return

        # Get all permissions by codename
        permissions = Permission.objects.filter(codename__in=permissions_code_names)

        if not permissions.exists():
            self.stdout.write(
                self.style.ERROR("No permissions found with the specified codenames.")
            )
            return

        self.stdout.write(
            self.style.SUCCESS(f"Found {permissions.count()} permissions to assign:")
        )
        for perm in permissions:
            self.stdout.write(f"  - {perm.codename}: {perm.name}")

        # Get all users with Employee role
        employee_users = User.objects.filter(role=employee_role)

        if not employee_users.exists():
            self.stdout.write(self.style.WARNING("No users found with Employee role."))
            return

        self.stdout.write(
            self.style.SUCCESS(
                f"\nFound {employee_users.count()} users with Employee role"
            )
        )

        # Assign permissions to each employee user
        updated_count = 0
        with transaction.atomic():
            for user in employee_users:
                # Set permissions (this replaces existing permissions)
                user.user_permissions.set(permissions)
                updated_count += 1
                self.stdout.write(f"  ✓ Updated permissions for: {user.email}")

        self.stdout.write(
            self.style.SUCCESS(
                f"\n✓ Successfully assigned permissions to {updated_count} Employee users!"
            )
        )

        # Show summary
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write(self.style.SUCCESS("SUMMARY"))
        self.stdout.write("=" * 60)
        self.stdout.write(f"Role: Employee")
        self.stdout.write(f"Users Updated: {updated_count}")
        self.stdout.write(f"Permissions Assigned: {permissions.count()}")
        self.stdout.write("=" * 60)
