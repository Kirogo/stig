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

"""Torrent commands for the TUI"""

from ...logging import make_logger
log = make_logger(__name__)

from shutil import get_terminal_size
TERMSIZE = get_terminal_size(fallback=(None, None))
import os

from ..base import torrent as base
from . import mixin
from .. import ExpectedResource
from ...utils import strwidth
from ...columns.tlist import COLUMNS as TLIST_COLUMNS
from ...columns.flist import COLUMNS as FLIST_COLUMNS
from ...columns.flist import create_directory_data



def _print_table(items, columns_wanted, COLUMN_SPECS):
    """Print table from a two-dimensional array of column objects

    `COLUMN_SPECS` maps column IDs to ColumnBase classes.  A column ID is any
    hashable object, but you probably want strings like 'name', 'id', 'date',
    etc.

    `columns_wanted` is a sequence of column IDs.

    `items` is a sequence of arbitrary objects that are used to create cell
    objects by passing them to the classes in `COLUMN_SPECS`.
    """

    # Create two-dimensional list to represent a table.  Each cell must be a
    # ColumnBase instance (see columns.tlist module).
    rows  = []
    for item in items:
        row = []
        for i,colname in enumerate(columns_wanted):
            cell = COLUMN_SPECS[colname](item)
            cell.index = i
            row.append(cell)
        rows.append(row)

    delimiter = '|' if TERMSIZE.columns is None else '│'

    # Whether to print for a human or for a machine to read our output
    pretty_output = TERMSIZE.columns is not None

    def assemble_line(row):
        line = []
        for cell in row:
            if pretty_output:
                line.append(cell.get_string())
            else:
                line.append(str(cell.get_raw()))
        return delimiter.join(line)

    def assemble_headers():
        # This must be called after shrink_and_expand_to_fit() so we can
        # grab the final column widths from the first row.
        widths = tuple(cell.width for cell in rows[0])
        headers = []
        for colname,width in zip(columns_wanted, widths):
            header_items = COLUMN_SPECS[colname].header
            left  = header_items.get('left', '')
            right = header_items.get('right', '')
            space = ' '*(width - len(left) - len(right))
            header = ''.join((left, space, right))[:width]
            headers.append(header)
        return delimiter.join(headers)

    def shrink_and_expand_to_fit():
        log.debug('TTY width is %dx%d', TERMSIZE.columns, TERMSIZE.lines)

        def get_colwidth(colindex):
            # Get maximum column width (width of widest cell in all rows)
            return max(strwidth(row[colindex].get_string())
                       for row in rows)

        def set_colwidth(colindex, width):
            # Set column width of all rows
            for row in rows:
                cell = row[colindex]
                cell.width = width

        def widest_columns():
            # Column indexes sorted by column width
            return sorted(range(len(columns_wanted)),
                          key=lambda colindex: get_colwidth(colindex),
                          reverse=True)

        # Expand column widths to make all cell values fit
        for colindex in range(len(columns_wanted)):
            colwidth = get_colwidth(colindex)
            set_colwidth(colindex, colwidth)

        # Rows should have identical column widths from now on, so we can
        # use the first row to check our progress.
        while strwidth(assemble_line(rows[0])) > TERMSIZE.columns:
            excess = strwidth(assemble_line(rows[0])) - TERMSIZE.columns
            widest = widest_columns()
            widest_0 = get_colwidth(widest[0])
            widest_1 = get_colwidth(widest[1])

            # Shorten widest column by difference to second widest column
            # (leaving them at the same width), but not by more than `excess`
            # characters and at least one character.

            # TODO: This is very slow when listing lots of rows in a small
            # terminal because the widest column is shrunk by only 1 character
            # before checking again.
            shorten_by = max(1, min(excess, widest_0 - widest_1))
            set_colwidth(widest[0], widest_0 - shorten_by)

    if rows:
        if not pretty_output:
            log.debug('Could not detect TTY size - assuming stdout is no TTY')
            headerstr = None
        elif TERMSIZE.columns < len(columns_wanted)*3:
            log.error('Terminal is too narrow for %d columns', len(columns_wanted))
            return False
        else:
            shrink_and_expand_to_fit()
            headerstr = '\033[1;4m' + assemble_headers() + '\033[0m'

        for linenum,row in enumerate(rows):
            if headerstr is not None and \
               linenum % (TERMSIZE.lines-1) == 0:
                log.info(headerstr)
            log.info(assemble_line(row))



