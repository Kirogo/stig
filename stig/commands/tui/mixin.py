# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details
# http://www.gnu.org/licenses/gpl-3.0.txt

"""Mixin classes for TUI commands"""

from ...logging import make_logger
log = make_logger(__name__)


from .. import ExpectedResource
from .. import utils


class polling_frenzy():
    aioloop = ExpectedResource

    def polling_frenzy(self, duration=2, short_interval=0.5):
        """Reduce polling interval for a few seconds

        This affects TorrentListWidgets and FileListWidgets.
        """
        srvapi = self.srvapi
        if srvapi.interval > 1:
            import asyncio
            async def coro():
                log.debug('Setting poll interval to %s for %s seconds', short_interval, duration)
                orig_interval = srvapi.interval
                srvapi.interval = short_interval
                await asyncio.sleep(duration, loop=self.aioloop)
                srvapi.interval = orig_interval
                log.debug('Interval restored to %s', srvapi.interval)
            self.aioloop.create_task(coro())


class make_request():
    async def make_request(self, request_coro, polling_frenzy=False, quiet=False):
        """Awaits request coroutine and logs messages; returns response"""
        response = await request_coro
        utils.log_msgs(log, response.msgs, quiet)
        if response.success and polling_frenzy and hasattr(self, 'polling_frenzy'):
            self.polling_frenzy()
        return response


class select_torrents():
    tui = ExpectedResource

    def select_torrents(self, FILTER, allow_no_filter=True, discover_torrent=True):
        """Get TorrentFilter instance, focused torrent ID in a tuple or None

        If `FILTER` evaluates to True, it is passed to TorrentFilter and the
        resulting object is returned.

        If `FILTER` evaluates to False, a torrent ID is returned in a tuple if
        possible and `discover_torrent` evaluates to True. Otherwise, None is
        returned if `allow_no_filter` evaluates to True, else a ValueError is
        raised.

        Torrents are discovered by getting the:
            - `focused_torrent` attribute in this command's object (e.g. set
              by the 'tab' command),
            - `focused_torrent` attribute of the focused tab's widget
              (e.g. TorrentListWidget),
            - `focused_torrent_id` attribute of the focused tab's widget
              (e.g. FileListWidget).
        """
        if FILTER:
            from ...client import TorrentFilter
            return TorrentFilter(FILTER)
        else:
            if discover_torrent:
                tid = self._find_torrent_id()
                if tid is not None:
                    return (tid,)
            if allow_no_filter:
                return None
            else:
                raise ValueError('No torrent specified')

    def _find_torrent_id(self):
        focused_widget = self.tui.tabs.focus

        # Get Torrent object from attribute set by 'tab' command (this
        # happens if for example when you run 'tab filelist' while a
        # torrent is focused)
        if hasattr(self, 'focused_torrent'):
            return self.focused_torrent['id']

        # Get Torrent object from widget in focused tab
        elif hasattr(focused_widget, 'focused_torrent') and \
             focused_widget.focused_torrent is not None:
            return focused_widget.focused_torrent.tid

        # Get torrent ID from widget in focused tab
        elif hasattr(focused_widget, 'focused_torrent_id') and \
             focused_widget.focused_torrent_id is not None:
            return focused_widget.focused_torrent_id


class select_files():
    tui = ExpectedResource

    def select_files(self, FILTER, allow_no_filter=True, discover_file=True):
        """Get TorrentFileFilter instance, focused file ID or None

        If `FILTER` evaluates to True, it is passed to TorrentFileFilter and
        the resulting object is returned.

        If `FILTER` evaluates to False and `discover_file` evaluates to True,
        the file ID (or IDs) are returned in a tuple if possible. Otherwise,
        None is returned if `allow_no_filter` evaluates to True, else a
        ValueError is raised.

        File are discovered by getting the `focused_file_id` of the focused
        tab's widget.
        """
        if FILTER:
            from ...client import TorrentFileFilter
            return TorrentFileFilter(FILTER)
        else:
            if discover_file:
                fids = self._find_file_ids()
                if fids is not None:
                    return fids
            if allow_no_filter:
                return None
            else:
                raise ValueError('No torrent file specified')

    def _find_file_ids(self):
        focused_widget = self.tui.tabs.focus

        # Get torrent ID from widget in focused tab
        if hasattr(focused_widget, 'focused_file_ids') and \
           focused_widget.focused_file_ids is not None:
            return focused_widget.focused_file_ids
