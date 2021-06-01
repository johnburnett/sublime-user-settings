import os
import socket
import tempfile
import textwrap

import sublime, sublime_plugin

MY_NAME = os.path.splitext(os.path.basename(__file__))[0]

# When you run this tool and the active view is dirty, it dumps the active code
# (either full file or the selected text) into a temp file for compiling in
# Maya.  This controls whether the temp file should be deleted afterwards.
# Only really handy for dev work on this tool.
DELETE_TEMP_FILE = True

# This controls whether the same temp file is used each run or not.
#
# Originally the original file path was threaded through to the compile call so
# it would show up in stack traces nicely, even though the file holding the
# actual code was off in a temp file.  However, that feeds into inspect and
# showing lines of source.  The original file on disk is in a different state
# than what exists transiently in the editor buffer (and the temp file), so
# inspect.getsourcefile was picking up the wrong thing.
#
# Similarly, if you reuse the same filename for each run and then only partially
# evaluate the source (e.g. via a selection), live objects in Maya will be
# pointing to old copies of the code and source file references, which makes
# stack traces less than truthful.  I don't think there's much to be done in
# that case, and it's just something to be aware of.  Getting full, reliable,
# and correct traces requires re-evaluation of all affected code, so it's a
# trade-off between handy partial evaluation and rebuilding the world?
REUSE_TEMP_FILE = False

MAYA_BUFFER_SIZE = 4096

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
    maya.cmds.undoInfo(openChunk=True, chunkName="Sublime Code Eval")
    if '{syntax}' == 'python':
        with open("{code_filepath}") as fp:
            source = fp.read()
        code = compile(source, "{code_filepath}", 'exec')
        exec(code, __main__.__dict__, __main__.__dict__)
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


def error(msg):
    sublime.error_message("%s: %s" % (MY_NAME, msg))

def escape_filepath(filepath):
    return filepath.replace('\\', '\\\\')

class EvalInMayaCommand(sublime_plugin.TextCommand):
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

        code_filepath, is_temp = self._get_code_filepath()
        should_delete = is_temp and DELETE_TEMP_FILE
        code_filepath = escape_filepath(code_filepath)
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
        """Returns a tuple of (filepath, is_temp)
        """

        # TODO: richerr in maya doesn't seem to be picking up changes to files on disk, so always
        # write out temp file.  repro:
        # eval saved py.py
        # edit py.py to raise
        # eval py.py without saving
        # save py.py and eval again... this run will show the old py.py lines

        eval_regions = [r for r in self.view.sel() if not r.empty()]
        if REUSE_TEMP_FILE:
            code_filepath = os.path.join(tempfile.gettempdir(), MY_NAME)
            file_no = os.open(code_filepath, os.O_WRONLY|os.O_CREAT|os.O_TRUNC)
        else:
            file_no, code_filepath = tempfile.mkstemp(prefix='%s_temp_' % MY_NAME, suffix='.txt', text=True)
        try:
            for chunk in self._get_eval_chunks(eval_regions):
                os.write(file_no, chunk.encode(encoding='utf-8'))
        finally:
            os.close(file_no)
        is_temp = True
        return code_filepath, is_temp


    def _get_eval_chunks(self, eval_regions):
        if eval_regions:
            lines_written = -1
            for eval_region in eval_regions:
                ## dedents, but doesn't preserve line numbering
                # region_text = self.view.substr(eval_region)
                # yield textwrap.dedent(region_text)

                ## preserves line numbering, but doesn't dedent
                # region_start_line = self.view.rowcol(eval_region.begin())[0]
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
