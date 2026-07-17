from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from django.db.models import Count
from django.utils import timezone

from accounting.models import (
    AssetCategory,
    Asset,
    AssetDepreciation,
    AssetDisposal,
    AssetImpairment,
    AssetTransfer,
)
from accounting.serializers.asset_serializers import (
    AssetCategorySerializer,
    AssetDetailSerializer,
    AssetDepreciationSerializer,
    AssetDisposalSerializer,
    AssetImpairmentSerializer,
    AssetTransferSerializer,
)


class AssetCategoryViewSet(viewsets.ModelViewSet):
    queryset = AssetCategory.objects.annotate(assets_count=Count("assets")).all()
    serializer_class = AssetCategorySerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ["depreciation_method", "is_active"]
    search_fields = ["name", "code"]


class AssetViewSet(viewsets.ModelViewSet):
    # Always return full detail (with nested impairments/transfers/lines)
    # so the frontend workspace hook doesn't need a second per-asset fetch.
    queryset = Asset.objects.select_related(
        "category", "vendor", "cost_center"
    ).prefetch_related(
        "depreciation_lines", "impairments", "transfers", "disposal"
    ).all()
    serializer_class = AssetDetailSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["category", "status", "cost_center"]
    search_fields = ["name", "code", "serial_number", "location", "custodian"]
    ordering_fields = ["purchase_date", "purchase_cost", "current_value"]

    def perform_create(self, serializer):
        serializer.save(
            created_by=self.request.user,
            current_value=serializer.validated_data.get("purchase_cost", 0),
        )

    @action(detail=True, methods=["post"])
    def start(self, request, pk=None):
        """Move asset from draft to running."""
        asset = self.get_object()
        if asset.status != "draft":
            return Response(
                {"detail": "Only draft assets can be started."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        asset.status = "running"
        asset.save(update_fields=["status", "updated_at"])
        return Response(AssetDetailSerializer(asset).data)

    @action(detail=True, methods=["post"])
    def run_depreciation(self, request, pk=None):
        """Post a single depreciation entry for the current period."""
        asset = self.get_object()
        if asset.status not in ("running", "fully_depreciated"):
            return Response(
                {"detail": "Asset must be running."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        from decimal import Decimal
        import math
        salvage = float(asset.salvage_value or 0)
        current = float(asset.current_value or 0)
        cost = float(asset.purchase_cost or 0)
        life = int(asset.useful_life or 1)
        posted_periods = asset.depreciation_lines.filter(status="posted").count()
        remaining_periods = max(life - posted_periods, 1)
        depreciable_base = max(current - salvage, 0)
        amount = Decimal(str(round(depreciable_base / remaining_periods, 2)))
        new_value = Decimal(str(max(round(current - float(amount), 2), salvage)))
        period_num = posted_periods + 1
        new_status = "fully_depreciated" if float(new_value) <= salvage else "running"
        dep = AssetDepreciation.objects.create(
            asset=asset,
            date=timezone.now().date(),
            period=period_num,
            depreciation_amount=amount,
            accumulated_depreciation=Decimal(str(round(cost - float(new_value), 2))),
            remaining_value=new_value,
            status="posted",
        )

        # Create depreciation journal entry (DEBIT: Depreciation Expense, CREDIT: Accumulated Depreciation)
        from accounting.models import Journal, JournalEntry, JournalItem, Account
        journal = Journal.objects.filter(journal_type="general").first()
        if journal:
            entry = JournalEntry.objects.create(
                journal=journal,
                date=timezone.now().date(),
                reference=f"Depreciation: {asset.name} Period {period_num}",
                status="posted",
                total_debit=amount,
                total_credit=amount,
                posted_by=request.user,
                posted_at=timezone.now(),
            )
            dep_expense = Account.objects.filter(name__icontains="depreciation").first() or Account.objects.filter(code__startswith="63").first()
            accum_dep = Account.objects.filter(name__icontains="accumulated depreciation").first() or Account.objects.filter(code__startswith="16").first()
            if dep_expense:
                JournalItem.objects.create(journal_entry=entry, account=dep_expense, label=f"Depreciation: {asset.name}", debit=amount, credit=0)
                dep_expense.current_balance += amount
                dep_expense.save(update_fields=["current_balance"])
            if accum_dep:
                JournalItem.objects.create(journal_entry=entry, account=accum_dep, label=f"Depreciation: {asset.name}", debit=0, credit=amount)
                accum_dep.current_balance += amount
                accum_dep.save(update_fields=["current_balance"])

        asset.current_value = new_value
        asset.status = new_status
        asset.save(update_fields=["current_value", "status", "updated_at"])
        return Response(AssetDepreciationSerializer(dep).data)

    @action(detail=True, methods=["post"])
    def dispose(self, request, pk=None):
        """Record asset disposal."""
        asset = self.get_object()
        if asset.status == "disposed":
            return Response(
                {"detail": "Asset already disposed."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = AssetDisposalSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        sale_amount = serializer.validated_data.get("sale_amount", 0)
        gain_loss = float(sale_amount) - float(asset.current_value)

        with transaction.atomic():
            serializer.save(
                asset=asset,
                created_by=request.user,
                gain_loss=gain_loss,
            )

            # Create disposal journal entry
            from accounting.models import Journal, JournalEntry, JournalItem, Account
            journal = Journal.objects.filter(journal_type="general").first()
            if journal:
                entry = JournalEntry.objects.create(
                    journal=journal,
                    date=timezone.now().date(),
                    reference=f"Disposal: {asset.name}",
                    status="posted",
                    total_debit=float(sale_amount) + float(asset.current_value),
                    total_credit=float(sale_amount) + float(asset.current_value),
                    posted_by=request.user,
                    posted_at=timezone.now(),
                )
                # DEBIT: Cash/Bank (sale proceeds)
                cash_account = Account.objects.filter(name__icontains="cash").first() or Account.objects.filter(code__startswith="101").first()
                if cash_account and sale_amount > 0:
                    JournalItem.objects.create(journal_entry=entry, account=cash_account, label=f"Sale of {asset.name}", debit=sale_amount, credit=0)
                    cash_account.current_balance += sale_amount
                    cash_account.save(update_fields=["current_balance"])
                # DEBIT: Accumulated Depreciation (remove from books)
                accum_dep = Account.objects.filter(name__icontains="accumulated depreciation").first() or Account.objects.filter(code__startswith="16").first()
                accum_amount = float(asset.purchase_cost or 0) - float(asset.current_value or 0)
                if accum_dep and accum_amount > 0:
                    JournalItem.objects.create(journal_entry=entry, account=accum_dep, label=f"Remove accum depr: {asset.name}", debit=accum_amount, credit=0)
                    accum_dep.current_balance -= accum_amount
                    accum_dep.save(update_fields=["current_balance"])
                # CREDIT: Asset account (remove from books)
                asset_account = Account.objects.filter(name__icontains=asset.category.name if hasattr(asset, 'category') and asset.category else "").first() or Account.objects.filter(code__startswith="15").first()
                if asset_account:
                    JournalItem.objects.create(journal_entry=entry, account=asset_account, label=f"Remove asset: {asset.name}", debit=0, credit=float(asset.purchase_cost or 0))
                    asset_account.current_balance -= float(asset.purchase_cost or 0)
                    asset_account.save(update_fields=["current_balance"])
                # Record gain/loss if any
                if gain_loss != 0:
                    gl_account = Account.objects.filter(name__icontains="gain" if gain_loss > 0 else "loss").first() or Account.objects.filter(account_type__classification="income" if gain_loss > 0 else "expense").first()
                    if gl_account:
                        if gain_loss > 0:
                            JournalItem.objects.create(journal_entry=entry, account=gl_account, label=f"Gain on disposal: {asset.name}", debit=0, credit=gain_loss)
                            gl_account.current_balance += gain_loss
                        else:
                            JournalItem.objects.create(journal_entry=entry, account=gl_account, label=f"Loss on disposal: {asset.name}", debit=abs(gain_loss), credit=0)
                            gl_account.current_balance += abs(gain_loss)
                        gl_account.save(update_fields=["current_balance"])

            asset.status = "disposed"
            asset.current_value = 0
            asset.save(update_fields=["status", "current_value", "updated_at"])
        return Response({"detail": "Asset disposed."})

    @action(detail=True, methods=["post"], url_path="record-impairment")
    def record_impairment(self, request, pk=None):
        """Post an impairment charge against the asset."""
        asset = self.get_object()
        if asset.status not in ("running", "fully_depreciated"):
            return Response(
                {"detail": "Impairment can only be posted against active assets."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        from decimal import Decimal
        amount = Decimal(str(request.data.get("amount", 0)))
        date = request.data.get("date") or timezone.now().date()
        reason = request.data.get("reason", "")
        reviewer = request.data.get("reviewer", "Finance Controller")
        salvage = float(asset.salvage_value or 0)
        new_value = max(float(asset.current_value) - float(amount), salvage)
        impairment = AssetImpairment.objects.create(
            asset=asset,
            date=date,
            amount=amount,
            reason=reason,
            reviewer=reviewer,
        )
        asset.current_value = Decimal(str(round(new_value, 2)))
        asset.schedule_revision += 1
        asset.save(update_fields=["current_value", "schedule_revision", "updated_at"])
        return Response(AssetImpairmentSerializer(impairment).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def transfer(self, request, pk=None):
        """Record an internal asset transfer (location / custodian change)."""
        asset = self.get_object()
        date = request.data.get("date") or timezone.now().date()
        to_location = request.data.get("to_location", asset.location)
        assignee = request.data.get("assignee", asset.custodian)
        reason = request.data.get("reason", "")
        cost_center_id = request.data.get("cost_center_id")

        transfer = AssetTransfer.objects.create(
            asset=asset,
            date=date,
            from_location=asset.location,
            to_location=to_location,
            assignee=assignee,
            reason=reason,
            from_cost_center=asset.cost_center,
            to_cost_center_id=cost_center_id or (asset.cost_center_id),
        )
        asset.location = to_location
        asset.custodian = assignee
        if cost_center_id:
            asset.cost_center_id = cost_center_id
        asset.save(update_fields=["location", "custodian", "cost_center_id", "updated_at"])
        return Response(AssetTransferSerializer(transfer).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def recalculate(self, request, pk=None):
        """Bump the schedule revision number (signals a schedule recalculation)."""
        asset = self.get_object()
        asset.schedule_revision += 1
        asset.save(update_fields=["schedule_revision", "updated_at"])
        return Response({"detail": "Schedule recalculated.", "schedule_revision": asset.schedule_revision})


class AssetDepreciationViewSet(viewsets.ModelViewSet):
    queryset = AssetDepreciation.objects.select_related("asset").all()
    serializer_class = AssetDepreciationSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["asset", "status"]
    ordering_fields = ["date", "period"]


class AssetDisposalViewSet(viewsets.ModelViewSet):
    queryset = AssetDisposal.objects.select_related("asset").all()
    serializer_class = AssetDisposalSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["disposal_method"]


class AssetImpairmentViewSet(viewsets.ModelViewSet):
    queryset = AssetImpairment.objects.select_related("asset").all()
    serializer_class = AssetImpairmentSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["asset"]


class AssetTransferViewSet(viewsets.ModelViewSet):
    queryset = AssetTransfer.objects.select_related(
        "asset", "from_cost_center", "to_cost_center"
    ).all()
    serializer_class = AssetTransferSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["asset"]
