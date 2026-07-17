from django.db.models import Sum, Count, F, Q, Avg, Count
from projects.models import Project
from .models import (
    Beneficiary,
    ServiceRH,
    CaseFile,
    ServiceDelivery,
    ComplaintsFeedback,
    OutcomeIndicator,
    VulnerabilityAssessment,
    HouseholdProfiling,
    Referral,
    ExitGraduation,
    ProtectionCase,
    DuplicateRecord,
    SatisfactionSurvey,
)
from django.utils import timezone


def get_beneficiary_summary():

    beneficiary_stats = Beneficiary.objects.aggregate(
        total_beneficiaries=Count("id"),
        active=Count("id", filter=Q(status="Active")),
        graduated=Count("id", filter=Q(status="Graduated")),
        male=Count("id", filter=Q(sex="Male")),
        female=Count("id", filter=Q(sex="Female")),
    )
    Service_stats = ServiceRH.objects.aggregate(
        Services=Count("id"), total_value=Sum("value")
    )
    data = {**beneficiary_stats, **Service_stats}
    if data["total_value"] is None:
        data["total_value"] = 0

    return data


def get_casefile_summary():
    """
    Returns aggregated statistics for CaseFile dashboard.
    """
    stats = CaseFile.objects.aggregate(
        total_cases=Count("id"),
        open_cases=Count("id", filter=Q(status="Open")),
        in_progress_cases=Count("id", filter=Q(status="In Progress")),
        resolved_cases=Count("id", filter=Q(status="Resolved")),
        critical_cases=Count("id", filter=Q(priority="Critical")),
    )
    return stats


def get_service_delivery_stats():
    """
    Returns aggregated statistics for ServiceDelivery dashboard
    """
    stats = ServiceDelivery.objects.aggregate(
        total_services=Count("id"),
        completed_services=Count("id", filter=Q(status="Completed")),
        in_progress_services=Count("id", filter=Q(status="In Progress")),
        planned_services=Count("id", filter=Q(status="Planned")),
        total_cost=Sum("cost"),  # note: sum of all cost (ignores null automatically)
    )
    return stats


def get_duplicate_record_summary():
    """Returns aggregate counts for duplicate record dashboard."""
    stats = DuplicateRecord.objects.aggregate(
        total_detected=Count("id"),
        pending_review=Count("id", filter=Q(status="Pending Review")),
        merged=Count("id", filter=Q(status="Merged")),
    )
    return stats


########
def get_vulnerability_summary():

    total_assessments = VulnerabilityAssessment.objects.count()

    risk_counts = VulnerabilityAssessment.objects.values("risk_level").annotate(
        count=Count("id")
    )

    risk_map = {item["risk_level"]: item["count"] for item in risk_counts}

    risk_distribution = [
        {
            "level": "Critical Risk",
            "count": risk_map.get("Critical", 0),
            "message": "Immediate action needed",
        },
        {
            "level": "High Risk",
            "count": risk_map.get("High", 0),
            "message": "Priority intervention",
        },
        {
            "level": "Medium Risk",
            "count": risk_map.get("Medium", 0),
            "message": "Regular monitoring",
        },
        {
            "level": "Low Risk",
            "count": risk_map.get("Low", 0),
            "message": "Stable situation",
        },
    ]

    category_average = VulnerabilityAssessment.objects.aggregate(
        food_avg=Avg("food"),
        shelter_avg=Avg("shelter"),
        health_avg=Avg("health"),
        protection_avg=Avg("protection"),
        education_avg=Avg("education"),
        livelihood_avg=Avg("livelihood"),
    )

    # Chart-compatible formats
    chart_risk_distribution = [
        {"name": "Critical", "value": risk_map.get("Critical", 0), "fill": "#ef4444"},
        {"name": "High", "value": risk_map.get("High", 0), "fill": "#f97316"},
        {"name": "Medium", "value": risk_map.get("Medium", 0), "fill": "#eab308"},
        {"name": "Low", "value": risk_map.get("Low", 0), "fill": "#10b981"},
    ]

    chart_category_averages = [
        {"category": "Food Security", "score": round(category_average.get("food_avg") or 0, 1)},
        {"category": "Shelter", "score": round(category_average.get("shelter_avg") or 0, 1)},
        {"category": "Health", "score": round(category_average.get("health_avg") or 0, 1)},
        {"category": "Protection", "score": round(category_average.get("protection_avg") or 0, 1)},
        {"category": "Education", "score": round(category_average.get("education_avg") or 0, 1)},
        {"category": "Livelihood", "score": round(category_average.get("livelihood_avg") or 0, 1)},
    ]

    return {
        "total_assessments": total_assessments,
        "critical_risk": risk_map.get("Critical", 0),
        "high_risk": risk_map.get("High", 0),
        "medium_risk": risk_map.get("Medium", 0),
        "low_risk": risk_map.get("Low", 0),
        "risk_distribution": chart_risk_distribution,
        "category_averages": chart_category_averages,
        "category_average": category_average,
    }


