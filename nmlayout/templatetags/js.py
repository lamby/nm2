# nm.debian.org website layout
#
# Copyright (C) 2012  Enrico Zini <enrico@debian.org>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from django import template
from django.conf import settings
from django.utils.safestring import mark_safe
from backend import const

STATIC_URL = getattr(settings, "STATIC_URL", "/static/")

register = template.Library()

JS_MODULES = dict(
    core=dict(
        files=["jquery-1.10.2.min.js"]
    ),
    tables=dict(
        deps=["core"],
        files=["jquery.tablesorter.min.js"],
    ),
    nm=dict(
        deps=["core"],
        files=["nm.js"],
    ),
    ui=dict(
        deps=["core"],
        files=["jquery-ui-1.10.3.custom.min.js"],
    ),
    jqplot=dict(
        deps=["core"],
        files=[
            "jquery.jqplot.min.js",
            "plugins/jqplot.barRenderer.min.js",
            "plugins/jqplot.pieRenderer.min.js",
            "plugins/jqplot.canvasTextRenderer.min.js",
            "plugins/jqplot.canvasAxisLabelRenderer.min.js",
        ]
    ),
    sparkline=dict(
        deps=["core"],
        files=[
            "jquery.sparkline.min.js",
        ]
    ),
)

@register.simple_tag
def jsinclude(modlist):
    seen = set()
    modules = []

    def add_module(name):
        info = JS_MODULES[name]

        # Add dependencies
        for dep in info.get("deps", []):
            add_module(dep)

        # Add files
        for fn in info.get("files", []):
            if fn in seen: continue
            modules.append('<script src="%sjs/%s"></script>' % (STATIC_URL, fn))
            seen.add(fn)

    # Fill in the module list
    for name in modlist.split(","):
        add_module(name)

    return mark_safe("\n".join(modules))


