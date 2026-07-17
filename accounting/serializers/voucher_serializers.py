from rest_framework import serializers
from accounting.models import (
    Voucher,
    VoucherLine,
    VoucherApproval,
    VoucherAttachment,
)


class VoucherLineSerializer(serializers.ModelSerializer):
    account_code = serializers.CharField(source="account.code", read_only=True)
    account_name = serializers.CharField(source="account.name", read_only=True)

    class Meta:
        model = VoucherLine
        fields = "__all__"
        read_only_fields = ["voucher"]


class VoucherApprovalSerializer(serializers.ModelSerializer):
    approver_name = serializers.CharField(
        source="approver.get_full_name", read_only=True
    )

    class Meta:
        model = VoucherApproval
        fields = "__all__"


class VoucherAttachmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = VoucherAttachment
        fields = "__all__"


class VoucherListSerializer(serializers.ModelSerializer):
    voucher_type_display = serializers.CharField(
        source="get_voucher_type_display", read_only=True
    )
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    journal_name = serializers.CharField(source="journal.name", read_only=True)
    created_by_name = serializers.CharField(
        source="created_by.get_full_name", read_only=True, default=""
    )
    project_name = serializers.CharField(
        source="project.name", read_only=True, default=""
    )
    line_count = serializers.SerializerMethodField()

    class Meta:
        model = Voucher
        fields = [
            "id",
            "voucher_number",
            "voucher_type",
            "voucher_type_display",
            "journal",
            "journal_name",
            "date",
            "payee",
            "total_amount",
            "status",
            "status_display",
            "project_name",
            "created_by_name",
            "line_count",
            "created_at",
        ]

    def get_line_count(self, obj):
        return obj.lines.count()


class VoucherDetailSerializer(serializers.ModelSerializer):
    lines = VoucherLineSerializer(many=True, read_only=True)
    approvals = VoucherApprovalSerializer(many=True, read_only=True)
    attachments = VoucherAttachmentSerializer(many=True, read_only=True)
    voucher_type_display = serializers.CharField(
        source="get_voucher_type_display", read_only=True
    )
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    journal_name = serializers.CharField(source="journal.name", read_only=True)
    created_by_name = serializers.CharField(
        source="created_by.get_full_name", read_only=True, default=""
    )
    approved_by_name = serializers.CharField(
        source="approved_by.get_full_name", read_only=True, default=""
    )

    class Meta:
        model = Voucher
        fields = "__all__"


class VoucherWriteSerializer(serializers.ModelSerializer):
    lines = VoucherLineSerializer(many=True, required=False, allow_null=True)
    project = serializers.IntegerField(required=False, allow_null=True)

    class Meta:
        model = Voucher
        exclude = ["created_by", "approved_by", "approved_at", "journal_entry"]

    def resolve_project(self, project_id):
        if project_id is None:
            return None
        try:
            return Voucher._meta.get_field("project").remote_field.model.objects.get(pk=project_id)
        except Voucher._meta.get_field("project").remote_field.model.DoesNotExist:
            return None

    def create(self, validated_data):
        project_id = validated_data.pop("project", None)
        lines_data = validated_data.pop("lines", [])
        validated_data["project"] = self.resolve_project(project_id)
        voucher = Voucher.objects.create(**validated_data)

        if lines_data:
            for line_data in lines_data:
                VoucherLine.objects.create(voucher=voucher, **line_data)
            total_debit = sum(line_data.get('debit', 0) for line_data in lines_data)
            voucher.total_amount = total_debit
            voucher.save(update_fields=['total_amount'])

        return voucher

    def update(self, instance, validated_data):
        project_id = validated_data.pop("project", None)
        if project_id is not None:
            validated_data["project"] = self.resolve_project(project_id)

        lines_data = validated_data.pop("lines", None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if lines_data is not None:
            instance.lines.all().delete()
            if lines_data:
                for line_data in lines_data:
                    VoucherLine.objects.create(voucher=instance, **line_data)
                total_debit = sum(line_data.get('debit', 0) for line_data in lines_data)
                instance.total_amount = total_debit
                instance.save(update_fields=['total_amount'])
            else:
                instance.total_amount = 0
                instance.save(update_fields=['total_amount'])

        return instance