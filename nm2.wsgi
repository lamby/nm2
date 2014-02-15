#!/usr/bin/python

import os
import sys

project_root = '/srv/nm.debian.org/nm2'

os.umask(005)

paths = [project_root]
for path in paths:
    if path not in sys.path:
        sys.path.append(path)

os.environ['DJANGO_SETTINGS_MODULE'] = 'settings'

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
