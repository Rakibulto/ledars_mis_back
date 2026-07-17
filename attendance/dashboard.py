from datetime import date
from django.http import JsonResponse
from django.views import View
from employee.utils import HRDashboardAnalytics


##--------------- New Dashboard ------------------ 

# All HR dashboard analytics in one endpoint
class HRDashboardView(View):
    """Endpoint for all HR dashboard analytics"""
    def get(self, request):
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')
        
        # Convert string dates to date objects if provided
        if start_date:
            start_date = date.fromisoformat(start_date)
        if end_date:
            end_date = date.fromisoformat(end_date)
        
        data = HRDashboardAnalytics.get_all_counts(start_date, end_date)
        return JsonResponse(data)

## Individual employee data
class IndividualEmployeeView(View):
    """Endpoint for individual employee dashboard data using utility function"""
    def get(self, request, employee_id):
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')
        
        # Convert string dates to date objects if provided
        if start_date:
            start_date = date.fromisoformat(start_date)
        if end_date:
            end_date = date.fromisoformat(end_date)
        
        # Use the utility function to get individual employee data
        data = HRDashboardAnalytics.get_individual_employee_data(employee_id, start_date, end_date)
        
        # Check if there was an error
        if 'error' in data:
            return JsonResponse(data, status=404)
        
        return JsonResponse(data)

## Supervisor dashboard data
class SupervisorDashboardView(View):
    """Endpoint for supervisor dashboard data - shows aggregate data for all subordinates"""
    def get(self, request, supervisor_id):
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')
        
        # Convert string dates to date objects if provided
        if start_date:
            start_date = date.fromisoformat(start_date)
        if end_date:
            end_date = date.fromisoformat(end_date)
        
        # Use the utility function to get supervisor dashboard data
        data = HRDashboardAnalytics.get_supervisor_dashboard_data(supervisor_id, start_date, end_date)
        
        # Check if there was an error
        if 'error' in data:
            return JsonResponse(data, status=404)
        
        return JsonResponse(data)