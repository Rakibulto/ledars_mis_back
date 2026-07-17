from rest_framework import serializers


class DashboardKPISerializer(serializers.Serializer):
    total_beneficiaries = serializers.IntegerField()
    active_beneficiaries = serializers.IntegerField()
    new_this_month = serializers.IntegerField()
    graduated = serializers.IntegerField()
    male = serializers.IntegerField()
    female = serializers.IntegerField()
    children = serializers.IntegerField()
    households_served = serializers.IntegerField()
    active_cases = serializers.IntegerField()
    pending_referrals = serializers.IntegerField()
    pending_complaints = serializers.IntegerField()
    services_delivered_this_month = serializers.IntegerField()
    avg_vulnerability_score = serializers.FloatField()
    projects_active = serializers.IntegerField()
    districts_covered = serializers.IntegerField()
    upazilas_covered = serializers.IntegerField()
    satisfaction_rate = serializers.FloatField()
    protection_cases_active = serializers.IntegerField()
    duplicate_records = serializers.IntegerField()
    data_completeness = serializers.FloatField()


class DemographicsSerializer(serializers.Serializer):
    by_sex = serializers.ListField()
    by_age_group = serializers.ListField()
    by_division = serializers.ListField()
    by_status = serializers.ListField()
    by_vulnerability = serializers.ListField()
