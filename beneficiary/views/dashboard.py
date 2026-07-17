from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from beneficiary.serializers import DashboardKPISerializer, DemographicsSerializer
from beneficiary.services import get_dashboard_kpis, get_demographics, get_beneficiary_analytics


class DashboardKPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        data = get_dashboard_kpis()
        serializer = DashboardKPISerializer(data)
        return Response(serializer.data)


class DemographicsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        data = get_demographics()
        serializer = DemographicsSerializer(data)
        return Response(serializer.data)


class BeneficiaryAnalyticsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        data = get_beneficiary_analytics()
        return Response(data)
