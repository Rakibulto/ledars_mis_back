from django.utils import timezone
from rest_framework import serializers
from authentication.models import Role, User
from ..models.models import VendorProfile, VendorDocument


class VendorDocumentSerializer(serializers.ModelSerializer):
    created_by = serializers.CharField(source='created_by.username', read_only=True)
    reviewer = serializers.CharField(source='reviewer.username', read_only=True)
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = VendorDocument
        fields = '__all__'
        read_only_fields = [
            'reviewer',
            'review_date',
            'created_by',
            'uploaded_at',
            'updated_at',
        ]

    def get_file_url(self, obj):
        request = self.context.get('request')
        if obj.file and request:
            return request.build_absolute_uri(obj.file.url)
        return None

    def update(self, instance, validated_data):
        status_changed = (
            'review_status' in validated_data
            and validated_data['review_status'] != instance.review_status
        )

        instance = super().update(instance, validated_data)

        if status_changed:
            request = self.context.get('request')
            if request and hasattr(request, 'user'):
                instance.reviewer = request.user
            instance.review_date = timezone.now()
        else:
            instance.reviewer = None
            instance.review_date = None

        instance.save(update_fields=['reviewer', 'review_date'])
        return instance


class SimpleVendorDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = VendorDocument
        fields = ('id', 'review_status')


class VendorUserSerializer(serializers.ModelSerializer):
    role = serializers.CharField(source='role.name', read_only=True)

    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'role')


class CategoryLabelRelatedField(serializers.PrimaryKeyRelatedField):
    def to_representation(self, value):
        return f"{value.pk} - {value.name}"

    def to_internal_value(self, data):
        if isinstance(data, str):
            # Accept both plain PK strings and "id - name" labels
            candidate = data.strip()
            if ' - ' in candidate:
                candidate = candidate.split(' - ', 1)[0].strip()
            if candidate.isdigit():
                return super().to_internal_value(int(candidate))
        return super().to_internal_value(data)


class SimpleVendorProfileSerializer(serializers.ModelSerializer):
    user = serializers.SerializerMethodField()
    documents = SimpleVendorDocumentSerializer(many=True, read_only=True)

    class Meta:
        model = VendorProfile
        fields = ('id', 'code', 'name', 'company_name_bn', 'user', 'status', 'documents')

    def get_user(self, obj):
        if obj.user:
            return VendorUserSerializer(obj.user).data
        return None


class VendorProfileSerializer(serializers.ModelSerializer):
    created_by = serializers.CharField(source='created_by.username', read_only=True)
    documents = VendorDocumentSerializer(many=True, read_only=True)
    all_docs_verified = serializers.SerializerMethodField()
    user = serializers.SerializerMethodField()
    categories = CategoryLabelRelatedField(
        many=True,
        queryset=VendorProfile.categories.rel.model.objects.all()
    )

    class Meta:
        model = VendorProfile
        fields = '__all__'
        read_only_fields = [
            'code',
            'rating',
            'total_orders',
            'active_contracts',
            'verification_state',
            'registration_date',
            'enlistment_year',
            'trade_license_expiry',
            'approved_notes',
            'user',
            'created_at',
            'updated_at',
            'created_by',
        ]

    def get_all_docs_verified(self, obj):
        docs = obj.documents.all()
        return docs.exists() and not docs.exclude(review_status='Verified').exists()

    def get_matching_user(self, email):
        if not email:
            return None
        return User.objects.filter(email__iexact=email).first()

    def get_vendor_role(self):
        role, _ = Role.objects.get_or_create(name='Vendor')
        return role

    def get_user(self, obj):
        matched_user = self.get_matching_user(obj.email)
        if matched_user:
            vendor_role = self.get_vendor_role()
            if matched_user.role != vendor_role:
                matched_user.role = vendor_role
                matched_user.save(update_fields=['role'])
            return VendorUserSerializer(matched_user).data
        return None

    def create(self, validated_data):
        user = self.get_matching_user(validated_data.get('email'))
        vendor = super().create(validated_data)
        if user:
            vendor.user = user
            vendor.save(update_fields=['user'])
        return vendor

    def update(self, instance, validated_data):
        instance = super().update(instance, validated_data)
        instance.user = self.get_matching_user(instance.email)
        instance.save(update_fields=['user'])
        return instance

# class VendorCreateSerializer(serializers.ModelSerializer):
#     documents = VendorDocumentSerializer(many=True, required=False)

#     class Meta:
#         model = VendorProfile
#         fields = '__all__'
#         read_only_fields = ['code', 'created_by']

#     def create(self, validated_data):
#         documents_data = validated_data.pop('documents', [])
#         categories = validated_data.pop('categories', [])

#         request = self.context.get('request')

#         vendor = VendorProfile.objects.create(
#             **validated_data,
#             created_by=request.user if request else None
#         )

#         vendor.categories.set(categories)

#         for doc in documents_data:
#             VendorDocument.objects.create(vendor=vendor, **doc)

#         return vendor