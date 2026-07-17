from rest_framework import serializers
from ..models.apply_rfq_models import ApplyRFQ, ApplyRFQAttachment, ApplyRFQStatusLog, PriceProposal
from procurement.models.quotation_models import VendorQuotation, QuotationItem
from ..models.models import VendorProfile
from django.utils import timezone
from datetime import timedelta
from procurement.models.rfq_models import RFQ
from ..models.invitation_rfq_models import Invitation_rfq


class ApplyRFQStatusLogSerializer(serializers.ModelSerializer):
    acted_by_name = serializers.CharField(source='acted_by.username', read_only=True)
    rfq_number_display = serializers.CharField(source='rfq_number.rfq_number', read_only=True)

    class Meta:
        model = ApplyRFQStatusLog
        fields = [
            'id', 'rfq_number', 'rfq_number_display', 'status', 'action',
            'comments', 'acted_by', 'acted_by_name', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class ApplyRFQAttachmentSerializer(serializers.ModelSerializer):
    uploaded_by_name = serializers.CharField(source='uploaded_by.username', read_only=True)
    rfq_number_display = serializers.CharField(source='rfq_number.rfq_number', read_only=True)
    filename = serializers.ReadOnlyField()

    class Meta:
        model = ApplyRFQAttachment
        fields = [
            'id', 'rfq_number', 'rfq_number_display', 'name', 'type', 'file',
            'status', 'reviewer_comment', 'expires_at', 'uploaded_by',
            'uploaded_by_name', 'uploaded_at', 'created_at', 'filename'
        ]
        read_only_fields = ['id', 'uploaded_at', 'created_at', 'filename']


class ApplyRFQAttachmentCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating attachments without requiring rfq_number"""

    class Meta:
        model = ApplyRFQAttachment
        fields = [
            'name', 'type', 'file', 'status', 'reviewer_comment', 'expires_at'
        ]
        # Explicitly define choices to ensure validation works
        extra_kwargs = {
            'type': {'choices': ApplyRFQAttachment.TYPE_CHOICES},
            'status': {'choices': ApplyRFQAttachment.STATUS_CHOICES}
        }


class ApplyRFQStatusLogCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating status logs without requiring rfq_number"""

    class Meta:
        model = ApplyRFQStatusLog
        fields = [
            'status', 'action', 'comments'
        ]
        # rfq_number and acted_by will be set in the view


class PriceProposalSerializer(serializers.ModelSerializer):
    item_name = serializers.CharField(source='item.name', read_only=True)
    item_code = serializers.CharField(source='item.code', read_only=True)
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)

    class Meta:
        model = PriceProposal
        fields = [
            'id', 'item', 'item_name', 'item_code', 'proposed_price', 'quantity',
            'total_price', 'delivery_days', 'delivery_terms', 'validity_days',
            'payment_terms', 'warranty_period', 'technical_specs', 'comments',
            'status', 'created_by', 'created_by_name', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'total_price', 'created_at', 'updated_at', 'created_by_name']
        extra_kwargs = {
            'status': {'choices': PriceProposal.STATUS_CHOICES}
        }


class ApplyRFQSerializer(serializers.ModelSerializer):
    profile_name = serializers.CharField(source='profile.name', read_only=True)
    invitation_rfq_details = serializers.SerializerMethodField()
    attachments = serializers.SerializerMethodField()
    status_logs = serializers.SerializerMethodField()
    price_proposals = serializers.SerializerMethodField()
    total_price_proposal = serializers.SerializerMethodField()
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)

    class Meta:
        model = ApplyRFQ
        fields = [
            'id', 'profile', 'profile_name', 'invitation_rfq', 'invitation_rfq_details',
            'submission_note', 'attachments', 'status_logs', 'price_proposals',
            'total_price_proposal', 'created_by', 'created_by_name', 'created_at'
        ]
        read_only_fields = ['id', 'created_at', 'created_by_name']

    def get_invitation_rfq_details(self, obj):
        invitation = obj.invitation_rfq
        rfq = invitation.rfq_number
        items_data = []
        for item in rfq.items.all():
            items_data.append({
                'id': item.id,
                'code': item.code,
                'name': item.name,
                'description': item.description,
                'product_type': item.product_type,
                'category': item.category.name if item.category else None,
                'subcategory': item.subcategory.name if item.subcategory else None,
                'uom': item.uom.name if item.uom else None,
                'cost': item.cost,
                'sale_price': item.sale_price,
                'on_hand': item.on_hand,
                'available': item.available,
                'reorder_level': item.reorder_level,
                'max_stock': item.max_stock,
                'tracking': item.tracking,
                'weight': item.weight,
                'barcode': item.barcode,
                'status': item.status,
                'stock_status': item.stock_status
            })

        return {
            # Invitation RFQ fields
            'id': invitation.id,
            'submitted_at': invitation.submitted_at,
            'created_by_name': invitation.created_by.username if invitation.created_by else None,
            
            # RFQ fields
            'rfq_id': rfq.id,
            'rfq_number': rfq.rfq_number,
            'rfq_title': rfq.rfq_title,
            'description': rfq.description,
            'submission_deadline': rfq.submission_deadline,
            'status': rfq.status,
            'urgency': rfq.urgency,
            'payment_terms': rfq.payment_terms,
            'incoterm': rfq.incoterm,
            'tax_terms': rfq.tax_terms,
            'delivery_commitment_days': rfq.delivery_commitment_days,
            'total_estimated_value': rfq.total_estimated_value,
            'suppliers_count': rfq.suppliers_count,
            'responses_received': rfq.responses_received,
            'items_count': rfq.items_count,
            'rfq_created_by_name': rfq.created_by.username if rfq.created_by else None,
            'rfq_created_at': rfq.created_at,
            'rfq_updated_at': rfq.updated_at,
            
            # Items
            'items': items_data
        }

    def get_attachments(self, obj):
        attachments = obj.invitation_rfq.rfq_number.attachments.all()
        return ApplyRFQAttachmentSerializer(attachments, many=True).data

    def get_status_logs(self, obj):
        status_logs = obj.invitation_rfq.rfq_number.status_logs.all()
        return ApplyRFQStatusLogSerializer(status_logs, many=True).data

    def get_price_proposals(self, obj):
        price_proposals = obj.price_proposals.all()
        return PriceProposalSerializer(price_proposals, many=True).data

    def get_total_price_proposal(self, obj):
        return obj.total_price_proposal


