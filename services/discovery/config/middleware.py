"""Origin-restricted CORS and request metadata logging, without credentials."""
import logging
from time import perf_counter
from django.conf import settings
from django.http import HttpResponse

logger = logging.getLogger("requests")


class RequestMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        started = perf_counter()
        response = HttpResponse(status=204) if request.method == "OPTIONS" else self.get_response(request)
        if request.headers.get("Origin") == settings.UI_ORIGIN:
            response["Access-Control-Allow-Origin"] = settings.UI_ORIGIN
            response["Access-Control-Allow-Headers"] = "Authorization, Content-Type"
            response["Access-Control-Allow-Methods"] = "GET, POST, PUT, OPTIONS"
            response["Vary"] = "Origin"
        logger.info("%s %s %s %.1fms", request.method, request.path,
                    response.status_code, (perf_counter() - started) * 1000)
        return response
