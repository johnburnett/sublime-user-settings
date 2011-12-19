import os
import socket
import tempfile
import traceback

import sublime, sublime_plugin

"""The port number that will be used to communicate with Maya."""
#todo: make a setting
k_maya_port = 8000

k_evalpy_mel_str = """catch(python("
def __eval_in_maya():
    execfile('%s', globals())
__eval_in_maya()
"))"""


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

        temp_file_path = None
        if not self.view.file_name() or self.view.is_dirty():
            temp_file_path = self.write_temp_file()
        eval_file_path = temp_file_path if temp_file_path else self.view.file_name()
        eval_file_path = eval_file_path.replace('\\', '/')

        if syntax == 'python':
            mel_str = k_evalpy_mel_str % eval_file_path
        elif syntax == 'mel':
            mel_str = 'catch(eval("source\\"%s\\""))' % eval_file_path

        if temp_file_path:
            # Make Maya delete the file itself to avoid race condition of
            # deleting the file before Maya has read it.
            mel_str += ';sysFile -delete "%s"' % eval_file_path

        mel_str = mel_str.strip().replace('\n', '\\n')

        success = False
        sock = None
        try:
            sock = socket.create_connection(("", k_maya_port), 2.0)
            sock.sendall(mel_str)
            success = True
        except:
            sublime.error_message("Error sending command to Maya.\n\nSee Sublime console for details.")
            traceback.print_exc()
            if temp_file_path:
                os.remove(temp_file_path)
        finally:
            if sock:
                sock.close()


    def get_file_syntax(self):
        #todo: test with mel file and mel syntax addon.......?
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


    def write_temp_file(self):
        all_text_region = sublime.Region(0, self.view.size())
        all_text = self.view.substr(all_text_region)
        fileInfo = tempfile.mkstemp(prefix="eval_in_maya_temp_", text=True)
        if not fileInfo:
            sublime.error_message("Can't create temp file")
            return None
        try:
            os.write(fileInfo[0], all_text)
        finally:
            os.close(fileInfo[0])
        return fileInfo[1]

