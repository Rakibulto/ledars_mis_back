import random
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand
from django.contrib.auth.hashers import make_password
from django.core.management import call_command
from authentication.models import User, Role
from employee.models import Employee, Department, Designation, Branch
from shift.models import Shift


class Command(BaseCommand):
    help = (
        "Creates test users with employees, assigns shifts, and seeds attendance data"
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--count",
            type=int,
            default=10,
            help="Number of test users to create (default: 10)",
        )
        parser.add_argument(
            "--clean",
            action="store_true",
            help="Clean/delete all test users and their related data",
        )

    def handle(self, *args, **kwargs):
        if kwargs["clean"]:
            self.clean_test_users()
            return

        count = kwargs["count"]
        self.stdout.write(self.style.SUCCESS(f"Creating {count} test users..."))

        try:
            # Ensure required data exists
            self.ensure_basic_data()

            # Create test users
            test_users = self.create_test_users(count)

            # Create employees for test users
            test_employees = self.create_employees_for_users(test_users)

            # Assign shifts to employees
            self.assign_shifts_to_employees(test_employees)

            # Seed attendance for test users
            self.seed_attendance_for_test_users(test_employees)

            self.stdout.write(
                self.style.SUCCESS(
                    f"Successfully created {count} test users with complete data! 🎉"
                )
            )

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error creating test users: {str(e)}"))
            import traceback

            traceback.print_exc()
            raise

    def ensure_basic_data(self):
        """Ensure basic data like roles, departments, etc. exist"""
        self.stdout.write("Ensuring basic data exists...")

        # Ensure roles exist
        roles = ["Admin", "Supervisor", "Employee"]
        for role_name in roles:
            Role.objects.get_or_create(name=role_name)

        # Ensure departments exist
        departments = ["IT", "HR", "Finance", "Operations", "Marketing"]
        for dept_name in departments:
            Department.objects.get_or_create(name=dept_name)

        # Ensure branches exist
        branches = ["Main Office", "Branch A", "Branch B"]
        for branch_name in branches:
            Branch.objects.get_or_create(name=branch_name)

        # Ensure shifts exist (call the shift seeder if needed)
        if not Shift.objects.exists():
            try:
                call_command("seed_shifts")
            except:
                self.stdout.write(
                    self.style.WARNING("Could not run seed_shifts command")
                )

        self.stdout.write(self.style.SUCCESS("Basic data ensured."))

    def create_test_users(self, count):
        """Create test users with unique emails"""
        self.stdout.write(f"Creating {count} test users...")

        test_users = []
        roles = list(Role.objects.all())

        for i in range(count):
            email = f"testuser{i+1}@Ledar's.org"
            username = f"testuser{i+1}"

            # Skip if user already exists
            if User.objects.filter(email=email).exists():
                self.stdout.write(f"Test user {email} already exists, skipping...")
                continue

            # Random role (mostly employees, some supervisors)
            role = random.choice(roles + [roles[0]] * 3)  # Bias towards Employee role

            user = User.objects.create(
                email=email,
                username=username,
                password=make_password("testpass123"),
                role=role,
                is_active=True,
                is_staff=False,
            )

            test_users.append(user)
            if (len(test_users) + 1) % 10 == 0:
                self.stdout.write(f"Created {len(test_users)} test users...")

        self.stdout.write(self.style.SUCCESS(f"Created {len(test_users)} test users."))
        return test_users

    def create_employees_for_users(self, users):
        """Create employee records for test users"""
        self.stdout.write(f"Creating employees for {len(users)} test users...")

        employees = []
        departments = list(Department.objects.all())
        branches = list(Branch.objects.all())
        designations = []

        # Create some designations if they don't exist
        dept_designations = {
            "IT": ["Software Engineer", "System Administrator", "IT Support"],
            "HR": ["HR Manager", "HR Executive", "Recruiter"],
            "Finance": ["Accountant", "Financial Analyst", "Finance Manager"],
            "Operations": ["Operations Manager", "Operations Executive"],
            "Marketing": ["Marketing Manager", "Marketing Executive"],
        }

        for dept in departments:
            for designation_name in dept_designations.get(dept.name, ["Executive"]):
                designation, _ = Designation.objects.get_or_create(
                    department=dept, name=designation_name
                )
                designations.append(designation)

        for user in users:
            # Delete any existing employee for this user first
            Employee.objects.filter(user=user).delete()

            department = random.choice(departments)
            designation = random.choice(
                [d for d in designations if d.department == department]
            )
            branch = random.choice(branches)

            employee = Employee.objects.create(
                user=user,
                employee_id=f"TEST{user.id:04d}",
                employee_name=f"Test User {user.id}",
                department=department,
                designation=designation,
                location=branch,
                joining_date=datetime(2024, 1, 1).date(),
                status="active",
            )

            employees.append(employee)

        self.stdout.write(
            self.style.SUCCESS(f"Created {len(employees)} employee records.")
        )
        return employees

    def assign_shifts_to_employees(self, employees):
        """Assign random shifts to employees"""
        self.stdout.write(f"Assigning shifts to {len(employees)} employees...")

        shifts = list(Shift.objects.all())
        if not shifts:
            self.stdout.write(
                self.style.WARNING("No shifts found, skipping shift assignment")
            )
            return

        for employee in employees:
            shift = random.choice(shifts)
            employee.office_time = shift
            employee.save(update_fields=["office_time"])

        self.stdout.write(
            self.style.SUCCESS(f"Assigned shifts to {len(employees)} employees.")
        )

    def seed_attendance_for_test_users(self, employees):
        """Seed attendance data for test employees"""
        self.stdout.write(f"Seeding attendance for {len(employees)} test employees...")

        from attendance.models import AttendanceHistory, AttendanceData
        from datetime import datetime, timedelta

        # Seed attendance for the last 7 working days only (more realistic for testing)
        end_date = datetime.now().date()
        start_date = end_date - timedelta(
            days=10
        )  # 10 days back to ensure we get working days

        attendance_created = 0
        for employee in employees:
            for date in [
                start_date + timedelta(days=i)
                for i in range((end_date - start_date).days + 1)
            ]:
                # Skip weekends if needed (optional)
                if date.weekday() >= 5:  # Saturday = 5, Sunday = 6
                    continue

                # Create attendance history record
                attendance, created = AttendanceHistory.objects.get_or_create(
                    employee=employee,
                    date=date,
                    defaults={
                        "status": "Present",
                        "check_in_time": datetime.combine(
                            date, datetime.strptime("09:00", "%H:%M").time()
                        ),
                        "check_out_time": datetime.combine(
                            date, datetime.strptime("18:00", "%H:%M").time()
                        ),
                        "is_late": False,
                        "late_by": timedelta(0),
                        "rfid_or_machine_code": f"TEST{employee.pk}",
                        "device_serial_number": "TEST_DEVICE",
                    },
                )
                if created:
                    attendance_created += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully seeded {attendance_created} attendance records for test employees (last 7 working days)."
            )
        )

    def clean_test_users(self):
        """Clean/delete all test users and their related data"""
        self.stdout.write(self.style.WARNING("Cleaning test users and related data..."))

        # Find test users (users with email starting with 'testuser' and ending with '@Ledar's.org')
        test_users = User.objects.filter(
            email__startswith="testuser", email__endswith="@Ledar's.org"
        )

        # Also find orphaned employees (employees with test user names)
        orphaned_employees = Employee.objects.filter(
            employee_name__startswith="testuser"
        )

        total_to_clean = len(test_users) + len(orphaned_employees)

        if total_to_clean == 0:
            self.stdout.write(
                self.style.SUCCESS(
                    "No test users or orphaned employees found to clean."
                )
            )
            return

        self.stdout.write(
            f"Found {len(test_users)} test users and {len(orphaned_employees)} orphaned employees to clean."
        )

        # Delete related data first
        for user in test_users:
            # Delete attendance history
            from attendance.models import AttendanceHistory, AttendanceData

            AttendanceHistory.objects.filter(employee__user=user).delete()
            AttendanceData.objects.filter(employee__user=user).delete()

            # Delete employee
            Employee.objects.filter(user=user).delete()

        # Delete orphaned employees and their attendance data
        for employee in orphaned_employees:
            AttendanceHistory.objects.filter(employee=employee).delete()
            AttendanceData.objects.filter(employee=employee).delete()
            employee.delete()

        # Delete users
        test_users.delete()

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully cleaned {total_to_clean} test users/employees and all related data. 🧹"
            )
        )
