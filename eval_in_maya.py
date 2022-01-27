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

EVAL_BUFFER = {}


def error(msg):
    sublime.error_message(f"{MY_NAME}: {msg}")


def escape_filepath(filepath):
    return filepath.replace('\\', '/')


class MayaCommand(sublime_plugin.TextCommand):
    MAYA_BUFFER_SIZE = 4096

    EVAL_COMMAND_TEMPLATE = textwrap.dedent('''
        import __main__
        import datetime
        import sys
        import maya.cmds
        import maya.mel
        try:
            nowStr = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            execLine = f'# {my_name} {{nowStr}}'
            trailingHashes = '#' * max(0, 80 - len(execLine))
            maya.cmds.undoInfo(openChunk=True, chunkName="Sublime Code Eval")
            if '{syntax}' == 'python':
                with open("{code_filepath}") as fp:
                    source = fp.read()
                code = compile(source, "{code_filepath}", 'exec')
                exec(code, __main__.__dict__, __main__.__dict__)
            else:
                maya.mel.eval('rehash; source "{code_filepath}"')
            msg = f'<span style="color:rgb(255,192,192)">{{nowStr}}: Evaluated Sublime code</span>'
            maya.cmds.inViewMessage(statusMessage=msg, fade=True, fadeInTime=0, fadeStayTime=500, fadeOutTime=500)
            # Hack to forces inViewMessage to show when Maya window doesn't have focus
            maya.cmds.setFocus('MayaWindow')
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
    ''')

    def eval_code_in_maya(self, syntax, code_gen_iterator):
        # Always use a file on disk to run in Maya, so the command port buffer doesn't
        # have to be huge, we don't have to worry about escaping all quotes, etc.
        # If current view is not dirty, use that file, otherwise use a temp file that
        # will be cleaned up after running.

        file_no, code_filepath = tempfile.mkstemp(prefix=f'{MY_NAME}_temp_', suffix='.txt', text=True)
        try:
            for text in code_gen_iterator:
                os.write(file_no, text.encode(encoding='utf-8'))
        finally:
            os.close(file_no)

        should_delete = DELETE_TEMP_FILE
        code_filepath = escape_filepath(code_filepath)
        command = self.EVAL_COMMAND_TEMPLATE.format(
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


    def get_settings(self):
        settingsPath = f'{MY_NAME}.sublime-settings'
        return sublime.load_settings(settingsPath)


    def get_syntax(self):
        syntax = os.path.splitext(os.path.basename(self.view.settings().get('syntax')))[0].lower()
        if 'python' in syntax:
            return 'python'
        elif 'mel' in syntax:
            return 'mel'
        else:
            return None


    def send_to_maya(self, command):
        commandBytes = command.encode(encoding='utf-8')
        if len(commandBytes) > self.MAYA_BUFFER_SIZE:
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


class EvalInMayaCommand(MayaCommand):
    def run(self, edit, eval_source='selection'):
        syntax = self.get_syntax()
        if syntax is None:
            error("Current file syntax is not supported.")
            return

        assert isinstance(eval_source, str)
        eval_source = EvalSource.fromString(eval_source)

        self.eval_code_in_maya(syntax, self._get_eval_chunks(eval_source))


    def is_enabled(self):
        syntax = self.get_syntax()
        return syntax is not None


    def _get_eval_chunks(self, eval_source):
        if eval_source == EvalSource.eval_buffer:
            syntax = self.get_syntax()
            buffer = EVAL_BUFFER.get(syntax)
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
        EVAL_BUFFER[syntax] = textwrap.dedent(self.view.substr(region))


class PrintInMayaCommand(MayaCommand):
    PRINT_COMMAND_TEMPLATE = textwrap.dedent('''
        try:
            res = eval("""{expr}""")
        except Exception as ex:
            print('Error evaluating expression:', ex)
        else:
            print(f"{expr} =", repr(res))
    ''')

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
            command = self.PRINT_COMMAND_TEMPLATE.format(expr=expr)
            self.eval_code_in_maya(syntax, [command])


class ReloadModuleInMayaCommand(MayaCommand):
    RELOAD_COMMAND_TEMPLATE = textwrap.dedent('''
        import importlib
        import {package_path}
        importlib.reload({package_path})
        print('Reloaded {package_path}')
    ''')

    def run(self, edit):
        syntax = self.get_syntax()
        if syntax != 'python':
            error("Current file syntax must be Python.")
            return

        file_path = self.view.file_name()
        if not file_path:
            error("Module file must be on disk to be reloaded.")
            return

        if self.view.is_dirty():
            self.view.run_command('save')

        package_path = self.find_module_package_path(file_path)
        code = self.RELOAD_COMMAND_TEMPLATE.format(package_path=package_path)
        self.eval_code_in_maya(syntax, [code])


    def find_module_package_path(self, file_path):
        dir_path, file_name = os.path.split(file_path)
        module_name, _ = os.path.splitext(file_name)
        package_path_parts = [module_name]
        while True:
            init_path = os.path.join(dir_path, '__init__.py')
            if os.path.isfile(init_path):
                dir_path, dir_name = os.path.split(dir_path)
                package_path_parts.append(dir_name)
            else:
                break
        package_path = '.'.join(reversed(package_path_parts))
        return package_path
