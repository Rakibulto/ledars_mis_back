from rest_framework import generics, serializers, viewsets
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from attendance.models import CutOff
from employee.models import Employee
from .models import (
    CompensatoryLeaveBalance,
    CompensatoryLeaveEarned,
    LeaveApproval,
    LeaveGroup,
    LeavePolicy,
    LeaveRequest,
    LeaveReset,
    LeaveTransfer,
    SupervisorLevel,
    SpecialLeavePolicy,
)
from .serializers import (
    CompensatoryLeaveEarnedSerializer,
    LeaveApprovalSerializer,
    LeaveGroupEmployeeSerializer,
    LeavePolicySerializer,
    LeaveRequestSerializer,
    LeaveResetSerializer,
    SupervisorLevelSerializer,
    SpecialLeavePolicySerializer,
)
from django.db import transaction
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from django.db.models import Q, Max
from django.utils import timezone
from datetime import timedelta, datetime, date
from dateutil.relativedelta import relativedelta
from django.http import Http404
from .utils import LeaveBalanceCalculator
from datetime import timedelta
from decimal import Decimal
from django.core.exceptions import ValidationError

# View to list and create leave groups


class LeaveGroupListCreateAPIView(generics.ListCreateAPIView):
    """View to list and create leave groups."""

    queryset = LeaveGroup.objects.all().order_by("-created_at")
    serializer_class = LeaveGroupEmployeeSerializer
    permission_classes = [IsAuthenticated]

    def has_permission(self, user):
        return hasattr(user, "role") and user.has_perm("leave.add_leavegroup")

    def create(self, request, *args, **kwargs):
        if not self.has_permission(request.user):
            raise PermissionDenied("You do not have permission to perform this action.")
        return super().create(request, *args, **kwargs)


class LeaveGroupRetrieveUpdateDestroyAPIView(generics.RetrieveUpdateDestroyAPIView):
    """View to retrieve, update, or delete a leave group."""

    queryset = LeaveGroup.objects.all().order_by("-created_at")
    serializer_class = LeaveGroupEmployeeSerializer
    permission_classes = [IsAuthenticated]

    def has_permission(self, user):
        return hasattr(user, "role") and user.has_perm("leave.change_leavegroup")

    def get_object(self):
        if not self.has_permission(self.request.user):
            raise PermissionDenied("You do not have permission to perform this action.")
        return super().get_object()


# View to list and create leave policies


class EmployeeLeavePolicyListAPIView(generics.ListAPIView):
    """View to list leave policies for a specific employee with eligibility checks.
    Optimized with prefetch_related for many-to-many relationships.
    """

    serializer_class = LeavePolicySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        employee_id = self.kwargs.get("employee_id")

        try:
            employee = Employee.objects.get(employee_id=employee_id)

            if not employee.leave_group:
                return LeavePolicy.objects.none()

            # Base queryset - policies for the employee's leave group with optimization
            policies = LeavePolicy.objects.prefetch_related("leave_groups").filter(
                leave_groups=employee.leave_group, is_active=True
            )

            # Filter by gender if policy specifies
            policies = policies.filter(Q(gender="any") | Q(gender=employee.gender))

            # Filter by service duration
            today = timezone.now().date()
            effective_policies = []

            for policy in policies:
                if policy.effective_from == "joining":
                    effective_policies.append(policy.id)
                elif (
                    policy.effective_from == "confirmation"
                    and employee.confirmation_date
                    and employee.confirmation_date <= today
                ):
                    effective_policies.append(policy.id)
                elif policy.effective_from == "one_year" and employee.joining_date:
                    one_year_later = employee.joining_date + timedelta(days=365)
                    if one_year_later <= today:
                        effective_policies.append(policy.id)

            return LeavePolicy.objects.filter(id__in=effective_policies)

        except Employee.DoesNotExist:
            raise Http404("Employee not found")


class LeavePolicyListCreateAPIView(generics.ListCreateAPIView):
    """View to list and create leave policies."""

    queryset = LeavePolicy.objects.all().order_by("-created_at")
    serializer_class = LeavePolicySerializer
    permission_classes = [IsAuthenticated]

    def has_permission(self, user):
        return hasattr(user, "role") and user.has_perm("leave.add_leavepolicy")

    def create(self, request, *args, **kwargs):
        if not self.has_permission(request.user):
            raise PermissionDenied("You do not have permission to perform this action.")
        return super().create(request, *args, **kwargs)


class LeavePolicyRetrieveUpdateDestroyAPIView(generics.RetrieveUpdateDestroyAPIView):
    """View to retrieve, update, or delete a leave policy."""

    queryset = LeavePolicy.objects.all().order_by("-created_at")
    serializer_class = LeavePolicySerializer
    permission_classes = [IsAuthenticated]

    def has_permission(self, user):
        return hasattr(user, "role") and user.has_perm("leave.change_leavepolicy")

    def get_object(self):
        if not self.has_permission(self.request.user):
            raise PermissionDenied("You do not have permission to perform this action.")
        return super().get_object()


# Views for leave requests


