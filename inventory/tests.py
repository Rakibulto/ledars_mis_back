from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIRequestFactory

from approval_workflow.models import ApprovalLevel, ApprovalLevelUser, ApprovalWorkflow
from inventory.models import Category, GIN, GINLineItem, GRN, GRNLineItem, InventoryValuation, OperationType, Product, PutawayRule, RemovalStrategy, Route, StockAdjustment, StockAdjustmentLine, StockMove, StorageLocation, Warehouse
from inventory.models.product import LocationStock
from inventory.serializers import GINWriteSerializer, StockAdjustmentWriteSerializer
from inventory.views.dashboard import InventoryDashboardOverviewView, InventoryLogAnalyticsView, InventoryLogHistoryView
from inventory.views.operations import GINViewSet, StockAdjustmentViewSet
from inventory.views.warehouse import OperationTypeViewSet, PutawayRuleViewSet, RemovalStrategyViewSet, RouteViewSet
from procurement.models.grn_models import GoodsReceiptNote, GRNItem as ProcurementGRNItem
from procurement.models.office_models import OfficeManagement


class GINApprovalStockReductionTests(TestCase):
	def setUp(self):
		self.user = get_user_model().objects.create_user(
			email="approver@example.com",
			username="approver",
			password="pass1234",
			is_active=True,
		)
		self.office = OfficeManagement.objects.create(
			name="Main Store",
			code="OFF-MAIN",
			district="Dhaka",
			division="Dhaka",
			address="Dhaka",
			created_by=self.user,
		)
		self.product = Product.objects.create(
			code="PRD-TST-001",
			name="Test Relief Item",
			on_hand=Decimal("10.00"),
			cost=Decimal("100.00"),
			sale_price=Decimal("150.00"),
			created_by=self.user,
			is_active=True,
			status="Active",
		)
		self.location_stock = LocationStock.objects.create(
			product=self.product,
			office_location=self.office,
			quantity=Decimal("10.00"),
		)
		self.gin = GIN.objects.create(
			issue_date=date.today(),
			issue_from="Main Store",
			office_location=self.office,
			status="Pending Approval",
			requested_by=self.user,
			total_value=Decimal("300.00"),
		)
		GINLineItem.objects.create(
			gin=self.gin,
			product=self.product,
			item_code=self.product.code,
			item_name=self.product.name,
			requested_qty=3,
			issued_qty=3,
			unit="pcs",
			unit_price=Decimal("100.00"),
		)

	def test_approving_gin_does_not_deduct_location_stock(self):
		serializer = GINWriteSerializer(
			instance=self.gin,
			data={"status": "Approved"},
			partial=True,
		)

		self.assertTrue(serializer.is_valid(), serializer.errors)
		serializer.save()

		self.location_stock.refresh_from_db()
		self.gin.refresh_from_db()

		self.assertEqual(self.gin.status, "Approved")
		self.assertEqual(self.location_stock.quantity, Decimal("10.00"))

	def test_issuing_gin_reduces_location_stock_once(self):
		approve_serializer = GINWriteSerializer(
			instance=self.gin,
			data={"status": "Approved"},
			partial=True,
		)
		self.assertTrue(approve_serializer.is_valid(), approve_serializer.errors)
		approve_serializer.save()

		issue_serializer = GINWriteSerializer(
			instance=self.gin,
			data={"status": "Issued"},
			partial=True,
		)
		self.assertTrue(issue_serializer.is_valid(), issue_serializer.errors)
		issue_serializer.save()

		self.location_stock.refresh_from_db()
		self.assertEqual(self.location_stock.quantity, Decimal("7.00"))

	def test_issuing_gin_creates_delivery_history_for_each_line_item(self):
		approve_serializer = GINWriteSerializer(
			instance=self.gin,
			data={"status": "Approved"},
			partial=True,
		)
		self.assertTrue(approve_serializer.is_valid(), approve_serializer.errors)
		approve_serializer.save()

		issue_serializer = GINWriteSerializer(
			instance=self.gin,
			data={"status": "Issued"},
			partial=True,
		)
		self.assertTrue(issue_serializer.is_valid(), issue_serializer.errors)
		issue_serializer.save()

		delivery_moves = StockMove.objects.filter(
			reference=self.gin.gin_number,
			move_type="Delivery",
		).order_by("id")

		self.assertEqual(delivery_moves.count(), self.gin.line_items.count())
		self.assertEqual(delivery_moves.first().quantity, Decimal("3"))

		request = APIRequestFactory().get(
			"/api/inventory-log/history/",
			{"pagination": "false", "search": self.gin.gin_number},
		)
		response = InventoryLogHistoryView.as_view()(request)
		response.render()
		results = response.data if isinstance(response.data, list) else response.data.get("results", [])

		self.assertEqual(len(results), 1)
		self.assertEqual(results[0]["reference"], self.gin.gin_number)
		self.assertEqual(results[0]["history_status"], "Stock_out")
		self.assertEqual(results[0]["direction"], "Out")


