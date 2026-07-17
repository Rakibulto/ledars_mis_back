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
    code = serializers.CharField(read_only=True)
    account_type_name = serializers.CharField(
        source="account_type.name", read_only=True
    )
    classification = serializers.CharField(
        source="account_type.classification", read_only=True
    )
    group_name = serializers.CharField(
        source="account_group.name", read_only=True, default=""
    )
    parent_name = serializers.CharField(
        source="parent.name", read_only=True, default=""
    )
    tag_names = serializers.SerializerMethodField()

    class Meta:
        model = Account
        fields = [
            "id",
            "code",
            "name",
            "account_type",
            "account_type_name",
            "classification",
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

    def create(self, validated_data):
        validated_data['current_balance'] = validated_data.get('opening_balance', 0)
        return super().create(validated_data)


class AccountDetailSerializer(serializers.ModelSerializer):
    account_type_detail = AccountTypeSerializer(source="account_type", read_only=True)
    account_group_detail = AccountGroupSerializer(
        source="account_group", read_only=True
    )
    tags_detail = serializers.SerializerMethodField()
    sub_accounts = serializers.SerializerMethodField()

    class Meta:
        model = Account
        fields = "__all__"

    def get_tags_detail(self, obj):
        return AccountTagSerializer(obj.tags.all(), many=True).data

    def get_sub_accounts(self, obj):
        return AccountListSerializer(
            obj.sub_accounts.filter(is_active=True), many=True
        ).data


class AccountTagSerializer(serializers.ModelSerializer):
    class Meta:
        model = AccountTag
        fields = "__all__"

    # def create(self, validated_data):
    #     # Set current_balance to the value of opening_balance during account creation
    #     validated_data['current_balance'] = validated_data.get('opening_balance', 0)
    #     return super().create(validated_data)