class EmployeeLeaveRequestListAPIView(generics.ListAPIView):
    """View to list leave requests for a specific employee and optionally their subordinates.
    Optimized with select_related to eliminate N+1 queries.
    """

    serializer_class = LeaveRequestSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        employee_id = self.kwargs.get("employee_id")
        include_subordinates = (
            self.request.query_params.get("include_subordinates", "false").lower()
            == "true"
        )

        try:
            employee = Employee.objects.get(employee_id=employee_id)

            # Start with the employee's own leave requests with optimized queries
            queryset = LeaveRequest.objects.select_related(
                "employee",
                "employee__department",
                "employee__location",
                "leave_policy",
                "creator",
            ).filter(employee=employee)

            # If include_subordinates is True, add subordinates' leave requests
            if include_subordinates:
                # Get all subordinates of this employee (where the employee's user is a supervisor)
                subordinates = Employee.objects.filter(
                    supervisor=employee.user, status="active"
                )

                # Add subordinates' leave requests to the queryset with optimizations
                subordinate_requests = LeaveRequest.objects.select_related(
                    "employee",
                    "employee__department",
                    "employee__location",
                    "leave_policy",
                    "creator",
                ).filter(employee__in=subordinates)

                queryset = queryset.union(subordinate_requests)

            return queryset.order_by("-created_at")

        except Employee.DoesNotExist:
            raise Http404("Employee not found")


