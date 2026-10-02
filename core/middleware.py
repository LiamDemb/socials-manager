import ipaddress

from django.http import HttpResponseForbidden


class LoopbackOnlyMiddleware:
    """Defence in depth: this no-login app must never answer non-loopback clients."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        addr = request.META.get("REMOTE_ADDR", "")
        try:
            if not ipaddress.ip_address(addr).is_loopback:
                return HttpResponseForbidden("Loopback access only.")
        except ValueError:
            return HttpResponseForbidden("Loopback access only.")
        return self.get_response(request)


class SecurityHeadersMiddleware:
    CSP = (
        "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
        "connect-src 'self'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'; object-src 'none'"
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response.setdefault("Content-Security-Policy", self.CSP)
        response.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        response.setdefault("Cache-Control", "no-store")
        return response
