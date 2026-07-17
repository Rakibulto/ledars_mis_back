import uuid
from datetime import date

from rest_framework import serializers

from inventory.models import (
    QualityCheck,
    QualityAlert,
    QualityControlPoint,
    QualityTeam,
    QCTemplate,
)


def _generate_qc_reference():
    today = date.today()
    return f"QC-{today.strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"


def _generate_qa_reference():
    today = date.today()
    return f"QA-{today.strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"


class QualityCheckSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    product_code = serializers.CharField(source="product.code", read_only=True)
    warehouse_name = serializers.CharField(source="warehouse.name", read_only=True)
    warehouse_code = serializers.CharField(source="warehouse.code", read_only=True)
    team_name = serializers.CharField(source="team.name", read_only=True)
    grn_reference = serializers.CharField(source="grn_line.grn.reference", read_only=True)
    office_location_name = serializers.CharField(
        source="office_location.name", read_only=True
    )
    office_location_type = serializers.CharField(
        source="office_location.type", read_only=True
    )
    created_by_name = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = QualityCheck
        fields = "__all__"
        extra_kwargs = {
            "reference": {"required": False, "allow_blank": True},
            "created_by": {"read_only": True},
        }

    def get_created_by_name(self, obj):
        return obj.created_by.username if obj.created_by else None

    def create(self, validated_data):
        if not validated_data.get("reference"):
            validated_data["reference"] = _generate_qc_reference()
        if not validated_data.get("status"):
            validated_data["status"] = "Pending"
        return super().create(validated_data)

    def validate(self, attrs):
        ref = attrs.get("reference", "")
        if ref:
            qs = QualityCheck.objects.filter(reference=ref)
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError(
                    {"reference": "A quality check with this reference already exists."}
                )
        return attrs


class QualityAlertSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    product_code = serializers.CharField(source="product.code", read_only=True)
    reported_by_name = serializers.CharField(
        source="reported_by.username", read_only=True
    )
    reported_by_email = serializers.CharField(
        source="reported_by.email", read_only=True
    )
    office_location_name = serializers.CharField(
        source="office_location.name", read_only=True
    )
    office_location_type = serializers.CharField(
        source="office_location.type", read_only=True
    )
    assigned_to_name = serializers.CharField(
        source="assigned_to.username", read_only=True
    )

    class Meta:
        model = QualityAlert
        fields = "__all__"
        extra_kwargs = {
            "reference": {"required": False, "allow_blank": True},
        }

    def create(self, validated_data):
        if not validated_data.get("reference"):
            validated_data["reference"] = _generate_qa_reference()
        if not validated_data.get("status"):
            validated_data["status"] = "New"
        return super().create(validated_data)


class QualityControlPointSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True)
    operation_type_name = serializers.CharField(
        source="operation_type.name", read_only=True
    )
    operation_type_code = serializers.CharField(
        source="operation_type.code", read_only=True
    )
    office_location_name = serializers.CharField(
        source="office_location.name", read_only=True
    )
    office_location_type = serializers.CharField(
        source="office_location.type", read_only=True
    )
    product_name = serializers.CharField(source="product.name", read_only=True)
    product_code = serializers.CharField(source="product.code", read_only=True)
    assigned_to_name = serializers.CharField(
        source="assigned_to.username", read_only=True
    )
    created_by_name = serializers.CharField(
        source="created_by.username", read_only=True
    )

    class Meta:
        model = QualityControlPoint
        fields = "__all__"
        extra_kwargs = {
            "reference": {"required": False, "allow_blank": True},
            "parameter": {"required": False, "allow_blank": True},
            "standard": {"required": False, "allow_blank": True},
            "created_by": {"read_only": True},
        }

    def create(self, validated_data):
        if not validated_data.get("reference"):
            today = date.today()
            validated_data["reference"] = f"QCP-{today.strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
        return super().create(validated_data)


class QualityTeamSerializer(serializers.ModelSerializer):
    leader_name = serializers.CharField(source="leader.username", read_only=True)
    category_name = serializers.CharField(source="category.name", read_only=True)
    member_count = serializers.SerializerMethodField()
    member_names = serializers.SerializerMethodField()

    class Meta:
        model = QualityTeam
        fields = "__all__"

    def get_member_count(self, obj):
        return obj.members.count()

    def get_member_names(self, obj):
        return list(obj.members.values_list("username", flat=True))


class QCTemplateSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True)
    checklist_count = serializers.SerializerMethodField()
    mandatory_item_count = serializers.SerializerMethodField()
    optional_item_count = serializers.SerializerMethodField()

    class Meta:
        model = QCTemplate
        fields = "__all__"

    def get_checklist_count(self, obj):
        return len(obj.checklist or [])

    def get_mandatory_item_count(self, obj):
        return sum(1 for item in (obj.checklist or []) if item.get("mandatory"))

    def get_optional_item_count(self, obj):
        return sum(1 for item in (obj.checklist or []) if not item.get("mandatory"))
