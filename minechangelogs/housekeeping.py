# nm.debian.org minechangelogs implementation
#
# Copyright (C) 2012--2015  Enrico Zini <enrico@debian.org>
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





import django_housekeeping as hk
from minechangelogs import models as mmodels
import logging

log = logging.getLogger(__name__)

class IndexChangelogs(hk.Task):
    """
    Update minechangelogs index
    """
    def run_main(self, stage):
        indexer = mmodels.Indexer()
        with mmodels.parse_projectb() as changes:
            indexer.index(changes)
        indexer.flush()
