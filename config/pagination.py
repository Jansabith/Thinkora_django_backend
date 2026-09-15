from rest_framework.pagination import PageNumberPagination


class StandardPagination(PageNumberPagination):
    """
    Long lists come in pages: ?page=2 gives items 21-40.
    The answer looks like {"count": 57, "next": "...", "previous": "...", "results": [...]}.
    """

    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100