###############
def get_impact_summary():

    # Total beneficiaries
    total_beneficiaries = Beneficiary.objects.count()

    # Beneficiaries reached in December 2025
    reached_december = Beneficiary.objects.filter(
        created_at__year=2025, created_at__month=12
    ).count()

    # Outcome indicators
    total_indicators = OutcomeIndicator.objects.count()

    # Positive outcomes (current > baseline)
    positive_outcomes = OutcomeIndicator.objects.filter(
        current__gt=F("baseline")
    ).count()

    positive_percentage = 0
    if total_indicators:
        positive_percentage = round((positive_outcomes / total_indicators) * 100)

    # Target achievement (current >= target)
    achieved_targets = OutcomeIndicator.objects.filter(current__gte=F("target")).count()
    target_percentage = 0
    if total_indicators:
        target_percentage = round((achieved_targets / total_indicators) * 100)

    # Active programs
    active_programs = Project.objects.filter(status="Active").count()

    return {
        "total_beneficiaries": total_beneficiaries,
        "reached_december_2025": reached_december,
        "positive_outcomes_percent": positive_percentage,
        "target_achievement_percent": target_percentage,
        "active_programs": active_programs,
    }


def get_household_summary():

    total_households = HouseholdProfiling.objects.count()
    avg_members = (
        HouseholdProfiling.objects.aggregate(total=Avg("members"))["total"] or 0
    )
    total_members = (
        HouseholdProfiling.objects.aggregate(total=Sum("members"))["total"] or 0
    )
    total_vulnerable = (
        HouseholdProfiling.objects.aggregate(total=Sum("vulnerable_members"))["total"] or 0
    )

    shelter_distribution = HouseholdProfiling.objects.values("shelter").annotate(
        count=Count("id")
    )

    return {
        "total_households": total_households,
        "total_members": total_members,
        "average_members": round(avg_members, 2),
        "total_vulnerable": total_vulnerable,
        "shelter_distribution": shelter_distribution,
    }


####


def get_referral_summary():

    total_referrals = Referral.objects.count()

    pending = Referral.objects.filter(status="Pending").count()

    in_progress = Referral.objects.filter(
        status__in=["Accepted", "In Progress"]
    ).count()

    completed = Referral.objects.filter(status="Completed").count()

    return {
        "total_referrals": total_referrals,
        "pending": pending,
        "in_progress": in_progress,
        "completed": completed,
    }


def get_complaints_feedback_summary():
    return ComplaintsFeedback.objects.aggregate(
        total_cases=Count("id"),
        open_cases=Count("id", filter=Q(status="Open")),
        under_review=Count("id", filter=Q(status="Under Review")),
        closed_cases=Count("id", filter=Q(status="Closed")),
        critical=Count("id", filter=Q(priority="Critical")),
        high=Count("id", filter=Q(priority="High")),
        medium=Count("id", filter=Q(priority="Medium")),
        low=Count("id", filter=Q(priority="Low")),
    )


