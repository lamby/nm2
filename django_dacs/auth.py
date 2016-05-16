# coding: utf8
from __future__ import print_function
from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals
import django.contrib.auth.backends
import django.contrib.auth.middleware
from django.conf import settings
from collections import namedtuple

# Name the various bits of information DACS gives us
DACSInfo = namedtuple('DACSInfo', ('federation', 'unknown1', "jurisdiction", "username"))

DACS_TEST_USERNAME = getattr(settings, "DACS_TEST_USERNAME", None)
CERT_TEST_USERNAME = getattr(settings, "CERT_TEST_USERNAME", None)

def _clean_dacs_username(username):
    """
    Map usernames from DACS to usernames in our auth database
    """
    if ":" in username:
        # Take the username out of DACS parts
        info = DACSInfo(*username.split(":"))
        if '@' in info.username:
            return info.username
        else:
            return info.username + "@debian.org"
    else:
        return username

class DACSRemoteUserMiddleware(django.contrib.auth.middleware.RemoteUserMiddleware):
    header = 'REMOTE_USER'
    cert_header = "SSL_CLIENT_S_DN_CN"

    def process_request(self, request):
        from django.contrib import auth
        from django.core.exceptions import ImproperlyConfigured

        # AuthenticationMiddleware is required so that request.user exists.
        if not hasattr(request, 'user'):
            raise ImproperlyConfigured(
                "The Django remote user auth middleware requires the"
                " authentication middleware to be installed.  Edit your"
                " MIDDLEWARE_CLASSES setting to insert"
                " 'django.contrib.auth.middleware.AuthenticationMiddleware'"
                " before the RemoteUserMiddleware class.")

        cert_user = request.META.get(self.cert_header, CERT_TEST_USERNAME)
        if cert_user is not None:
            request.debsso_uses_certs = True
            remote_user = cert_user
            request.sso_username = cert_user
        else:
            request.debsso_uses_certs = False

            # Allow to force a DACS user string during testing
            if DACS_TEST_USERNAME is not None:
                request.META[self.header] = DACS_TEST_USERNAME

            try:
                dacs_user = request.META[self.header]
            except KeyError:
                request.sso_username = None
                # If specified header doesn't exist then return (leaving
                # request.user set to AnonymousUser by the
                # AuthenticationMiddleware).

                # Actually, make really sure we are logged out!
                # See django bug #17869
                if request.user.is_authenticated():
                    auth.logout(request)
                return

            remote_user = dacs_user
            request.sso_username = _clean_dacs_username(dacs_user)

        # If the user is already authenticated and that user is the user we are
        # getting passed in the headers, then the correct user is already
        # persisted in the session and we don't need to continue.
        if request.user.is_authenticated():
            if request.user.username == self.clean_username(remote_user, request):
                return
            else:
                # sso username does not match the current person: we may have
                # an invalid entry in the browser session. Force a new login.
                auth.logout(request)

        # We are seeing this user for the first time in this session, attempt
        # to authenticate the user.
        user = auth.authenticate(remote_user=remote_user)
        if user:
            # User is valid.  Set request.user and persist user in the session
            # by logging the user in.
            request.user = user
            auth.login(request, user)
        else:
            # Actually, make really sure we are logged out!
            # FIXME: do we need to file a django bug for this case as well?
            if request.user.is_authenticated():
                auth.logout(request)

class DACSUserBackend(django.contrib.auth.backends.RemoteUserBackend):
    """
    RemoteUserBackend customised to create User objects from Person
    """

    def clean_username(self, username):
        """
        Map usernames from DACS to usernames in our auth database
        """
        return _clean_dacs_username(username)
