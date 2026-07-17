from django.dispatch import Signal
import threading
from django.db.models.signals import post_migrate, post_save, post_delete
from django.dispatch import receiver
from django.db.backends.signals import connection_created
from django.apps import apps
from .models import User
from employee.models import Employee


@receiver(connection_created)
def set_sqlite_wal_mode(sender, connection, **kwargs):
    """Enable WAL journal mode for SQLite to reduce lock contention."""
    if connection.vendor == "sqlite":
        connection.cursor().execute("PRAGMA journal_mode=WAL;")


@receiver(post_save, sender=User)
def create_employee_on_user_create(sender, instance, created, **kwargs):
    if created:
        user = instance
        # Skip creating Employee for Vendor users
        if user.role and user.role.name.lower() == "vendor":
            return

        Employee.objects.create(
            user=user,
            employee_name=user.username,
            personal_email_id=user.email,
        )


@receiver(post_save, sender=User)
def delete_employee_for_vendor_role(sender, instance, created, **kwargs):
    if instance.role and instance.role.name.lower() == "vendor":
        Employee.objects.filter(user=instance).delete()


post_import_completed = Signal()


def hash_passwords_in_background(user_pks_and_passwords):
    """
    This function contains the slow logic and will be run in a separate thread.
    """

    users_to_update = []
    user_ids = [pk for pk, password in user_pks_and_passwords]

    # Fetch all users in one query
    users = User.objects.filter(pk__in=user_ids)
    user_map = {user.pk: user for user in users}

    for user_pk, plain_password in user_pks_and_passwords:
        user = user_map.get(user_pk)
        if user:
            user.set_password(plain_password)
            users_to_update.append(user)

    if users_to_update:
        User.objects.bulk_update(users_to_update, ["password"])


@receiver(post_import_completed)
def on_post_import(sender, user_pks_and_passwords, **kwargs):
    """
    This receiver listens for the signal and starts the background thread.
    """
    # The 'target' is the function to run.
    # The 'args' is a tuple of arguments to pass to that function.
    thread = threading.Thread(
        target=hash_passwords_in_background, args=(user_pks_and_passwords,)
    )
    # This makes the thread a "daemon," meaning it won't block the main program from exiting.
    thread.daemon = True
    thread.start()
