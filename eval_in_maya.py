import os
import socket
import tempfile
import textwrap

import sublime, sublime_plugin

MY_NAME = os.path.splitext(os.path.basename(__file__))[0]

COMMAND_TEMPLATE = '''
from __future__ import print_function
import __main__
import datetime
import sys
import maya.cmds
import maya.mel
try:
    nowStr = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    execLine = '# {my_name} %s' % nowStr
    trailingHashes = '#' * max(0, 80 - len(execLine))
    print(execLine, trailingHashes)
    maya.cmds.undoInfo(openChunk=True, chunkName="Sublime Code Eval")
    if '{syntax}' == 'python':
        execfile("{code_filepath}", __main__.__dict__, __main__.__dict__)
    else:
        maya.mel.eval('rehash; source "{code_filepath}"')
except Exception as ex:
    # Directly call excepthook, as raising from this code seems to get swallowed
    # by Maya somehow.  Not using traceback because there might be a custom
    # exception hook installed that is better than that.
    sys.excepthook(*sys.exc_info())
finally:
    maya.cmds.undoInfo(closeChunk=True)
    if {should_delete}:
        # Make Maya delete the file itself to avoid race condition of
        # deleting the file before Maya has read it.
        try:
            os.unlink("{code_filepath}")
        except:
            pass
'''

MAYA_BUFFER_SIZE = 4096


def error(msg):
    sublime.error_message("%s: %s" % (MY_NAME, msg))


class eval_in_maya_command(sublime_plugin.TextCommand):
    def run(self, edit):
        syntax = self._get_syntax()
        if syntax is None:
            error("Current file syntax is not supported.")
            return

        settingsPath = '%s.sublime-settings' % MY_NAME
        settings = sublime.load_settings(settingsPath)

        # Always use a file on disk to run in Maya, so the command port buffer doesn't
        # have to be huge, we don't have to worry about escaping all quotes, etc.
        # If current view is not dirty, use that file, otherwise use a temp file that
        # will be cleaned up after running.

        code_filepath, should_delete = self._get_code_filepath()
        command = COMMAND_TEMPLATE.format(
            my_name=MY_NAME,
            syntax=syntax,
            code_filepath=code_filepath,
            should_delete=should_delete,
        )
        commandBytes = command.encode(encoding='utf-8')
        if len(commandBytes) > MAYA_BUFFER_SIZE:
            error("Command too large, and I'm too lazy to handle this case right now.")
            return

        sock = None
        try:
            host = '127.0.0.1'
            port = settings.get('maya_port', None)
            address = (host, port)
            sock = socket.create_connection(address, 1.0)
            sock.sendall(commandBytes)
        except:
            error("Error sending command to Maya.\n\nSee Sublime console for details.")
            if should_delete:
                try:
                    os.remove(code_filepath)
                except:
                    pass
            raise
        finally:
            if sock:
                sock.close()


    def is_enabled(self):
        syntax = self._get_syntax()
        return syntax is not None


    def _get_syntax(self):
        syntax = os.path.splitext(os.path.basename(self.view.settings().get('syntax')))[0].lower()
        if 'python' in syntax:
            return 'python'
        elif 'mel' in syntax:
            return 'mel'
        else:
            return None


    def _get_code_filepath(self):
        """Returns a tuple of (filepath, should_delete)
        """
        eval_regions = [r for r in self.view.sel() if not r.empty()]
        if eval_regions or self.view.is_dirty():
            file_no, eval_file_path = tempfile.mkstemp(prefix='%s_temp_' % MY_NAME, text=True)
            for chunk in self._get_eval_chunks(eval_regions):
                os.write(file_no, chunk.encode(encoding='utf-8'))
            os.close(file_no)
            is_temp = True
        else:
            eval_file_path = self.view.file_name()
            is_temp = False
        eval_file_path = eval_file_path.replace('\\', '/')
        return eval_file_path, is_temp


    def _get_eval_chunks(self, eval_regions):
        if eval_regions:
            lines_written = -1
            for eval_region in eval_regions:
                ## dedents, but doesn't preserve line numbering
                # region_text = self.view.substr(eval_region)
                # yield textwrap.dedent(region_text)

                ## preserves line numbering, but doesn't dedent
                # region_start_line = self.view.rowcol(eval_region.begin())[0]
                # print('region_start_line:', region_start_line)
                # for region_line in self.view.split_by_newlines(eval_region):
                #     lineno = self.view.rowcol(region_line.begin())[0]
                #     for ii in range(lineno - lines_written):
                #         yield '\n'
                #     lines_written = lineno
                #     yield self.view.substr(region_line)

                # Attempts to take each chunk of selected text, dedent it to
                # remove excess leading whitespace and make it syntactically
                # correct Python, and preserve original line numbers to make
                # any reported errors easier to find.  Having multiple
                # regions selected on a single line will lead to odd (and
                # likely invalid) results.
                chunk = ''
                for region_line in self.view.split_by_newlines(eval_region):
                    lineno = self.view.rowcol(region_line.begin())[0]
                    padding = lineno - lines_written
                    for ii in range(padding - 1):
                        yield '\n'
                    lines_written = lineno
                    chunk += self.view.substr(region_line) + '\n'
                yield textwrap.dedent(chunk)
        else:
            yield self.view.substr(sublime.Region(0, self.view.size()))