class GINWorkflowApprovalTests(TestCase):
	def setUp(self):
		self.user = get_user_model().objects.create_user(
			email="gin-approver@example.com",
			username="ginapprover",
			password="pass1234",
			is_active=True,
		)
		self.office = OfficeManagement.objects.create(
			name="Workflow Store",
			code="OFF-WF",
			district="Dhaka",
			division="Dhaka",
			address="Dhaka",
			created_by=self.user,
		)
		self.product = Product.objects.create(
			code="PRD-WF-001",
			name="Workflow Relief Item",
			on_hand=Decimal("10.00"),
			cost=Decimal("100.00"),
			sale_price=Decimal("150.00"),
			created_by=self.user,
			is_active=True,
			status="Active",
		)
		LocationStock.objects.create(
			product=self.product,
			office_location=self.office,
			quantity=Decimal("10.00"),
		)
		self.gin = GIN.objects.create(
			issue_date=date.today(),
			issue_from="Workflow Store",
			office_location=self.office,
			status="Pending Approval",
			requested_by=self.user,
			total_value=Decimal("300.00"),
		)
		GINLineItem.objects.create(
			gin=self.gin,
			product=self.product,
			item_code=self.product.code,
			item_name=self.product.name,
			requested_qty=3,
			issued_qty=3,
			unit="pcs",
			unit_price=Decimal("100.00"),
		)
		workflow = ApprovalWorkflow.objects.create(
			module_type_name="inventory",
			menu_name="good_issue_note",
			is_active=True,
			created_by=self.user,
		)
		level = ApprovalLevel.objects.create(
			workflow=workflow,
			level_number=1,
			from_amount=Decimal("0"),
			to_amount=None,
			minimum_approval_required=1,
			level_maintain_require="yes",
		)
		ApprovalLevelUser.objects.create(
			level=level,
			user=self.user,
			approval_order=1,
		)

	def test_workflow_approve_endpoint_moves_gin_to_approved(self):
		request = APIRequestFactory().post(f"/api/gin/{self.gin.id}/approve/")
		request.user = self.user
		response = GINViewSet.as_view({"post": "approve"})(request, pk=self.gin.id)

		self.assertEqual(response.status_code, 200)
		self.gin.refresh_from_db()
		self.assertEqual(self.gin.status, "Approved")
		self.assertEqual(self.gin.approval_level, 1)
		self.assertEqual(len(self.gin.approval_log), 1)

	def test_patch_to_approved_blocked_when_workflow_active(self):
		serializer = GINWriteSerializer(
			instance=self.gin,
			data={"status": "Approved"},
			partial=True,
		)
		self.assertFalse(serializer.is_valid())
		self.assertIn("status", serializer.errors)

	def test_intermediate_approvals_keep_pending_status_until_minimum_reached(self):
		user_b = get_user_model().objects.create_user(
			email="gin-approver-b@example.com",
			username="ginapproverb",
			password="pass1234",
			is_active=True,
		)
		user_c = get_user_model().objects.create_user(
			email="gin-approver-c@example.com",
			username="ginapproverc",
			password="pass1234",
			is_active=True,
		)
		level = ApprovalLevel.objects.get(workflow__menu_name="good_issue_note")
		level.minimum_approval_required = 3
		level.level_maintain_require = "no"
		level.save()
		ApprovalLevelUser.objects.create(level=level, user=user_b, approval_order=2)
		ApprovalLevelUser.objects.create(level=level, user=user_c, approval_order=3)

		first_request = APIRequestFactory().post(f"/api/gin/{self.gin.id}/approve/")
		first_request.user = self.user
		first_response = GINViewSet.as_view({"post": "approve"})(first_request, pk=self.gin.id)
		self.assertEqual(first_response.status_code, 200)
		self.gin.refresh_from_db()
		self.assertEqual(self.gin.status, "Pending Approval")
		self.assertEqual(self.gin.approval_level, 1)

		second_request = APIRequestFactory().post(f"/api/gin/{self.gin.id}/approve/")
		second_request.user = user_b
		second_response = GINViewSet.as_view({"post": "approve"})(second_request, pk=self.gin.id)
		self.assertEqual(second_response.status_code, 200)
		self.gin.refresh_from_db()
		self.assertEqual(self.gin.status, "Pending Approval")
		self.assertEqual(self.gin.approval_level, 2)

		third_request = APIRequestFactory().post(f"/api/gin/{self.gin.id}/approve/")
		third_request.user = user_c
		third_response = GINViewSet.as_view({"post": "approve"})(third_request, pk=self.gin.id)
		self.assertEqual(third_response.status_code, 200)
		self.gin.refresh_from_db()
		self.assertEqual(self.gin.status, "Approved")
		self.assertEqual(self.gin.approval_level, 3)

		status_moves = StockMove.objects.filter(
			reference=self.gin.gin_number,
			move_type="Status Change",
		).order_by("id")
		self.assertEqual(status_moves.count(), 3)
		self.assertEqual(status_moves[0].from_status, "Pending Approval")
		self.assertEqual(status_moves[0].to_status, "Pending Approval")
		self.assertEqual(status_moves[2].to_status, "Approved")

		repeat_request = APIRequestFactory().post(f"/api/gin/{self.gin.id}/approve/")
		repeat_request.user = user_c
		repeat_response = GINViewSet.as_view({"post": "approve"})(repeat_request, pk=self.gin.id)
		self.assertEqual(repeat_response.status_code, 400)


