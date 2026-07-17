
from rest_framework import serializers
from ..models.invitation_rfq_models import Invitation_rfq
from procurement.serializers.rfq_serializers import RFQSerializer, RFQLineItemSerializer
from procurement.models.quotation_models import VendorQuotation, QuotationItem
from ..models.models import VendorProfile
from django.utils import timezone
from datetime import timedelta

# class SubmitRFQSerializer(serializers.ModelSerializer):
#     rfq_number = serializers.SerializerMethodField()

#     class Meta:
#         model = SubmitRFQ
#         fields = ["id", "rfq_number", "submitted_by", "submitted_at", "notes"]


#         return {
#             "id": obj.rfq_number.id,
#             "rfq_number": obj.rfq_number.rfq_number,
#             "title": getattr(obj.rfq_number, "rfq_title", None),  # সঠিক ফিল্ড নাম
#             "status": obj.rfq_number.status,
#         }

class Invitation_rfqCreateSerializer(serializers.ModelSerializer):
    # Quotation fields
    vendor = serializers.PrimaryKeyRelatedField(queryset=VendorProfile.objects.all())
    validity_date = serializers.DateField(required=False)
    discount_percentage = serializers.DecimalField(max_digits=5, decimal_places=2, default=0)
    tax_amount = serializers.DecimalField(max_digits=15, decimal_places=2, default=0)
    delivery_terms = serializers.CharField(required=False, allow_blank=True)
    payment_terms = serializers.CharField(required=False, allow_blank=True)
    warranty_terms = serializers.CharField(required=False, allow_blank=True)
    remarks = serializers.CharField(required=False, allow_blank=True)
    quotation_items = serializers.JSONField(required=False)  # For item pricing data

    class Meta:
        model = Invitation_rfq
        fields = [
            "rfq_number",
            # Quotation fields
            "vendor",
            "validity_date",
            "discount_percentage", 
            "tax_amount",
            "delivery_terms",
            "payment_terms",
            "warranty_terms",
            "remarks",
            "quotation_items",
        ]

    def create(self, validated_data):
        # Extract quotation data
        vendor = validated_data.pop('vendor')
        validity_date = validated_data.pop('validity_date', None)
        discount_percentage = validated_data.pop('discount_percentage', 0)
        tax_amount = validated_data.pop('tax_amount', 0)
        delivery_terms = validated_data.pop('delivery_terms', '')
        payment_terms = validated_data.pop('payment_terms', '')
        warranty_terms = validated_data.pop('warranty_terms', '')
        remarks = validated_data.pop('remarks', '')
        quotation_items_data = validated_data.pop('quotation_items', [])

        # Create invitation_rfq first
        invitation_rfq = super().create(validated_data)

        # Set default validity_date if not provided (30 days from now)
        if not validity_date:
            validity_date = timezone.now().date() + timedelta(days=30)

        # Create quotation
        quotation_data = {
            'rfq': invitation_rfq.rfq_number,
            'vendor': vendor,
            'validity_date': validity_date,
            'discount_percentage': discount_percentage,
            'tax_amount': tax_amount,
            'delivery_terms': delivery_terms,
            'payment_terms': payment_terms,
            'warranty_terms': warranty_terms,
            'remarks': remarks,
            'created_by': self.context['request'].user,
        }

        quotation = VendorQuotation.objects.create(**quotation_data)

        # Create quotation items if provided
        for item_data in quotation_items_data:
            if isinstance(item_data, dict):
                QuotationItem.objects.create(
                    quotation=quotation,
                    item_id=item_data.get('item_id'),
                    quantity=item_data.get('quantity', 1),
                    unit_price=item_data.get('unit_price', 0),
                    remarks=item_data.get('remarks', '')
                )

        return invitation_rfq


class Invitation_rfqSerializer(serializers.ModelSerializer):
    
    rfq_number = serializers.SerializerMethodField()

    class Meta:
        model = Invitation_rfq
        fields = [
            "id",
            "rfq_number",
       
            "submitted_at",
        ]

    def get_rfq_number(self, obj):
        line_items = RFQLineItemSerializer(obj.rfq_number.line_items.all(), many=True).data
        return {
            "id": obj.rfq_number.id,
            "rfq_number": obj.rfq_number.rfq_number,
            "title": obj.rfq_number.rfq_title,
            "category": str(obj.rfq_number.rfq_category) if obj.rfq_number.rfq_category else None,
            # "location": obj.rfq_number.location,
            "published_date": obj.rfq_number.published_at,  # ✅ FIX
            "deadline": obj.rfq_number.submission_deadline,
            "status": obj.rfq_number.status,
            "budgetBand": obj.rfq_number.total_estimated_value,
            # "quotationStatus":
            "required_documents":obj.rfq_number.required_documents,
            "items": line_items,
            "created_by": obj.rfq_number.created_by.username if obj.rfq_number.created_by else None,
            
        }

    