class LeaveRequestListCreateAPIView(generics.ListCreateAPIView):
    """View to list and create leave requests with comprehensive validation.
    Optimized with select_related to eliminate N+1 queries.
    """

    queryset = LeaveRequest.objects.all().order_by("-created_at")
    serializer_class = LeaveRequestSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Optimize with select_related to fetch related objects in a single query
        queryset = (
            LeaveRequest.objects.select_related(
                "employee",
                "employee__department",
                "employee__location",
                "leave_policy",
                "creator",
                "updated_by",
            )
            .all()
            .order_by("-created_at")
        )

        today_data = self.request.query_params.get("today")

        # Get only today if params have today_data = True
        if today_data:
            today = timezone.now().date()
            queryset = queryset.filter(created_at__date=today)

        return queryset

    def perform_create(self, serializer):
        # Set creator of the leave request
        creator = self.request.user

        # Checking the user is a super admin or not
        is_admin = self.request.user.is_superuser

        if is_admin:
            # Admins must provide a user_id (foreign key to Employee's user)
            employee_obj = serializer.validated_data.get("employee")
            user_id = employee_obj.user_id

            if not user_id:
                raise serializers.ValidationError(
                    "Admins must specify a user_id for the leave request."
                )
            try:
                # Assuming Employee model has a foreign key to User
                employee = Employee.objects.get(user_id=user_id)
            except Employee.DoesNotExist:
                raise serializers.ValidationError(
                    "No employee found for the specified user_id."
                )
        else:
            # Non-admin users can only create requests for themselves
            try:
                employee = self.request.user.employee
            except AttributeError:
                raise serializers.ValidationError(
                    "No employee profile associated with this user."
                )

        leave_policy = serializer.validated_data["leave_policy"]
        start_date = serializer.validated_data["start_date"]
        end_date = serializer.validated_data["end_date"]
        is_half_day = serializer.validated_data.get("is_half_day", False)

        # If user is admin, skip all create-time validations and save directly
        if is_admin:
            serializer.save(creator=creator, employee=employee, status="pending")
            return

        # Non-admin users: Validate the leave request against the policy
        self.validate_leave_request(
            employee=employee,
            leave_policy=leave_policy,
            start_date=start_date,
            end_date=end_date,
            is_half_day=is_half_day,
            is_admin=is_admin,
        )

        # If all validations pass, save the leave request
        serializer.save(creator=creator, employee=employee, status="pending")

    def validate_leave_request(
        self, employee, leave_policy, start_date, end_date, is_half_day, is_admin
    ):
        """Comprehensive validation of leave request against all policy rules"""

        # Skip policy access validation if the user is an admin
        if not is_admin:
            # 1. Validate employee has access to the requested policy
            self.validate_policy_access(employee, leave_policy)

        # 2. Check if the user has permission to create leave requests
        self.validate_permissions(self.request.user)

        # # 3. Validate cut-off date for non-admin users
        # self.validate_cut_off_date()

        # 4. Check date validity
        self.validate_dates(start_date, end_date)

        # 5. Calculate effective leave days considering all rules
        requested_days = self.calculate_effective_days(
            employee, leave_policy, start_date, end_date, is_half_day
        )

        # 6. Validate against policy constraints (allow admins to bypass some checks)
        self.validate_policy_constraints(
            leave_policy, requested_days, is_half_day, start_date, is_admin
        )

        # 7. Check leave balance
        self.validate_leave_balance(
            employee, leave_policy, start_date, end_date, requested_days
        )

        # 8. Check for overlapping requests
        self.check_overlapping_requests(employee, start_date, end_date)

        # 9. Check SpecialLeavePolicy restrictions
        self.validate_special_leave_policy(employee, leave_policy, start_date, end_date)

        # Check max consecutive days across requests for the same policy
        self.validate_max_consecutive_days(
            employee, leave_policy, start_date, end_date, is_half_day
        )

        return True

    def validate_permissions(self, user):
        """Check if the user has permission to create leave requests."""
        if hasattr(user, "role") and not user.has_perm("leave.add_leaverequest"):
            raise PermissionDenied("You do not have permission to perform this action.")

    def validate_special_leave_policy(
        self, employee, leave_policy, start_date, end_date
    ):
        """Validate that new leave requests with a start date immediately before or after a SpecialLeavePolicy leave
        are restricted to available_policies in the SpecialLeavePolicy."""

        # Define buffer dates for the new request's start_date (day before and day after)
        day_before = start_date - timedelta(days=1)
        day_after = start_date + timedelta(days=1)

        # Check for approved special leaves where end_date = day_before or start_date = day_after
        special_leave_requests = LeaveRequest.objects.filter(
            Q(end_date=day_before) | Q(start_date=day_after),
            employee=employee,
            status="approved",
            leave_policy__special_policies__isnull=False,
        )

        if special_leave_requests.exists():
            # Get all SpecialLeavePolicy instances related to the approved leave policies
            special_policies = SpecialLeavePolicy.objects.filter(
                leave_policy__in=special_leave_requests.values_list(
                    "leave_policy", flat=True
                )
            )

            # Collect all available policies from these SpecialLeavePolicy instances
            allowed_policies = set()
            allowed_policy_names = []
            for special_policy in special_policies:
                for policy in special_policy.available_policies.all():
                    allowed_policies.add(policy.id)
                    allowed_policy_names.append(
                        policy.leave_type_name or f"Unnamed Policy (ID: {policy.id})"
                    )

            # Check if the requested leave_policy is in the allowed policies
            if leave_policy.id not in allowed_policies:
                allowed_policies_str = ", ".join(allowed_policy_names) or "None"
                raise serializers.ValidationError(
                    f"You can only request leaves from the following policies: "
                    f" {allowed_policies_str}."
                )

    def validate_policy_access(self, employee, leave_policy):
        """Validate employee has access to the requested policy"""
        if (
            not employee.leave_group
            or leave_policy not in employee.leave_group.leave_policies.all()
        ):
            raise serializers.ValidationError(
                "You don't have access to this leave policy."
            )

        if leave_policy.gender != "any" and leave_policy.gender != employee.gender:
            raise serializers.ValidationError(
                f"This leave policy is only for {leave_policy.gender} employees."
            )

        if not leave_policy.is_active:
            raise serializers.ValidationError("This leave policy is not active.")

        today = date.today()
        if leave_policy.effective_from == "confirmation" and (
            not employee.confirmation_date or employee.confirmation_date > today
        ):
            raise serializers.ValidationError(
                "This leave is only available after confirmation."
            )
        elif leave_policy.effective_from == "one_year" and (
            not employee.joining_date
            or employee.joining_date + timedelta(days=365) > today
        ):
            raise serializers.ValidationError(
                "This leave is only available after 1 year of service."
            )

    def validate_dates(self, start_date, end_date):
        """Validate date-related rules"""
        today = date.today()

        if start_date > end_date:
            raise serializers.ValidationError("Start date cannot be after end date.")

        # if end_date < today:
        #     raise serializers.ValidationError("Cannot apply for leave in the past.")

    def calculate_effective_days(
        self, employee, leave_policy, start_date, end_date, is_half_day
    ):
        """Calculate effective leave days considering all rules"""
        return LeaveBalanceCalculator.calculate_leave_days(
            start_date, end_date, employee, leave_policy, is_half_day
        )

    def validate_policy_constraints(
        self, leave_policy, requested_days, is_half_day, start_date, is_admin=False
    ):
        """Validate against policy constraints. Admins may bypass apply_before_days restriction."""
        if is_half_day and not leave_policy.allow_half_day:
            raise serializers.ValidationError(
                "Half-day leaves are not allowed for this policy."
            )

        # Only enforce apply_before_days for non-admin users
        if not is_admin and leave_policy.apply_before_days > 0:
            min_apply_date = date.today() + timedelta(
                days=leave_policy.apply_before_days
            )
            if start_date < min_apply_date:
                raise serializers.ValidationError(
                    f"This leave requires applying at least {leave_policy.apply_before_days} days in advance."
                )

        if not is_half_day:  # Only check min/max for full day leaves
            if (
                leave_policy.min_days_per_request
                and requested_days < leave_policy.min_days_per_request
            ):
                raise serializers.ValidationError(
                    f"Minimum {leave_policy.min_days_per_request} days required per request."
                )

            if (
                leave_policy.max_days_per_request
                and requested_days > leave_policy.max_days_per_request
            ):
                raise serializers.ValidationError(
                    f"Maximum {leave_policy.max_days_per_request} days allowed per request."
                )

    def validate_leave_balance(
        self, employee, leave_policy, start_date, end_date, requested_days
    ):
        """Validate leave balance considering dynamic reset periods"""
        if not leave_policy.total_leave_days:

            raise serializers.ValidationError(
                "This leave policy does not have a defined total leave days limit."
            )

        if leave_policy.leave_type_name == "Compensatory Leave":
            try:
                balance = employee.comp_leave_balance
                balance.clean_expired_leaves()

                if balance.current_balance < requested_days:
                    raise serializers.ValidationError(
                        f"Insufficient compensatory leave balance. "
                        f"Available: {balance.current_balance}, "
                        f"Required: {requested_days}"
                    )
                return  # Skip the normal balance check for compensatory leaves
            except CompensatoryLeaveBalance.DoesNotExist:
                raise serializers.ValidationError(
                    "No compensatory leave balance found."
                )

        # Get the current leave period based on the start date
        period_start, period_end = LeaveBalanceCalculator.get_leave_period_for_date(
            start_date
        )

        # Calculate used leaves in current period
        approved_leaves = LeaveRequest.objects.filter(
            employee=employee,
            leave_policy=leave_policy,
            status="approved",
            start_date__gte=period_start,
            end_date__lte=period_end,
        )

        # Calculate used days in current policy
        current_used = sum(
            LeaveBalanceCalculator.calculate_leave_days(
                max(leave.start_date, period_start),
                min(leave.end_date, period_end),
                employee,
                leave_policy,
                leave.is_half_day,
            )
            for leave in approved_leaves
        )

        # Get transferred days
        current_year = start_date
        transfer_data = (
            LeaveTransfer.objects.filter(
                employee=employee, to_leave_policy=leave_policy, year=current_year
            )
            .values("from_leave_policy", "to_leave_policy")
            .annotate(latest_transfer=Max("created_at"))
        )

        transferred_days = 0
        for data in transfer_data:
            transfer = LeaveTransfer.objects.filter(
                employee=employee,
                from_leave_policy=data["from_leave_policy"],
                to_leave_policy=data["to_leave_policy"],
                created_at=data["latest_transfer"],
            ).first()

            if transfer:
                transferred_days += float(transfer.days_transferred)

        # Calculate total used days (current + transferred)
        total_used = current_used + transferred_days

        # Check if requested leave exceeds balance
        available_balance = leave_policy.total_leave_days - total_used
        if requested_days > available_balance:
            raise serializers.ValidationError(
                f"Insufficient leave balance. Available: {available_balance} days, Requested: {requested_days} days."
            )

    def check_overlapping_requests(self, employee, start_date, end_date):
        """Check for overlapping leave requests"""
        overlapping_leaves = LeaveRequest.objects.filter(
            employee=employee,
            status__in=["pending", "approved"],
            start_date__lte=end_date,
            end_date__gte=start_date,
        ).exists()

        if overlapping_leaves:
            raise serializers.ValidationError(
                "You already have a leave request for this period."
            )

    # Check max consecutive days across requests for the same policy
    def validate_max_consecutive_days(
        self, employee, leave_policy, start_date, end_date, is_half_day
    ):
        """Validate that consecutive leave requests for the same policy do not exceed max_days_per_request."""

        if not leave_policy.max_days_per_request:
            return

        # Fetch existing approved or pending leave requests for the same policy
        existing_requests = (
            LeaveRequest.objects.filter(
                employee=employee,
                leave_policy=leave_policy,
                status__in=["pending", "approved"],
            )
            .order_by("start_date")
            .select_related("leave_policy")
        )

        # Create a list of leave periods including the new request
        leaves = [
            {
                "start_date": req.start_date,
                "end_date": req.end_date,
                "is_half_day": req.is_half_day,
                "is_new": False,
            }
            for req in existing_requests
        ]
        leaves.append(
            {
                "start_date": start_date,
                "end_date": end_date,
                "is_half_day": is_half_day,
                "is_new": True,
            }
        )

        if not leaves:
            return

        # Sort by start_date to process chronologically
        leaves = sorted(leaves, key=lambda x: x["start_date"])

        # Build chains of consecutive leave periods that include the new request
        chains = []
        current_chain = []
        has_new = False

        for req in leaves:
            if not current_chain:
                current_chain = [req]
                has_new = req.get("is_new", False)
            else:
                prev_end = current_chain[-1]["end_date"]
                gap_start = prev_end + timedelta(days=1)
                gap_end = req["start_date"] - timedelta(days=1)

                connected = True
                if gap_start <= gap_end:
                    current_date = gap_start
                    while current_date <= gap_end:
                        if self.is_working_day(current_date, employee):
                            connected = False
                            break
                        current_date += timedelta(days=1)

                if connected:
                    current_chain.append(req)
                    if req.get("is_new", False):
                        has_new = True
                else:
                    if has_new:
                        chains.append(current_chain)
                    current_chain = [req]
                    has_new = req.get("is_new", False)

        if has_new:
            chains.append(current_chain)

        # Validate each chain's total effective days
        for chain in chains:
            total_days = 0
            for req in chain:
                days = LeaveBalanceCalculator.calculate_leave_days(
                    req["start_date"],
                    req["end_date"],
                    employee,
                    leave_policy,
                    req["is_half_day"],
                )
                total_days += days
            if total_days > leave_policy.max_days_per_request:
                raise serializers.ValidationError(
                    f"Consecutive {leave_policy.leave_type_name} requests exceed the maximum allowed of "
                    f"{leave_policy.max_days_per_request} days."
                )

    def is_working_day(self, date, employee):
        """Determine if a given date is a working day for the employee using LeaveBalanceCalculator."""
        weekend_days = LeaveBalanceCalculator.get_weekend_days(employee)
        is_weekend = date.weekday() in weekend_days
        is_holiday = LeaveBalanceCalculator.is_holiday(date, employee)
        return not (is_weekend or is_holiday)