from datetime import date
from .models import ExitGraduation


def calculate_months(entry_date, exit_date):

    if not entry_date:
        return None

    end_date = exit_date or date.today()

    months = (end_date.year - entry_date.year) * 12 + (
        end_date.month - entry_date.month
    )

    return months


def get_exit_graduation_summary():

    qs = ExitGraduation.objects.all()

    graduated = qs.filter(status="Graduated").count()
    ready = qs.filter(status="Ready for Exit").count()
    progress = qs.filter(status="In Progress").count()

    durations = []

    for obj in qs:
        months = calculate_months(obj.entry_date, obj.exit_date)
        if months:
            durations.append(months)

    avg_duration = round(sum(durations) / len(durations)) if durations else 0

    return {
        "graduated": {
            "title": "Graduated",
            "count": graduated,
            "description": "Successfully exited",
        },
        "ready_for_exit": {
            "title": "Ready for Exit",
            "count": ready,
            "description": "Assessment complete",
        },
        "in_progress": {
            "title": "In Progress",
            "count": progress,
            "description": "Still in program",
        },
        "avg_duration": {
            "title": "Avg Duration",
            "count": f"{avg_duration} mo",
            "description": "Program enrollment",
        },
    }


def get_dashboard_kpis():
    now = timezone.now()
    total = Beneficiary.objects.count()
    active = Beneficiary.objects.filter(status="Active").count()
    new_this_month = Beneficiary.objects.filter(
        created_at__year=now.year, created_at__month=now.month
    ).count()
    graduated = Beneficiary.objects.filter(status="Graduated").count()
    male = Beneficiary.objects.filter(sex="Male").count()
    female = Beneficiary.objects.filter(sex="Female").count()
    children = Beneficiary.objects.filter(age__lt=18).count()
    households = HouseholdProfiling.objects.count()
    active_cases = CaseFile.objects.filter(status__in=["Open", "In Progress"]).count()
    pending_referrals = Referral.objects.filter(status="Pending").count()
    pending_complaints = ComplaintsFeedback.objects.filter(status="Open").count()
    services_this_month = ServiceDelivery.objects.filter(
        created_at__year=now.year, created_at__month=now.month
    ).count()
    avg_vuln = (
        VulnerabilityAssessment.objects.aggregate(avg=Avg("overall_score"))["avg"] or 0
    )
    projects_active = Project.objects.filter(status="Active").count()
    districts = (
        Beneficiary.objects.exclude(district__isnull=True)
        .exclude(district="")
        .values("district")
        .distinct()
        .count()
    )
    upazilas = (
        Beneficiary.objects.exclude(upazila__isnull=True)
        .exclude(upazila="")
        .values("upazila")
        .distinct()
        .count()
    )
    sat_avg = (
        SatisfactionSurvey.objects.aggregate(avg=Avg("avg_satisfaction"))["avg"] or 0
    )
    protection_active = ProtectionCase.objects.filter(
        status__in=["Open", "Under Investigation"]
    ).count()
    duplicates = DuplicateRecord.objects.filter(status="Pending Review").count()

    filled_fields = 0
    total_fields = 0
    check_fields = ["name", "age", "sex", "contact", "division", "district", "nid"]
    for b in Beneficiary.objects.all().values(*check_fields):
        for f in check_fields:
            total_fields += 1
            if b[f]:
                filled_fields += 1
    completeness = round((filled_fields / total_fields * 100), 1) if total_fields else 0

    return {
        "total_beneficiaries": total,
        "active_beneficiaries": active,
        "new_this_month": new_this_month,
        "graduated": graduated,
        "male": male,
        "female": female,
        "children": children,
        "households_served": households,
        "active_cases": active_cases,
        "pending_referrals": pending_referrals,
        "pending_complaints": pending_complaints,
        "services_delivered_this_month": services_this_month,
        "avg_vulnerability_score": round(avg_vuln, 1),
        "projects_active": projects_active,
        "districts_covered": districts,
        "upazilas_covered": upazilas,
        "satisfaction_rate": round(float(sat_avg), 1),
        "protection_cases_active": protection_active,
        "duplicate_records": duplicates,
        "data_completeness": completeness,
    }