class StockAdjustmentApprovalStockApplicationTests(TestCase):
	def setUp(self):
		self.user = get_user_model().objects.create_user(
			email="stock-adjustment@example.com",
			username="stockadjuster",
			password="pass1234",
			is_active=True,
		)
		self.product = Product.objects.create(
			code="PRD-ADJ-001",
			name="Adjustment Test Product",
			on_hand=Decimal("10.00"),
			available=Decimal("10.00"),
			cost=Decimal("50.00"),
			sale_price=Decimal("80.00"),
			created_by=self.user,
			is_active=True,
			status="Active",
		)

	def create_adjustment(self, *, status="Pending Approval", difference=4, counted_qty=14):
		adjustment = StockAdjustment.objects.create(
			adjustment_date=date.today(),
			adjustment_type="Increase" if difference >= 0 else "Decrease",
			status=status,
			adjusted_by=self.user,
		)
		StockAdjustmentLine.objects.create(
			adjustment=adjustment,
			product=self.product,
			item_code=self.product.code,
			item_name=self.product.name,
			system_qty=10,
			counted_qty=counted_qty,
			difference=difference,
			unit="pcs",
			unit_price=Decimal("50.00"),
		)
		return adjustment

	def test_approving_stock_adjustment_applies_difference_to_product_stock(self):
		adjustment = self.create_adjustment(status="Pending Approval", difference=4, counted_qty=14)

		serializer = StockAdjustmentWriteSerializer(
			instance=adjustment,
			data={"status": "Approved"},
			partial=True,
		)

		self.assertTrue(serializer.is_valid(), serializer.errors)
		serializer.save()

		self.product.refresh_from_db()
		adjustment.refresh_from_db()

		self.assertEqual(adjustment.status, "Approved")
		self.assertEqual(self.product.on_hand, Decimal("14.00"))
		self.assertEqual(self.product.available, Decimal("14.00"))

	def test_reapproving_stock_adjustment_does_not_apply_difference_twice(self):
		adjustment = self.create_adjustment(status="Pending Approval", difference=4, counted_qty=14)

		first_serializer = StockAdjustmentWriteSerializer(
			instance=adjustment,
			data={"status": "Approved"},
			partial=True,
		)
		self.assertTrue(first_serializer.is_valid(), first_serializer.errors)
		first_serializer.save()

		second_serializer = StockAdjustmentWriteSerializer(
			instance=adjustment,
			data={"status": "Approved"},
			partial=True,
		)
		self.assertTrue(second_serializer.is_valid(), second_serializer.errors)
		second_serializer.save()

		self.product.refresh_from_db()

		self.assertEqual(self.product.on_hand, Decimal("14.00"))

	def test_draft_stock_adjustment_does_not_change_stock_until_approved(self):
		adjustment = self.create_adjustment(status="Draft", difference=-3, counted_qty=7)

		self.product.refresh_from_db()
		self.assertEqual(self.product.on_hand, Decimal("10.00"))

		pending_serializer = StockAdjustmentWriteSerializer(
			instance=adjustment,
			data={"status": "Pending Approval"},
			partial=True,
		)
		self.assertTrue(pending_serializer.is_valid(), pending_serializer.errors)
		pending_serializer.save()

		self.product.refresh_from_db()
		self.assertEqual(self.product.on_hand, Decimal("10.00"))

		approve_serializer = StockAdjustmentWriteSerializer(
			instance=adjustment,
			data={"status": "Approved"},
			partial=True,
		)
		self.assertTrue(approve_serializer.is_valid(), approve_serializer.errors)
		approve_serializer.save()

		self.product.refresh_from_db()
		self.assertEqual(self.product.on_hand, Decimal("7.00"))