class ApplyRFQCreateSerializer(serializers.ModelSerializer):
    attachments = ApplyRFQAttachmentCreateSerializer(many=True, required=False)
    status_logs = ApplyRFQStatusLogCreateSerializer(many=True, required=False)
    price_proposals = PriceProposalSerializer(many=True, required=False)

    class Meta:
        model = ApplyRFQ
        fields = [
            'id', 'profile', 'invitation_rfq', 'submission_note', 'attachments',
            'status_logs', 'price_proposals', 'created_by', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']

    def _serialize_price_proposals(self, proposals):
        serialized_price_proposals = []
        for proposal in proposals:
            if isinstance(proposal, dict):
                item = proposal['item']
                proposed_price = proposal['proposed_price']
                quantity = proposal['quantity']
                delivery_days = proposal['delivery_days']
                delivery_terms = proposal.get('delivery_terms', '')
                validity_days = proposal['validity_days']
                payment_terms = proposal.get('payment_terms', '')
                warranty_period = proposal.get('warranty_period', '')
                technical_specs = proposal.get('technical_specs', '')
                comments = proposal.get('comments', '')
                status = proposal.get('status', 'Draft')
            else:
                item = proposal.item
                proposed_price = proposal.proposed_price
                quantity = proposal.quantity
                delivery_days = proposal.delivery_days
                delivery_terms = proposal.delivery_terms
                validity_days = proposal.validity_days
                payment_terms = proposal.payment_terms
                warranty_period = proposal.warranty_period
                technical_specs = proposal.technical_specs
                comments = proposal.comments
                status = proposal.status

            serialized_price_proposals.append({
                'item_id': item.id,
                'item_name': getattr(item, 'item_name', getattr(item, 'name', None)),
                'item_code': getattr(item, 'item_code', getattr(item, 'code', None)),
                'proposed_price': float(proposed_price),
                'quantity': float(quantity),
                'delivery_days': delivery_days,
                'delivery_terms': delivery_terms,
                'validity_days': validity_days,
                'payment_terms': payment_terms,
                'warranty_period': warranty_period,
                'technical_specs': technical_specs,
                'comments': comments,
                'status': status,
            })
        return serialized_price_proposals

    def _get_vendor_profile(self, apply_rfq):
        return apply_rfq.profile

    def _sync_vendor_quotation(self, apply_rfq, price_proposals, user=None):
        rfq = apply_rfq.invitation_rfq.rfq_number
        serialized_price_proposals = self._serialize_price_proposals(price_proposals)
        vendor_profile = self._get_vendor_profile(apply_rfq)
        quotation, created = VendorQuotation.objects.get_or_create(
            rfq=rfq,
            vendor=vendor_profile,
            defaults={
                'submission_date': timezone.now(),
                'validity_date': timezone.now().date() + timedelta(days=30),
                'status': 'Submitted',
                'price_proposal': serialized_price_proposals,
                'created_by': user,
            }
        )
        if not created:
            quotation.submission_date = timezone.now()
            quotation.validity_date = timezone.now().date() + timedelta(days=30)
            quotation.status = 'Submitted'
            quotation.price_proposal = serialized_price_proposals
            if user:
                quotation.created_by = user
            quotation.save()
        return quotation

    def create(self, validated_data):
        attachments_data = validated_data.pop('attachments', [])
        status_logs_data = validated_data.pop('status_logs', [])
        price_proposals_data = validated_data.pop('price_proposals', [])

        # Set created_by from request context
        request = self.context.get('request')
        if request and hasattr(request, 'user'):
            validated_data['created_by'] = request.user

        apply_rfq = ApplyRFQ.objects.create(**validated_data)

        # Create attachments for the RFQ that this invitation_rfq points to
        rfq = apply_rfq.invitation_rfq.rfq_number
        for attachment_data in attachments_data:
            ApplyRFQAttachment.objects.create(
                rfq_number=rfq,
                uploaded_by=request.user if request else None,
                **attachment_data
            )

        # Create status logs for the RFQ
        for status_log_data in status_logs_data:
            ApplyRFQStatusLog.objects.create(
                rfq_number=rfq,
                acted_by=request.user if request else None,
                **status_log_data
            )

        # Create price proposals for the ApplyRFQ
        for proposal_data in price_proposals_data:
            proposal_data['apply_rfq'] = apply_rfq
            proposal_data['created_by'] = request.user if request else None
            PriceProposal.objects.create(**proposal_data)

        # Serialize price proposals data for JSON storage
        serialized_price_proposals = []
        for proposal_data in price_proposals_data:
            serialized_proposal = {
                'item_id': proposal_data['item'].id,
                'item_name': proposal_data['item'].item_name,
                'item_code': proposal_data['item'].item_code,
                'proposed_price': float(proposal_data['proposed_price']),
                'quantity': float(proposal_data['quantity']),
                'delivery_days': proposal_data['delivery_days'],
                'delivery_terms': proposal_data.get('delivery_terms', ''),
                'validity_days': proposal_data['validity_days'],
                'payment_terms': proposal_data.get('payment_terms', ''),
                'warranty_period': proposal_data.get('warranty_period', ''),
                'technical_specs': proposal_data.get('technical_specs', ''),
                'comments': proposal_data.get('comments', ''),
                'status': proposal_data.get('status', 'Draft')
            }
            serialized_price_proposals.append(serialized_proposal)

        quotation, created = VendorQuotation.objects.get_or_create(
            rfq=rfq,
            vendor=self._get_vendor_profile(apply_rfq),
            defaults={
                'submission_date': timezone.now(),
                'validity_date': timezone.now().date() + timedelta(days=30),
                'status': 'Submitted',
                'price_proposal': serialized_price_proposals,  # Store serialized price proposal data
                'created_by': request.user if request else None,
            }
        )

        # If quotation already existed, update its status and dates
        if not created:
            quotation.submission_date = timezone.now()
            quotation.validity_date = timezone.now().date() + timedelta(days=30)
            quotation.status = 'Submitted'
            quotation.price_proposal = serialized_price_proposals  # Update serialized price proposal data
            quotation.created_by = request.user if request else None
            quotation.save()

        # Create or update QuotationItems from price proposals
        for proposal_data in price_proposals_data:
            QuotationItem.objects.update_or_create(
                quotation=quotation,
                item=proposal_data['item'],
                defaults={
                    'quantity': proposal_data['quantity'],
                    'unit_price': proposal_data['proposed_price'],
                    'remarks': proposal_data.get('comments', '')
                }
            )

        return apply_rfq

    def update(self, instance, validated_data):
        attachments_data = validated_data.pop('attachments', [])
        status_logs_data = validated_data.pop('status_logs', [])
        price_proposals_data = validated_data.pop('price_proposals', None)

        # Update main instance
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        request = self.context.get('request')
        user = request.user if request else None
        rfq = instance.invitation_rfq.rfq_number

        # Handle attachments - for simplicity, we'll replace all attachments
        if attachments_data:
            rfq.attachments.all().delete()  # Remove existing
            for attachment_data in attachments_data:
                ApplyRFQAttachment.objects.create(
                    rfq_number=rfq,
                    uploaded_by=user,
                    **attachment_data
                )

        # Handle status logs - for simplicity, we'll replace all status logs
        if status_logs_data:
            rfq.status_logs.all().delete()  # Remove existing
            for status_log_data in status_logs_data:
                ApplyRFQStatusLog.objects.create(
                    rfq_number=rfq,
                    acted_by=user,
                    **status_log_data
                )

        # Handle price proposals - for simplicity, we'll replace all proposals
        if price_proposals_data is not None:
            instance.price_proposals.all().delete()  # Remove existing
            for proposal_data in price_proposals_data:
                proposal_data['apply_rfq'] = instance
                proposal_data['created_by'] = user
                PriceProposal.objects.create(**proposal_data)
            quotation = self._sync_vendor_quotation(instance, price_proposals_data, user)
            for proposal_data in price_proposals_data:
                QuotationItem.objects.update_or_create(
                    quotation=quotation,
                    item=proposal_data['item'],
                    defaults={
                        'quantity': proposal_data['quantity'],
                        'unit_price': proposal_data['proposed_price'],
                        'remarks': proposal_data.get('comments', '')
                    }
                )
        else:
            if VendorQuotation.objects.filter(rfq=rfq, vendor=self._get_vendor_profile(instance)).exists():
                self._sync_vendor_quotation(instance, instance.price_proposals.all(), user)

        return instance