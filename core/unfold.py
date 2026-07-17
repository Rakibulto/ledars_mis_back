from django.urls import reverse_lazy
from django.templatetags.static import static
from django.utils.translation import gettext_lazy as _

UNFOLD = {
    "SITE_TITLE": ("HRM Super Admin Panel"),
    "SITE_HEADER": ("Human Resource Management"),
    "SITE_ICON": {
        "light": "/static/assets/logo/hrm-logo.png",  # light mode
        "dark": "/static/assets/logo/hrm-logo.png",  # dark mode
    },
    "SHOW_HISTORY": True,  # show/hide "History" button, default: True
    "SHOW_VIEW_ON_SITE": True,  # show/hide "View on site" button, default: True
    "SHOW_BACK_BUTTON": True,  # show/hide "Back" button on changeform in header, default: False
    "BORDER_RADIUS": "10px",
    "COLORS": {
        "base": {
            "50": "248, 250, 252",  # #F8FAFC
            "100": "241, 245, 249",  # #F1F5F9
            "200": "226, 232, 240",  # #E2E8F0
            "300": "203, 213, 225",  # #CBD5E1
            "400": "148, 163, 184",  # #94A3B8
            "500": "100, 116, 139",  # #64748B
            "600": "71, 85, 105",  # #475569
            "700": "51, 65, 85",  # #334155
            "800": "30, 41, 59",  # #1E293B
            "900": "15, 23, 42",  # #0F172A
            "950": "2, 6, 23",  # #020617
        },
        "primary": {
            "50": "245, 243, 255",  # #F5F3FF
            "100": "237, 233, 254",  # #EDE9FE
            "200": "221, 214, 254",  # #DDD6FE
            "300": "196, 181, 253",  # #C4B5FD
            "400": "167, 139, 250",  # #A78BFA
            "500": "139, 92, 246",  # #8B5CF6
            "600": "124, 58, 237",  # #7C3AED
            "700": "109, 40, 217",  # #6D28D9
            "800": "91, 33, 182",  # #5B21B6
            "900": "76, 29, 149",  # #4C1D95
            "950": "59, 7, 100",  # #3B0764
        },
        "font": {
            "subtle-light": "var(--color-base-500)",  # text-base-500
            "subtle-dark": "var(--color-base-400)",  # text-base-400
            "default-light": "var(--color-base-600)",  # text-base-600
            "default-dark": "var(--color-base-300)",  # text-base-300
            "important-light": "var(--color-base-900)",  # text-base-900
            "important-dark": "var(--color-base-100)",  # text-base-100
        },
    },
    "COMMAND": {
        "search_models": True,
        "search_callback": "utils.search_callback",
        "show_history": True,
    },
    "SIDEBAR": {
        "show_search": True,
        "show_all_applications": True,
        "command_search": False,  # Replace the sidebar search with the command search
        "navigation": [
            {
                "title": "Company Information",
                "icon": "business",
                "separator": True,
                "collapsible": True,
                "collapsed": True,
                "items": [
                    {
                        "title": "Company Info",
                        "icon": "info",
                        "link": reverse_lazy(
                            "admin:authentication_companyinfo_changelist"
                        ),
                    },
                ],
            },
            {
                "title": "Users",
                "icon": "security",  # Optional icon for the dropdown header
                "separator": True,
                "collapsible": True,
                "collapsed": True,
                "items": [
                    {
                        "title": "Users",
                        "icon": "people",
                        "link": reverse_lazy("admin:authentication_user_changelist"),
                    },
                    {
                        "title": "Employees",
                        "icon": "person",
                        "link": reverse_lazy("admin:employee_employee_changelist"),
                    },
                    {
                        "title": "Emergency Contacts",
                        "icon": "contact_emergency",
                        "link": reverse_lazy(
                            "admin:employee_emergencycontact_changelist"
                        ),
                    },
                    {
                        "title": "Nominees",
                        "icon": "family_restroom",
                        "link": reverse_lazy("admin:employee_nominee_changelist"),
                    },
                ],
            },
            {
                "title": "Attendance",
                "icon": "event",
                "separator": True,
                "collapsible": True,
                "collapsed": True,
                "items": [
                    {
                        "title": "Attendance Data",
                        "icon": "event",
                        "link": reverse_lazy(
                            "admin:attendance_attendancedata_changelist"
                        ),
                    },
                    {
                        "title": "Attendance History",
                        "icon": "history",
                        "link": reverse_lazy(
                            "admin:attendance_attendancehistory_changelist"
                        ),
                    },
                    {
                        "title": "Adjustment Requests",
                        "icon": "edit_calendar",
                        "link": reverse_lazy(
                            "admin:attendance_attendanceadjustmentrequest_changelist"
                        ),
                    },
                    {
                        "title": "Adjustment Approvals",
                        "icon": "check_circle",
                        "link": reverse_lazy(
                            "admin:attendance_attendanceadjustmentapproval_changelist"
                        ),
                    },
                ],
            },
            {
                "title": "Holiday Management",
                "icon": "holiday_village",
                "separator": True,
                "collapsible": True,
                "collapsed": True,
                "items": [
                    {
                        "title": "Holidays",
                        "icon": "holiday_village",
                        "link": reverse_lazy("admin:holiday_holiday_changelist"),
                    },
                ],
            },
            {
                "title": "Leave Management",
                "icon": "event_note",
                "separator": True,
                "collapsible": True,
                "collapsed": True,
                "items": [
                    {
                        "title": "Leave Requests",
                        "icon": "event_note",
                        "link": reverse_lazy("admin:leave_leaverequest_changelist"),
                    },
                    {
                        "title": "Supervisor Levels",
                        "icon": "supervisor_account",
                        "link": reverse_lazy("admin:leave_supervisorlevel_changelist"),
                    },
                    {
                        "title": "Leave Approvals",
                        "icon": "fact_check",
                        "link": reverse_lazy("admin:leave_leaveapproval_changelist"),
                    },
                    {
                        "title": "Leave Transfers",
                        "icon": "swap_horiz",
                        "link": reverse_lazy("admin:leave_leavetransfer_changelist"),
                    },
                    {
                        "title": "Compensatory Leave Balances",
                        "icon": "balance",
                        "link": reverse_lazy(
                            "admin:leave_compensatoryleavebalance_changelist"
                        ),
                    },
                    {
                        "title": "Compensatory Leaves Earned",
                        "icon": "redeem",
                        "link": reverse_lazy(
                            "admin:leave_compensatoryleaveearned_changelist"
                        ),
                    },
                ],
            },
            {
                "title": "Procurement",
                "icon": "shopping_cart",
                "separator": True,
                "collapsible": True,
                "collapsed": True,
                "items": [
                    {
                        "title": "Suppliers",
                        "icon": "store",
                        "link": reverse_lazy(
                            "admin:vendorportal_vendorprofile_changelist"
                        ),
                    },
                    {
                        "title": "Material Requisitions",
                        "icon": "assignment",
                        "link": reverse_lazy(
                            "admin:procurement_materialrequisition_changelist"
                        ),
                    },
                    {
                        "title": "Purchase Requisitions",
                        "icon": "request_quote",
                        "link": reverse_lazy(
                            "admin:procurement_purchaserequisition_changelist"
                        ),
                    },
                    {
                        "title": "Purchase Orders",
                        "icon": "receipt_long",
                        "link": reverse_lazy(
                            "admin:procurement_purchaseorder_changelist"
                        ),
                    },
                    {
                        "title": "RFQs",
                        "icon": "quiz",
                        "link": reverse_lazy("admin:procurement_rfq_changelist"),
                    },
                    {
                        "title": "Vendor Quotations",
                        "icon": "description",
                        "link": reverse_lazy(
                            "admin:procurement_vendorquotation_changelist"
                        ),
                    },
                    {
                        "title": "Comparative Statements",
                        "icon": "compare_arrows",
                        "link": reverse_lazy(
                            "admin:procurement_comparativestatement_changelist"
                        ),
                    },
                    {
                        "title": "Awards",
                        "icon": "emoji_events",
                        "link": reverse_lazy("admin:procurement_award_changelist"),
                    },
                    {
                        "title": "Work Orders",
                        "icon": "engineering",
                        "link": reverse_lazy("admin:procurement_workorder_changelist"),
                    },
                    {
                        "title": "Goods Receipt Notes",
                        "icon": "inventory_2",
                        "link": reverse_lazy(
                            "admin:procurement_goodsreceiptnote_changelist"
                        ),
                    },
                    {
                        "title": "Payment Requisitions",
                        "icon": "payments",
                        "link": reverse_lazy(
                            "admin:procurement_paymentrequisition_changelist"
                        ),
                    },
                    {
                        "title": "Treasury Processing",
                        "icon": "account_balance",
                        "link": reverse_lazy(
                            "admin:procurement_treasuryprocessing_changelist"
                        ),
                    },
                    {
                        "title": "Payment Records",
                        "icon": "paid",
                        "link": reverse_lazy(
                            "admin:procurement_paymentrecord_changelist"
                        ),
                    },
                    {
                        "title": "Approval Requests",
                        "icon": "approval",
                        "link": reverse_lazy(
                            "admin:procurement_approvalrequest_changelist"
                        ),
                    },
                ],
            },
            {
                "title": "Vendor Management",
                "icon": "handshake",
                "separator": True,
                "collapsible": True,
                "collapsed": True,
                "items": [
                    {
                        "title": "Vendor Categories",
                        "icon": "category",
                        "link": reverse_lazy(
                            "admin:procurement_vendorcategory_changelist"
                        ),
                    },
                    {
                        "title": "Vendor Evaluations",
                        "icon": "rate_review",
                        "link": reverse_lazy(
                            "admin:procurement_vendorevaluation_changelist"
                        ),
                    },
                    {
                        "title": "Vendor Onboarding",
                        "icon": "person_add",
                        "link": reverse_lazy(
                            "admin:procurement_vendoronboarding_changelist"
                        ),
                    },
                    {
                        "title": "Vendor Verification",
                        "icon": "verified",
                        "link": reverse_lazy(
                            "admin:procurement_vendorverification_changelist"
                        ),
                    },
                    {
                        "title": "Vendor Performance",
                        "icon": "trending_up",
                        "link": reverse_lazy(
                            "admin:procurement_vendorperformance_changelist"
                        ),
                    },
                ],
            },
            {
                "title": "Procurement Settings",
                "icon": "tune",
                "separator": True,
                "collapsible": True,
                "collapsed": True,
                "items": [
                    {
                        "title": "Budgets",
                        "icon": "account_balance_wallet",
                        "link": reverse_lazy("admin:procurement_budget_changelist"),
                    },
                    {
                        "title": "Accounts",
                        "icon": "credit_card",
                        "link": reverse_lazy("admin:procurement_account_changelist"),
                    },
                    {
                        "title": "Approval Matrix",
                        "icon": "rule",
                        "link": reverse_lazy(
                            "admin:procurement_approvalmatrix_changelist"
                        ),
                    },
                    {
                        "title": "Email Templates",
                        "icon": "mail",
                        "link": reverse_lazy(
                            "admin:procurement_emailtemplate_changelist"
                        ),
                    },
                    {
                        "title": "Procurement Roles",
                        "icon": "admin_panel_settings",
                        "link": reverse_lazy(
                            "admin:procurement_procurementrole_changelist"
                        ),
                    },
                    {
                        "title": "Notification Settings",
                        "icon": "notification_important",
                        "link": reverse_lazy(
                            "admin:procurement_notificationsetting_changelist"
                        ),
                    },
                    {
                        "title": "Office Management",
                        "icon": "location_on",
                        "link": reverse_lazy(
                            "admin:procurement_officemanagement_changelist"
                        ),
                    },
                ],
            },
            {
                "title": "Notifications",
                "icon": "notifications",
                "separator": True,
                "collapsible": True,
                "collapsed": True,
                "items": [
                    {
                        "title": "Notifications",
                        "icon": "notifications",
                        "link": reverse_lazy(
                            "admin:notification_notification_changelist"
                        ),
                    },
                    {
                        "title": "Procurement Notifications",
                        "icon": "campaign",
                        "link": reverse_lazy(
                            "admin:procurement_procurementnotification_changelist"
                        ),
                    },
                ],
            },
            {
                "title": "Projects",
                "icon": "folder_special",
                "separator": True,
                "collapsible": True,
                "collapsed": True,
                "items": [
                    {
                        "title": "Projects",
                        "icon": "work",
                        "link": reverse_lazy("admin:projects_project_changelist"),
                    },
                    {
                        "title": "Project Activities",
                        "icon": "timeline",
                        "link": reverse_lazy(
                            "admin:projects_projectactivity_changelist"
                        ),
                    },
                    {
                        "title": "Workspaces",
                        "icon": "workspaces",
                        "link": reverse_lazy("admin:projects_workspace_changelist"),
                    },
                    {
                        "title": "Workspace Members",
                        "icon": "group_work",
                        "link": reverse_lazy(
                            "admin:projects_workspacemember_changelist"
                        ),
                    },
                    {
                        "title": "Spaces",
                        "icon": "space_dashboard",
                        "link": reverse_lazy("admin:projects_space_changelist"),
                    },
                    {
                        "title": "Space Members",
                        "icon": "people_outline",
                        "link": reverse_lazy("admin:projects_spacemember_changelist"),
                    },
                    {
                        "title": "Lists",
                        "icon": "list_alt",
                        "link": reverse_lazy("admin:projects_list_changelist"),
                    },
                ],
            },
            {
                "title": "Task Management",
                "icon": "task_alt",
                "separator": True,
                "collapsible": True,
                "collapsed": True,
                "items": [
                    {
                        "title": "Tasks",
                        "icon": "check_circle",
                        "link": reverse_lazy("admin:projects_task_changelist"),
                    },
                    {
                        "title": "Subtasks",
                        "icon": "subdirectory_arrow_right",
                        "link": reverse_lazy("admin:projects_subtask_changelist"),
                    },
                    {
                        "title": "Checklists",
                        "icon": "checklist",
                        "link": reverse_lazy("admin:projects_checklist_changelist"),
                    },
                    {
                        "title": "Task Comments",
                        "icon": "comment",
                        "link": reverse_lazy("admin:projects_taskcomment_changelist"),
                    },
                    {
                        "title": "Task Activity Logs",
                        "icon": "history",
                        "link": reverse_lazy(
                            "admin:projects_taskactivitylog_changelist"
                        ),
                    },
                    {
                        "title": "Tags",
                        "icon": "label",
                        "link": reverse_lazy("admin:projects_tag_changelist"),
                    },
                    {
                        "title": "Status Groups",
                        "icon": "view_kanban",
                        "link": reverse_lazy("admin:projects_statusgroup_changelist"),
                    },
                    {
                        "title": "Statuses",
                        "icon": "flag",
                        "link": reverse_lazy("admin:projects_status_changelist"),
                    },
                ],
            },
            {
                "title": "PM Planning",
                "icon": "calendar_month",
                "separator": True,
                "collapsible": True,
                "collapsed": True,
                "items": [
                    {
                        "title": "Sprints",
                        "icon": "sprint",
                        "link": reverse_lazy("admin:projects_sprint_changelist"),
                    },
                    {
                        "title": "Milestones",
                        "icon": "flag_circle",
                        "link": reverse_lazy("admin:projects_milestone_changelist"),
                    },
                    {
                        "title": "Goals",
                        "icon": "track_changes",
                        "link": reverse_lazy("admin:projects_goal_changelist"),
                    },
                    {
                        "title": "Time Entries",
                        "icon": "timer",
                        "link": reverse_lazy("admin:projects_timeentry_changelist"),
                    },
                ],
            },
            {
                "title": "PM Tools",
                "icon": "build",
                "separator": True,
                "collapsible": True,
                "collapsed": True,
                "items": [
                    {
                        "title": "Docs",
                        "icon": "article",
                        "link": reverse_lazy("admin:projects_doc_changelist"),
                    },
                    {
                        "title": "Whiteboards",
                        "icon": "draw",
                        "link": reverse_lazy("admin:projects_whiteboard_changelist"),
                    },
                    {
                        "title": "Dashboards",
                        "icon": "dashboard",
                        "link": reverse_lazy("admin:projects_dashboard_changelist"),
                    },
                    {
                        "title": "Saved Views",
                        "icon": "view_list",
                        "link": reverse_lazy("admin:projects_savedview_changelist"),
                    },
                    {
                        "title": "Custom Fields",
                        "icon": "tune",
                        "link": reverse_lazy("admin:projects_customfield_changelist"),
                    },
                    {
                        "title": "Forms",
                        "icon": "dynamic_form",
                        "link": reverse_lazy("admin:projects_form_changelist"),
                    },
                    {
                        "title": "Templates",
                        "icon": "content_copy",
                        "link": reverse_lazy("admin:projects_template_changelist"),
                    },
                ],
            },
            {
                "title": "PM Automation",
                "icon": "smart_toy",
                "separator": True,
                "collapsible": True,
                "collapsed": True,
                "items": [
                    {
                        "title": "Automations",
                        "icon": "auto_fix_high",
                        "link": reverse_lazy("admin:projects_automation_changelist"),
                    },
                    {
                        "title": "Automation Logs",
                        "icon": "receipt_long",
                        "link": reverse_lazy("admin:projects_automationlog_changelist"),
                    },
                ],
            },
            {
                "title": "PM Access & Config",
                "icon": "admin_panel_settings",
                "separator": True,
                "collapsible": True,
                "collapsed": True,
                "items": [
                    {
                        "title": "PM Roles",
                        "icon": "shield",
                        "link": reverse_lazy("admin:projects_pmrole_changelist"),
                    },
                    {
                        "title": "PM User Roles",
                        "icon": "manage_accounts",
                        "link": reverse_lazy("admin:projects_pmuserrole_changelist"),
                    },
                    {
                        "title": "PM Notifications",
                        "icon": "notifications_active",
                        "link": reverse_lazy(
                            "admin:projects_pmnotification_changelist"
                        ),
                    },
                    {
                        "title": "Favorites",
                        "icon": "star",
                        "link": reverse_lazy("admin:projects_favorite_changelist"),
                    },
                ],
            },
            {
                "title": "Accounting - Chart of Accounts",
                "icon": "account_tree",
                "separator": True,
                "collapsible": True,
                "collapsed": True,
                "items": [
                    {
                        "title": "Account Types",
                        "icon": "category",
                        "link": reverse_lazy("admin:accounting_accounttype_changelist"),
                    },
                    {
                        "title": "Account Groups",
                        "icon": "folder",
                        "link": reverse_lazy(
                            "admin:accounting_accountgroup_changelist"
                        ),
                    },
                    {
                        "title": "Accounts",
                        "icon": "account_balance",
                        "link": reverse_lazy("admin:accounting_account_changelist"),
                    },
                    {
                        "title": "Account Tags",
                        "icon": "label",
                        "link": reverse_lazy("admin:accounting_accounttag_changelist"),
                    },
                ],
            },
            {
                "title": "Accounting - Journals & Vouchers",
                "icon": "menu_book",
                "separator": True,
                "collapsible": True,
                "collapsed": True,
                "items": [
                    {
                        "title": "Fiscal Years",
                        "icon": "date_range",
                        "link": reverse_lazy("admin:accounting_fiscalyear_changelist"),
                    },
                    {
                        "title": "Journals",
                        "icon": "book",
                        "link": reverse_lazy("admin:accounting_journal_changelist"),
                    },
                    {
                        "title": "Journal Entries",
                        "icon": "receipt",
                        "link": reverse_lazy(
                            "admin:accounting_journalentry_changelist"
                        ),
                    },
                    {
                        "title": "Vouchers",
                        "icon": "confirmation_number",
                        "link": reverse_lazy("admin:accounting_voucher_changelist"),
                    },
                    {
                        "title": "Recurring Journals",
                        "icon": "autorenew",
                        "link": reverse_lazy(
                            "admin:accounting_recurringjournaltemplate_changelist"
                        ),
                    },
                ],
            },
            {
                "title": "Accounting - Payables & Receivables",
                "icon": "swap_horiz",
                "separator": True,
                "collapsible": True,
                "collapsed": True,
                "items": [
                    {
                        "title": "Vendors",
                        "icon": "store",
                        "link": reverse_lazy("admin:accounting_vendor_changelist"),
                    },
                    {
                        "title": "Bills",
                        "icon": "receipt_long",
                        "link": reverse_lazy("admin:accounting_bill_changelist"),
                    },
                    {
                        "title": "Customers",
                        "icon": "people",
                        "link": reverse_lazy("admin:accounting_customer_changelist"),
                    },
                    {
                        "title": "Invoices",
                        "icon": "description",
                        "link": reverse_lazy("admin:accounting_invoice_changelist"),
                    },
                    {
                        "title": "Debit Notes",
                        "icon": "note_add",
                        "link": reverse_lazy("admin:accounting_debitnote_changelist"),
                    },
                    {
                        "title": "Credit Notes",
                        "icon": "note",
                        "link": reverse_lazy("admin:accounting_creditnote_changelist"),
                    },
                ],
            },
            {
                "title": "Accounting - Banking & Payments",
                "icon": "account_balance",
                "separator": True,
                "collapsible": True,
                "collapsed": True,
                "items": [
                    {
                        "title": "Bank Accounts",
                        "icon": "account_balance",
                        "link": reverse_lazy("admin:accounting_bankaccount_changelist"),
                    },
                    {
                        "title": "Bank Transactions",
                        "icon": "compare_arrows",
                        "link": reverse_lazy(
                            "admin:accounting_banktransaction_changelist"
                        ),
                    },
                    {
                        "title": "Bank Reconciliations",
                        "icon": "fact_check",
                        "link": reverse_lazy(
                            "admin:accounting_bankreconciliation_changelist"
                        ),
                    },
                    {
                        "title": "Payments",
                        "icon": "payments",
                        "link": reverse_lazy("admin:accounting_payment_changelist"),
                    },
                    {
                        "title": "Cash Registers",
                        "icon": "point_of_sale",
                        "link": reverse_lazy(
                            "admin:accounting_cashregister_changelist"
                        ),
                    },
                ],
            },
            {
                "title": "Accounting - Budgets & Analytics",
                "icon": "analytics",
                "separator": True,
                "collapsible": True,
                "collapsed": True,
                "items": [
                    {
                        "title": "Budgets",
                        "icon": "account_balance_wallet",
                        "link": reverse_lazy("admin:accounting_budget_changelist"),
                    },
                    {
                        "title": "Budget Transfers",
                        "icon": "swap_horiz",
                        "link": reverse_lazy(
                            "admin:accounting_budgettransfer_changelist"
                        ),
                    },
                    {
                        "title": "Cost Centers",
                        "icon": "hub",
                        "link": reverse_lazy("admin:accounting_costcenter_changelist"),
                    },
                    {
                        "title": "Analytic Accounts",
                        "icon": "insights",
                        "link": reverse_lazy(
                            "admin:accounting_analyticaccount_changelist"
                        ),
                    },
                ],
            },
            {
                "title": "Accounting - Tax & Currency",
                "icon": "percent",
                "separator": True,
                "collapsible": True,
                "collapsed": True,
                "items": [
                    {
                        "title": "Tax Groups",
                        "icon": "folder",
                        "link": reverse_lazy("admin:accounting_taxgroup_changelist"),
                    },
                    {
                        "title": "Taxes",
                        "icon": "percent",
                        "link": reverse_lazy("admin:accounting_tax_changelist"),
                    },
                    {
                        "title": "Withholding Taxes",
                        "icon": "money_off",
                        "link": reverse_lazy(
                            "admin:accounting_withholdingtax_changelist"
                        ),
                    },
                    {
                        "title": "Currencies",
                        "icon": "currency_exchange",
                        "link": reverse_lazy("admin:accounting_currency_changelist"),
                    },
                    {
                        "title": "Exchange Rates",
                        "icon": "trending_up",
                        "link": reverse_lazy(
                            "admin:accounting_exchangerate_changelist"
                        ),
                    },
                ],
            },
            {
                "title": "Accounting - Reports & Settings",
                "icon": "summarize",
                "separator": True,
                "collapsible": True,
                "collapsed": True,
                "items": [
                    {
                        "title": "Report Templates",
                        "icon": "description",
                        "link": reverse_lazy(
                            "admin:accounting_financialreporttemplate_changelist"
                        ),
                    },
                    {
                        "title": "Generated Reports",
                        "icon": "assessment",
                        "link": reverse_lazy(
                            "admin:accounting_generatedreport_changelist"
                        ),
                    },
                    {
                        "title": "Accounting Settings",
                        "icon": "settings",
                        "link": reverse_lazy(
                            "admin:accounting_accountingsettings_changelist"
                        ),
                    },
                    {
                        "title": "Number Sequences",
                        "icon": "format_list_numbered",
                        "link": reverse_lazy(
                            "admin:accounting_numbersequence_changelist"
                        ),
                    },
                    {
                        "title": "Approval Rules",
                        "icon": "rule",
                        "link": reverse_lazy(
                            "admin:accounting_approvalrule_changelist"
                        ),
                    },
                    {
                        "title": "Audit Logs",
                        "icon": "history",
                        "link": reverse_lazy("admin:accounting_auditlog_changelist"),
                    },
                ],
            },
            {
                "title": "Settings",
                "icon": "person",
                "separator": True,
                "collapsible": True,
                "collapsed": True,
                "items": [
                    {
                        "title": "Departments",
                        "icon": "business",
                        "link": reverse_lazy("admin:employee_department_changelist"),
                    },
                    {
                        "title": "Designations",
                        "icon": "badge",
                        "link": reverse_lazy("admin:employee_designation_changelist"),
                    },
                    {
                        "title": "Branch",
                        "icon": "location_city",
                        "link": reverse_lazy("admin:employee_branch_changelist"),
                    },
                    {
                        "title": "Shifts",
                        "icon": "schedule",
                        "link": reverse_lazy("admin:shift_shift_changelist"),
                    },
                    {
                        "title": "Roles",
                        "icon": "group",
                        "link": reverse_lazy("admin:authentication_role_changelist"),
                    },
                    {
                        "title": "Leave Groups",
                        "icon": "groups",
                        "link": reverse_lazy("admin:leave_leavegroup_changelist"),
                    },
                    {
                        "title": "Leave Policies",
                        "icon": "policy",
                        "link": reverse_lazy("admin:leave_leavepolicy_changelist"),
                    },
                    {
                        "title": "Special Leave Policies",
                        "icon": "stars",
                        "link": reverse_lazy(
                            "admin:leave_specialleavepolicy_changelist"
                        ),
                    },
                    {
                        "title": "Leave Reset Periods",
                        "icon": "autorenew",
                        "link": reverse_lazy("admin:leave_leavereset_changelist"),
                    },
                    {
                        "title": "Pre Approved IPs",
                        "icon": "security",
                        "link": reverse_lazy(
                            "admin:authentication_preapprovedip_changelist"
                        ),
                    },
                    {
                        "title": "Allowed Any IP Logins",
                        "icon": "public",
                        "link": reverse_lazy(
                            "admin:authentication_allowedanyiplogins_changelist"
                        ),
                    },
                    {
                        "title": "Cut Off",
                        "icon": "content_cut",
                        "link": reverse_lazy("admin:attendance_cutoff_changelist"),
                    },
                ],
            },
        ],
    },
}