def get_demographics():
    by_sex = list(
        Beneficiary.objects.values("sex").annotate(count=Count("id")).order_by("sex")
    )
    by_sex = [{"label": s["sex"] or "Unknown", "value": s["count"]} for s in by_sex]

    age_ranges = [
        ("0-17", Q(age__lt=18)),
        ("18-30", Q(age__gte=18, age__lte=30)),
        ("31-45", Q(age__gte=31, age__lte=45)),
        ("46-60", Q(age__gte=46, age__lte=60)),
        ("60+", Q(age__gt=60)),
    ]
    by_age_group = []
    for label, q in age_ranges:
        count = Beneficiary.objects.filter(q).count()
        by_age_group.append({"label": label, "value": count})

    by_division = list(
        Beneficiary.objects.exclude(division__isnull=True)
        .exclude(division="")
        .values("division")
        .annotate(count=Count("id"))
        .order_by("-count")
    )
    by_division = [{"label": d["division"], "value": d["count"]} for d in by_division]

    by_status = list(
        Beneficiary.objects.values("status")
        .annotate(count=Count("id"))
        .order_by("status")
    )
    by_status = [
        {"label": s["status"] or "Unknown", "value": s["count"]} for s in by_status
    ]

    vuln_counts = {}
    for b in Beneficiary.objects.exclude(vulnerability_type__isnull=True).values_list(
        "vulnerability_type", flat=True
    ):
        if isinstance(b, list):
            for v in b:
                vuln_counts[v] = vuln_counts.get(v, 0) + 1
        elif isinstance(b, str):
            vuln_counts[b] = vuln_counts.get(b, 0) + 1
    by_vulnerability = [{"label": k, "value": v} for k, v in vuln_counts.items()]

    return {
        "by_sex": by_sex,
        "by_age_group": by_age_group,
        "by_division": by_division,
        "by_status": by_status,
        "by_vulnerability": by_vulnerability,
    }


def get_beneficiary_analytics():
    """Monthly trends, service distribution, and location breakdown for analytics dashboard."""
    # Monthly registrations, services, and graduations (last 6 months)
    now = timezone.now()
    monthly_data = []
    for i in range(5, -1, -1):
        month = now.month - i
        year = now.year
        if month <= 0:
            month += 12
            year -= 1
        registered = Beneficiary.objects.filter(
            created_at__year=year, created_at__month=month
        ).count()
        served = ServiceDelivery.objects.filter(
            created_at__year=year, created_at__month=month
        ).count()
        graduated = ExitGraduation.objects.filter(
            created_at__year=year, created_at__month=month
        ).count()
        month_name = timezone.datetime(year, month, 1).strftime("%b")
        monthly_data.append(
            {"month": month_name, "registered": registered, "served": served, "graduated": graduated}
        )

    # Service distribution by category
    service_distribution = list(
        ServiceDelivery.objects.values("category__name")
        .annotate(count=Count("id"))
        .order_by("-count")
    )
    service_distribution = [
        {"service": s["category__name"] or "Uncategorized", "count": s["count"]}
        for s in service_distribution
    ]

    # Location distribution
    location_data = list(
        Beneficiary.objects.exclude(district__isnull=True)
        .exclude(district="")
        .values("district")
        .annotate(count=Count("id"))
        .order_by("-count")[:10]
    )
    location_data = [
        {"location": l["district"], "count": l["count"]}
        for l in location_data
    ]

    return {
        "monthly_data": monthly_data,
        "service_distribution": service_distribution,
        "location_data": location_data,
    }