class LeaveRequestRetrieveUpdateDestroyAPIView(generics.RetrieveUpdateDestroyAPIView):
    """View to retrieve, update, or delete a leave request."""

    queryset = LeaveRequest.objects.all()
    serializer_class = LeaveRequestSerializer
    permission_classes = [IsAuthenticated]

    def has_permission(self, user):
        return hasattr(user, "role") and user.has_perm("leave.change_leaverequest")

    def get_object(self):
        if not self.has_permission(self.request.user):
            raise PermissionDenied("You do not have permission to perform this action.")
        return super().get_object()

    def update(self, request, *args, **kwargs):
        updated_by = self.request.user
        instance = self.get_object()
        instance.updated_by = updated_by
        # Allow superuser to update anytime
        if not request.user.is_superuser:
            if instance.status != "pending":
                raise PermissionDenied(
                    "You can only update leave requests while status is 'pending'."
                )
        try:
            instance.save()
            return super().update(request, *args, **kwargs)
        except ValidationError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    def partial_update(self, request, *args, **kwargs):
        updated_by = self.request.user
        instance = self.get_object()
        instance.updated_by = updated_by
        # Allow superuser to update anytime
        if not request.user.is_superuser:
            if instance.status != "pending":
                raise PermissionDenied(
                    "You can only update leave requests while status is 'pending'."
                )
        try:
            instance.save()
            return super().partial_update(request, *args, **kwargs)
        except ValidationError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


