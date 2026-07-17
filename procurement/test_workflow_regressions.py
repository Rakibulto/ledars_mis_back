from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from authentication.models import Role, User
from procurement.models.settings_models import UserManagement
from vendorportal.models.models import VendorProfile


class ProcurementWorkflowRegressionTests(APITestCase):
	def setUp(self):
		self.admin_role, _ = Role.objects.get_or_create(name="Admin")
		self.employee_role, _ = Role.objects.get_or_create(name="Employee")
		self.vendor_role, _ = Role.objects.get_or_create(name="Vendor")
		self.request_user = User.objects.create_user(
			email="workflow-admin@example.com",
			username="workflow-admin",
			password="testpass123",
			role=self.admin_role,
			is_active=True,
			is_staff=True,
		)
		self.client.force_authenticate(user=self.request_user)

	def _set_employee_name(self, user, name):
		employee = getattr(user, "employee", None)
		if employee is not None:
			employee.employee_name = name
			employee.save(update_fields=["employee_name"])

	def _create_managed_user(self, *, email, username, name, role, is_active=True, status_value="active"):
		user = User.objects.create_user(
			email=email,
			username=username,
			password="testpass123",
			role=role,
			is_active=is_active,
		)
		UserManagement.objects.create(
			user=user,
			username=user.username,
			email=user.email,
			name=name,
			role=role,
			status=status_value,
		)
		self._set_employee_name(user, name)
		return user

	def _create_auth_user(self, *, email, username, name, role, is_active=True):
		user = User.objects.create_user(
			email=email,
			username=username,
			password="testpass123",
			role=role,
			is_active=is_active,
		)
		self._set_employee_name(user, name)
		return user

	def test_simple_user_endpoint_excludes_vendor_accounts(self):
		approver = self._create_managed_user(
			email="approver@example.com",
			username="approver-user",
			name="Approver User",
			role=self.employee_role,
		)
		vendor_user = self._create_managed_user(
			email="vendor@example.com",
			username="vendor-user",
			name="Vendor User",
			role=self.vendor_role,
		)
		VendorProfile.objects.create(
			name="Vendor User",
			email=vendor_user.email,
			created_by=self.request_user,
		)

		response = self.client.get(reverse("simple-user-list"))

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		results = response.data["results"] if isinstance(response.data, dict) else response.data
		results_by_id = {row["id"]: row for row in results}
		self.assertIn(approver.id, results_by_id)
		self.assertNotIn(vendor_user.id, results_by_id)
		self.assertEqual(results_by_id[approver.id]["role_name"], "Employee")

	def test_simple_user_endpoint_includes_active_auth_users_without_user_management(self):
		auth_only_user = self._create_auth_user(
			email="auth-only@example.com",
			username="auth-only-user",
			name="Auth Only User",
			role=self.employee_role,
		)
		inactive_user = self._create_auth_user(
			email="inactive-auth@example.com",
			username="inactive-auth-user",
			name="Inactive Auth User",
			role=self.employee_role,
			is_active=False,
		)
		vendor_user = self._create_auth_user(
			email="vendor-auth@example.com",
			username="vendor-auth-user",
			name="Vendor Auth User",
			role=self.vendor_role,
		)
		VendorProfile.objects.create(
			name="Vendor Auth User",
			email=vendor_user.email,
			created_by=self.request_user,
		)

		response = self.client.get(reverse("simple-user-list"))

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		results = response.data["results"] if isinstance(response.data, dict) else response.data
		result_ids = {row["id"] for row in results}
		self.assertIn(auth_only_user.id, result_ids)
		self.assertNotIn(inactive_user.id, result_ids)
		self.assertNotIn(vendor_user.id, result_ids)

	def test_aprover_user_endpoint_returns_unpaginated_non_vendor_users(self):
		admin_user = self._create_auth_user(
			email="approver-admin@example.com",
			username="approver-admin",
			name="Approver Admin",
			role=self.admin_role,
		)
		employee_user = self._create_auth_user(
			email="approver-employee@example.com",
			username="approver-employee",
			name="Approver Employee",
			role=self.employee_role,
		)
		vendor_user = self._create_auth_user(
			email="approver-vendor@example.com",
			username="approver-vendor",
			name="Approver Vendor",
			role=self.vendor_role,
		)

		response = self.client.get(reverse("aprover-user-list"))

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertIsInstance(response.data, list)
		result_ids = {row["id"] for row in response.data}
		self.assertEqual(result_ids, {self.request_user.id, admin_user.id, employee_user.id})

		result_map = {row["id"]: row for row in response.data}
		self.assertEqual(result_map[admin_user.id]["full_name"], "Approver Admin")
		self.assertEqual(result_map[admin_user.id]["role_name"], "Admin")
		self.assertEqual(result_map[employee_user.id]["full_name"], "Approver Employee")
		self.assertEqual(result_map[employee_user.id]["role_name"], "Employee")
