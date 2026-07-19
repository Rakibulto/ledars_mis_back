from django.urls import path, include
from rest_framework.routers import DefaultRouter
from beneficiary.views import (
    BeneficiaryViewSet,
    ServiceCategoryViewSet,
    ServiceDeliveryViewSet,
    VulnerabilityTypeViewSet,
    ImpactMeasurementViewSet,
    OutcomeIndicatorViewSet,
    ServiceRHViewSet,
    CaseFileViewSet,
    ComplaintsFeedbackViewSet,
    HouseholdProfilingViewSet,
    VulnerabilityAssessmentViewSet,
    ReferralViewSet,
    ExitGraduationViewSet,
    GraduationCriteriaViewSet,
    AlumniTrackingViewSet,
    ProtectionCaseViewSet,
    ConsentRecordViewSet,
    SafeguardingIncidentViewSet,
    TargetingCriteriaViewSet,
    NeedsAssessmentViewSet,
    DistributionPlanViewSet,
    ServiceCalendarEventViewSet,
    CaseWorkerAssignmentViewSet,
    FollowUpScheduleViewSet,
    SatisfactionSurveyViewSet,
    GrievanceRedressalViewSet,
    ProgressTrackingViewSet,
    DuplicateRecordViewSet,
    DonorReportViewSet,
    AttendanceTrackerViewSet,
    HouseholdSurveyViewSet,
    EligibilityScreeningViewSet,
    ReferralNetworkPartnerViewSet,
    CoverageAreaViewSet,
    BeneficiarySettingViewSet,
    DashboardKPIView,
    DemographicsView,
    BeneficiaryAnalyticsView,
)
from ..views.core import SimpleBeneficieryViews


router = DefaultRouter()
router.register("beneficiary", BeneficiaryViewSet, basename="beneficiary")
router.register(
    "services_received_history", ServiceRHViewSet, basename="services_received_history"
)

router.register(
    "service_categories", ServiceCategoryViewSet, basename="service_categories"
)
router.register(
    "vulnerability_types", VulnerabilityTypeViewSet, basename="vulnerability_types"
)
router.register(
    "service_deliveries", ServiceDeliveryViewSet, basename="service_deliveries"
)
router.register("case_files", CaseFileViewSet, basename="case_files")
router.register("assessments", VulnerabilityAssessmentViewSet, basename="assessments")
router.register("impact_measurements", ImpactMeasurementViewSet)
router.register("outcome_indicators", OutcomeIndicatorViewSet)
router.register("households", HouseholdProfilingViewSet, basename="households")
router.register("referrals", ReferralViewSet, basename="referrals")
router.register(
    "complaint_feedback", ComplaintsFeedbackViewSet, basename="complaint_feedback"
)
router.register("exit_graduations", ExitGraduationViewSet, basename="exit_graduation")

# New endpoints
router.register(
    "graduation_criteria", GraduationCriteriaViewSet, basename="graduation_criteria"
)
router.register("alumni_tracking", AlumniTrackingViewSet, basename="alumni_tracking")
router.register("protection_cases", ProtectionCaseViewSet, basename="protection_cases")
router.register("consent_records", ConsentRecordViewSet, basename="consent_records")
router.register(
    "safeguarding_incidents",
    SafeguardingIncidentViewSet,
    basename="safeguarding_incidents",
)
router.register(
    "targeting_criteria", TargetingCriteriaViewSet, basename="targeting_criteria"
)
router.register(
    "needs_assessments", NeedsAssessmentViewSet, basename="needs_assessments"
)
router.register(
    "distribution_plans", DistributionPlanViewSet, basename="distribution_plans"
)
router.register(
    "service_calendar", ServiceCalendarEventViewSet, basename="service_calendar"
)
router.register(
    "case_worker_assignments",
    CaseWorkerAssignmentViewSet,
    basename="case_worker_assignments",
)
router.register(
    "follow_up_schedules", FollowUpScheduleViewSet, basename="follow_up_schedules"
)
router.register(
    "satisfaction_surveys", SatisfactionSurveyViewSet, basename="satisfaction_surveys"
)
router.register(
    "grievance_records", GrievanceRedressalViewSet, basename="grievance_records"
)
router.register(
    "progress_tracking", ProgressTrackingViewSet, basename="progress_tracking"
)
router.register(
    "duplicate_records", DuplicateRecordViewSet, basename="duplicate_records"
)
router.register("donor_reports", DonorReportViewSet, basename="donor_reports")
router.register(
    "attendance_tracker", AttendanceTrackerViewSet, basename="attendance_tracker"
)
router.register(
    "household_surveys", HouseholdSurveyViewSet, basename="household_surveys"
)
router.register(
    "eligibility_screening",
    EligibilityScreeningViewSet,
    basename="eligibility_screening",
)
router.register(
    "referral_network", ReferralNetworkPartnerViewSet, basename="referral_network"
)
router.register("coverage_areas", CoverageAreaViewSet, basename="coverage_areas")
router.register(
    "beneficiary_settings", BeneficiarySettingViewSet, basename="beneficiary_settings"
)


urlpatterns = [
    path("", include(router.urls)),
    path("simple-beneficiaries/", SimpleBeneficieryViews.as_view(), name="simple-beneficiaries"),
    path(
        "beneficiary-dashboard-kpis/",
        DashboardKPIView.as_view(),
        name="beneficiary-dashboard-kpis",
    ),
    path(
        "beneficiary-demographics/",
        DemographicsView.as_view(),
        name="beneficiary-demographics",
    ),
    path(
        "beneficiary-analytics/",
        BeneficiaryAnalyticsView.as_view(),
        name="beneficiary-analytics",
    ),
]
