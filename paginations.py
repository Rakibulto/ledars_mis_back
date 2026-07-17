# from rest_framework.pagination import PageNumberPagination
# from rest_framework.response import Response


# class Pagination(PageNumberPagination):
#     page_size = 10
#     page_size_query_param = 'page_size'
#     max_page_size = 500

#     # Override paginate_queryset to control pagination using ?pagination=true
#     def paginate_queryset(self, queryset, request, view=None):
#         paginate = request.query_params.get('pagination', 'false').lower()

#         # If pagination=true -> normal pagination
#         if paginate == 'true':
#             return super().paginate_queryset(queryset, request, view)

#         # If no pagination -> return None (DRF will skip pagination)
#         return None  

#     # Custom response if paginated
#     def get_paginated_response(self, data):
#         return Response({
#             "total": self.page.paginator.count,      # total considering filters (after filtering)
#             "count": len(data),                      # items in this page
#             "page_size": self.page_size,
#             "next": self.get_next_link(),
#             "previous": self.get_previous_link(),
#             "results": data
#         })


# your_app/pagination.py
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


class Pagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 1000

    def paginate_queryset(self, queryset, request, view=None):
        """
        Only paginate if pagination=true is explicitly requested.
        """
        # Check if pagination is explicitly requested
        pagination_enabled = (
            request.query_params.get("pagination", "").lower() == "true"
        )

        if not pagination_enabled:
            # Return None to indicate no pagination should be applied
            return None

        # If pagination is requested, use the standard pagination
        return super().paginate_queryset(queryset, request, view)

    def get_paginated_response(self, data):
        return Response(
            {
                "count": self.page.paginator.count,
                "total_pages": self.page.paginator.num_pages,
                "current_page": self.page.number,
                "page_size": self.get_page_size(self.request),
                "next": self.get_next_link(),
                "previous": self.get_previous_link(),
                "results": data,
            }
        )
