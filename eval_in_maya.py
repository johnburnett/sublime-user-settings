import enum
import os
import socket
import tempfile
import textwrap

import sublime, sublime_plugin


class EvalSource(enum.Enum):
    file = enum.auto()
    selection = enum.auto()
    eval_buffer = enum.auto()

    @staticmethod
    def fromString(s):
        assert s in dir(EvalSource)
        return EvalSource[s]


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

EVAL_COMMAND_TEMPLATE = '''
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

# todo: print "None" if expr is None
# todo: printing cmds.getAttr('gameExporterPreset1.convertNurbsSurfaceTo') fails (quoting issue?)

PRINT_COMMAND_TEMPLATE = '''
import __main__
try:
    code = compile('print("{expr} =", repr({expr}))', "<string>", 'exec')
    exec(code, __main__.__dict__, __main__.__dict__)
except:
    print('Error printing "{expr}"')
'''

eval_buffer = {}


def error(msg):
    sublime.error_message("%s: %s" % (MY_NAME, msg))


def escape_filepath(filepath):
    return filepath.replace('\\', '\\\\')


class MayaCommand(sublime_plugin.TextCommand):
    def send_to_maya(self, command):
        commandBytes = command.encode(encoding='utf-8')
        if len(commandBytes) > MAYA_BUFFER_SIZE:
            error("Command too large, and I'm too lazy to handle this case right now.")
            return

        settings = self.get_settings()
        sock = None
        try:
            host = '127.0.0.1'
            port = settings.get('maya_port', None)
            address = (host, port)
            sock = socket.create_connection(address, 1.0)
            sock.sendall(commandBytes)
        except:
            error("Error sending command to Maya.\n\nSee Sublime console for details.")
            raise
        finally:
            if sock:
                sock.close()


    def get_settings(self):
        settingsPath = '%s.sublime-settings' % MY_NAME
        return sublime.load_settings(settingsPath)


    def get_syntax(self):
        syntax = os.path.splitext(os.path.basename(self.view.settings().get('syntax')))[0].lower()
        if 'python' in syntax:
            return 'python'
        elif 'mel' in syntax:
            return 'mel'
        else:
            return None


class EvalInMayaCommand(MayaCommand):
    def run(self, edit, eval_source='selection'):
        syntax = self.get_syntax()
        if syntax is None:
            error("Current file syntax is not supported.")
            return

        assert isinstance(eval_source, str)
        eval_source = EvalSource.fromString(eval_source)

        # Always use a file on disk to run in Maya, so the command port buffer doesn't
        # have to be huge, we don't have to worry about escaping all quotes, etc.
        # If current view is not dirty, use that file, otherwise use a temp file that
        # will be cleaned up after running.

        code_filepath, is_temp = self._get_code_filepath(eval_source)
        should_delete = is_temp and DELETE_TEMP_FILE
        code_filepath = escape_filepath(code_filepath)
        command = EVAL_COMMAND_TEMPLATE.format(
            my_name=MY_NAME,
            syntax=syntax,
            code_filepath=code_filepath,
            should_delete=should_delete,
        )

        try:
            self.send_to_maya(command)
        except:
            if should_delete:
                try:
                    os.remove(code_filepath)
                except:
                    pass
            raise


    def is_enabled(self):
        syntax = self.get_syntax()
        return syntax is not None


    def _get_code_filepath(self, eval_source):
        """Returns a tuple of (filepath, is_temp)
        """

        # TODO: richerr in maya doesn't seem to be picking up changes to files on disk, so always
        # write out temp file.  repro:
        # eval saved py.py
        # edit py.py to raise
        # eval py.py without saving
        # save py.py and eval again... this run will show the old py.py lines

        if REUSE_TEMP_FILE:
            code_filepath = os.path.join(tempfile.gettempdir(), MY_NAME)
            file_no = os.open(code_filepath, os.O_WRONLY|os.O_CREAT|os.O_TRUNC)
        else:
            file_no, code_filepath = tempfile.mkstemp(prefix='%s_temp_' % MY_NAME, suffix='.txt', text=True)
        try:
            for chunk in self._get_eval_chunks(eval_source):
                os.write(file_no, chunk.encode(encoding='utf-8'))
        finally:
            os.close(file_no)
        is_temp = True
        return code_filepath, is_temp


    def _get_eval_chunks(self, eval_source):
        if eval_source == EvalSource.eval_buffer:
            syntax = self.get_syntax()
            buffer = eval_buffer.get(syntax)
            if buffer:
                yield buffer
            return

        eval_regions = []
        if eval_source == EvalSource.selection:
            eval_regions = [r for r in self.view.sel() if not r.empty()]
        if not eval_regions or eval_source == EvalSource.file:
            eval_regions = [sublime.Region(0, self.view.size())]

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
        return


class SetMayaEvalBufferCommand(MayaCommand):
    def run(self, edit):
        syntax = self.get_syntax()
        if not syntax:
            return
        selected_regions = self.view.sel()
        if len(selected_regions) != 1:
            return
        region = selected_regions[0]
        text = textwrap.dedent(self.view.substr(region))
        eval_buffer[syntax] = textwrap.dedent(self.view.substr(region))


class PrintInMayaCommand(MayaCommand):
    def run(self, edit):
        syntax = self.get_syntax()
        if syntax != 'python':
            error("Current file syntax must be Python.")
            return

        regions = [r for r in self.view.sel() if not r.empty()]
        for region in regions:
            expr = self.view.substr(region)
            expr = expr.strip()
            if not expr:
                continue
            if '\n' in expr:
                continue
            command = PRINT_COMMAND_TEMPLATE.format(expr=expr)
            self.send_to_maya(command)
