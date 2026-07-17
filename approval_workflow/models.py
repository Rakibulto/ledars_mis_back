from django.db import models
from authentication.models import User


MODULE_TYPE_INVENTORY = 'inventory'
MODULE_TYPE_PROCUREMENT = 'procurement'
MODULE_TYPE_BENEFICIARY = 'beneficiary'
LEVEL_MAINTAIN_REQUIRE_YES = 'yes'
LEVEL_MAINTAIN_REQUIRE_NO = 'no'


MODULE_TYPE_CHOICES = [
    (MODULE_TYPE_INVENTORY, 'Inventory'),
    (MODULE_TYPE_PROCUREMENT, 'Procurement'),
    (MODULE_TYPE_BENEFICIARY, 'Beneficiary'),
    
]

LEVEL_MAINTAIN_REQUIRE_CHOICES = [
    (LEVEL_MAINTAIN_REQUIRE_YES, 'Yes'),
    (LEVEL_MAINTAIN_REQUIRE_NO, 'No'),
]

INVENTORY_MENUS = [
    'good_issue_note',
    'internal_transfers',
    'stock_adjustment',
    'stock_adjustment_add_stock',
    'scrap_management',
    'return_management',
]

PROCUREMENT_MENUS = [
    'material_requisition',
    'rfq',
    'quotation',
]

BENEFICIARY_MENUS = [
    'register_beneficiary',
    
]

MENU_CHOICES_BY_TYPE = {
    MODULE_TYPE_INVENTORY: INVENTORY_MENUS,
    MODULE_TYPE_PROCUREMENT: PROCUREMENT_MENUS,
    MODULE_TYPE_BENEFICIARY: BENEFICIARY_MENUS,
}

MENU_CHOICES = [(item, item) for item in INVENTORY_MENUS + PROCUREMENT_MENUS + BENEFICIARY_MENUS]


class ApprovalWorkflow(models.Model):
    """
    A configured approval workflow for a specific module type and menu.
    """
    module_type_name = models.CharField(max_length=50, choices=MODULE_TYPE_CHOICES)
    menu_name = models.CharField(max_length=100, choices=MENU_CHOICES, default="good_issue_note", blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approval_workflows'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Approval Workflow'
        verbose_name_plural = 'Approval Workflows'

    def __str__(self):
        return f"Workflow: {self.module_type_name} → {self.menu_name}"

    @property
    def total_levels(self):
        return self.levels.count()


class ApprovalLevel(models.Model):
    """
    An individual approval level within a workflow.
    """
    workflow = models.ForeignKey(
        ApprovalWorkflow, on_delete=models.CASCADE, related_name='levels'
    )
    level_number = models.PositiveSmallIntegerField()
    from_amount = models.DecimalField(max_digits=18, decimal_places=5, default=0)
    to_amount = models.DecimalField(
        max_digits=18, decimal_places=5, null=True, blank=True,
        help_text='Leave blank for unlimited upper bound'
    )
    minimum_approval_required = models.PositiveSmallIntegerField(
        default=1,
        help_text='Minimum number of approvers that must approve before this level completes'
    )
    level_maintain_require = models.CharField(
        max_length=3,
        choices=LEVEL_MAINTAIN_REQUIRE_CHOICES,
        default=LEVEL_MAINTAIN_REQUIRE_YES,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['workflow', 'level_number']
        unique_together = ('workflow', 'level_number')
        verbose_name = 'Approval Level'
        verbose_name_plural = 'Approval Levels'

    def __str__(self):
        return f"Level {self.level_number} — {self.workflow}"


class ApprovalLevelUser(models.Model):
    """
    Users assigned to a specific approval level, with an individual approval order.
    """
    level = models.ForeignKey(
        ApprovalLevel, on_delete=models.CASCADE, related_name='level_users'
    )
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='workflow_level_assignments'
    )
    approval_order = models.PositiveSmallIntegerField(
        default=1,
        help_text='Sequence order for this approver within the level'
    )

    class Meta:
        unique_together = [('level', 'user'), ('level', 'approval_order')]
        ordering = ['level', 'approval_order']
        verbose_name = 'Approval Level User'
        verbose_name_plural = 'Approval Level Users'

    def __str__(self):
        return f"{self.user} @ {self.level} (order {self.approval_order})"
