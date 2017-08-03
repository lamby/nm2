# coding: utf8




from django.conf import settings

class AuthMiddleware(object):
    def process_request(self, request):
        request.sso_username = None

        # Allow to override the current user via settings for tests
        remote_user = getattr(settings, "TEST_USER", None)
        if remote_user is not None:
            request.META["REMOTE_USER"] = remote_user
            request.sso_username = remote_user
            return

        # Get user from SSO certificates
        cert_user = request.META.get("SSL_CLIENT_S_DN_CN", None)
        if cert_user is not None:
            request.META["REMOTE_USER"] = cert_user
            request.sso_username = cert_user
        else:
            request.META.pop("REMOTE_USER", None)
