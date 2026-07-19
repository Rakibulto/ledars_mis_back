"""Build Project Expenditure and Monthly Action Plan payloads from project plans."""

from calendar import monthrange
from datetime import date, timedelta
from decimal import Decimal


def _as_date(value):
    if isinstance(value, date):
        return value
    return None


def _decimal(value):
    try:
        return Decimal(str(value or 0))
    except Exception:
        return Decimal("0")


def _ordinal(n):
    if 10 <= (n % 100) <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def _format_month_year(value):
    return value.strftime("%b-%y")


def build_project_years(start_date, end_date):
    start = _as_date(start_date)
    end = _as_date(end_date)
    if not start or not end or end < start:
        return []

    years = []
    cursor = start
    index = 1
    while cursor <= end:
        year_end = min(date(cursor.year, 12, 31), end)
        years.append(
            {
                "index": index,
                "label": (
                    f"{_ordinal(index)} project year "
                    f"({_format_month_year(cursor)} to {_format_month_year(year_end)})"
                ),
                "start_date": cursor.isoformat(),
                "end_date": year_end.isoformat(),
                "year": cursor.year,
            }
        )
        index += 1
        cursor = year_end + timedelta(days=1)
    return years


def build_project_months(start_date, end_date):
    start = _as_date(start_date)
    end = _as_date(end_date)
    if not start or not end or end < start:
        return []

    months = []
    cursor = date(start.year, start.month, 1)
    end_month = date(end.year, end.month, 1)
    index = 1
    while cursor <= end_month:
        last_day = monthrange(cursor.year, cursor.month)[1]
        month_end = min(date(cursor.year, cursor.month, last_day), end)
        month_start = max(cursor, start)
        months.append(
            {
                "index": index,
                "label": cursor.strftime("%b-%y"),
                "year": cursor.year,
                "month": cursor.month,
                "start_date": month_start.isoformat(),
                "end_date": month_end.isoformat(),
            }
        )
        index += 1
        if cursor.month == 12:
            cursor = date(cursor.year + 1, 1, 1)
        else:
            cursor = date(cursor.year, cursor.month + 1, 1)
    return months


def build_project_weeks(start_date, end_date):
    start = _as_date(start_date)
    end = _as_date(end_date)
    if not start or not end or end < start:
        return []

    # Align to Monday of the start week
    cursor = start - timedelta(days=start.weekday())
    weeks = []
    index = 1
    while cursor <= end:
        week_end = cursor + timedelta(days=6)
        overlap_start = max(cursor, start)
        overlap_end = min(week_end, end)
        if overlap_start <= overlap_end:
            iso = overlap_start.isocalendar()
            weeks.append(
                {
                    "index": index,
                    "label": f"W{iso.week} {iso.year}",
                    "year": iso.year,
                    "week": iso.week,
                    "start_date": overlap_start.isoformat(),
                    "end_date": overlap_end.isoformat(),
                }
            )
            index += 1
        cursor = week_end + timedelta(days=1)
    return weeks


def _user_designation(user):
    employee = getattr(user, "employee", None)
    if employee is None:
        return ""
    designation = getattr(employee, "designation", None)
    if designation is None:
        return ""
    return getattr(designation, "name", None) or str(designation) or ""


def _format_responsible(users):
    labels = []
    for user in users:
        designation = _user_designation(user)
        labels.append(designation or user.username or "User")
    return ", ".join(labels)


def _range_periods(sub_plan):
    """Normalized list of (start_date, end_date, unit_no) for a sub plan."""
    periods = []
    for period in sub_plan.unit_periods.all():
        unit_no = _decimal(period.unit_no)
        if unit_no <= 0:
            continue
        start = _as_date(period.start_date)
        end = _as_date(period.end_date)
        if start and end:
            if end < start:
                start, end = end, start
            periods.append((start, end, unit_no))
            continue
        # Legacy monthly bucket
        if period.period_type == "monthly" and int(period.month or 0) > 0:
            last_day = monthrange(int(period.year), int(period.month))[1]
            periods.append(
                (
                    date(int(period.year), int(period.month), 1),
                    date(int(period.year), int(period.month), last_day),
                    unit_no,
                )
            )
    if periods:
        return periods

    unit_no = _decimal(sub_plan.unit_no)
    if not unit_no:
        return periods
    start = _as_date(sub_plan.start_date)
    end = _as_date(sub_plan.end_date) or start
    if start and end:
        periods.append((start, end, unit_no))
    return periods


def _overlap_days(a_start, a_end, b_start, b_end):
    overlap_start = max(a_start, b_start)
    overlap_end = min(a_end, b_end)
    if overlap_start > overlap_end:
        return 0
    return (overlap_end - overlap_start).days + 1


def _is_off_day(value):
    """Friday and Saturday are non-working days."""
    return value.weekday() in (4, 5)


def _off_days_in_month(target_year, target_month, days_in_month):
    return [
        day
        for day in range(1, days_in_month + 1)
        if _is_off_day(date(target_year, target_month, day))
    ]


