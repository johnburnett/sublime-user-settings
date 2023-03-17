from dataclasses import dataclass
import os
import socket
import tempfile
import textwrap

import sublime
import sublime_plugin


THIS_MODULE_NAME = os.path.splitext(os.path.basename(__file__))[0]

EXEC_CODE_TEMPLATES = {
    'blender': textwrap.dedent('''
        import __main__
        import datetime
        import os
        import sys
        try:
            now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            exec_line = f'# {this_module_name} {{now_str}}'
            trailing_hashes = '#' * max(0, 80 - len(exec_line))
            with open("{code_filepath}") as fp:
                source = fp.read()
            code = compile(source, "{code_filepath}", 'exec')
            exec(code, __main__.__dict__, __main__.__dict__)
            msg = f'<span style="color:rgb(255,192,192)">{{now_str}}: Evaluated Sublime code</span>'
        except Exception as ex:
            sys.excepthook(*sys.exc_info())
        finally:
            try:
                os.unlink("{code_filepath}")
            except:
                pass
        '''),
    'maya': textwrap.dedent('''
        import __main__
        import datetime
        import os
        import sys
        import maya.cmds
        import maya.mel
        try:
            now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            exec_line = f'# {this_module_name} {{now_str}}'
            trailing_hashes = '#' * max(0, 80 - len(exec_line))
            maya.cmds.undoInfo(openChunk=True, chunkName="Sublime Code Eval")
            if '{syntax}' == 'python':
                with open("{code_filepath}") as fp:
                    source = fp.read()
                code = compile(source, "{code_filepath}", 'exec')
                exec(code, __main__.__dict__, __main__.__dict__)
            else:
                maya.mel.eval('rehash; source "{code_filepath}"')
            msg = f'<span style="color:rgb(255,192,192)">{{now_str}}: Evaluated Sublime code</span>'
            maya.cmds.inViewMessage(statusMessage=msg, fade=True, fadeInTime=0, fadeStayTime=500, fadeOutTime=500)
            # Hack to forces inViewMessage to show when Maya window doesn't have focus
            # maya.cmds.setFocus('MayaWindow')
        except Exception as ex:
            sys.excepthook(*sys.exc_info())
        finally:
            maya.cmds.undoInfo(closeChunk=True)
            # Make Maya delete the file itself to avoid race condition of
            # deleting the file before Maya has read it.
            try:
                os.unlink("{code_filepath}")
            except:
                pass
        '''),
}

PRINT_EXPR_TEMPLATES = {
    'python': textwrap.dedent('''
        try:
            __eval_result = eval("""{expr}""")
        except Exception as ex:
            print('Error evaluating expression:', ex)
        else:
            print(f"{expr} =", repr(__eval_result))
        '''),
}

RELOAD_TEMPLATES = {
    'python': textwrap.dedent('''
        import importlib
        import {package_path}
        importlib.reload({package_path})
        print('Reloaded {package_path}')
        '''),
}

SCRATCH_BUFFER = None


@dataclass
class CodeBuffer:
    syntax: str
    code: str


def error(msg):
    sublime.error_message(f"{THIS_MODULE_NAME}: {msg}")


def escape_filepath(file_path):
    return file_path.replace('\\', '/')


def get_setting(key, default_value):
    settings_path = f'{THIS_MODULE_NAME}.sublime-settings'
    settings = sublime.load_settings(settings_path)
    return settings.get(key, default_value)


def get_syntax(view):
    syntax = view.syntax()
    return syntax.name.lower()


def find_module_package_path(file_path):
    dir_path, file_name = os.path.split(file_path)
    module_name, _ = os.path.splitext(file_name)
    package_path_parts = []
    if module_name != "__init__":
        package_path_parts.append(module_name)
    while True:
        init_path = os.path.join(dir_path, '__init__.py')
        if os.path.isfile(init_path):
            dir_path, dir_name = os.path.split(dir_path)
            package_path_parts.append(dir_name)
        else:
            break
    package_path = '.'.join(reversed(package_path_parts))
    return package_path


def send_code_to_remote(port, code_buffer, exec_template):
    # Always use a file on disk so the command port buffer doesn't have to
    # be huge, we don't have to worry about escaping all quotes, etc.
    file_no, code_filepath = tempfile.mkstemp(prefix=f'{THIS_MODULE_NAME}_temp_', suffix='.txt')
    try:
        os.write(file_no, code_buffer.code.encode(encoding='utf-8'))
    finally:
        os.close(file_no)

    code_filepath = escape_filepath(code_filepath)
    command = exec_template.format(
        this_module_name=THIS_MODULE_NAME,
        syntax=code_buffer.syntax,
        code_filepath=code_filepath,
    )

    try:
        command_bytes = command.encode(encoding='utf-8')
        if len(command_bytes) > 4096:
            error("Command too large, and I'm too lazy to handle this case right now.")
            return

        sock = None
        try:
            address = ('127.0.0.1', port)
            sock = socket.create_connection(address, 1.0)
            sock.sendall(command_bytes)
        except Exception as ex:
            error(f"Error sending to remote:\n\n{ex}\n\nSee Sublime console for details.")
            raise
        finally:
            if sock:
                sock.close()
    except:
        try:
            os.remove(code_filepath)
        except:
            pass
        raise


