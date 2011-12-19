import os
import socket
import tempfile
import traceback

import sublime, sublime_plugin


k_evalpy_mel_str = """catch(python("
def __eval_in_maya():
    execfile('%s', globals())
__eval_in_maya()
"))"""

g_settings = sublime.load_settings('footools.sublime-settings')


class eval_in_maya(sublime_plugin.TextCommand):
    def run(self, edit):
        syntax = self.get_file_syntax()
        if not syntax:
            sublime.error_message("Current file is neither Python nor MEL.")
            return

        # Always use a file on disk to run in Maya, so the command port buffer doesn't
        # have to be huge, we don't have to worry about escaping all quotes, etc.
        # If current view is not dirty, use that file, otherwise use a temp file that
        # will be cleaned up after running.

        eval_file_path, is_temp_file = self.get_eval_file_path()

        if syntax == 'python':
            mel_str = k_evalpy_mel_str % eval_file_path
        elif syntax == 'mel':
            mel_str = 'catch(eval("source\\"%s\\""))' % eval_file_path

        if is_temp_file:
            # Make Maya delete the file itself to avoid race condition of
            # deleting the file before Maya has read it.
            mel_str += ';sysFile -delete "%s"' % eval_file_path

        mel_str = mel_str.strip().replace('\n', '\\n')

        success = False
        sock = None
        try:
            sock = socket.create_connection(("", g_settings.get('maya_port', 8000)), 2.0)
            sock.sendall(mel_str)
            success = True
        except:
            sublime.error_message("Error sending command to Maya.\n\nSee Sublime console for details.")
            traceback.print_exc()
            if is_temp_file:
                os.remove(eval_file_path)
        finally:
            if sock:
                sock.close()


    def is_enabled(self):
        syntax = self.get_file_syntax()
        return bool(syntax)


    def get_file_syntax(self):
        syntax, _ = os.path.splitext(os.path.basename(self.view.settings().get('syntax')))
        syntax = syntax.lower()
        if syntax == 'plain text':
            file_name = self.view.file_name()
            if file_name:
                _, ext = os.path.splitext(file_name)
                syntax = ext.lower().strip('.')
                if syntax == 'py':
                    syntax = 'python'
        return syntax if syntax in ('python', 'mel') else None


    def get_eval_file_path(self):
        """Returns a tuple of (filepath, is_temp_file)"""

        is_temp = False
        eval_regions = [r for r in self.view.sel() if not r.empty()]
        if eval_regions:
            region_text = u''
            for r in eval_regions:
                region_text += self.view.substr(r)
            # todo: remove trailing common whitespace, if any
            eval_file_path = self.write_temp_file(region_text)
            is_temp = True
        else:
            if self.view.file_name() and not self.view.is_dirty():
                eval_file_path = self.view.file_name()
            else:
                all_text = self.view.substr(sublime.Region(0, self.view.size()))
                eval_file_path = self.write_temp_file(all_text)
                is_temp = True

        eval_file_path = eval_file_path.replace('\\', '/')
        return eval_file_path, is_temp


    def write_temp_file(self, txt):
        fileInfo = tempfile.mkstemp(prefix="eval_in_maya_temp_", text=True)
        if not fileInfo:
            sublime.error_message("Can't create temp file")
            return None
        try:
            os.write(fileInfo[0], txt)
        finally:
            os.close(fileInfo[0])
        return fileInfo[1]