def _distributed_working_days_in_month(ranges, target_year, target_month, days_in_month):
    """Days in the month that fall inside a unit distribution range (excluding off days)."""
    marks = []
    for day in range(1, days_in_month + 1):
        current = date(target_year, target_month, day)
        if _is_off_day(current):
            continue
        for range_start, range_end, _units in ranges:
            if range_start <= current <= range_end:
                marks.append(day)
                break
    return sorted(set(marks))


def _units_for_bucket_from_ranges(ranges, bucket_start, bucket_end):
    """
    Allocate each range's units to a bucket proportionally by overlapping working days.
    """
    total = Decimal("0")
    for range_start, range_end, range_units in ranges:
        range_days = _working_days_in_range(range_start, range_end)
        if range_days <= 0:
            continue
        overlap = _overlap_working_days(range_start, range_end, bucket_start, bucket_end)
        if overlap <= 0:
            continue
        total += (range_units * Decimal(overlap) / Decimal(range_days)).quantize(Decimal("0.01"))
    return total


def _working_days_in_range(start, end):
    if end < start:
        start, end = end, start
    count = 0
    cursor = start
    while cursor <= end:
        if not _is_off_day(cursor):
            count += 1
        cursor += timedelta(days=1)
    return count


def _overlap_working_days(a_start, a_end, b_start, b_end):
    overlap_start = max(a_start, b_start)
    overlap_end = min(a_end, b_end)
    if overlap_start > overlap_end:
        return 0
    return _working_days_in_range(overlap_start, overlap_end)


def build_expenditure_payload(project, period="yearly"):
    period = (period or "yearly").strip().lower()
    if period not in {"yearly", "monthly", "weekly"}:
        period = "yearly"

    if period == "monthly":
        buckets = build_project_months(project.start_date, project.end_date)
    elif period == "weekly":
        buckets = build_project_weeks(project.start_date, project.end_date)
    else:
        buckets = build_project_years(project.start_date, project.end_date)

    partner = ""
    if getattr(project, "donor", None):
        partner = getattr(project.donor, "name", "") or ""
    if not partner:
        partner = "LEDARS"

    currency = project.currency or "BDT"
    rows = [
        {
            "row_type": "section",
            "budget_code": "",
            "title": "Project activities",
            "unit_no": None,
            "unit_cost": None,
            "period_splits": [
                {"period_index": b["index"], "unit_no": None, "unit_cost": None, "cost": None}
                for b in buckets
            ],
            "total_cost": None,
        }
    ]

    total_expenditure = Decimal("0")
    plans = list(project.plans.all().order_by("serial_no", "id"))

    for plan in plans:
        sub_plans = list(plan.sub_plans.all().order_by("sort_order", "id"))
        plan_unit_no = sum((_decimal(s.unit_no) for s in sub_plans), Decimal("0"))
        plan_cost = sum((_decimal(s.cost) for s in sub_plans), Decimal("0"))
        plan_unit_cost = (
            (plan_cost / plan_unit_no).quantize(Decimal("0.01")) if plan_unit_no else Decimal("0")
        )

        plan_bucket_units = {b["index"]: Decimal("0") for b in buckets}
        plan_bucket_costs = {b["index"]: Decimal("0") for b in buckets}
        sub_rows = []

        for sub in sub_plans:
            unit_cost = _decimal(sub.unit_cost)
            unit_no = _decimal(sub.unit_no)
            sub_cost = _decimal(sub.cost) or (unit_no * unit_cost)
            total_expenditure += sub_cost
            ranges = _range_periods(sub)

            splits = []
            for bucket in buckets:
                b_start = date.fromisoformat(bucket["start_date"])
                b_end = date.fromisoformat(bucket["end_date"])
                b_units = _units_for_bucket_from_ranges(ranges, b_start, b_end)

                b_cost = (b_units * unit_cost).quantize(Decimal("0.01")) if b_units else Decimal("0")
                plan_bucket_units[bucket["index"]] += b_units
                plan_bucket_costs[bucket["index"]] += b_cost
                splits.append(
                    {
                        "period_index": bucket["index"],
                        "unit_no": float(b_units) if b_units else None,
                        "unit_cost": float(unit_cost) if b_units else None,
                        "cost": float(b_cost) if b_units else None,
                    }
                )

            sub_rows.append(
                {
                    "row_type": "sub",
                    "budget_code": sub.serial_code or "",
                    "title": sub.title or "Untitled sub activity",
                    "unit_no": float(unit_no) if unit_no else None,
                    "unit_cost": float(unit_cost) if unit_cost else None,
                    "period_splits": splits,
                    "total_cost": float(sub_cost) if sub_cost else None,
                }
            )

        plan_splits = []
        for bucket in buckets:
            b_units = plan_bucket_units[bucket["index"]]
            b_cost = plan_bucket_costs[bucket["index"]]
            b_unit_cost = (
                (b_cost / b_units).quantize(Decimal("0.01")) if b_units else Decimal("0")
            )
            plan_splits.append(
                {
                    "period_index": bucket["index"],
                    "unit_no": float(b_units) if b_units else None,
                    "unit_cost": float(b_unit_cost) if b_units else None,
                    "cost": float(b_cost) if b_cost else None,
                }
            )

        rows.append(
            {
                "row_type": "main",
                "budget_code": plan.serial_code or str(plan.serial_no or ""),
                "title": plan.title or "Untitled activity",
                "unit_no": float(plan_unit_no) if plan_unit_no else None,
                "unit_cost": float(plan_unit_cost) if plan_unit_no else None,
                "period_splits": plan_splits,
                "total_cost": float(plan_cost) if plan_cost else None,
            }
        )
        rows.extend(sub_rows)

    contingency = (total_expenditure * Decimal("0.02")).quantize(Decimal("0.01"))
    grand_total = total_expenditure + contingency

    return {
        "project": {
            "id": project.id,
            "title": project.title or "",
            "code": project.code or "",
            "partner": partner,
            "start_date": project.start_date.isoformat() if project.start_date else None,
            "end_date": project.end_date.isoformat() if project.end_date else None,
            "currency": currency,
            "budget_id": project.budget_id,
            "budget_code": getattr(project.budget, "code", None) if project.budget_id else None,
        },
        "period": period,
        "periods": buckets,
        # backward-compatible alias used by older UI
        "years": buckets if period == "yearly" else [],
        "rows": rows,
        "total_expenditure": float(total_expenditure),
        "contingency_percent": 2,
        "contingency_amount": float(contingency),
        "grand_total": float(grand_total),
    }


