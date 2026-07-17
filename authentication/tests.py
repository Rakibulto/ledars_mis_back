from django.test import TestCase

from authentication.models import Role, User
from employee.models import Employee


class VendorUserEmployeeTests(TestCase):
    def test_vendor_user_creation_does_not_create_employee(self):
        vendor_role, _ = Role.objects.get_or_create(name="Vendor")

        user = User.objects.create_user(
            email="vendor1@example.com",
            username="vendor1",
            password="pass123",
            role=vendor_role,
            is_active=True,
        )

        self.assertEqual(user.role.name, "Vendor")
        self.assertFalse(Employee.objects.filter(user=user).exists())

    def test_user_role_changed_to_vendor_deletes_employee(self):
        vendor_role, _ = Role.objects.get_or_create(name="Vendor")

        user = User.objects.create_user(
            email="vendor2@example.com",
            username="vendor2",
            password="pass123",
        )

        self.assertTrue(Employee.objects.filter(user=user).exists())

        user.role = vendor_role
        user.save()

        self.assertFalse(Employee.objects.filter(user=user).exists())
