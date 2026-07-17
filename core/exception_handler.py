import logging
from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status
from django.db import IntegrityError

logger = logging.getLogger(__name__)


def custom_exception_handler(exc, context):
    """
    Global DRF exception handler that returns structured JSON error responses
    and catches database integrity errors.
    """
    response = exception_handler(exc, context)

    if response is not None:
        # Standardise DRF errors into { detail, status_code }
        error_data = {
            "status_code": response.status_code,
            "detail": response.data,
        }
        response.data = error_data
        return response

    # Handle database integrity errors (constraint violations, duplicates, etc.)
    if isinstance(exc, IntegrityError):
        logger.error("Database integrity error: %s", exc, exc_info=True)
        return Response(
            {
                "status_code": 400,
                "detail": "A database constraint was violated. Please check your data and try again.",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Catch any other unhandled exception so 500s return JSON, not HTML
    logger.error("Unhandled exception: %s", exc, exc_info=True)
    return Response(
        {
            "status_code": 500,
            "detail": "An unexpected error occurred. Please try again later.",
        },
        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )
