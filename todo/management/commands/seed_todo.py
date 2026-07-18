from datetime import date, timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from authentication.models import User
from todo.models import Todo, TodoAttachment


class Command(BaseCommand):
    help = "Seed todo module with realistic test data"

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Clear existing todo data before seeding",
        )

    def handle(self, *args, **options):
        if options["clear"]:
            self.stdout.write("Clearing existing todo data...")
            TodoAttachment.objects.all().delete()
            Todo.objects.all().delete()
            self.stdout.write("Cleared all todo data.")

        self.stdout.write("Seeding todo data...")

        users = self._get_or_create_users()
        creator = users[0]

        self._create_todos(creator, users)

        self.stdout.write(self.style.SUCCESS("Successfully seeded all todo data!"))

    def _get_or_create_users(self):
        """Ensure a set of users exist so todos can be assigned/created."""
        user_data = [
            ("leaders@leaders.com", "leaders", "Leaders1234", True),
            (
                "procurement_officer@leaders.com",
                "procurement_officer@leaders.com",
                "pass",
                False,
            ),
            (
                "finance_manager@leaders.com",
                "finance_manager@leaders.com",
                "pass",
                False,
            ),
            ("store_keeper@leaders.com", "store_keeper@leaders.com", "pass", False),
            ("hr_officer@leaders.com", "hr_officer@leaders.com", "pass", False),
        ]
        users = []
        for email, username, password, is_super in user_data:
            user, created = User.objects.get_or_create(
                email=email,
                defaults={
                    "username": username,
                    "is_superuser": is_super,
                    "is_staff": is_super,
                    "is_active": True,
                },
            )
            if created:
                user.set_password(password)
                user.save()
            users.append(user)
        return users

    def _create_todos(self, creator, users):
        today = date.today()

        todo_data = [
            {
                "todo_title": "Prepare monthly procurement report",
                "description": (
                    "<p>Compile the monthly procurement summary including "
                    "requisitions, RFQs, awards and payments for management review.</p>"
                ),
                "expected_date": today + timedelta(days=5),
                "status": "pending",
                "assign_users": [users[1], users[2]],
                "is_recurring": False,
                "recurrence_type": "none",
            },
            {
                "todo_title": "Follow up on pending vendor quotations",
                "description": (
                    "<p>Contact suppliers who have not yet submitted quotations "
                    "for the open RFQs and send reminders.</p>"
                ),
                "expected_date": today + timedelta(days=2),
                "status": "pending",
                "assign_users": [users[1]],
                "is_recurring": False,
                "recurrence_type": "none",
            },
            {
                "todo_title": "Verify GRN for office supplies delivery",
                "description": (
                    "<p>Inspect and verify the goods receipt note for the recently "
                    "delivered office supplies before payment processing.</p>"
                ),
                "expected_date": today - timedelta(days=1),
                "status": "hold",
                "assign_users": [users[3]],
                "is_recurring": False,
                "recurrence_type": "none",
            },
            {
                "todo_title": "Draft annual inventory audit plan",
                "description": (
                    "<p>Prepare the plan and checklist for the upcoming annual "
                    "physical inventory audit across all offices.</p>"
                ),
                "expected_date": today + timedelta(days=14),
                "status": "draft",
                "assign_users": [users[3]],
                "is_recurring": False,
                "recurrence_type": "none",
            },
            {
                "todo_title": "Submit finance reconciliation for Q2",
                "description": (
                    "<p>Reconcile procurement expenditures with finance records "
                    "and submit the signed reconciliation report.</p>"
                ),
                "expected_date": today - timedelta(days=3),
                "status": "completed",
                "assign_users": [users[2]],
                "is_recurring": False,
                "recurrence_type": "none",
            },
            {
                "todo_title": "Daily team stand-up meeting",
                "description": (
                    "<p>Short daily sync with the procurement team to review "
                    "priorities and blockers.</p>"
                ),
                "expected_date": today + timedelta(days=1),
                "status": "pending",
                "assign_users": [users[1], users[3]],
                "is_recurring": True,
                "recurrence_type": "daily",
            },
            {
                "todo_title": "Weekly procurement status review",
                "description": (
                    "<p>Weekly review of all open requisitions, work orders and "
                    "payment requests with department heads.</p>"
                ),
                "expected_date": today + timedelta(days=7),
                "status": "pending",
                "assign_users": [users[1], users[2]],
                "is_recurring": True,
                "recurrence_type": "weekly",
                "recurrence_weekdays": [0],  # Monday
            },
            {
                "todo_title": "Monthly vendor performance evaluation",
                "description": (
                    "<p>Evaluate vendor performance for the previous month and "
                    "update vendor scorecards.</p>"
                ),
                "expected_date": today + timedelta(days=30),
                "status": "pending",
                "assign_users": [users[1]],
                "is_recurring": True,
                "recurrence_type": "monthly",
                "recurrence_day_of_month": 1,
            },
        ]

        created = 0
        for data in todo_data:
            assign_users = data.pop("assign_users", [])
            recurrence_type = data.get("recurrence_type", "none")
            expected_date = data.get("expected_date")

            # Calculate next_expected_date for recurring todos
            next_expected_date = None
            if data.get("is_recurring") and expected_date and recurrence_type != "none":
                if recurrence_type == "daily":
                    next_expected_date = expected_date + timedelta(days=1)
                elif recurrence_type == "weekly":
                    next_expected_date = expected_date + timedelta(days=7)
                elif recurrence_type == "monthly":
                    from dateutil.relativedelta import relativedelta

                    next_expected_date = expected_date + relativedelta(months=1)

            todo, _ = Todo.objects.get_or_create(
                todo_title=data["todo_title"],
                creator=creator,
                defaults={
                    "description": data.get("description"),
                    "expected_date": expected_date,
                    "status": data["status"],
                    "is_recurring": data.get("is_recurring", False),
                    "recurrence_type": recurrence_type,
                    "recurrence_weekdays": data.get("recurrence_weekdays"),
                    "recurrence_day_of_month": data.get("recurrence_day_of_month"),
                    "next_expected_date": next_expected_date,
                    "creator_name": creator.username,
                    "creator_email": creator.email,
                    "creator_user_id": creator.id,
                },
            )
            if assign_users:
                todo.assign_users.set(assign_users)
            created += 1

        self.stdout.write(f"  Created {created} todos")
