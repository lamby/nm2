"""
WSGI config for nm2 project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/1.7/howto/deployment/wsgi/
"""

import os
import sys

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "nm2.settings")
os.umask(005)

project_root = '/srv/nm.debian.org/nm2'
paths = [project_root]
for path in paths:
    if path not in sys.path:
        sys.path.append(path)

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