class StockAdjustmentWorkflowApprovalTests(TestCase):
	def setUp(self):
		self.user = get_user_model().objects.create_user(
			email="adj-approver@example.com",
			username="adjapprover",
			password="pass1234",
			is_active=True,
		)
		self.product = Product.objects.create(
			code="PRD-ADJ-WF-001",
			name="Workflow Adjustment Product",
			on_hand=Decimal("10.00"),
			available=Decimal("10.00"),
			cost=Decimal("50.00"),
			sale_price=Decimal("80.00"),
			created_by=self.user,
			is_active=True,
			status="Active",
		)
		self.adjustment = StockAdjustment.objects.create(
			adjustment_date=date.today(),
			adjustment_type="Increase",
			status="Pending Approval",
			adjusted_by=self.user,
			total_value=Decimal("200.00"),
		)
		StockAdjustmentLine.objects.create(
			adjustment=self.adjustment,
			product=self.product,
			item_code=self.product.code,
			item_name=self.product.name,
			system_qty=10,
			counted_qty=14,
			difference=4,
			unit="pcs",
			unit_price=Decimal("50.00"),
		)
		workflow = ApprovalWorkflow.objects.create(
			module_type_name="inventory",
			menu_name="stock_adjustment",
			is_active=True,
			created_by=self.user,
		)
		level = ApprovalLevel.objects.create(
			workflow=workflow,
			level_number=1,
			from_amount=Decimal("0"),
			to_amount=None,
			minimum_approval_required=1,
			level_maintain_require="yes",
		)
		ApprovalLevelUser.objects.create(
			level=level,
			user=self.user,
			approval_order=1,
		)

	def test_workflow_approve_endpoint_moves_adjustment_to_approved(self):
		request = APIRequestFactory().post(
			f"/api/stock-adjustments/{self.adjustment.id}/approve/"
		)
		request.user = self.user
		response = StockAdjustmentViewSet.as_view({"post": "approve"})(
			request, pk=self.adjustment.id
		)

		self.assertEqual(response.status_code, 200)
		self.adjustment.refresh_from_db()
		self.product.refresh_from_db()
		self.assertEqual(self.adjustment.status, "Approved")
		self.assertEqual(self.adjustment.approval_level, 1)
		self.assertEqual(len(self.adjustment.approval_log), 1)
		self.assertEqual(self.product.on_hand, Decimal("14.00"))

	def test_patch_to_approved_blocked_when_workflow_active(self):
		serializer = StockAdjustmentWriteSerializer(
			instance=self.adjustment,
			data={"status": "Approved"},
			partial=True,
		)
		self.assertFalse(serializer.is_valid())
		self.assertIn("status", serializer.errors)

	def test_intermediate_approvals_keep_pending_status_until_minimum_reached(self):
		user_b = get_user_model().objects.create_user(
			email="adj-approver-b@example.com",
			username="adjapproverb",
			password="pass1234",
			is_active=True,
		)
		user_c = get_user_model().objects.create_user(
			email="adj-approver-c@example.com",
			username="adjapproverc",
			password="pass1234",
			is_active=True,
		)
		level = ApprovalLevel.objects.get(workflow__menu_name="stock_adjustment")
		level.minimum_approval_required = 3
		level.level_maintain_require = "no"
		level.save()
		ApprovalLevelUser.objects.create(level=level, user=user_b, approval_order=2)
		ApprovalLevelUser.objects.create(level=level, user=user_c, approval_order=3)

		first_request = APIRequestFactory().post(
			f"/api/stock-adjustments/{self.adjustment.id}/approve/"
		)
		first_request.user = self.user
		first_response = StockAdjustmentViewSet.as_view({"post": "approve"})(
			first_request, pk=self.adjustment.id
		)
		self.assertEqual(first_response.status_code, 200)
		self.adjustment.refresh_from_db()
		self.assertEqual(self.adjustment.status, "Pending Approval")
		self.assertEqual(self.adjustment.approval_level, 1)

		second_request = APIRequestFactory().post(
			f"/api/stock-adjustments/{self.adjustment.id}/approve/"
		)
		second_request.user = user_b
		second_response = StockAdjustmentViewSet.as_view({"post": "approve"})(
			second_request, pk=self.adjustment.id
		)
		self.assertEqual(second_response.status_code, 200)
		self.adjustment.refresh_from_db()
		self.assertEqual(self.adjustment.status, "Pending Approval")
		self.assertEqual(self.adjustment.approval_level, 2)

		third_request = APIRequestFactory().post(
			f"/api/stock-adjustments/{self.adjustment.id}/approve/"
		)
		third_request.user = user_c
		third_response = StockAdjustmentViewSet.as_view({"post": "approve"})(
			third_request, pk=self.adjustment.id
		)
		self.assertEqual(third_response.status_code, 200)
		self.adjustment.refresh_from_db()
		self.assertEqual(self.adjustment.status, "Approved")
		self.assertEqual(self.adjustment.approval_level, 3)

		status_moves = StockMove.objects.filter(
			reference=self.adjustment.adjustment_number,
			move_type="Status Change",
		).order_by("id")
		self.assertEqual(status_moves.count(), 3)
		self.assertEqual(status_moves[0].from_status, "Pending Approval")
		self.assertEqual(status_moves[0].to_status, "Pending Approval")
		self.assertEqual(status_moves[2].to_status, "Approved")

		repeat_request = APIRequestFactory().post(
			f"/api/stock-adjustments/{self.adjustment.id}/approve/"
		)
		repeat_request.user = user_c
		repeat_response = StockAdjustmentViewSet.as_view({"post": "approve"})(
			repeat_request, pk=self.adjustment.id
		)
		self.assertEqual(repeat_response.status_code, 400)

	def test_force_unordered_allows_any_order_when_level_maintain_require_yes(self):
		user_b = get_user_model().objects.create_user(
			email="adj-approver-unordered@example.com",
			username="adjapproverunordered",
			password="pass1234",
			is_active=True,
		)
		level = ApprovalLevel.objects.get(workflow__menu_name="stock_adjustment")
		level.minimum_approval_required = 2
		level.level_maintain_require = "yes"
		level.save()
		ApprovalLevelUser.objects.create(level=level, user=user_b, approval_order=2)

		request = APIRequestFactory().post(
			f"/api/stock-adjustments/{self.adjustment.id}/approve/",
			{"force_unordered": True},
			format="json",
		)
		request.user = user_b
		response = StockAdjustmentViewSet.as_view({"post": "approve"})(
			request, pk=self.adjustment.id
		)

		self.assertEqual(response.status_code, 200)
		self.adjustment.refresh_from_db()
		self.assertEqual(self.adjustment.status, "Pending Approval")
		self.assertEqual(self.adjustment.approval_level, 1)


