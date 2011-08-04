import os
import subprocess
import sys

import sublime, sublime_plugin

class open_shell_here(sublime_plugin.TextCommand):

    def run(self, edit):
        dir_path = self.get_dir()
        if dir_path:
            self.open_shell(dir_path)

    def is_enabled(self):
        return bool(self.get_dir())

    def get_dir(self):
        filename = self.view.file_name()
        if filename:
            dir_path = os.path.dirname(filename)
            if os.path.isdir(dir_path):
                return dir_path
        return None

    def open_shell(self, dir_path):
        raise NotImplemented()


class open_cmd_here(open_shell_here):

    def is_enabled(self):
        return sys.platform == 'win32' and super(self.__class__, self).is_enabled()

    def open_shell(self, dir_path):
        subprocess.Popen(['cmd.exe', '/k', 'pushd', dir_path], shell=False)


class open_bash_here(open_shell_here):

    def is_enabled(self):
        return sys.platform == 'win32' and super(self.__class__, self).is_enabled()

    def open_shell(self, dir_path):
        cmd_path = os.path.join(os.environ.get('SystemRoot', ''), r'SysWOW64\cmd.exe')
        bash_path = os.path.join(os.environ.get('ProgramFiles(x86)', ''), r'Git\bin\sh.exe')

        cmd = '%s /c "pushd "%s" && "%s" --login -i"' % (cmd_path, dir_path, bash_path)
        subprocess.Popen(cmd)
