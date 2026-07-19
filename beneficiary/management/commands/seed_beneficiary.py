from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import date, timedelta
from decimal import Decimal
from authentication.models import User
from beneficiary.models import (
    Beneficiary, ServiceRH, ServiceCategory, ServiceDelivery,
    CaseFile, VulnerabilityAssessment, ImpactMeasurement, OutcomeIndicator,
    HouseholdProfiling, Referral, ComplaintsFeedback, ExitGraduation,
    GraduationCriteria, AlumniTracking, ProtectionCase, ConsentRecord,
    SafeguardingIncident, TargetingCriteria, NeedsAssessment, DistributionPlan,
    ServiceCalendarEvent, CaseWorkerAssignment, FollowUpSchedule,
    SatisfactionSurvey, GrievanceRedressal, ProgressTracking, DuplicateRecord,
    DonorReport, AttendanceTracker, HouseholdSurvey, EligibilityScreening,
    ReferralNetworkPartner, CoverageArea, BeneficiarySetting,
)


class Command(BaseCommand):
    help = "Seed beneficiary management data"

    def handle(self, *args, **options):
        user = User.objects.first()
        today = date.today()

        self.stdout.write("Clearing old beneficiary data...")
        for model in [
            BeneficiarySetting, CoverageArea, ReferralNetworkPartner,
            EligibilityScreening, HouseholdSurvey, AttendanceTracker,
            DonorReport, DuplicateRecord, ProgressTracking, GrievanceRedressal,
            SatisfactionSurvey, FollowUpSchedule, CaseWorkerAssignment,
            ServiceCalendarEvent, DistributionPlan, NeedsAssessment,
            TargetingCriteria, SafeguardingIncident, ConsentRecord,
            ProtectionCase, AlumniTracking, GraduationCriteria, ExitGraduation,
            ComplaintsFeedback, Referral, HouseholdProfiling, OutcomeIndicator,
            ImpactMeasurement, VulnerabilityAssessment, CaseFile,
            ServiceDelivery, ServiceRH, ServiceCategory, Beneficiary,
        ]:
            model.objects.all().delete()

        # Beneficiaries
        self.stdout.write("Creating beneficiaries...")
        bens = []
        ben_data = [
            {"name": "Fatima Begum", "father_name": "Abdul Karim", "mother_name": "Amina Khatun",
             "age": 35, "sex": "Female", "nid": "1990567890123", "contact": "01712345678",
             "district": "Satkhira", "upazila": "Shyamnagar",
             "village": "Munshiganj", "household_size": 5, "monthly_income": Decimal("8000"),
             "education_level": "Secondary", "main_income_sources": ["Day labor"],
             "vulnerability_categories": ["Extreme poor", "Woman-headed household"]},
            {"name": "Rahim Uddin", "father_name": "Kashem Ali", "mother_name": "Jahanara Begum",
             "age": 45, "sex": "Male", "nid": "1980234567891", "contact": "01812345679",
             "district": "Satkhira", "upazila": "Shyamnagar",
             "village": "Gabura", "household_size": 7, "monthly_income": Decimal("6000"),
             "education_level": "Primary incomplete", "main_income_sources": ["Day labor"],
             "vulnerability_categories": ["Extreme poor"]},
            {"name": "Nasreen Akter", "father_name": "Shamsul Haque", "mother_name": "Nurjahan Begum",
             "age": 28, "sex": "Female", "nid": "1995678901234", "contact": "01912345680",
             "district": "Satkhira", "upazila": "Shyamnagar",
             "village": "Padmapukur", "household_size": 4, "monthly_income": Decimal("5000"),
             "education_level": "Higher Secondary", "main_income_sources": ["Small business"],
             "vulnerability_categories": ["Extreme poor"]},
            {"name": "Kamal Hossain", "father_name": "Jalal Uddin", "mother_name": "Razia Sultana",
             "age": 52, "sex": "Male", "nid": "1972345678901", "contact": "01612345681",
             "district": "Satkhira", "upazila": "Shyamnagar",
             "village": "Burigoalini", "household_size": 6, "monthly_income": Decimal("12000"),
             "education_level": "Graduate & above", "main_income_sources": ["Small business"],
             "vulnerability_categories": ["Climate-affected household"]},
            {"name": "Rashida Khatun", "father_name": "Moinul Islam", "mother_name": "Sufia Begum",
             "age": 40, "sex": "Female", "nid": "1984567890123", "contact": "01512345682",
             "district": "Satkhira", "upazila": "Shyamnagar",
             "village": "Atulia", "household_size": 3, "monthly_income": Decimal("7500"),
             "education_level": "Primary complete", "main_income_sources": ["Day labor"],
             "vulnerability_categories": ["Woman-headed household", "Extreme poor"]},
            {"name": "Sumon Ahmed", "father_name": "Akbar Ali", "mother_name": "Hasina Begum",
             "age": 22, "sex": "Male", "nid": "2002345678901", "contact": "01712345683",
             "district": "Satkhira", "upazila": "Shyamnagar",
             "village": "Kashimari", "household_size": 4, "monthly_income": Decimal("4000"),
             "education_level": "Higher Secondary", "main_income_sources": ["Fishing"],
             "vulnerability_categories": ["Extreme poor"]},
            {"name": "Halima Siddiqua", "father_name": "Siddiqur Rahman", "mother_name": "Kulsum Begum",
             "age": 60, "sex": "Female", "nid": "1964567890123", "contact": "01812345684",
             "district": "Satkhira", "upazila": "Shyamnagar",
             "village": "Bhurulia", "household_size": 2, "monthly_income": Decimal("3000"),
             "education_level": "No schooling", "main_income_sources": ["Other"],
             "vulnerability_categories": ["Elderly living alone", "Extreme poor"]},
            {"name": "Mizanur Rahman", "father_name": "Rafiqul Islam", "mother_name": "Monowara Begum",
             "age": 38, "sex": "Male", "nid": "1986789012345", "contact": "01912345685",
             "district": "Satkhira", "upazila": "Shyamnagar",
             "village": "Ishwaripur", "household_size": 5, "monthly_income": Decimal("9000"),
             "education_level": "Secondary", "main_income_sources": ["Agriculture"],
             "vulnerability_categories": ["Climate-affected household"]},
        ]
        for d in ben_data:
            b = Beneficiary.objects.create(
                enrollment_date=today - timedelta(days=180), created_by=user, **d
            )
            bens.append(b)
        self.stdout.write(f"  Created {len(bens)} beneficiaries")

        # Service Categories
        self.stdout.write("Creating service categories...")
        cat_names = [
            ("Food Assistance", "Emergency and regular food distribution"),
            ("Healthcare", "Primary healthcare and medical support"),
            ("Education", "Formal and non-formal education programs"),
            ("Livelihood", "Income generating activities and skill development"),
            ("WASH", "Water sanitation and hygiene programs"),
            ("Shelter", "Housing and shelter improvement"),
            ("Protection", "Child protection and GBV prevention"),
            ("Psychosocial", "Mental health and psychosocial support"),
            ("Legal Aid", "Legal assistance and rights awareness"),
            ("Cash Transfer", "Conditional and unconditional cash transfers"),
        ]
        cats = []
        for name, desc in cat_names:
            c = ServiceCategory.objects.create(name=name, description=desc, status=True, created_by=user)
            cats.append(c)

        # Service Deliveries
        self.stdout.write("Creating service deliveries...")
        sd_data = [
            (bens[0], "Food Package Distribution", cats[0], "Dhanmondi Center", "Completed", "LEDARS", 2, "Package", Decimal("5000")),
            (bens[1], "Primary Health Checkup", cats[1], "Hathazari Clinic", "Completed", "Dr. Karim", 1, "Session", Decimal("2000")),
            (bens[2], "Sewing Training", cats[3], "Khalishpur Center", "In Progress", "LEDARS Training", 1, "Course", Decimal("15000")),
            (bens[3], "Agricultural Input Support", cats[3], "Shaheb Bazar", "Completed", "LEDARS", 1, "Kit", Decimal("8000")),
            (bens[4], "Tailoring Skill Development", cats[3], "Barishal Center", "In Progress", "BRAC", 1, "Course", Decimal("12000")),
            (bens[5], "Education Stipend", cats[2], "Sylhet School", "Completed", "LEDARS", 1, "Stipend", Decimal("3000")),
        ]
        for ben, stype, cat, loc, status, provider, qty, unit, cost in sd_data:
            ServiceDelivery.objects.create(
                beneficiary=ben, service_type=stype, category=cat, location=loc,
                delivery_date=today - timedelta(days=30), status=status,
                provider=provider, quantity=qty, unit=unit, cost=cost, created_by=user)

        # Service History
        self.stdout.write("Creating service history...")
        for i, ben in enumerate(bens[:5]):
            ServiceRH.objects.create(
                beneficiary=ben, name=f"Service Record {i+1}",
                description=f"Service received by {ben.name}",
                value=Decimal(str(3000 + i * 1000)), staff="Field Officer",
                status="Completed", created_by=user)

        # Case Files
        self.stdout.write("Creating case files...")
        case_data = [
            (bens[0], "Livelihood Support", "High", "In Progress"),
            (bens[1], "Medical Assistance", "Critical", "Open"),
            (bens[2], "Skills Training", "Medium", "In Progress"),
            (bens[4], "Widow Support", "High", "Open"),
            (bens[6], "Elderly Care", "Medium", "Resolved"),
        ]
        for ben, ctype, pri, status in case_data:
            CaseFile.objects.create(
                beneficiary=ben, case_type=ctype, priority=pri, status=status,
                opened_date=today - timedelta(days=60), description=f"{ctype} case for {ben.name}",
                interventions=3, next_follow_up=today + timedelta(days=14), created_by=user)

        # Vulnerability Assessments
        self.stdout.write("Creating vulnerability assessments...")
        va_data = [
            (bens[0], "Critical", 82, 15, 18, 20, 14, 8, 7),
            (bens[1], "High", 68, 12, 15, 14, 12, 8, 7),
            (bens[2], "Medium", 55, 8, 12, 10, 10, 8, 7),
            (bens[4], "High", 72, 14, 16, 16, 10, 8, 8),
            (bens[6], "Critical", 85, 18, 18, 18, 16, 8, 7),
        ]
        for ben, risk, score, food, shelter, health, prot, edu, live in va_data:
            VulnerabilityAssessment.objects.create(
                beneficiary=ben, assessment_date=today - timedelta(days=90),
                assessor="Ahmed Hasan", overall_score=score, risk_level=risk,
                food=food, shelter=shelter, health=health, protection=prot,
                education=edu, livelihood=live,
                recommendations="Immediate intervention required" if risk in ["Critical", "High"] else "Regular monitoring",
                created_by=user)

        # Impact Measurements
        self.stdout.write("Creating impact measurements...")
        months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        for i, m in enumerate(months):
            ImpactMeasurement.objects.create(
                month=m, year=2026,
                education=45 + i * 3, health=50 + i * 2,
                livelihood=30 + i * 4, wash=40 + i * 2, created_by=user)

        # Outcome Indicators
        self.stdout.write("Creating outcome indicators...")
        ind_data = [
            ("School Enrollment Rate", 65, 78, 90, "%"),
            ("Household Income Increase", 5000, 7500, 12000, "BDT"),
            ("Vaccination Coverage", 60, 82, 95, "%"),
            ("Beneficiaries with Safe Water", 45, 68, 85, "%"),
            ("Women in Income Activities", 20, 45, 60, "%"),
            ("Child Malnutrition Rate", 35, 22, 10, "%"),
            ("WASH Facility Access", 40, 65, 80, "%"),
            ("Literacy Rate", 55, 72, 85, "%"),
        ]
        for ind, base, curr, tgt, unit in ind_data:
            OutcomeIndicator.objects.create(
                indicator=ind, baseline=Decimal(str(base)),
                current=Decimal(str(curr)), target=Decimal(str(tgt)),
                unit=unit, created_by=user)

        # Household Profiling
        self.stdout.write("Creating household profiles...")
        hh_data = [
            ("Fatima Household", 5, "Dhanmondi Dhaka", "A", "Permanent", Decimal("8000"), 2),
            ("Rahim Household", 7, "Hathazari Chattogram", "B", "Semi-permanent", Decimal("6000"), 3),
            ("Nasreen Household", 4, "Khalishpur Khulna", "A", "Temporary", Decimal("5000"), 1),
            ("Kamal Household", 6, "Shaheb Bazar Rajshahi", "C", "Permanent", Decimal("12000"), 1),
            ("Halima Household", 2, "Shapla Nagar Rangpur", "D", "Semi-permanent", Decimal("3000"), 1),
        ]
        for head, members, loc, block, shelter, income, vuln in hh_data:
            HouseholdProfiling.objects.create(
                head_of_household=head, members=members, location=loc,
                block=block, shelter=shelter, income=income,
                vulnerable_members=vuln, created_by=user)

        # Referrals
        self.stdout.write("Creating referrals...")
        ref_data = [
            (bens[0], "Dhaka Medical College", "Healthcare", "Completed", "High"),
            (bens[1], "CDD Disability Support", "Disability Services", "In Progress", "Critical"),
            (bens[2], "BRAC Skills Center", "Skills Training", "Pending", "Medium"),
            (bens[4], "Womens Legal Aid", "Legal Support", "Accepted", "High"),
            (bens[6], "Elderly Care Foundation", "Geriatric Care", "Pending", "Medium"),
        ]
        for ben, referred_to, service, status, pri in ref_data:
            Referral.objects.create(
                beneficiary=ben, referred_to=referred_to, service=service,
                date=today - timedelta(days=45), status=status, priority=pri, created_by=user)

        # Complaints and Feedback
        self.stdout.write("Creating complaints and feedback...")
        cf_data = [
            (bens[0], "Complaint", "Service Quality", "Delayed food distribution", "Under Review", "High"),
            (bens[1], "Feedback", "Staff Behavior", "Very helpful field officer", "Closed", "Low"),
            (bens[3], "Suggestion", "Program", "More agricultural training needed", "Open", "Medium"),
            (bens[5], "Complaint", "Access", "Center too far from home", "Open", "Medium"),
        ]
        for ben, typ, cat, msg, status, pri in cf_data:
            ComplaintsFeedback.objects.create(
                beneficiary=ben, type=typ, category=cat, subject=f"{typ} - {cat}",
                message=msg, status=status, priority=pri, satisfaction=4, created_by=user)

        # Exit and Graduation
        self.stdout.write("Creating exit graduation records...")
        eg_data = [
            (bens[3], "Graduated", "Employed", 5, today - timedelta(days=730), today - timedelta(days=30)),
            (bens[0], "In Progress", "Pending", 3, today - timedelta(days=365), None),
            (bens[2], "Ready for Exit", "Self-sufficient", 4, today - timedelta(days=540), None),
        ]
        for ben, status, outcome, sat, entry, exit_d in eg_data:
            ExitGraduation.objects.create(
                beneficiary=ben, entry_date=entry, exit_date=exit_d,
                duration="24 months" if exit_d else "Ongoing",
                status=status, outcome=outcome, satisfaction=sat, created_by=user)

        # Graduation Criteria
        self.stdout.write("Creating graduation criteria...")
        gc_data = [
            ("Stable Income Above Poverty Line", 25, "Monthly income >= 10000 BDT", "Income verification"),
            ("Children in School", 20, "All school-age children enrolled", "Enrollment records"),
            ("Food Security Score", 15, "Food consumption score >= 42", "Food security assessment"),
            ("Savings Account Active", 10, "Regular savings for 6+ months", "Bank statement"),
            ("Health Insurance Enrolled", 15, "Family health coverage active", "Insurance card"),
            ("Skills Training Completed", 15, "At least one vocational training", "Certificate"),
        ]
        for criteria, weight, measurement, indicator in gc_data:
            GraduationCriteria.objects.create(
                criteria=criteria, weight=weight, indicator=indicator,
                measurement=measurement, status="Active", created_by=user)

        # Alumni Tracking
        self.stdout.write("Creating alumni tracking...")
        al_data = [
            (bens[3], today - timedelta(days=30), "Employed", "+40%", today - timedelta(days=7), "Monthly", False),
            (bens[0], today - timedelta(days=180), "Self-employed", "+25%", today - timedelta(days=30), "Quarterly", False),
            (bens[2], today - timedelta(days=90), "In Training", "+10%", today - timedelta(days=14), "Monthly", True),
            (bens[7], today - timedelta(days=365), "Employed", "+55%", today - timedelta(days=60), "Quarterly", False),
        ]
        for ben, grad_date, status, income_chg, last_contact, interval, needs in al_data:
            AlumniTracking.objects.create(
                beneficiary=ben, graduation_date=grad_date, current_status=status,
                income_change=income_chg, last_contact=last_contact,
                follow_up_interval=interval, needs_support=needs, created_by=user)

        # Protection Cases
        self.stdout.write("Creating protection cases...")
        pc_data = [
            (bens[0], "GBV", "High", "Under Investigation", False, "Pending", 3),
            (bens[2], "Child Protection", "Medium", "Open", True, "None", 1),
            (bens[6], "Other", "Low", "Resolved", False, "Completed", 5),
        ]
        for ben, typ, risk, status, safe, legal, sessions in pc_data:
            ProtectionCase.objects.create(
                beneficiary=ben, type=typ, risk_level=risk, status=status,
                opened_date=today - timedelta(days=120),
                safe_space_referred=safe, legal_action=legal,
                psychosocial_sessions=sessions, created_by=user)

        # Consent Records
        self.stdout.write("Creating consent records...")
        consent_types = ["Data Collection", "Photo/Video", "Data Sharing", "Program Participation"]
        sharing_types = ["Full", "Partial", "Anonymized Only", "None"]
        for i, ben in enumerate(bens[:4]):
            ConsentRecord.objects.create(
                beneficiary=ben, consent_type=consent_types[i],
                granted=True, date=today - timedelta(days=180),
                expiry=today + timedelta(days=365),
                collected_by="Registration Officer",
                photo_consent=i < 2, data_sharing=sharing_types[i], created_by=user)

        # Safeguarding Incidents
        self.stdout.write("Creating safeguarding incidents...")
        si_data = [
            ("Verbal", "Medium", "Dhaka Office", "Anonymous", "Resolved", "Warning issued", "HR Manager"),
            ("Physical", "High", "Field Site B", "Teacher", "Under Investigation", None, "Protection Officer"),
        ]
        for kind, severity, loc, reporter, status, action, lead in si_data:
            SafeguardingIncident.objects.create(
                date=today - timedelta(days=60), type=kind, severity=severity,
                location=loc, reporter=reporter, status=status,
                action_taken=action, investigation_lead=lead,
                resolution_date=today - timedelta(days=30) if status == "Resolved" else None,
                created_by=user)

        # Targeting Criteria
        self.stdout.write("Creating targeting criteria...")
        tc_data = [
            ("Monthly income below 8000 BDT", "Economic", 25, "Income verification survey"),
            ("Female-headed household", "Demographic", 20, "Registration data"),
            ("Household size >= 5 members", "Demographic", 15, "Family census"),
            ("Located in climate-vulnerable area", "Geographic", 15, "GIS mapping"),
            ("Person with disability in family", "Vulnerability", 15, "Medical assessment"),
            ("No adult male income earner", "Social", 10, "Household interview"),
            ("Children not enrolled in school", "Social", 10, "Education records"),
        ]
        for crit, typ, weight, measurement in tc_data:
            TargetingCriteria.objects.create(
                criterion=crit, type=typ, weight=weight,
                measurement=measurement, status="Active", created_by=user)

        # Needs Assessments
        self.stdout.write("Creating needs assessments...")
        na_data = [
            ("Kurigram Flood Zone", today - timedelta(days=90), "Field Team Alpha", 2500, ["Food", "Shelter", "WASH"], Decimal("78.5"), "Completed"),
            ("Sylhet Haor Region", today - timedelta(days=60), "Field Team Beta", 1800, ["Health", "Education", "Livelihood"], Decimal("65.2"), "In Progress"),
            ("Coxs Bazar South", today - timedelta(days=30), "Field Team Gamma", 5000, ["Protection", "Food", "Health"], Decimal("88.0"), "Draft"),
        ]
        for loc, dt, assessor, pop, needs, gap, status in na_data:
            NeedsAssessment.objects.create(
                location=loc, date=dt, assessor=assessor, population=pop,
                priority_needs=needs, gap_score=gap, status=status,
                recommendations=f"Urgent intervention needed in {loc}", created_by=user)

        # Distribution Plans
        self.stdout.write("Creating distribution plans...")
        dp_data = [
            ("Winter Blanket Distribution", "Rangpur Division", today + timedelta(days=15), 500, "Blankets Winter Clothing", "Planning"),
            ("Flood Relief Package", "Sylhet Division", today + timedelta(days=5), 1200, "Food Water Medicine", "Approved"),
            ("Eid Food Distribution", "Dhaka Division", today + timedelta(days=30), 800, "Food Package Cash", "In Progress"),
        ]
        for name, loc, dt, target, items, status in dp_data:
            DistributionPlan.objects.create(
                name=name, location=loc, date=dt,
                beneficiaries_targeted=target, items=items,
                status=status, coordinator="Field Coordinator", created_by=user)

        # Service Calendar Events
        self.stdout.write("Creating service calendar events...")
        sce_data = [
            ("Health Camp - Dhaka", today + timedelta(days=5), "Health Camp", "Dhaka Division", 200, "Scheduled"),
            ("Skills Training Batch 3", today + timedelta(days=10), "Training", "Khulna Center", 30, "Scheduled"),
            ("Food Distribution Round 4", today + timedelta(days=3), "Distribution", "Rangpur Division", 500, "In Progress"),
            ("Community Awareness Session", today + timedelta(days=7), "Awareness", "Sylhet Division", 100, "Scheduled"),
            ("Vaccination Drive", today + timedelta(days=14), "Health Camp", "Chattogram", 350, "Scheduled"),
            ("Graduation Ceremony", today + timedelta(days=60), "Ceremony", "Dhaka HQ", 50, "Scheduled"),
        ]
        for title, dt, typ, loc, bens_count, status in sce_data:
            ServiceCalendarEvent.objects.create(
                title=title, date=dt, type=typ, location=loc,
                beneficiaries=bens_count, status=status, created_by=user)

        # Case Worker Assignments
        self.stdout.write("Creating case worker assignments...")
        cw_data = [
            ("Field Supervisor", "Dhaka Division", 15, 25, "Livelihood", "01711111111", "cw1@ledars.org"),
            ("Case Manager", "Khulna Division", 22, 30, "Protection", "01722222222", "cw2@ledars.org"),
            ("Protection Officer", "Chattogram Division", 18, 20, "GBV/Child Protection", "01733333333", "cw3@ledars.org"),
            ("Health Worker", "Sylhet Division", 10, 20, "Health/Nutrition", "01744444444", "cw4@ledars.org"),
            ("Education Coordinator", "Rangpur Division", 12, 25, "Education", "01755555555", "cw5@ledars.org"),
        ]
        for desig, area, active, maxc, spec, phone, email in cw_data:
            CaseWorkerAssignment.objects.create(
                designation=desig, area=area, active_cases=active,
                max_capacity=maxc, specialization=spec,
                phone=phone, email=email, created_by=user)

        # Follow-Up Schedules
        self.stdout.write("Creating follow-up schedules...")
        fu_data = [
            (bens[0], today + timedelta(days=3), "Home Visit", "Check livelihood progress", "Scheduled", "High"),
            (bens[1], today + timedelta(days=7), "Phone Call", "Medical follow-up", "Scheduled", "Critical"),
            (bens[2], today + timedelta(days=5), "Office Visit", "Training enrollment", "Scheduled", "Medium"),
            (bens[4], today - timedelta(days=2), "Home Visit", "Post-referral check", "Completed", "High"),
            (bens[6], today + timedelta(days=14), "Group Session", "Elderly support group", "Scheduled", "Medium"),
        ]
        for ben, dt, typ, purpose, status, pri in fu_data:
            FollowUpSchedule.objects.create(
                beneficiary=ben, follow_up_date=dt, type=typ,
                purpose=purpose, status=status, priority=pri, created_by=user)

        # Satisfaction Surveys
        self.stdout.write("Creating satisfaction surveys...")
        ss_data = [
            ("Q1 2026 Beneficiary Satisfaction", "Q1 2026", 250, Decimal("4.2"), Decimal("85.0"), "Completed"),
            ("Mid-Year Service Quality", "H1 2026", 180, Decimal("3.8"), Decimal("72.0"), "Active"),
            ("Post-Distribution Feedback", "March 2026", 120, Decimal("4.5"), Decimal("92.0"), "Completed"),
        ]
        for name, period, respondents, avg, rate, status in ss_data:
            SatisfactionSurvey.objects.create(
                survey_name=name, period=period, respondents=respondents,
                avg_satisfaction=avg, response_rate=rate, status=status,
                key_findings="Good overall satisfaction", created_by=user)

        # Grievance Redressal
        self.stdout.write("Creating grievance records...")
        gr_data = [
            (today - timedelta(days=45), "Fatima Begum", "Service Delay", "Food distribution delayed by 2 weeks", "Field Supervisor", "Resolved", "Distribution rescheduled", today - timedelta(days=30), 15),
            (today - timedelta(days=20), "Rahim Uddin", "Staff Behavior", "Rude behavior by distribution team", "HR Manager", "Under Investigation", None, None, None),
            (today - timedelta(days=10), "Anonymous", "Quality Issue", "Poor quality food items received", "Program Manager", "Open", None, None, None),
        ]
        for dt, complainant, typ, desc, assigned, status, resolution, res_date, days in gr_data:
            GrievanceRedressal.objects.create(
                date=dt, complainant=complainant, type=typ, description=desc,
                assigned_to=assigned, status=status, resolution=resolution,
                resolution_date=res_date, days_to_resolve=days, created_by=user)

        # Progress Tracking
        self.stdout.write("Creating progress tracking...")
        pt_data = [
            (bens[0], today - timedelta(days=365), 8, 5, 62, "Phase 2", "Complete savings goal", today + timedelta(days=180)),
            (bens[2], today - timedelta(days=540), 10, 7, 70, "Phase 3", "Final skills assessment", today + timedelta(days=90)),
            (bens[5], today - timedelta(days=180), 6, 2, 33, "Phase 1", "Complete basic training", today + timedelta(days=365)),
            (bens[7], today - timedelta(days=730), 8, 8, 100, "Completed", "Graduated", today - timedelta(days=30)),
        ]
        for ben, enrolled, total, completed, progress, phase, milestone, target in pt_data:
            ProgressTracking.objects.create(
                beneficiary=ben, enrolled_date=enrolled,
                milestones_total=total, milestones_completed=completed,
                progress=progress, current_phase=phase,
                next_milestone=milestone, target_graduation=target, created_by=user)

        # Duplicate Records
        self.stdout.write("Creating duplicate records...")
        dup_data = [
            ("BEN-2026-0001", "BEN-2026-0009", "Fatima Begum", "Fatema Begum", True, False, 92, True, "Pending Review"),
            ("BEN-2026-0003", "BEN-2026-0010", "Nasreen Akter", "Nasrin Akhter", False, True, 85, True, "Pending Review"),
            ("BEN-2026-0004", "BEN-2026-0011", "Kamal Hossain", "Kamal Hossain", True, True, 98, False, "Merged"),
        ]
        for ra, rb, na, nb, nid_m, con_m, score, auto, status in dup_data:
            DuplicateRecord.objects.create(
                record_a=ra, record_b=rb, name_a=na, name_b=nb,
                nid_match=nid_m, contact_match=con_m, similarity_score=score,
                auto_detected=auto, status=status,
                detected_date=today - timedelta(days=5), created_by=user)

        # Donor Reports
        self.stdout.write("Creating donor reports...")
        dr_data = [
            ("USAID", "Q4 2025", 1500, 2000, Decimal("75.0"), Decimal("450000"), Decimal("600000"), "Submitted", today + timedelta(days=15)),
            ("DFID/FCDO", "Q1 2026", 800, 1200, Decimal("66.7"), Decimal("250000"), Decimal("400000"), "Draft", today + timedelta(days=30)),
            ("EU Delegation", "Annual 2025", 3200, 3000, Decimal("106.7"), Decimal("1200000"), Decimal("1500000"), "Approved", today - timedelta(days=15)),
            ("UNICEF", "H1 2026", 950, 1500, Decimal("63.3"), Decimal("380000"), Decimal("550000"), "Overdue", today - timedelta(days=5)),
        ]
        for donor, period, reached, target, ach, utilized, total, status, due in dr_data:
            DonorReport.objects.create(
                donor=donor, period=period, beneficiaries_reached=reached,
                target=target, achievement=ach, budget_utilized=utilized,
                budget_total=total, status=status, due_date=due, created_by=user)

        # Attendance Tracker
        self.stdout.write("Creating attendance tracker...")
        at_data = [
            ("Sewing Training Session", "Khulna Center", today - timedelta(days=7), 25, 22, Decimal("88.0"), "Trainer A"),
            ("Health Awareness Workshop", "Dhaka Office", today - timedelta(days=3), 40, 35, Decimal("87.5"), "Dr. Rahman"),
            ("Computer Literacy Class", "Sylhet Center", today - timedelta(days=1), 15, 14, Decimal("93.3"), "Trainer B"),
            ("Agricultural Training", "Rajshahi Field", today, 30, 28, Decimal("93.3"), "Agri Expert"),
        ]
        for activity, loc, dt, reg, attended, rate, facilitator in at_data:
            AttendanceTracker.objects.create(
                activity=activity, location=loc, date=dt,
                registered=reg, attended=attended, attendance_rate=rate,
                facilitator=facilitator, created_by=user)

        # Household Surveys
        self.stdout.write("Creating household surveys...")
        hs_data = [
            ("Baseline Household Assessment 2026", 500, 420, Decimal("84.0"), today - timedelta(days=90), today - timedelta(days=30), "Completed", Decimal("92.5")),
            ("Mid-term Evaluation Survey", 300, 180, Decimal("60.0"), today - timedelta(days=30), today + timedelta(days=30), "Active", Decimal("88.0")),
            ("Food Security Monitoring", 200, 50, Decimal("25.0"), today - timedelta(days=7), today + timedelta(days=60), "Active", Decimal("90.0")),
        ]
        for name, target, completed, rate, start, end, status, quality in hs_data:
            HouseholdSurvey.objects.create(
                survey_name=name, target_households=target, completed=completed,
                completion_rate=rate, start_date=start, end_date=end,
                status=status, data_quality_score=quality, created_by=user)

        # Eligibility Screening
        self.stdout.write("Creating eligibility screening...")
        es_data = [
            ("Aminul Islam", "1990111222333", today - timedelta(days=14), 5, 7, Decimal("71.4"), True, "Screener A", "Approved"),
            ("Sharmin Akter", "1988222333444", today - timedelta(days=10), 6, 7, Decimal("85.7"), True, "Screener B", "Approved"),
            ("Jabbar Ali", "1975333444555", today - timedelta(days=7), 3, 7, Decimal("42.9"), False, "Screener A", "Rejected"),
            ("Farida Begum", "1992444555666", today - timedelta(days=3), 4, 7, Decimal("57.1"), False, "Screener C", "Under Review"),
        ]
        for applicant, nid, dt, met, total, score, eligible, screener, status in es_data:
            EligibilityScreening.objects.create(
                applicant=applicant, nid=nid, screening_date=dt,
                criteria_met=met, criteria_total=total, score=score,
                eligible=eligible, screener=screener, status=status, created_by=user)

        # Referral Network Partners
        self.stdout.write("Creating referral network partners...")
        rn_data = [
            ("Dhaka Medical College Hospital", "Government Hospital", ["Healthcare", "Emergency"], "Dhaka Division", "Dr. Ahmed - 01711111111", "Active", 45),
            ("BRAC Skills Development", "NGO", ["Training", "Livelihood"], "Nationwide", "info@brac.net", "Active", 32),
            ("Bangladesh Legal Aid Trust", "Legal Organization", ["Legal Aid", "Rights"], "Dhaka Chattogram", "legal@blast.org.bd", "Active", 18),
            ("UNICEF Bangladesh", "UN Agency", ["Child Protection", "Education", "WASH"], "Nationwide", "dhaka@unicef.org", "Active", 56),
            ("Acid Survivors Foundation", "Specialized NGO", ["Medical", "Rehabilitation", "Legal"], "Dhaka", "contact@asf.org.bd", "Active", 8),
        ]
        for org, typ, services, coverage, contact, status, referrals in rn_data:
            ReferralNetworkPartner.objects.create(
                organization=org, type=typ, services=services,
                coverage=coverage, contact=contact, status=status,
                referrals_made=referrals, created_by=user)

        # Coverage Areas
        self.stdout.write("Creating coverage areas...")
        ca_data = [
            ("Dhaka", ["Dhaka", "Gazipur", "Narayanganj", "Manikganj"], 2500, 8, 3),
            ("Chattogram", ["Chattogram", "Coxs Bazar", "Comilla"], 1800, 5, 2),
            ("Khulna", ["Khulna", "Jessore", "Satkhira"], 1200, 4, 2),
            ("Rajshahi", ["Rajshahi", "Natore", "Chapainawabganj"], 900, 3, 1),
            ("Barishal", ["Barishal", "Patuakhali"], 600, 2, 1),
            ("Sylhet", ["Sylhet", "Moulvibazar", "Habiganj"], 800, 3, 1),
            ("Rangpur", ["Rangpur", "Kurigram", "Dinajpur"], 1100, 4, 2),
            ("Mymensingh", ["Mymensingh", "Netrokona"], 700, 2, 1),
        ]
        for div, districts, bens_count, projects, offices in ca_data:
            CoverageArea.objects.create(
                division=div, districts=districts, beneficiaries=bens_count,
                projects=projects, field_offices=offices, created_by=user)

        # Beneficiary Settings
        self.stdout.write("Creating beneficiary settings...")
        settings_data = [
            ("Auto Code Generation", "Enabled", "Registration"),
            ("Code Format", "BEN-YYYY-####", "Registration"),
            ("Duplicate Detection", "Enabled", "Data Quality"),
            ("Similarity Threshold", "80%", "Data Quality"),
            ("Consent Required", "Yes", "Privacy"),
            ("Data Retention Period", "5 years", "Privacy"),
            ("Photo Required", "Optional", "Registration"),
            ("Assessment Frequency", "Quarterly", "Assessment"),
            ("Follow-up Default Interval", "30 days", "Case Management"),
            ("Max Caseload Per Worker", "30", "Case Management"),
        ]
        for setting, value, category in settings_data:
            BeneficiarySetting.objects.create(
                setting=setting, value=value, category=category, created_by=user)

        self.stdout.write(self.style.SUCCESS("\nBeneficiary data seeded successfully!"))
        self.stdout.write(f"  Beneficiaries: {Beneficiary.objects.count()}")
        self.stdout.write(f"  Service Categories: {ServiceCategory.objects.count()}")
        self.stdout.write(f"  Service Deliveries: {ServiceDelivery.objects.count()}")
        self.stdout.write(f"  Case Files: {CaseFile.objects.count()}")
        self.stdout.write(f"  Assessments: {VulnerabilityAssessment.objects.count()}")
        self.stdout.write(f"  Total models seeded: 34")