class InventoryLogHistoryOrderingTests(TestCase):
	def setUp(self):
		self.user = get_user_model().objects.create_user(
			email="history-order@example.com",
			username="historyorder",
			password="pass1234",
			is_active=True,
		)
		self.product = Product.objects.create(
			code="PRD-HISTORY-001",
			name="History Ordering Product",
			on_hand=Decimal("50.00"),
			available=Decimal("50.00"),
			cost=Decimal("10.00"),
			sale_price=Decimal("15.00"),
			created_by=self.user,
			is_active=True,
			status="Active",
		)

	def test_history_defaults_to_latest_created_rows_first(self):
		base_time = timezone.now()

		older_created = StockMove.objects.create(
			date=base_time + timedelta(days=6),
			reference="REF-OLDER",
			product=self.product,
			source_location="Vendor",
			destination_location="Main Store",
			quantity=Decimal("10.00"),
			uom="pcs",
			move_type="Receipt",
			done_by=self.user,
		)
		newer_created = StockMove.objects.create(
			date=base_time,
			reference="REF-NEWER",
			product=self.product,
			source_location="Main Store",
			destination_location="Field Team",
			quantity=Decimal("5.00"),
			uom="pcs",
			move_type="Delivery",
			done_by=self.user,
		)

		StockMove.objects.filter(id=older_created.id).update(created_at=base_time - timedelta(days=1))
		StockMove.objects.filter(id=newer_created.id).update(created_at=base_time)

		request = APIRequestFactory().get("/api/inventory-log/history/", {"pagination": "false"})
		response = InventoryLogHistoryView.as_view()(request)
		response.render()
		results = response.data if isinstance(response.data, list) else response.data.get("results", [])

		self.assertGreaterEqual(len(results), 2)
		self.assertEqual(results[0]["reference"], "REF-NEWER")
		self.assertEqual(results[1]["reference"], "REF-OLDER")


class InventoryLogAnalyticsSourceTests(TestCase):
	def setUp(self):
		self.user = get_user_model().objects.create_user(
			email="analytics-source@example.com",
			username="analyticssource",
			password="pass1234",
			is_active=True,
		)
		self.product = Product.objects.create(
			code="PRD-ANL-001",
			name="Analytics Source Product",
			on_hand=Decimal("40.00"),
			available=Decimal("40.00"),
			cost=Decimal("100.00"),
			sale_price=Decimal("150.00"),
			created_by=self.user,
			is_active=True,
			status="Active",
		)

	def test_analytics_exposes_source_summaries_and_populated_timeline(self):
		grn = GoodsReceiptNote.objects.create(
			receipt_date=date.today() + timedelta(days=2),
			status="Verified",
			created_by=self.user,
		)
		ProcurementGRNItem.objects.create(
			grn=grn,
			item=self.product,
			ordered_quantity=10,
			received_quantity=8,
			accepted_quantity=6,
			rejected_quantity=2,
			unit_price=Decimal("100.00"),
		)
		GoodsReceiptNote.objects.filter(id=grn.id).update(updated_at=timezone.localtime())
		grn.refresh_from_db()

		gin = GIN.objects.create(
			issue_date=date.today(),
			issue_from="Main Store",
			issued_to="Field Team",
			status="Issued",
			requested_by=self.user,
		)
		GINLineItem.objects.create(
			gin=gin,
			product=self.product,
			item_code=self.product.code,
			item_name=self.product.name,
			requested_qty=4,
			issued_qty=4,
			unit="pcs",
			unit_price=Decimal("100.00"),
		)

		request = APIRequestFactory().get("/api/inventory-log/analytics/", {"period": "monthly"})
		response = InventoryLogAnalyticsView.as_view()(request)
		response.render()
		data = response.data

		self.assertEqual(data["source_overview"]["items"]["total_records"], 1)
		self.assertEqual(data["source_overview"]["gin"]["total_documents"], 1)
		self.assertEqual(data["source_overview"]["grn"]["total_documents"], 1)
		self.assertEqual(data["source_overview"]["grn"]["verified_documents"], 1)
		self.assertEqual(data["movement_summary"]["total_in_count"], 1)
		self.assertEqual(data["movement_summary"]["total_in_quantity"], Decimal("6"))
		self.assertTrue(any(row["in_count"] > 0 for row in data["movement_timeline"]))
		self.assertEqual(data["latest_grns"][0]["reference"], grn.grn_number)
		self.assertTrue(any(move["move_type"] == "Receipt" for move in data["recent_moves"]))
		self.assertEqual(data["latest_gins"][0]["reference"], gin.gin_number)


