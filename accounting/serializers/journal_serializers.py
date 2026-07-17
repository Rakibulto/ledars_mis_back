from rest_framework import serializers
from accounting.models import (
    Journal,
    JournalEntry,
    JournalItem,
    JournalEntryAttachment,
    RecurringJournalTemplate,
    RecurringJournalLine,
)


class JournalSerializer(serializers.ModelSerializer):
    journal_type_display = serializers.CharField(
        source="get_journal_type_display", read_only=True
    )

    class Meta:
        model = Journal
        fields = "__all__"
        read_only_fields = ("code",)


class JournalItemSerializer(serializers.ModelSerializer):
    account_code = serializers.CharField(source="account.code", read_only=True)
    account_name = serializers.CharField(source="account.name", read_only=True)
    analytic_account_name = serializers.CharField(
        source="analytic_account.name", read_only=True, default=""
    )
    cost_center_name = serializers.CharField(
        source="cost_center.name", read_only=True, default=""
    )
    # Flattened entry context so journal-items page can render without extra requests
    entry_reference = serializers.CharField(
        source="journal_entry.reference", read_only=True, default=""
    )
    entry_date = serializers.DateField(
        source="journal_entry.date", read_only=True, default=None
    )
    entry_status = serializers.CharField(
        source="journal_entry.status", read_only=True, default=""
    )
    entry_narration = serializers.CharField(
        source="journal_entry.narration", read_only=True, default=""
    )
    journal_id = serializers.IntegerField(
        source="journal_entry.journal_id", read_only=True, default=None
    )
    journal_name = serializers.CharField(
        source="journal_entry.journal.name", read_only=True, default=""
    )

    class Meta:
        model = JournalItem
        fields = "__all__"


class JournalEntryListSerializer(serializers.ModelSerializer):
    journal_name = serializers.CharField(source="journal.name", read_only=True)
    journal_code = serializers.CharField(source="journal.code", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    created_by_name = serializers.CharField(
        source="created_by.get_full_name", read_only=True, default=""
    )
    item_count = serializers.SerializerMethodField()
    items = JournalItemSerializer(many=True, read_only=True)

    class Meta:
        model = JournalEntry
        fields = [
            "id",
            "reference",
            "journal",
            "journal_name",
            "journal_code",
            "date",
            "narration",
            "status",
            "status_display",
            "total_debit",
            "total_credit",
            "is_auto_generated",
            "source_document",
            "created_by_name",
            "item_count",
            "items",
            "created_at",
        ]

    def get_item_count(self, obj):
        return obj.items.count()


class JournalEntryDetailSerializer(serializers.ModelSerializer):
    journal_detail = JournalSerializer(source="journal", read_only=True)
    items = JournalItemSerializer(many=True, read_only=True)
    attachments = serializers.SerializerMethodField()
    created_by_name = serializers.CharField(
        source="created_by.get_full_name", read_only=True, default=""
    )
    posted_by_name = serializers.CharField(
        source="posted_by.get_full_name", read_only=True, default=""
    )

    class Meta:
        model = JournalEntry
        fields = "__all__"

    def get_attachments(self, obj):
        return JournalEntryAttachmentSerializer(
            obj.attachments.all(), many=True, context=self.context
        ).data


class JournalEntryAttachmentSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()

    class Meta:
        model = JournalEntryAttachment
        fields = ["id", "name", "file", "url", "uploaded_at"]
        read_only_fields = ["id", "uploaded_at"]

    def get_url(self, obj):
        request = self.context.get("request")
        if obj.file and request:
            return request.build_absolute_uri(obj.file.url)
        return obj.file.url if obj.file else ""


class JournalItemNestedSerializer(serializers.ModelSerializer):
    class Meta:
        model = JournalItem
        exclude = ['journal_entry']

class JournalEntryWriteSerializer(serializers.ModelSerializer):
    items = JournalItemNestedSerializer(many=True, required=False)

    class Meta:
        model = JournalEntry
        exclude = ["created_by", "posted_by", "posted_at"]

    def create(self, validated_data):
        items_data = validated_data.pop("items", [])
        entry = JournalEntry.objects.create(**validated_data)
        for item_data in items_data:
            JournalItem.objects.create(journal_entry=entry, **item_data)
        return entry

    def update(self, instance, validated_data):
        items_data = validated_data.pop("items", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if items_data is not None:
            instance.items.all().delete()
            for item_data in items_data:
                JournalItem.objects.create(journal_entry=instance, **item_data)
        return instance


class RecurringJournalLineSerializer(serializers.ModelSerializer):
    account_code = serializers.CharField(source="account.code", read_only=True)
    account_name = serializers.CharField(source="account.name", read_only=True)

    class Meta:
        model = RecurringJournalLine
        fields = "__all__"


class RecurringJournalTemplateSerializer(serializers.ModelSerializer):
    lines = RecurringJournalLineSerializer(many=True, read_only=True)
    journal_name = serializers.CharField(source="journal.name", read_only=True)

    class Meta:
        model = RecurringJournalTemplate
        fields = "__all__"