class AddTorrentsCmd(base.AddTorrentsCmdbase,
                     mixin.make_request):
    provides = {'cli'}


class AnnounceTorrentsCmd(base.AnnounceTorrentsCmdbase,
                     mixin.make_request, mixin.select_torrents):
    provides = {'cli'}


class ListTorrentsCmd(base.ListTorrentsCmdbase,
                      mixin.make_request, mixin.select_torrents):
    provides = {'cli'}
    srvapi = ExpectedResource  # TUI version of 'list' doesn't need srvapi
    async def make_tlist(self, tfilter, sort, columns):
        # Get wanted torrents and sort them
        if tfilter is None:
            keys = set(sort.needed_keys)
        else:
            keys = set(sort.needed_keys + tfilter.needed_keys)
        for colname in columns:
            keys.update(TLIST_COLUMNS[colname].needed_keys)
        response = await self.make_request(
            self.srvapi.torrent.torrents(tfilter, keys=keys),
            quiet=True)
        torrents = sort.apply(response.torrents)

        if torrents:
            _print_table(torrents, columns, TLIST_COLUMNS)
        return len(torrents) > 0


class ListFilesCmd(base.ListFilesCmdbase,
                   mixin.make_request, mixin.select_torrents, mixin.select_files):
    provides = {'cli'}
    srvapi = ExpectedResource
    async def make_flist(self, tfilter, ffilter, columns):
        response = await self.make_request(
            self.srvapi.torrent.torrents(tfilter, keys=('name', 'files')),
            quiet=True)
        torrents = response.torrents

        if len(torrents) < 1:
            return False

        filelist = []
        for torrent in sorted(torrents, key=lambda t: t['name'].lower()):
            files, filtered_count = self._flatten_tree(torrent['files'], ffilter)
            filelist.extend(files)

        if filelist:
            _print_table(filelist, columns, FLIST_COLUMNS)
            return True
        else:
            if str(tfilter) != 'all':
                log.error('No matching files in {} torrents: {}'.format(tfilter, ffilter))
            else:
                log.error('No matching files: {}'.format(ffilter))
            return False

    def _flatten_tree(self, files, ffilter=None, _indent_level=0):
        """Return list of rows for _print_table

        `files` must be a nested mapping tree (i.e. TorrentFileTree).
        `ffilter` must be a TorrentFileFilter instance or None.
        """
        if TERMSIZE.columns is None:
            def indent_file_name(node):
                node['name'] = os.path.join(node['path'], node['name'])

            def indent_directory_name(node):
                node['name'] = node['path']
        else:
            def indent_file_name(node):
                node['name'] = '%s%s' % ('  '*(_indent_level), node['name'])
            indent_directory_name = indent_file_name

        flist = []
        filtered_count = 0
        for key,value in sorted(files.items(), key=lambda pair: pair[0].lower()):
            if value.nodetype == 'leaf':
                if ffilter is None or ffilter.match(value):
                    filenode = dict(value)  # Copy original TorrentFile
                    indent_file_name(filenode)
                    flist.append(filenode)
                else:
                    filtered_count += 1

            elif value.nodetype == 'parent':
                sub_flist, sub_filtered_count = self._flatten_tree(value, ffilter, _indent_level+1)
                dirnode = create_directory_data(key, value, sub_filtered_count)
                indent_directory_name(dirnode)
                flist.append(dirnode)
                flist.extend(sub_flist)

        return flist, filtered_count


class MoveTorrentsCmd(base.MoveTorrentsCmdbase,
                      mixin.make_request, mixin.select_torrents):
    provides = {'cli'}


class PriorityCmd(base.PriorityCmdbase,
                  mixin.make_request, mixin.select_torrents, mixin.select_files):
    provides = {'cli'}


class RemoveTorrentsCmd(base.RemoveTorrentsCmdbase,
                        mixin.make_request, mixin.select_torrents):
    provides = {'cli'}


class StopTorrentsCmd(base.StopTorrentsCmdbase,
                      mixin.make_request, mixin.select_torrents):
    provides = {'cli'}


class StartTorrentsCmd(base.StartTorrentsCmdbase,
                       mixin.make_request, mixin.select_torrents):
    provides = {'cli'}


class VerifyTorrentsCmd(base.VerifyTorrentsCmdbase,
                        mixin.make_request, mixin.select_torrents):
    provides = {'cli'}