class InventoryDashboardOverviewTests(TestCase):
	def setUp(self):
		self.user = get_user_model().objects.create_user(
			email="dashboard-overview@example.com",
			username="dashboardoverview",
			password="pass1234",
			is_active=True,
		)
		self.main_warehouse = Warehouse.objects.create(
			name="Main Office Warehouse",
			code="MAIN-001",
			warehouse_type="Central",
			is_active=True,
		)
		self.field_warehouse = Warehouse.objects.create(
			name="Field Warehouse",
			code="FIELD-001",
			warehouse_type="Field",
			is_active=True,
		)
		self.main_product = Product.objects.create(
			code="PRD-DASH-001",
			name="Main Office Stock",
			on_hand=Decimal("35.00"),
			available=Decimal("35.00"),
			cost=Decimal("100.00"),
			sale_price=Decimal("120.00"),
			reorder_level=Decimal("10.00"),
			created_by=self.user,
			is_active=True,
			status="Active",
		)
		self.field_product = Product.objects.create(
			code="PRD-DASH-002",
			name="Field Warehouse Stock",
			on_hand=Decimal("12.00"),
			available=Decimal("12.00"),
			cost=Decimal("80.00"),
			sale_price=Decimal("110.00"),
			reorder_level=Decimal("5.00"),
			created_by=self.user,
			is_active=True,
			status="Active",
		)
		InventoryValuation.objects.create(
			product=self.main_product,
			warehouse=self.main_warehouse,
			on_hand=Decimal("30.00"),
			unit_cost=Decimal("100.00"),
		)
		InventoryValuation.objects.create(
			product=self.main_product,
			on_hand=Decimal("5.00"),
			unit_cost=Decimal("100.00"),
		)
		InventoryValuation.objects.create(
			product=self.field_product,
			warehouse=self.field_warehouse,
			on_hand=Decimal("12.00"),
			unit_cost=Decimal("80.00"),
		)
		StockMove.objects.create(
			date=timezone.now() - timedelta(days=1),
			reference="RCV-MAIN",
			product=self.main_product,
			source_location="Vendor",
			destination_location=self.main_warehouse.name,
			quantity=Decimal("10.00"),
			uom="pcs",
			move_type="Receipt",
			done_by=self.user,
		)
		StockMove.objects.create(
			date=timezone.now() - timedelta(days=2),
			reference="ISS-MAIN",
			product=self.main_product,
			source_location="Main inventory",
			destination_location="Field Team",
			quantity=Decimal("2.00"),
			uom="pcs",
			move_type="Delivery",
			done_by=self.user,
		)
		StockMove.objects.create(
			date=timezone.now() - timedelta(days=1),
			reference="ISS-FIELD",
			product=self.field_product,
			source_location=self.field_warehouse.name,
			destination_location="Programme Team",
			quantity=Decimal("4.00"),
			uom="pcs",
			move_type="Delivery",
			done_by=self.user,
		)

	def test_overview_exposes_main_office_and_selected_warehouse_metrics(self):
		main_request = APIRequestFactory().get(
			"/api/inventory-dashboard/overview/",
			{"warehouse": "main-office"},
		)
		main_response = InventoryDashboardOverviewView.as_view()(main_request)
		main_response.render()
		main_data = main_response.data

		self.assertEqual(main_data["selected_scope"]["key"], "main-office")
		self.assertEqual(Decimal(str(main_data["summary"]["on_hand_qty"])), Decimal("35.00"))
		self.assertEqual(
			Decimal(str(main_data["main_office_overview"]["on_hand_qty"])),
			Decimal("35.00"),
		)
		self.assertEqual(
			Decimal(str(main_data["summary"]["outbound_qty_30d"])),
			Decimal("2.00"),
		)
		self.assertTrue(
			any(option["id"] == self.field_warehouse.id for option in main_data["warehouse_options"])
		)

		field_request = APIRequestFactory().get(
			"/api/inventory-dashboard/overview/",
			{"warehouse": str(self.field_warehouse.id)},
		)
		field_response = InventoryDashboardOverviewView.as_view()(field_request)
		field_response.render()
		field_data = field_response.data

		self.assertEqual(field_data["selected_scope"]["warehouse_id"], self.field_warehouse.id)
		self.assertEqual(Decimal(str(field_data["summary"]["on_hand_qty"])), Decimal("12.00"))
		self.assertEqual(Decimal(str(field_data["summary"]["outbound_qty_30d"])), Decimal("4.00"))
		self.assertEqual(field_data["summary"]["sku_count"], 1)


class PutawayRuleViewSetTests(TestCase):
	def setUp(self):
		self.user = get_user_model().objects.create_user(
			email="putaway@example.com",
			username="putawaytester",
			password="pass1234",
			is_active=True,
		)
		self.main_warehouse = Warehouse.objects.create(
			name="Main Putaway Warehouse",
			code="PUT-MAIN",
			warehouse_type="Central",
			is_active=True,
		)
		self.field_warehouse = Warehouse.objects.create(
			name="Field Putaway Warehouse",
			code="PUT-FIELD",
			warehouse_type="Field",
			is_active=True,
		)
		self.main_location = StorageLocation.objects.create(
			name="Bulk A1",
			warehouse=self.main_warehouse,
			location_type="internal",
		)
		self.field_location = StorageLocation.objects.create(
			name="Field Rack B2",
			warehouse=self.field_warehouse,
			location_type="internal",
		)
		self.category = Category.objects.create(
			code="CAT-PUT-001",
			name="Medical Supplies",
			level="Main",
			created_by=self.user,
		)
		self.product = Product.objects.create(
			code="PRD-PUT-001",
			name="Relief Blanket",
			on_hand=Decimal("10.00"),
			available=Decimal("10.00"),
			cost=Decimal("50.00"),
			sale_price=Decimal("70.00"),
			created_by=self.user,
			is_active=True,
			status="Active",
		)
		self.product_rule = PutawayRule.objects.create(
			product=self.product,
			warehouse=self.main_warehouse,
			location=self.main_location,
			sequence=1,
			is_active=True,
		)
		self.category_rule = PutawayRule.objects.create(
			category=self.category,
			warehouse=self.field_warehouse,
			location=self.field_location,
			sequence=8,
			is_active=False,
		)

	def test_list_supports_server_side_search_filter_and_pagination(self):
		request = APIRequestFactory().get(
			"/api/putaway-rules/",
			{
				"pagination": "true",
				"page": 1,
				"page_size": 1,
				"search": "blanket",
				"warehouse": self.main_warehouse.id,
				"target_type": "product",
				"is_active": "true",
				"ordering": "sequence",
			},
		)
		response = PutawayRuleViewSet.as_view({"get": "list"})(request)
		response.render()
		data = response.data

		self.assertEqual(data["count"], 1)
		self.assertEqual(data["total_pages"], 1)
		self.assertEqual(data["current_page"], 1)
		self.assertEqual(len(data["results"]), 1)
		self.assertEqual(data["results"][0]["id"], self.product_rule.id)
		self.assertEqual(data["results"][0]["warehouse_name"], self.main_warehouse.name)
		self.assertEqual(data["results"][0]["target_type"], "product")
		self.assertEqual(data["results"][0]["target_name"], self.product.name)

	def test_create_requires_single_target_and_matching_location_warehouse(self):
		create_view = PutawayRuleViewSet.as_view({"post": "create"})

		missing_target_request = APIRequestFactory().post(
			"/api/putaway-rules/",
			{
				"warehouse": self.main_warehouse.id,
				"location": self.main_location.id,
				"sequence": 3,
				"is_active": True,
			},
			format="json",
		)
		missing_target_response = create_view(missing_target_request)
		missing_target_response.render()

		self.assertEqual(missing_target_response.status_code, 400)
		self.assertIn("target", missing_target_response.data)

		wrong_location_request = APIRequestFactory().post(
			"/api/putaway-rules/",
			{
				"product": self.product.id,
				"warehouse": self.main_warehouse.id,
				"location": self.field_location.id,
				"sequence": 4,
				"is_active": True,
			},
			format="json",
		)
		wrong_location_response = create_view(wrong_location_request)
		wrong_location_response.render()

		self.assertEqual(wrong_location_response.status_code, 400)
		self.assertIn("location", wrong_location_response.data)

		valid_request = APIRequestFactory().post(
			"/api/putaway-rules/",
			{
				"category": self.category.id,
				"warehouse": self.main_warehouse.id,
				"location": self.main_location.id,
				"sequence": 5,
				"is_active": True,
			},
			format="json",
		)
		valid_response = create_view(valid_request)
		valid_response.render()

		self.assertEqual(valid_response.status_code, 201)
		self.assertTrue(
			PutawayRule.objects.filter(
				category=self.category,
				warehouse=self.main_warehouse,
				location=self.main_location,
				sequence=5,
			).exists()
		)