def send_code_to_maya(code_buffer):
    port = get_setting('maya_port', None)
    template = EXEC_CODE_TEMPLATES['maya']
    send_code_to_remote(port, code_buffer, template)


def send_code_to_blender(code_buffer):
    port = get_setting('blender_port', None)
    template = EXEC_CODE_TEMPLATES['blender']
    send_code_to_remote(port, code_buffer, template)


def get_current_code(view):
    eval_regions = [r for r in view.sel() if not r.empty()]
    if not eval_regions:
        eval_regions = [sublime.Region(0, view.size())]

    lines_written = -1
    chunks = []
    for eval_region in eval_regions:
        # Attempts to take each chunk of selected text, dedent it to
        # remove excess leading whitespace and make it syntactically
        # correct Python, and preserve original line numbers to make
        # any reported errors easier to find.  Having multiple
        # regions selected on a single line will lead to odd (and
        # likely invalid) results.
        chunk = ''
        for region_line in view.split_by_newlines(eval_region):
            lineno = view.rowcol(region_line.begin())[0]
            padding = lineno - lines_written
            for ii in range(padding - 1):
                chunks.append('\n')
            lines_written = lineno
            chunk += view.substr(region_line) + '\n'
        chunks.append(textwrap.dedent(chunk))
    return ''.join(chunks)


def exec_current(view, send_code_func):
    syntax = get_syntax(view)
    code = get_current_code(view)
    send_code_func(CodeBuffer(syntax, code))


def exec_scratch_buffer(view, send_code_func):
    if not SCRATCH_BUFFER:
        return error('No buffer saved, use the save_exec_scratch_buffer command.')
    send_code_func(SCRATCH_BUFFER)


def print_selected_values(view, send_code_func):
    syntax = get_syntax(view)
    template = PRINT_EXPR_TEMPLATES.get(syntax)
    if not template:
        return error(f'No print template for current syntax ({syntax}).')

    regions = [r for r in view.sel() if not r.empty()]
    for region in regions:
        expr = view.substr(region)
        expr = expr.strip()
        if not expr:
            continue
        if '\n' in expr:
            continue
        code = template.format(expr=expr)
        send_code_func(CodeBuffer(syntax, code))


def reload_current_module(view, send_code_func):
    file_path = view.file_name()
    if not file_path:
        return error("Module file must be on disk to be reloaded.")

    if view.is_dirty():
        view.run_command('save')

    syntax = get_syntax(view)
    template = RELOAD_TEMPLATES.get(syntax)
    if not template:
        return error(f'No reload template for current syntax ({syntax}).')

    package_path = find_module_package_path(file_path)
    code = template.format(package_path=package_path)
    send_code_func(CodeBuffer(syntax, code))


# Generic Sublime plugins


class SaveExecScratchBufferCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        syntax = get_syntax(self.view)
        regions = [r for r in self.view.sel() if not r.empty()]
        if len(regions) != 1:
            return error('Must have a single region selected to save.')
        code = self.view.substr(regions[0])
        code = textwrap.dedent(code)
        global SCRATCH_BUFFER
        SCRATCH_BUFFER = CodeBuffer(syntax, code)


class PrintExecScratchBufferCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        if SCRATCH_BUFFER:
            print(
                '# Exec scratch buffer begin ######################################################'
            )
            print(SCRATCH_BUFFER.code)
            print(
                '# Exec scratch buffer end ########################################################'
            )
        else:
            print('No exec scratch buffer set.')


# Maya Sublime plugins

class MayaCommandEnabledMixin:
    def is_enabled():
        syntax = get_syntax(self.view)
        return syntax in ('python', 'mel')


class ExecInMayaCommand(sublime_plugin.TextCommand, MayaCommandEnabledMixin):
    def run(self, edit):
        exec_current(self.view, send_code_to_maya)


class ExecScratchBufferInMayaCommand(sublime_plugin.TextCommand, MayaCommandEnabledMixin):
    def run(self, edit):
        exec_scratch_buffer(self.view, send_code_to_maya)


class PrintSelectedValuesInMayaCommand(sublime_plugin.TextCommand, MayaCommandEnabledMixin):
    def run(self, edit):
        print_selected_values(self.view, send_code_to_maya)


class ReloadModuleInMayaCommand(sublime_plugin.TextCommand, MayaCommandEnabledMixin):
    def run(self, edit):
        reload_current_module(self.view, send_code_to_maya)


# Blender Sublime plugins

class BlenderCommandEnabledMixin:
    def is_enabled():
        syntax = get_syntax(self.view)
        return syntax == 'python'


class ExecInBlenderCommand(sublime_plugin.TextCommand, BlenderCommandEnabledMixin):
    def run(self, edit):
        exec_current(self.view, send_code_to_blender)


class ExecScratchBufferInBlenderCommand(sublime_plugin.TextCommand, BlenderCommandEnabledMixin):
    def run(self, edit):
        exec_scratch_buffer(self.view, send_code_to_blender)


class PrintSelectedValuesInBlenderCommand(sublime_plugin.TextCommand, BlenderCommandEnabledMixin):
    def run(self, edit):
        print_selected_values(self.view, send_code_to_blender)


class ReloadModuleInBlenderCommand(sublime_plugin.TextCommand, BlenderCommandEnabledMixin):
    def run(self, edit):
        reload_current_module(self.view, send_code_to_blender)
