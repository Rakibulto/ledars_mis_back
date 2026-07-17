# procurement_dashboard/serializers/account_serializer.py
from rest_framework import serializers
from ..models.account_models import Account, AccountCategory


class AccountCategorySerializer(serializers.ModelSerializer):
    subcategories = serializers.SerializerMethodField()

    class Meta:
        model = AccountCategory
        fields = ['id', 'name', 'parent', 'is_active', 'subcategories']

    def get_subcategories(self, obj):
        children = obj.subcategories.filter(is_active=True)
        return AccountCategorySerializer(children, many=True).data

class SimpleAccountCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = AccountCategory
        fields = ['id', 'name']


class AccountSerializer(serializers.ModelSerializer):
    category_details = AccountCategorySerializer(source='category', read_only=True)
    sub_category_details = AccountCategorySerializer(source='sub_category', read_only=True)
    created_by = serializers.CharField(source="created_by.username", read_only=True)

    class Meta:
        model = Account
        fields = [
            'id',
            'code',
            'name',
            'category',
            'sub_category',
            'category_details',
            'sub_category_details',
            'balance',
            'created_by',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'code', 'created_by', 'created_at', 'updated_at']

    def validate(self, attrs):
        category = attrs.get('category', getattr(self.instance, 'category', None))
        sub_category = attrs.get('sub_category', getattr(self.instance, 'sub_category', None))

        if sub_category is not None and category is None:
            raise serializers.ValidationError({
                'category': 'Please select a main category before selecting a subcategory.'
            })

        if category is not None:
            if category.subcategories.filter(is_active=True).exists() and sub_category is None:
                raise serializers.ValidationError({
                    'sub_category': 'Please select a subcategory under the selected main category.'
                })

        if category is not None and sub_category is not None:
            if sub_category.parent_id != category.id:
                raise serializers.ValidationError({
                    'sub_category': 'Selected subcategory is not under the chosen main category.'
                })

        return attrs