class RemovalStrategyViewSetTests(TestCase):
	def setUp(self):
		self.main_warehouse = Warehouse.objects.create(
			name="Main Removal Warehouse",
			code="REM-MAIN",
			warehouse_type="Central",
			is_active=True,
		)
		self.field_warehouse = Warehouse.objects.create(
			name="Field Removal Warehouse",
			code="REM-FIELD",
			warehouse_type="Field",
			is_active=True,
		)
		self.fifo_strategy = RemovalStrategy.objects.create(
			name="FIFO Core",
			strategy="fifo",
			warehouse=self.main_warehouse,
			is_active=True,
		)
		self.fefo_strategy = RemovalStrategy.objects.create(
			name="Expiry First",
			strategy="fefo",
			warehouse=self.field_warehouse,
			is_active=False,
		)

	def test_list_supports_server_side_search_filter_and_pagination(self):
		request = APIRequestFactory().get(
			"/api/removal-strategies/",
			{
				"pagination": "true",
				"page": 1,
				"page_size": 1,
				"search": "fifo",
				"warehouse": self.main_warehouse.id,
				"strategy": "fifo",
				"is_active": "true",
				"ordering": "name",
			},
		)
		response = RemovalStrategyViewSet.as_view({"get": "list"})(request)
		response.render()
		data = response.data

		self.assertEqual(data["count"], 1)
		self.assertEqual(data["total_pages"], 1)
		self.assertEqual(data["current_page"], 1)
		self.assertEqual(len(data["results"]), 1)
		self.assertEqual(data["results"][0]["id"], self.fifo_strategy.id)
		self.assertEqual(data["results"][0]["warehouse_name"], self.main_warehouse.name)
		self.assertEqual(data["results"][0]["warehouse_code"], self.main_warehouse.code)
		self.assertEqual(data["results"][0]["strategy_label"], "First In, First Out (FIFO)")

	def test_create_accepts_model_backed_payload(self):
		create_view = RemovalStrategyViewSet.as_view({"post": "create"})

		request = APIRequestFactory().post(
			"/api/removal-strategies/",
			{
				"name": "Closest Bin Fast Pick",
				"strategy": "closest",
				"warehouse": self.main_warehouse.id,
				"is_active": True,
			},
			format="json",
		)
		response = create_view(request)
		response.render()

		self.assertEqual(response.status_code, 201)
		self.assertTrue(
			RemovalStrategy.objects.filter(
				name="Closest Bin Fast Pick",
				strategy="closest",
				warehouse=self.main_warehouse,
				is_active=True,
			).exists()
		)


