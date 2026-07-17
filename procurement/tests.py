from datetime import date, timedelta
from io import BytesIO
import tempfile
from unittest.mock import patch
from zipfile import ZipFile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from authentication.models import User
from employee.models import Employee
from inventory.models import Warehouse as InventoryWarehouse
from vendorportal.models.apply_rfq_models import FinancialItem, FinancialProposal, VendorRFQSubmission
from vendorportal.models.models import VendorProfile
from procurement.models.office_models import OfficeManagement
from procurement.models.award_models import Award
from procurement.models.comparative_models import ComparativeStatement
from procurement.models.grn_models import GRNItem, GoodsReceiptNote
from procurement.models.requisition_models import MaterialRequisition
from procurement.models.payment_requisition_models import PaymentRequisition
from procurement.models.quotation_models import VendorQuotation
from procurement.models.rfq_models import RFQ, RFQLineItem
from procurement.models.settings_models import UserManagement
from procurement.models.vendor_models import VendorPerformance
from procurement.models.work_order_models import WorkOrder, WorkOrderAttachment, WorkOrderNotificationLog
from procurement.serializers.award_serializers import AwardSerializer
from procurement.serializers.comparative_serializers import _sync_award_for_cs
from procurement.serializers.work_order_serializers import WorkOrderSerializer


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class ProcurementContractTests(APITestCase):
	def setUp(self):
		self.user = User.objects.create_user(
			email="procurement-tests@example.com",
			username="procurement-tests",
			password="testpass123",
			is_active=True,
		)
		self.client.force_authenticate(user=self.user)

		self.supplier = VendorProfile.objects.create(
			name="Test Supplier",
			email="supplier@example.com",
			created_by=self.user,
		)

	def assertPaginatedEndpoint(self, route_name, params=None):
		query_params = {"pagination": "true"}
		if params:
			query_params.update(params)

		response = self.client.get(reverse(route_name), query_params)
		self.assertEqual(response.status_code, status.HTTP_200_OK, route_name)
		self.assertIsInstance(response.data, dict)
		self.assertIn("count", response.data)
		self.assertIn("results", response.data)
		self.assertIsInstance(response.data["results"], list)
		return response

	def assertObjectEndpoint(self, route_name, expected_keys, params=None):
		response = self.client.get(reverse(route_name), params or {})
		self.assertEqual(response.status_code, status.HTTP_200_OK, route_name)
		self.assertIsInstance(response.data, dict)
		for key in expected_keys:
			self.assertIn(key, response.data)
		return response

	def test_payment_requisition_status_can_be_patched_to_approved(self):
		prf = PaymentRequisition.objects.create(
			supplier=self.supplier,
			total_amount=1000,
			tax_amount=100,
			status="Pending Approval",
		)

		response = self.client.patch(
			reverse("payment-requisitions-detail", args=[prf.id]),
			{"status": "Approved", "finance_remarks": "Approved for payment."},
			format="json",
		)

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		prf.refresh_from_db()
		self.assertEqual(prf.status, "Approved")
		self.assertEqual(prf.finance_remarks, "Approved for payment.")
		self.assertIsNotNone(prf.approved_date)

	def test_vendor_acceptance_updates_work_order_vendor_status(self):
		work_order = WorkOrder.objects.create(
			title="Emergency procurement",
			vendor_status="pending-acceptance",
			acceptance_deadline=date.today() + timedelta(days=5),
			created_by=self.user,
		)

		response = self.client.post(
			reverse("vendor-acceptances-list"),
			{
				"work_order": work_order.id,
				"status": "Accepted",
				"remarks": "Accepted as issued.",
			},
			format="json",
		)

		self.assertEqual(response.status_code, status.HTTP_201_CREATED)
		work_order.refresh_from_db()
		self.assertEqual(work_order.vendor_status, "accepted")
		self.assertIsNotNone(work_order.vendor_acceptance_date)

	def test_direct_evaluation_accepted_award_matches_accepted_vendor_status_filter(self):
		rfq = RFQ.objects.create(rfq_title="Direct evaluation RFQ", created_by=self.user)
		quotation = VendorQuotation.objects.create(
			rfq=rfq,
			is_direct_evaluation=True,
			direct_vendor_name="Direct Supplier",
			total_amount=100,
			grand_total=100,
			status="accepted",
			created_by=self.user,
		)
		comparative = ComparativeStatement.objects.create(
			rfq=rfq,
			title="Direct evaluation CS",
			status="approved",
			created_by=self.user,
		)
		comparative.quotations.add(quotation)
		award = Award.objects.create(
			comparative_statement=comparative,
			rfq=rfq,
			vendor_profile=None,
			title="Direct evaluation award",
			total_amount=100,
			status="active",
			acceptance_status="accepted",
			awarded_by=self.user,
		)
		work_order = WorkOrder.objects.create(
			award=award,
			title="Approved direct evaluation work order",
			status="Approved",
			approval_status="fully-approved",
			vendor_status="sent",
			created_by=self.user,
		)

		response = self.client.get(
			reverse("work-orders-list"),
			{
				"pagination": "false",
				"status": "Approved",
				"vendor_status": "accepted",
			},
		)

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertEqual([row["id"] for row in response.data], [work_order.id])

	def test_grn_summary_reports_pending_verification_value(self):
		grn = GoodsReceiptNote.objects.create(
			supplier=self.supplier,
			status="Pending Verification",
			receipt_date=date.today(),
			invoice_amount=250,
			created_by=self.user,
		)
		GRNItem.objects.create(
			grn=grn,
			ordered_quantity=5,
			received_quantity=4,
			accepted_quantity=4,
			rejected_quantity=0,
			unit_price=50,
			remarks="Item: Test line",
		)

		response = self.client.get(reverse("grn-summary"))

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertEqual(response.data["total"], 1)
		self.assertEqual(response.data["pending_verification"], 1)
		self.assertEqual(float(response.data["total_value"]), 200.0)

	def test_simple_user_endpoint_returns_active_auth_user_ids(self):
		approver = User.objects.create_user(
			email="approver@example.com",
			username="approver-user",
			password="testpass123",
			is_active=True,
		)
		UserManagement.objects.create(
			user=approver,
			username=approver.username,
			email=approver.email,
			name="Approver User",
			status="active",
		)

		inactive_user = User.objects.create_user(
			email="inactive-approver@example.com",
			username="inactive-approver",
			password="testpass123",
			is_active=False,
		)
		UserManagement.objects.create(
			user=inactive_user,
			username=inactive_user.username,
			email=inactive_user.email,
			name="Inactive Approver",
			status="inactive",
		)

		response = self.client.get(reverse("simple-user-list"))

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		results = response.data["results"] if isinstance(response.data, dict) else response.data
		results_by_id = {row["id"]: row for row in results}
		self.assertIn(approver.id, results_by_id)
		self.assertNotIn(inactive_user.id, results_by_id)
		self.assertEqual(results_by_id[approver.id]["username"], approver.username)
		self.assertEqual(results_by_id[approver.id]["full_name"], "Approver User")

	def test_office_management_embeds_inventory_warehouses_payload(self):
		office = OfficeManagement.objects.create(
			name="Head Office",
			code="OFF-HQ",
			district="Dhaka",
			division="Dhaka",
			address="Dhaka",
			created_by=self.user,
		)
		InventoryWarehouse.objects.create(
			name="Regional Warehouse",
			code="WH-REG",
			address="Gazipur",
			manager="Manager One",
			phone="01710000000",
			warehouse_type="Regional",
			capacity_sqft=2455,
			is_active=True,
		)
		InventoryWarehouse.objects.create(
			name="Field Warehouse",
			code="WH-FIELD",
			address="Cox's Bazar",
			manager="Manager Two",
			phone="01710000001",
			warehouse_type="Field",
			capacity_sqft=1200,
			is_active=True,
		)

		office_response = self.client.get(reverse("office_management-list"))
		warehouse_response = self.client.get("/api/warehouses/")

		self.assertEqual(office_response.status_code, status.HTTP_200_OK)
		self.assertEqual(warehouse_response.status_code, status.HTTP_200_OK)
		self.assertEqual(len(office_response.data), 1)
		self.assertEqual(office_response.data[0]["id"], office.id)
		self.assertEqual(office_response.data[0]["warehouses"], warehouse_response.data)
		self.assertEqual(
			set(office_response.data[0]["warehouses"][0].keys()),
			{
				"id",
				"location_count",
				"warehouse_type_label",
				"name",
				"code",
				"address",
				"manager",
				"phone",
				"warehouse_type",
				"capacity_sqft",
				"is_active",
				"created_at",
				"updated_at",
			},
		)

	def test_requisitions_action_required_queue_only_returns_current_due_approver_items(self):
		approver1_user = User.objects.create_user(
			email="approver1@example.com",
			username="approver1",
			password="testpass123",
			is_active=True,
			is_staff=True,
		)
		approver2_user = User.objects.create_user(
			email="approver2@example.com",
			username="approver2",
			password="testpass123",
			is_active=True,
			is_staff=True,
		)

		approver1 = Employee.objects.get(user=approver1_user)
		approver1.employee_id = approver1.employee_id or "EMP-A1"
		approver1.employee_name = approver1.employee_name or "Approver One"
		approver1.save(update_fields=["employee_id", "employee_name"])

		approver2 = Employee.objects.get(user=approver2_user)
		approver2.employee_id = approver2.employee_id or "EMP-A2"
		approver2.employee_name = approver2.employee_name or "Approver Two"
		approver2.save(update_fields=["employee_id", "employee_name"])

		requisition = MaterialRequisition.objects.create(
			status="Pending Approval",
			priority="High",
			purpose="Queue regression",
			approver1=approver1,
			approver2=approver2,
			created_by=self.user,
		)

		self.client.force_authenticate(user=approver1_user)
		response = self.client.get(
			reverse("material_requisitions-list"),
			{"pagination": "false", "action_required": "true"},
		)

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertEqual(len(response.data), 1)
		self.assertEqual(response.data[0]["id"], requisition.id)

		response = self.client.patch(
			reverse("material_requisitions-change-status", args=[requisition.id]),
			{"status": "Finance Review", "action": "Approved"},
			format="json",
		)

		self.assertEqual(response.status_code, status.HTTP_200_OK)

		response = self.client.get(
			reverse("material_requisitions-list"),
			{"pagination": "false", "action_required": "true"},
		)

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertEqual(response.data, [])

		self.client.force_authenticate(user=approver2_user)
		response = self.client.get(
			reverse("material_requisitions-list"),
			{"pagination": "false", "action_required": "true"},
		)

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertEqual(len(response.data), 1)
		self.assertEqual(response.data[0]["id"], requisition.id)

	def test_send_to_vendor_marks_fully_approved_work_order_as_sent(self):
		work_order = WorkOrder.objects.create(
			title="Approved work order",
			status="Approved",
			approval_status="fully-approved",
			vendor_status="not-sent",
			created_by=self.user,
		)

		response = self.client.post(reverse("work-orders-send-to-vendor", args=[work_order.id]))

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		work_order.refresh_from_db()
		self.assertEqual(work_order.status, "Sent to Vendor")
		self.assertEqual(work_order.vendor_status, "sent")
		self.assertTrue(work_order.notification_sent)

	def test_send_to_vendor_rejects_work_orders_with_vendor_response(self):
		work_order = WorkOrder.objects.create(
			title="Accepted work order",
			status="Accepted by Vendor",
			approval_status="fully-approved",
			vendor_status="accepted",
			notification_sent=True,
			vendor_acceptance_date=date.today(),
			created_by=self.user,
		)

		response = self.client.post(reverse("work-orders-send-to-vendor", args=[work_order.id]))

		self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
		work_order.refresh_from_db()
		self.assertEqual(work_order.status, "Accepted by Vendor")
		self.assertEqual(work_order.vendor_status, "accepted")

	def test_work_order_pending_mode_only_returns_current_users_pending_approvals(self):
		my_pending = WorkOrder.objects.create(
			title="My pending work order",
			status="Pending Approval",
			approval_status="pending-approval",
			approver=self.user,
			created_by=self.user,
		)
		other_user = User.objects.create_user(
			email="other-approver@example.com",
			username="other-approver",
			password="testpass123",
			is_active=True,
		)
		WorkOrder.objects.create(
			title="Other pending work order",
			status="Pending Approval",
			approval_status="pending-approval",
			approver=other_user,
			created_by=self.user,
		)
		approved = WorkOrder.objects.create(
			title="Approved work order",
			status="Approved",
			approval_status="fully-approved",
			created_by=self.user,
		)

		response = self.client.get(
			reverse("work-orders-list"),
			{"pagination": "false", "mode": "pending"},
		)

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertEqual([row["id"] for row in response.data], [my_pending.id])

		response = self.client.get(
			reverse("work-orders-list"),
			{"pagination": "false", "exclude_pending_approval": "true"},
		)

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertEqual([row["id"] for row in response.data], [approved.id])

	def test_only_selected_work_order_approver_can_approve_and_api_returns_fully_approved_label(self):
		approver = User.objects.create_user(
			email="selected-approver@example.com",
			username="selected-approver",
			password="testpass123",
			is_active=True,
		)
		other_user = User.objects.create_user(
			email="not-selected@example.com",
			username="not-selected",
			password="testpass123",
			is_active=True,
		)
		work_order = WorkOrder.objects.create(
			title="Pending approval work order",
			status="Pending Approval",
			approval_status="pending-approval",
			approver=approver,
			created_by=self.user,
		)

		self.client.force_authenticate(user=other_user)
		response = self.client.post(reverse("work-orders-approve", args=[work_order.id]))

		self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

		self.client.force_authenticate(user=approver)
		response = self.client.post(
			reverse("work-orders-approve", args=[work_order.id]),
			{"comments": "Approved by selected approver."},
			format="json",
		)

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		work_order.refresh_from_db()
		self.assertEqual(work_order.status, "Approved")
		self.assertEqual(work_order.approval_status, "fully-approved")
		self.assertTrue(work_order.notification_sent)
		self.assertEqual(work_order.vendor_status, "sent")
		self.assertTrue(
			WorkOrderNotificationLog.objects.filter(
				work_order=work_order,
				status="sent",
			).exists()
		)
		self.assertEqual(response.data["status"], "Approved")
		self.assertEqual(response.data["approvalStatus"], "Fully Approved")

	def test_work_order_vendor_email_filter_returns_only_notified_vendor_work_orders(self):
		other_vendor = VendorProfile.objects.create(
			name="Other Supplier",
			email="other-supplier@example.com",
			created_by=self.user,
		)
		visible_work_order = WorkOrder.objects.create(
			title="Visible to vendor",
			status="Approved",
			approval_status="fully-approved",
			notification_sent=True,
			vendor_status="sent",
			vendor=self.supplier,
			created_by=self.user,
		)
		WorkOrderNotificationLog.objects.create(
			work_order=visible_work_order,
			channel="email",
			date="2026-05-07 10:00",
			status="sent",
			recipient=self.supplier.email,
		)
		WorkOrder.objects.create(
			title="Hidden until notified",
			status="Approved",
			approval_status="fully-approved",
			notification_sent=False,
			vendor_status="not-sent",
			vendor=self.supplier,
			created_by=self.user,
		)
		WorkOrder.objects.create(
			title="Different vendor work order",
			status="Approved",
			approval_status="fully-approved",
			notification_sent=True,
			vendor_status="sent",
			vendor=other_vendor,
			created_by=self.user,
		)

		response = self.client.get(
			reverse("work-orders-list"),
			{
				"pagination": "false",
				"vendor_email": self.supplier.email,
			},
		)

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertEqual([row["id"] for row in response.data], [visible_work_order.id])

	def test_download_pdf_returns_pdf_attachment(self):
		work_order = WorkOrder.objects.create(
			title="Printable work order",
			status="Approved",
			approval_status="fully-approved",
			created_by=self.user,
		)

		response = self.client.get(reverse("work-orders-download-pdf", args=[work_order.id]))

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertEqual(response["Content-Type"], "application/pdf")
		self.assertIn("attachment; filename=", response["Content-Disposition"])
		self.assertTrue(bytes(response.content).startswith(b"%PDF"))

	def test_download_documents_returns_zip_bundle(self):
		work_order = WorkOrder.objects.create(
			title="Bundle work order",
			status="Approved",
			approval_status="fully-approved",
			created_by=self.user,
		)
		WorkOrderAttachment.objects.create(
			work_order=work_order,
			name="spec-sheet.txt",
			file=SimpleUploadedFile("spec-sheet.txt", b"technical specs", content_type="text/plain"),
		)

		response = self.client.get(reverse("work-orders-download-documents", args=[work_order.id]))

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertEqual(response["Content-Type"], "application/zip")
		archive = ZipFile(BytesIO(response.content))
		names = archive.namelist()
		self.assertIn("README.txt", names)
		self.assertTrue(any(name.endswith(".pdf") for name in names))
		self.assertIn("attachments/spec-sheet.txt", names)

	def test_work_order_serializer_total_items_sums_item_quantities(self):
		serializer = WorkOrderSerializer()

		with patch.object(
			WorkOrderSerializer,
			"get_items",
			return_value=[
				{"quantity": 5},
				{"quantity": "2"},
				{"quantity": None},
				{},
			],
		):
			self.assertEqual(serializer.get_totalItems(object()), 7)

	def test_procurement_module_list_endpoints_return_paginated_payloads(self):
		for route_name in [
			"material_requisitions-list",
			"rfq-list",
			"quotations-list",
			"comparative_statements-list",
			"vendor-categories-list",
			"vendor-performance-list",
			"approval-matrix-list",
			"email-templates-list",
			"procurement-roles-list",
			"notification-settings-list",
			"user-management-list",
		]:
			with self.subTest(route_name=route_name):
				self.assertPaginatedEndpoint(route_name)

	def test_procurement_module_summary_endpoints_return_expected_shapes(self):
		self.assertObjectEndpoint(
			"material_requisitions-form-options",
			[
				"departments",
				"projects",
				"donor_codes",
				"budgets",
				"accounts",
				"items",
				"requesting_offices",
				"delivery_offices",
				"current_user",
			],
		)
		self.assertObjectEndpoint(
			"material_requisitions-stats",
			["total", "pending_approval", "approved", "total_amount"],
		)
		self.assertPaginatedEndpoint("rfq-simple-rfq")
		self.assertPaginatedEndpoint("rfq-invited-vendors-summary")
		self.assertObjectEndpoint(
			"rfq-rfq-summary",
			["total", "draft", "open", "total_vendors", "total_estimated_value"],
		)
		self.assertObjectEndpoint(
			"quotations-summary",
			["total", "draft", "submitted", "under_review", "accepted"],
		)
		self.assertObjectEndpoint(
			"comparative_statements-summary",
			["total", "draft", "approved", "rejected"],
		)
		self.assertObjectEndpoint(
			"vendor-performance-summary",
			[
				"total_orders",
				"total_on_time",
				"total_late",
				"total_rejected",
				"total_spent",
				"avg_compliance",
			],
		)

	def test_procurement_report_endpoints_return_expected_shapes(self):
		for route_name, expected_keys in [
			(
				"report-requisitions",
				["total", "status_breakdown", "priority_breakdown", "monthly_trend"],
			),
			("report-rfq", ["total", "status_breakdown", "total_value", "avg_suppliers"]),
			(
				"report-vendor-participation",
				["total_vendors", "active_vendors", "vendor_participation"],
			),
			("report-vendor-awards", ["total_awards", "total_value", "vendor_awards"]),
			("report-work-orders", ["total", "total_value", "status_breakdown"]),
			(
				"report-inventory-received",
				["total_grns", "total_value", "status_breakdown", "monthly_trend"],
			),
			("report-payment-status", ["total", "total_amount", "status_breakdown"]),
			(
				"report-budget-utilization",
				["total_budgets", "total_allocated", "budgets"],
			),
		]:
			with self.subTest(route_name=route_name):
				self.assertObjectEndpoint(route_name, expected_keys)

	def test_rfq_reports_return_data_backed_totals(self):
		RFQ.objects.create(
			rfq_title="Office Chairs",
			status="open",
			vendors_count=2,
			responses_received=1,
			total_estimated_value=100,
			created_by=self.user,
		)
		RFQ.objects.create(
			rfq_title="Office Desks",
			status="published",
			vendors_count=1,
			responses_received=3,
			total_estimated_value=300,
			created_by=self.user,
		)

		report_response = self.assertObjectEndpoint(
			"report-rfq",
			["total", "status_breakdown", "total_value", "avg_suppliers", "avg_responses"],
		)
		status_breakdown = {
			entry["status"]: entry["count"] for entry in report_response.data["status_breakdown"]
		}
		self.assertEqual(report_response.data["total"], 2)
		self.assertEqual(float(report_response.data["total_value"]), 400.0)
		self.assertEqual(float(report_response.data["avg_suppliers"]), 1.5)
		self.assertEqual(float(report_response.data["avg_responses"]), 2.0)
		self.assertEqual(status_breakdown["open"], 1)
		self.assertEqual(status_breakdown["published"], 1)

		summary_response = self.assertObjectEndpoint(
			"rfq-rfq-summary",
			["total", "published", "open", "total_vendors", "total_estimated_value"],
		)
		self.assertEqual(summary_response.data["total"], 2)
		self.assertEqual(summary_response.data["published"], 1)
		self.assertEqual(summary_response.data["open"], 1)
		self.assertEqual(float(summary_response.data["total_vendors"]), 3.0)
		self.assertEqual(float(summary_response.data["total_estimated_value"]), 400.0)

	def test_comparative_summary_returns_actual_status_counts(self):
		rfq = RFQ.objects.create(rfq_title="Comparative RFQ", created_by=self.user)
		ComparativeStatement.objects.create(rfq=rfq, title="Under Review", status="under_review")
		ComparativeStatement.objects.create(rfq=rfq, title="Pending", status="pending_approval")
		ComparativeStatement.objects.create(rfq=rfq, title="Approved", status="approved")
		ComparativeStatement.objects.create(rfq=rfq, title="Rejected", status="rejected")

		response = self.assertObjectEndpoint(
			"comparative_statements-summary",
			["total", "draft", "under_review", "pending_approval", "approved", "rejected"],
		)
		self.assertEqual(response.data["total"], 4)
		self.assertEqual(response.data["draft"], 0)
		self.assertEqual(response.data["under_review"], 1)
		self.assertEqual(response.data["pending_approval"], 1)
		self.assertEqual(response.data["approved"], 1)
		self.assertEqual(response.data["rejected"], 1)

	def test_comparative_pending_approval_can_be_approved_via_action_patch(self):
		rfq = RFQ.objects.create(rfq_title="Approval RFQ", created_by=self.user)
		comparative = ComparativeStatement.objects.create(
			rfq=rfq,
			title="Pending comparative",
			status="pending_approval",
		)

		response = self.client.patch(
			reverse("comparative_statements-detail", args=[comparative.id]),
			{
				"action": "approve",
				"remarks": "Looks good.",
				"recommended_vendor": self.supplier.id,
			},
			format="json",
		)

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		comparative.refresh_from_db()
		self.assertEqual(comparative.status, "approved")
		self.assertEqual(comparative.recommended_vendor_id, self.supplier.id)
		self.assertEqual(comparative.approved_by_id, self.user.id)
		self.assertIsNotNone(comparative.approved_date)
		self.assertEqual(comparative.notes.count(), 1)
		self.assertEqual(comparative.notes.first().text, "Looks good.")

	def test_award_items_prefer_recommended_vendor_financial_proposal(self):
		rfq = RFQ.objects.create(rfq_title="Award RFQ", created_by=self.user)
		rfq_line_pen = RFQLineItem.objects.create(
			rfq=rfq,
			item_name="Matador all-time ball pen",
			specification="Blue ink",
			quantity=10,
			unit="pcs",
			sort_order=1,
		)
		rfq_line_phone = RFQLineItem.objects.create(
			rfq=rfq,
			item_name="IPhone 17 Pro max",
			specification="512GB",
			quantity=5,
			unit="pcs",
			sort_order=2,
		)

		comparative = ComparativeStatement.objects.create(
			rfq=rfq,
			title="Award Source",
			status="approved",
			recommended_vendor=self.supplier,
		)
		submission = VendorRFQSubmission.objects.create(
			rfq=rfq,
			vendor_id=self.supplier.id,
			vendor_name=self.supplier.name,
			status="submitted",
			created_by=self.user,
		)
		financial_proposal = FinancialProposal.objects.create(
			submission=submission,
			sub_total=440010,
			vat=0,
			ait=0,
			delivery_charge=0,
			grand_total=440010,
		)
		FinancialItem.objects.create(
			financial_proposal=financial_proposal,
			line_item_id=rfq_line_phone.id,
			item_name="IPhone 17 Pro max",
			description="Flagship phone",
			qty=5,
			unit="pcs",
			unit_price=88000,
			total=440000,
		)
		FinancialItem.objects.create(
			financial_proposal=financial_proposal,
			line_item_id=rfq_line_pen.id,
			item_name="Matador all-time ball pen",
			description="Ball pen",
			qty=10,
			unit="pcs",
			unit_price=1,
			total=10,
		)

		_sync_award_for_cs(comparative)
		award = Award.objects.get(comparative_statement=comparative)
		self.assertEqual(award.items[0]["name"], "IPhone 17 Pro max")
		self.assertEqual(award.items[0]["unitPrice"], 88000.0)
		self.assertEqual(award.items[0]["specification"], "512GB")

		award.items = [
			{
				"description": "",
				"specification": "",
				"quantity": 10.0,
				"unitPrice": 1.0,
				"total": 10.0,
			},
			{
				"description": "",
				"specification": "",
				"quantity": 5.0,
				"unitPrice": 88000.0,
				"total": 440000.0,
			},
		]
		award.save(update_fields=["items"])

		serialized_items = AwardSerializer(award).data["items"]
		self.assertEqual(serialized_items[0]["name"], "IPhone 17 Pro max")
		self.assertEqual(serialized_items[0]["description"], "Flagship phone")
		self.assertEqual(serialized_items[0]["specification"], "512GB")
		self.assertEqual(serialized_items[0]["quantity"], 5.0)
		self.assertEqual(serialized_items[0]["unitPrice"], 88000.0)
		self.assertEqual(serialized_items[1]["name"], "Matador all-time ball pen")
		self.assertEqual(serialized_items[1]["quantity"], 10.0)
		self.assertEqual(serialized_items[1]["unitPrice"], 1.0)

	def test_vendor_reports_return_data_backed_totals(self):
		self.supplier.status = "Active"
		self.supplier.save(update_fields=["status"])
		second_vendor = VendorProfile.objects.create(
			name="Backup Supplier",
			email="backup-supplier@example.com",
			status="Pending",
			created_by=self.user,
		)
		rfq_one = RFQ.objects.create(rfq_title="Stationery", created_by=self.user)
		rfq_two = RFQ.objects.create(rfq_title="IT Equipment", created_by=self.user)
		VendorQuotation.objects.create(
			rfq=rfq_one,
			vendor=self.supplier,
			total_amount=450,
			grand_total=450,
			created_by=self.user,
		)
		VendorQuotation.objects.create(
			rfq=rfq_two,
			vendor=self.supplier,
			total_amount=150,
			grand_total=150,
			created_by=self.user,
		)
		VendorPerformance.objects.create(
			supplier=self.supplier,
			period_month=5,
			period_year=2026,
			total_orders=3,
			on_time_deliveries=2,
			late_deliveries=1,
			rejected_items=0,
			total_spent=600,
			compliance_score=92.5,
		)
		comparative = ComparativeStatement.objects.create(
			rfq=rfq_one,
			title="Vendor Award",
			status="approved",
		)
		Award.objects.create(
			comparative_statement=comparative,
			rfq=rfq_one,
			vendor_profile=self.supplier,
			total_amount=700,
		)

		participation_response = self.assertObjectEndpoint(
			"report-vendor-participation",
			["total_vendors", "active_vendors", "vendor_participation"],
		)
		self.assertEqual(participation_response.data["total_vendors"], 2)
		self.assertEqual(participation_response.data["active_vendors"], 1)
		self.assertEqual(participation_response.data["vendor_participation"][0]["vendor__name"], self.supplier.name)
		self.assertEqual(participation_response.data["vendor_participation"][0]["quotations_submitted"], 2)
		self.assertEqual(float(participation_response.data["vendor_participation"][0]["total_amount"]), 600.0)

		performance_response = self.assertObjectEndpoint(
			"vendor-performance-summary",
			[
				"total_orders",
				"total_on_time",
				"total_late",
				"total_rejected",
				"total_spent",
				"avg_compliance",
			],
		)
		self.assertEqual(performance_response.data["total_orders"], 3)
		self.assertEqual(performance_response.data["total_on_time"], 2)
		self.assertEqual(performance_response.data["total_late"], 1)
		self.assertEqual(performance_response.data["total_rejected"], 0)
		self.assertEqual(float(performance_response.data["total_spent"]), 600.0)
		self.assertEqual(float(performance_response.data["avg_compliance"]), 92.5)

		award_response = self.assertObjectEndpoint(
			"report-vendor-awards",
			["total_awards", "total_value", "vendor_awards"],
		)
		self.assertEqual(award_response.data["total_awards"], 1)
		self.assertEqual(float(award_response.data["total_value"]), 700.0)
		self.assertEqual(award_response.data["vendor_awards"][0]["vendor_profile__name"], self.supplier.name)
		self.assertEqual(float(award_response.data["vendor_awards"][0]["total_value"]), 700.0)