def build_action_plan_payload(project, year=None, month=None):
    today = date.today()
    target_year = int(year) if year else (project.start_date.year if project.start_date else today.year)
    target_month = int(month) if month else (
        project.start_date.month if project.start_date else today.month
    )
    if target_month < 1 or target_month > 12:
        target_month = today.month

    days_in_month = monthrange(target_year, target_month)[1]
    month_start = date(target_year, target_month, 1)
    month_end = date(target_year, target_month, days_in_month)

    off_days = _off_days_in_month(target_year, target_month, days_in_month)

    rows = [
        {
            "row_type": "section",
            "si_no": "",
            "title": "Project Activities",
            "target": None,
            "day_marks": [],
            "responsible": "",
        }
    ]

    plans = list(project.plans.all().order_by("serial_no", "id"))
    for plan in plans:
        sub_plans = list(plan.sub_plans.all().order_by("sort_order", "id"))
        plan_users = list(plan.assigned_users.all())
        target = sum((_decimal(s.unit_no) for s in sub_plans), Decimal("0"))

        sub_rows = []
        main_marks = []

        for sub in sub_plans:
            sub_users = list(sub.assigned_users.all())
            sub_marks = _distributed_working_days_in_month(
                _range_periods(sub), target_year, target_month, days_in_month
            )
            main_marks.extend(sub_marks)
            sub_rows.append(
                {
                    "row_type": "sub",
                    "si_no": sub.serial_code or "",
                    "title": sub.title or "Untitled sub activity",
                    "target": float(_decimal(sub.unit_no)) if _decimal(sub.unit_no) else None,
                    "day_marks": sub_marks,
                    "responsible": _format_responsible(sub_users or plan_users),
                }
            )

        rows.append(
            {
                "row_type": "main",
                "si_no": plan.serial_code or str(plan.serial_no or ""),
                "title": plan.title or "Untitled activity",
                "target": float(target) if target else None,
                "day_marks": sorted(set(main_marks)),
                "responsible": _format_responsible(plan_users),
            }
        )
        rows.extend(sub_rows)

    return {
        "project": {
            "id": project.id,
            "title": project.title or "",
            "code": project.code or "",
            "location": project.location or "",
            "organization": "LEDARS",
        },
        "month": {
            "year": target_year,
            "month": target_month,
            "label": month_start.strftime("%B, %Y"),
            "days_in_month": days_in_month,
            "weekend_days": off_days,
            "off_days": off_days,
        },
        "rows": rows,
    }


def sync_project_procurement_budget(project, user=None):
    """Create/update linked procurement.Budget from plan sub-activity costs."""
    from procurement.models.budget_models import Budget

    total = Decimal("0")
    for plan in project.plans.all():
        for sub in plan.sub_plans.all():
            total += _decimal(sub.cost) or (_decimal(sub.unit_no) * _decimal(sub.unit_cost))

    contingency = (total * Decimal("0.02")).quantize(Decimal("0.01"))
    allocated = total + contingency

    budget = project.budget
    if budget is None:
        budget = Budget.objects.create(
            name=f"{project.code or project.title} Expenditure Budget",
            allocated_amount=allocated,
            spent=0,
            fiscal_year=str(project.start_date.year) if project.start_date else "",
            created_by=user if getattr(user, "is_authenticated", False) else None,
        )
        project.budget = budget
        project.budget_amount = allocated
        project.save(update_fields=["budget", "budget_amount", "updated_at"])
    else:
        budget.name = budget.name or f"{project.code or project.title} Expenditure Budget"
        budget.allocated_amount = allocated
        budget.save(update_fields=["name", "allocated_amount", "balance", "updated_at"])
        if project.budget_amount != allocated:
            project.budget_amount = allocated
            project.save(update_fields=["budget_amount", "updated_at"])

    return budget