class OperationTypeViewSetTests(TestCase):
	def setUp(self):
		self.main_warehouse = Warehouse.objects.create(
			name="Main Operation Warehouse",
			code="OP-MAIN",
			warehouse_type="Central",
			is_active=True,
		)
		self.field_warehouse = Warehouse.objects.create(
			name="Field Operation Warehouse",
			code="OP-FIELD",
			warehouse_type="Field",
			is_active=True,
		)
		self.main_source = StorageLocation.objects.create(
			name="Inbound Gate",
			warehouse=self.main_warehouse,
			location_type="internal",
		)
		self.main_destination = StorageLocation.objects.create(
			name="Main Picking Zone",
			warehouse=self.main_warehouse,
			location_type="internal",
		)
		self.field_location = StorageLocation.objects.create(
			name="Field Buffer",
			warehouse=self.field_warehouse,
			location_type="internal",
		)
		self.active_operation = OperationType.objects.create(
			name="Inbound Receipts",
			code="OP-IN-001",
			operation_type="incoming",
			warehouse=self.main_warehouse,
			default_source=self.main_source,
			default_destination=self.main_destination,
			is_active=True,
		)
		self.inactive_operation = OperationType.objects.create(
			name="Return Inspection",
			code="OP-RET-001",
			operation_type="returns",
			warehouse=self.field_warehouse,
			default_source=self.field_location,
			default_destination=self.field_location,
			is_active=False,
		)

	def test_list_supports_server_side_search_filter_and_pagination(self):
		request = APIRequestFactory().get(
			"/api/operation-types/",
			{
				"pagination": "true",
				"page": 1,
				"page_size": 1,
				"search": "inbound",
				"warehouse": self.main_warehouse.id,
				"operation_type": "incoming",
				"is_active": "true",
				"ordering": "name",
			},
		)
		response = OperationTypeViewSet.as_view({"get": "list"})(request)
		response.render()
		data = response.data

		self.assertEqual(data["count"], 1)
		self.assertEqual(data["total_pages"], 1)
		self.assertEqual(data["current_page"], 1)
		self.assertEqual(len(data["results"]), 1)
		self.assertEqual(data["results"][0]["id"], self.active_operation.id)
		self.assertEqual(data["results"][0]["warehouse_name"], self.main_warehouse.name)
		self.assertEqual(data["results"][0]["warehouse_code"], self.main_warehouse.code)
		self.assertEqual(data["results"][0]["operation_type_label"], "Receipts")
		self.assertEqual(
			data["results"][0]["default_destination_name"],
			self.main_destination.name,
		)

	def test_create_validates_locations_and_accepts_model_backed_payload(self):
		create_view = OperationTypeViewSet.as_view({"post": "create"})

		invalid_request = APIRequestFactory().post(
			"/api/operation-types/",
			{
				"name": "Outbound Dispatch",
				"code": "OP-OUT-001",
				"operation_type": "outgoing",
				"warehouse": self.main_warehouse.id,
				"default_source": self.field_location.id,
				"default_destination": self.main_destination.id,
				"is_active": True,
			},
			format="json",
		)
		invalid_response = create_view(invalid_request)
		invalid_response.render()

		self.assertEqual(invalid_response.status_code, 400)
		self.assertIn("default_source", invalid_response.data)

		valid_request = APIRequestFactory().post(
			"/api/operation-types/",
			{
				"name": "Internal Move",
				"code": "OP-INT-001",
				"operation_type": "internal",
				"warehouse": self.main_warehouse.id,
				"default_source": self.main_source.id,
				"default_destination": self.main_destination.id,
				"is_active": True,
			},
			format="json",
		)
		valid_response = create_view(valid_request)
		valid_response.render()

		self.assertEqual(valid_response.status_code, 201)
		self.assertTrue(
			OperationType.objects.filter(
				name="Internal Move",
				code="OP-INT-001",
				operation_type="internal",
				warehouse=self.main_warehouse,
				default_source=self.main_source,
				default_destination=self.main_destination,
				is_active=True,
			).exists()
		)


class RouteViewSetTests(TestCase):
	def setUp(self):
		self.active_route = Route.objects.create(
			name="Dispatch Pipeline",
			code="ROUTE-001",
			description="Outbound dispatch route",
			steps=["Pick", "Pack", "Dispatch"],
			is_active=True,
		)
		self.inactive_route = Route.objects.create(
			name="Returns Flow",
			code="ROUTE-002",
			description="Returns inspection route",
			steps=[],
			is_active=False,
		)

	def test_list_supports_server_side_search_filter_and_pagination(self):
		request = APIRequestFactory().get(
			"/api/routes/",
			{
				"pagination": "true",
				"page": 1,
				"page_size": 1,
				"search": "dispatch",
				"is_active": "true",
				"has_steps": "true",
				"ordering": "name",
			},
		)
		response = RouteViewSet.as_view({"get": "list"})(request)
		response.render()
		data = response.data

		self.assertEqual(data["count"], 1)
		self.assertEqual(data["total_pages"], 1)
		self.assertEqual(data["current_page"], 1)
		self.assertEqual(len(data["results"]), 1)
		self.assertEqual(data["results"][0]["id"], self.active_route.id)
		self.assertEqual(data["results"][0]["code"], self.active_route.code)
		self.assertEqual(data["results"][0]["step_count"], 3)

	def test_create_accepts_model_backed_payload(self):
		create_view = RouteViewSet.as_view({"post": "create"})

		request = APIRequestFactory().post(
			"/api/routes/",
			{
				"name": "Warehouse Transfer Flow",
				"code": "ROUTE-003",
				"description": "Internal transfer routing",
				"steps": ["Request", "Approve", "Move", "Receive"],
				"is_active": True,
			},
			format="json",
		)
		response = create_view(request)
		response.render()

		self.assertEqual(response.status_code, 201)
		self.assertTrue(
			Route.objects.filter(
				name="Warehouse Transfer Flow",
				code="ROUTE-003",
				is_active=True,
			).exists()
		)
