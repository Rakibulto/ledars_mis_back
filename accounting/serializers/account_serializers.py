from rest_framework import serializers
from accounting.models import (
    AccountType,
    AccountGroup,
    Account,
    AccountTag,
)


class AccountTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = AccountType
        fields = "__all__"


class AccountGroupSerializer(serializers.ModelSerializer):
    children = serializers.SerializerMethodField()

    class Meta:
        model = AccountGroup
        fields = "__all__"

    def get_children(self, obj):
        children = obj.children.all()
        return AccountGroupSerializer(children, many=True).data


class AccountListSerializer(serializers.ModelSerializer):
    code = serializers.CharField(required=False, allow_blank=True)
    account_type_name = serializers.CharField(
        source="account_type.name", read_only=True
    )
    classification = serializers.CharField(
        source="account_type.classification", read_only=True
    )
    liquidity_type = serializers.CharField(
        source="account_type.liquidity_type", read_only=True, default=""
    )
    group_name = serializers.CharField(
        source="account_group.name", read_only=True, default=""
    )
    parent_name = serializers.CharField(
        source="parent.name", read_only=True, default=""
    )
    ngo_project_title = serializers.CharField(
        source="ngo_project.title", read_only=True, default=""
    )
    is_global = serializers.SerializerMethodField()
    tag_names = serializers.SerializerMethodField()

    class Meta:
        model = Account
        fields = [
            "id",
            "code",
            "name",
            "ngo_project",
            "ngo_project_title",
            "is_global",
            "account_type",
            "account_type_name",
            "classification",
            "liquidity_type",
            "account_group",
            "group_name",
            "parent",
            "parent_name",
            "current_balance",
            "opening_balance",
            "is_reconcilable",
            "is_active",
            "is_deprecated",
            "is_contra",
            "description",
            "tag_names",
            "created_at",
        ]

    def get_tag_names(self, obj):
        return list(obj.tags.values_list("name", flat=True))

    def get_is_global(self, obj):
        return obj.ngo_project_id is None

    def validate(self, attrs):
        parent = attrs.get("parent")
        if parent is None and self.instance:
            parent = attrs.get("parent", self.instance.parent)
        ngo_project = attrs.get("ngo_project")
        if "ngo_project" not in attrs and self.instance:
            ngo_project = self.instance.ngo_project
        ngo_project_id = getattr(ngo_project, "id", ngo_project)
        if parent is not None:
            if parent.ngo_project_id != ngo_project_id:
                raise serializers.ValidationError(
                    {
                        "parent": (
                            "Parent account must belong to the same project "
                            "(or both must be global)."
                        )
                    }
                )
        return attrs

    def create(self, validated_data):
        code = validated_data.get("code") or ""
        if not str(code).strip():
            validated_data.pop("code", None)
        validated_data["current_balance"] = validated_data.get("opening_balance", 0)
        return super().create(validated_data)


class AccountDetailSerializer(serializers.ModelSerializer):
    account_type_detail = AccountTypeSerializer(source="account_type", read_only=True)
    account_group_detail = AccountGroupSerializer(
        source="account_group", read_only=True
    )
    tags_detail = serializers.SerializerMethodField()
    sub_accounts = serializers.SerializerMethodField()
    is_global = serializers.SerializerMethodField()
    ngo_project_title = serializers.CharField(
        source="ngo_project.title", read_only=True, default=""
    )
    liquidity_type = serializers.CharField(
        source="account_type.liquidity_type", read_only=True, default=""
    )

    class Meta:
        model = Account
        fields = "__all__"

    def get_tags_detail(self, obj):
        return AccountTagSerializer(obj.tags.all(), many=True).data

    def get_sub_accounts(self, obj):
        return AccountListSerializer(
            obj.sub_accounts.filter(is_active=True), many=True
        ).data

    def get_is_global(self, obj):
        return obj.ngo_project_id is None


class AccountTagSerializer(serializers.ModelSerializer):
    class Meta:
        model = AccountTag
        fields = "__all__"
