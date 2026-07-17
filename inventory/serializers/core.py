from rest_framework import serializers
from inventory.models import Category, UnitOfMeasure


class CategorySerializer(serializers.ModelSerializer):
    parent_name = serializers.CharField(source="parent.name", read_only=True)
    parent = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.filter(level="Main"), allow_null=True, required=False
    )

    class Meta:
        model = Category
        fields = [
            "id",
            "code",
            "name",
            "description",
            "level",
            "parent",
            "parent_name",
            "item_count",
            "costing_method",
            "status",
            "created_by",
            "created_at",
        ]
        read_only_fields = ["code", "item_count", "created_by", "created_at"]

    def validate(self, attrs):
        level = attrs.get("level")
        parent = attrs.get("parent")
        if level == "Sub" and not parent:
            raise serializers.ValidationError(
                {"parent": "Sub category must have a parent."}
            )
        if level == "Sub" and parent and parent.level != "Main":
            raise serializers.ValidationError(
                {"parent": "Parent must be a Main category."}
            )
        if level == "Main" and parent:
            raise serializers.ValidationError(
                {"parent": "Main category cannot have a parent."}
            )
        return attrs

    def update(self, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance


class UnitOfMeasureSerializer(serializers.ModelSerializer):
    class Meta:
        model = UnitOfMeasure
        fields = ["id", "name", "is_active"]
        read_only_fields = ["id"]