# Views for Supervisor Levels
class EmployeeSupervisorsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, employee_id):
        """Get all supervisors for a given employee."""
        supervisors = SupervisorLevel.objects.filter(
            employee__employee_id=employee_id
        ).order_by("level")
        serializer = SupervisorLevelSerializer(supervisors, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class SupervisorLevelListCreateAPIView(generics.ListCreateAPIView):
    """View to list and create supervisor levels with bulk creation logic and uniqueness enforcement.
    Optimized with select_related to eliminate N+1 queries.
    """

    queryset = (
        SupervisorLevel.objects.select_related(
            "employee", "supervisor", "supervisor__employee"
        )
        .all()
        .order_by("-created_at")
    )
    serializer_class = SupervisorLevelSerializer
    permission_classes = [IsAuthenticated]

    def create(self, request, *args, **kwargs):
        """Handle bulk creation of supervisor levels with uniqueness checks."""

        # Check if the user has permission to create supervisor levels
        if hasattr(request.user, "role") and not request.user.has_perm(
            "leave.add_supervisorlevel"
        ):
            raise PermissionDenied("You do not have permission to perform this action.")

        is_bulk = isinstance(request.data, list)
        data = request.data if is_bulk else [request.data]

        # Check for duplicate supervisor assignments for the same employee
        for item in data:
            employee = item.get("employee")
            supervisor = item.get("supervisor")
            if SupervisorLevel.objects.filter(
                employee=employee, supervisor=supervisor
            ).exists():
                return Response(
                    {"detail": "This supervisor is already assigned to the employee."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        serializer = self.get_serializer(data=request.data, many=is_bulk)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            self.perform_create(serializer)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def perform_create(self, serializer):
        serializer.save()


class SupervisorLevelRetrieveUpdateDestroyAPIView(
    generics.RetrieveUpdateDestroyAPIView
):
    """View to retrieve, update, or delete a supervisor level."""

    queryset = SupervisorLevel.objects.all().order_by("-created_at")
    serializer_class = SupervisorLevelSerializer
    permission_classes = [IsAuthenticated]

    def has_permission(self, user):
        return hasattr(user, "role") and user.has_perm("leave.change_supervisorlevel")

    def get_object(self):
        if not self.has_permission(self.request.user):
            raise PermissionDenied("You do not have permission to perform this action.")
        return super().get_object()


# Views for Leave Approval


class LeaveApprovalAPIView(generics.ListCreateAPIView):
    """View to list and create leave approvals, with optional filtering by approver id.
    Optimized with select_related to eliminate N+1 queries.
    """

    serializer_class = LeaveApprovalSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Optimize with select_related to fetch related objects in a single query
        queryset = (
            LeaveApproval.objects.select_related(
                "leave_request",
                "leave_request__employee",
                "leave_request__employee__department",
                "leave_request__employee__location",
                "leave_request__leave_policy",
                "approver",
                "approver__employee",
            )
            .all()
            .order_by("-created_at")
        )

        approver_id = self.request.query_params.get("approver_id")
        leave_request_id = self.request.query_params.get("leave_request_id")

        if approver_id is not None:
            queryset = queryset.filter(approver=approver_id)

        if leave_request_id is not None:
            queryset = queryset.filter(leave_request__id=leave_request_id)
        return queryset


class LeaveApprovalRetrieveUpdateDestroyAPIView(generics.RetrieveUpdateDestroyAPIView):
    """View to retrieve, update, or delete a leave approval with supervisor hierarchy enforcement."""

    queryset = LeaveApproval.objects.all()
    serializer_class = LeaveApprovalSerializer
    permission_classes = [IsAuthenticated]

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        user = request.user

        # Ensure the user has permission to update leave approvals
        if not user.has_perm("leave.change_leaveapproval"):
            raise PermissionDenied(
                "You do not have permission to update leave approvals."
            )

        # Allow admin users to update any approval
        if user.is_superuser:
            return super().update(request, *args, **kwargs)

        approval_instance = instance.leave_request.start_date
        approval_status = request.data.get("status")
        employee = instance.leave_request.employee
        leave_policy = instance.leave_request.leave_policy
        start_date = instance.leave_request.start_date

        # Get current cut-off information
        current_cut_off = CutOff.objects.latest("created_at")
        current_cut_off_end = current_cut_off.cut_off
        current_cut_off_start = (
            current_cut_off_end - relativedelta(months=1)
        ) + timedelta(days=1)

        # Check if leave request falls in the CURRENT cut-off period (Allows future dates)
        is_in_current_period = current_cut_off_start <= approval_instance

        # Check if today's date has PASSED the cut-off end date
        cut_off_has_passed = timezone.now().date() > current_cut_off_end

        # If the leave is in current period BUT cut-off has passed, only allow rejection
        if is_in_current_period and cut_off_has_passed:
            # Current period but cut-off date passed - only allow rejection
            if approval_status != "rejected":
                raise PermissionDenied(
                    f"The cut-off date for this period ({current_cut_off_end}) has passed. "
                    f"You can only reject leave requests from this period, not approve them."
                )
        elif not is_in_current_period:
            # Leave is from a previous period - only allow rejection
            if approval_status != "rejected":
                raise PermissionDenied(
                    f"The leave request date ({approval_instance}) is from a previous cut-off period. "
                    f"You can only reject this request, not approve it."
                )
        else:
            # Leave is in current period AND cut-off hasn't passed - allow full updates
            if approval_status == "approved":
                self.validate_special_leave_policy(employee, leave_policy, start_date)

        # Ensure only the assigned approver can update this approval
        if instance.approver != user:
            raise PermissionDenied(
                "You are not allowed to update this other's approval"
            )

        # Get the supervisor level for this approval and employee
        supervisor_level = SupervisorLevel.objects.filter(
            employee=employee, supervisor=user
        ).first()

        if not supervisor_level:
            raise PermissionDenied("You are not a supervisor for this employee.")

        # Check if all lower levels have approved
        lower_levels = SupervisorLevel.objects.filter(
            employee=employee, level__lt=supervisor_level.level
        ).values_list("supervisor", flat=True)

        if lower_levels.exists():
            # Check if all lower level supervisors have approved
            pending_approvals = LeaveApproval.objects.filter(
                leave_request=instance.leave_request,
                approver__in=lower_levels,
            ).exclude(status="approved")
            if pending_approvals.exists():
                raise PermissionDenied("Lower level supervisors must approve first.")

        return super().update(request, *args, **kwargs)

    def validate_special_leave_policy(self, employee, leave_policy, start_date):
        """Validate that new leave requests with a start date immediately before or after a SpecialLeavePolicy leave
        are restricted to available_policies in the SpecialLeavePolicy."""
        from datetime import timedelta

        # Define buffer dates for the new request's start_date (day before and day after)
        day_before = start_date - timedelta(days=1)
        day_after = start_date + timedelta(days=1)

        # Check for approved special leaves where end_date = day_before or start_date = day_after
        special_leave_requests = LeaveRequest.objects.filter(
            Q(end_date=day_before) | Q(start_date=day_after),
            employee=employee,
            status="approved",
            leave_policy__special_policies__isnull=False,
        )
        if special_leave_requests.exists():
            # Get all SpecialLeavePolicy instances related to the approved leave policies
            special_policies = SpecialLeavePolicy.objects.filter(
                leave_policy__in=special_leave_requests.values_list(
                    "leave_policy", flat=True
                )
            )

            # Collect all available policies from these SpecialLeavePolicy instances
            allowed_policies = set()
            allowed_policy_names = []
            for special_policy in special_policies:
                for policy in special_policy.available_policies.all():
                    allowed_policies.add(policy.id)
                    allowed_policy_names.append(
                        policy.leave_type_name or f"Unnamed Policy (ID: {policy.id})"
                    )

            # Check if the requested leave_policy is in the allowed policies
            if leave_policy.id not in allowed_policies:
                allowed_policies_str = ", ".join(allowed_policy_names) or "None"
                raise serializers.ValidationError(
                    f"You can only request leaves from the following policies: "
                    f" {allowed_policies_str}."
                )


# Views for calculating leave balance
class EmployeeLeaveBalanceAPI(APIView):
    """API endpoint for leave balance calculation including compensatory leave"""

    def get(self, request, employee_id=None):
        from_date = request.query_params.get("from_date")
        to_date = request.query_params.get("to_date")
        year = request.query_params.get("year")
        include_subordinates = (
            request.query_params.get("include_subordinates", "false").lower() == "true"
        )

        try:
            # Date range handling
            if year:
                year = int(year)
                start_date, end_date = LeaveBalanceCalculator.get_leave_period_for_year(
                    year
                )
            elif from_date and to_date:
                start_date = datetime.strptime(from_date, "%Y-%m-%d").date()
                end_date = datetime.strptime(to_date, "%Y-%m-%d").date()
            else:
                start_date, end_date = (
                    LeaveBalanceCalculator.get_leave_period_for_date()
                )

            if employee_id:
                return self.get_employee_balance(
                    employee_id, start_date, end_date, include_subordinates
                )
            return self.get_all_employees_balance(start_date, end_date)

        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def get_employee_balance(
        self, employee_id, from_date, to_date, include_subordinates=False
    ):
        try:
            employee = Employee.objects.get(employee_id=employee_id)

            if not employee.leave_group:
                return Response(
                    {"error": "Employee has no leave group assigned"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Get the main employee's balance
            main_employee_balance = self._calculate_employee_balance(
                employee, from_date, to_date
            )

            # If include_subordinates is True, get subordinates' balances too
            if include_subordinates:
                subordinates_balances = self._get_subordinates_balances(
                    employee, from_date, to_date
                )
                return Response(
                    {
                        "supervisor": main_employee_balance,
                        "subordinates": subordinates_balances,
                    },
                    status=status.HTTP_200_OK,
                )

            return Response(main_employee_balance, status=status.HTTP_200_OK)

        except Employee.DoesNotExist:
            return Response(
                {"error": "Employee not found"}, status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _get_subordinates_balances(self, supervisor_employee, from_date, to_date):
        """Get leave balances for all subordinates of a supervisor"""
        subordinates = Employee.objects.filter(
            supervisor=supervisor_employee.user,
            status="active",
            leave_group__isnull=False,
        )

        subordinates_data = []
        for subordinate in subordinates:
            try:
                subordinate_balance = self._calculate_employee_balance(
                    subordinate, from_date, to_date
                )
                subordinates_data.append(subordinate_balance)
            except Exception as e:
                # Log the error but continue with other subordinates
                subordinates_data.append(
                    {
                        "employee_id": subordinate.employee_id,
                        "employee_name": subordinate.employee_name,
                        "error": f"Error calculating balance: {str(e)}",
                    }
                )

        return subordinates_data

    def _calculate_employee_balance(self, employee, from_date, to_date):
        """Calculate leave balance for a single employee"""
        current_year = from_date.year
        # Filter policies based on employee's leave group, active status, and gender
        policies = LeavePolicy.objects.filter(
            leave_groups=employee.leave_group, is_active=True
        ).filter(Q(gender="any") | Q(gender=employee.gender))
        balances = []

        # Get compensatory leave policy first
        comp_policy = (
            LeavePolicy.objects.filter(
                leave_groups=employee.leave_group,
                is_active=True,
                leave_type_name="Compensatory Leave",
            )
            .filter(Q(gender="any") | Q(gender=employee.gender))
            .first()
        )

        # Get regular leave balances (existing logic)
        for policy in policies:
            # Skip compensatory leave policy as we'll handle it separately
            if policy.leave_type_name == "Compensatory Leave":
                continue

            # Original balance calculation logic for other leave types
            approved_leaves = LeaveRequest.objects.filter(
                employee=employee,
                leave_policy=policy,
                status="approved",
                start_date__lte=to_date,
                end_date__gte=from_date,
            )

            current_used = sum(
                LeaveBalanceCalculator.calculate_leave_days(
                    max(leave.start_date, from_date),
                    min(leave.end_date, to_date),
                    employee,
                    policy,
                    leave.is_half_day,
                )
                for leave in approved_leaves
            )

            transfer_data = (
                LeaveTransfer.objects.filter(
                    employee=employee,
                    to_leave_policy=policy,
                    year__gte=from_date,
                    year__lte=to_date,
                )
                .values("from_leave_policy", "to_leave_policy")
                .annotate(latest_transfer=Max("created_at"))
            )

            transferred_days = 0
            for data in transfer_data:
                transfer = LeaveTransfer.objects.filter(
                    employee=employee,
                    from_leave_policy=data["from_leave_policy"],
                    to_leave_policy=data["to_leave_policy"],
                    created_at=data["latest_transfer"],
                ).first()

                if transfer:
                    transferred_days += float(transfer.days_transferred)

            total_used = current_used + transferred_days

            pending_leaves = LeaveRequest.objects.filter(
                employee=employee,
                leave_policy=policy,
                status="pending",
                start_date__lte=to_date,
                end_date__gte=from_date,
            )

            pending_days = sum(
                LeaveBalanceCalculator.calculate_leave_days(
                    max(leave.start_date, from_date),
                    min(leave.end_date, to_date),
                    employee,
                    policy,
                    leave.is_half_day,
                )
                for leave in pending_leaves
            )

            balances.append(
                {
                    "employee_id": employee.employee_id,
                    "employee_name": employee.employee_name,
                    "department": (
                        employee.department.name if employee.department else None
                    ),
                    "designation": (
                        employee.designation.name if employee.designation else None
                    ),
                    "leave_policy_id": policy.id,
                    "leave_type_name": policy.leave_type_name,
                    "total_allowed": policy.total_leave_days,
                    "used": float(total_used),
                    "pending": float(pending_days),
                    "remaining": max(policy.total_leave_days - total_used, 0),
                    "counts_holidays": policy.count_holidays,
                    "counts_weekends": policy.count_weekends,
                    "from_date": from_date.isoformat(),
                    "to_date": to_date.isoformat(),
                }
            )

        # Add compensatory leave balance information if employee is eligible
        if comp_policy:
            total_earned = 0
            total_used = 0
            pending_comp_days = 0
            current_balance = Decimal("0")

            try:
                comp_balance = employee.comp_leave_balance

                # First clean expired leaves (this updates the is_expired status)
                comp_balance.clean_expired_leaves()

                # Get current balance after cleaning expired leaves
                current_balance = comp_balance.current_balance
                total_used = comp_balance.total_used

                # Calculate total earned (non-expired) leaves for display
                total_earned = comp_balance.total_earned

            except CompensatoryLeaveBalance.DoesNotExist:
                # If no compensatory balance exists, all remain 0
                total_earned = 0
                total_used = 0
                current_balance = Decimal("0")

            # Calculate pending compensatory leave requests
            pending_comp_leaves = LeaveRequest.objects.filter(
                employee=employee,
                leave_policy=comp_policy,
                status="pending",
                start_date__lte=to_date,
                end_date__gte=from_date,
            )
            pending_comp_days = sum(
                LeaveBalanceCalculator.calculate_leave_days(
                    max(leave.start_date, from_date),
                    min(leave.end_date, to_date),
                    employee,
                    comp_policy,
                    leave.is_half_day,
                )
                for leave in pending_comp_leaves
            )

            # Convert pending_comp_days to Decimal for consistent arithmetic
            pending_comp_days = Decimal(str(pending_comp_days))

            # Use current_balance for remaining (accounts for expired leaves)
            remaining = max(current_balance, Decimal("0"))

            balances.append(
                {
                    "employee_id": employee.employee_id,
                    "employee_name": employee.employee_name,
                    "department": (
                        employee.department.name if employee.department else None
                    ),
                    "designation": (
                        employee.designation.name if employee.designation else None
                    ),
                    "leave_policy_id": comp_policy.id,
                    "leave_type_name": "Compensatory Leave",
                    # Convert to float for JSON serialization
                    "total_allowed": float(current_balance),
                    # Convert to float for JSON serialization
                    "used": float(total_used),
                    # Convert to float for JSON serialization
                    "pending": float(pending_comp_days),
                    # Convert to float for JSON serialization
                    "remaining": float(remaining),
                    "counts_holidays": comp_policy.count_holidays,
                    "counts_weekends": comp_policy.count_weekends,
                    "from_date": from_date.isoformat(),
                    "to_date": to_date.isoformat(),
                    "is_compensatory": True,
                }
            )

        return balances

    def get_all_employees_balance(self, from_date, to_date):
        try:
            employees = Employee.objects.filter(
                status="active", leave_group__isnull=False
            )
            all_balances = []

            for employee in employees:
                try:
                    employee_balance = self._calculate_employee_balance(
                        employee, from_date, to_date
                    )
                    all_balances.extend(employee_balance)
                except Exception as e:
                    # Log the error but continue with other employees
                    all_balances.append(
                        {
                            "employee_id": employee.employee_id,
                            "employee_name": employee.employee_name,
                            "error": f"Error calculating balance: {str(e)}",
                        }
                    )

            return Response(all_balances, status=status.HTTP_200_OK)

        except Exception as e:
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class LeaveResetPeriodViewSet(generics.ListCreateAPIView):
    """View to list and create leave reset periods."""

    queryset = LeaveReset.objects.all().order_by("-created_at")
    serializer_class = LeaveResetSerializer
    permission_classes = [IsAuthenticated]

    def has_permission(self, user):
        return hasattr(user, "role") and user.has_perm("leave.add_leavereset")

    def create(self, request, *args, **kwargs):
        if not self.has_permission(request.user):
            raise PermissionDenied("You do not have permission to perform this action.")
        return super().create(request, *args, **kwargs)


class LeaveResetPeriodRetrieveUpdateDestroyAPIView(
    generics.RetrieveUpdateDestroyAPIView
):
    """View to retrieve, update, or delete a leave reset period."""

    queryset = LeaveReset.objects.all().order_by("-created_at")
    serializer_class = LeaveResetSerializer
    permission_classes = [IsAuthenticated]

    def has_permission(self, user):
        return hasattr(user, "role") and user.has_perm("leave.change_leavereset")

    def get_object(self):
        if not self.has_permission(self.request.user):
            raise PermissionDenied("You do not have permission to perform this action.")
        return super().get_object()


# View for Compensatory Leave Balance


class CompensatoryLeaveViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing compensatory leave earned records by employee_id and date range.
    Optimized with select_related to eliminate N+1 queries.
    """

    serializer_class = CompensatoryLeaveEarnedSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        employee_id = self.request.query_params.get("employee_id")
        from_date = self.request.query_params.get("from_date")

        # Optimize with select_related for employee relation
        queryset = CompensatoryLeaveEarned.objects.select_related("employee").filter(
            is_expired=False
        )

        if employee_id:
            queryset = queryset.filter(employee__employee_id=employee_id)

        if from_date:
            queryset = queryset.filter(expires_on__gte=from_date)

        if not employee_id and not self.request.user.is_superuser:
            return CompensatoryLeaveEarned.objects.none()

        return queryset


# Views for Special Leave Policies
class SpecialLeavePolicyListCreateAPIView(generics.ListCreateAPIView):
    """View to list and create special leave policies."""

    queryset = SpecialLeavePolicy.objects.all().order_by("-created_at")
    serializer_class = SpecialLeavePolicySerializer
    permission_classes = [IsAuthenticated]

    def has_permission(self, user, action):
        if action == "list":
            return hasattr(user, "role") and user.has_perm(
                "leave.view_specialleavepolicy"
            )
        elif action == "create":
            return hasattr(user, "role") and user.has_perm(
                "leave.add_specialleavepolicy"
            )
        return False

    @property
    def allowed_methods(self):
        methods = list(super().allowed_methods)
        if "POST" in methods and not self.has_permission(self.request.user, "create"):
            methods.remove("POST")
        return methods

    def list(self, request, *args, **kwargs):
        if not self.has_permission(request.user, "list"):
            raise PermissionDenied(
                "You do not have permission to view special leave policies."
            )
        return super().list(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        if not self.has_permission(request.user, "create"):
            raise PermissionDenied(
                "You do not have permission to create special leave policies."
            )
        return super().create(request, *args, **kwargs)

    def perform_create(self, serializer):
        serializer.save(creator=self.request.user)


class SpecialLeavePolicyRetrieveUpdateDestroyAPIView(
    generics.RetrieveUpdateDestroyAPIView
):
    """View to retrieve, update, or delete a special leave policy."""

    queryset = SpecialLeavePolicy.objects.all().order_by("-created_at")
    serializer_class = SpecialLeavePolicySerializer
    permission_classes = [IsAuthenticated]

    def has_permission(self, user, action):
        if action == "retrieve":
            return hasattr(user, "role") and user.has_perm(
                "leave.view_specialleavepolicy"
            )
        elif action == "update":
            return hasattr(user, "role") and user.has_perm(
                "leave.change_specialleavepolicy"
            )
        elif action == "destroy":
            return hasattr(user, "role") and user.has_perm(
                "leave.delete_specialleavepolicy"
            )
        return False

    @property
    def allowed_methods(self):
        methods = list(super().allowed_methods)
        if "PUT" in methods and not self.has_permission(self.request.user, "update"):
            methods.remove("PUT")
        if "PATCH" in methods and not self.has_permission(self.request.user, "update"):
            methods.remove("PATCH")
        if "DELETE" in methods and not self.has_permission(
            self.request.user, "destroy"
        ):
            methods.remove("DELETE")
        return methods

    def retrieve(self, request, *args, **kwargs):
        if not self.has_permission(request.user, "retrieve"):
            raise PermissionDenied(
                "You do not have permission to view special leave policies."
            )
        return super().retrieve(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        if not self.has_permission(request.user, "update"):
            raise PermissionDenied(
                "You do not have permission to update special leave policies."
            )
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        if not self.has_permission(request.user, "destroy"):
            raise PermissionDenied(
                "You do not have permission to delete special leave policies."
            )
        return super().destroy(request, *args, **kwargs)
