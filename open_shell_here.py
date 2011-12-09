import os
import subprocess
import sys

import sublime, sublime_plugin


def open_bash(dir_path):
    cmd_path = os.path.join(os.environ.get('SystemRoot', ''), r'SysWOW64\cmd.exe')
    bash_path = os.path.join(os.environ.get('ProgramFiles(x86)', ''), r'Git\bin\sh.exe')

    cmd = '%s /c "pushd "%s" && "%s" --login -i"' % (cmd_path, dir_path, bash_path)
    subprocess.Popen(cmd)


class open_shell_here(sublime_plugin.TextCommand):

    def run(self, edit):
        dir_path, file_path = self.get_dir_and_file()
        if dir_path:
            self.open_shell(dir_path, file_path)

    def is_enabled(self):
        return bool(self.get_dir_and_file()[0])

    def get_dir_and_file(self):
        """Returns (dir_path, file_path) tuple.  Either component may be
        None if that component doesn't exist on disk."""
        file_path = self.view.file_name()
        if file_path:
            dir_path = os.path.dirname(file_path)
            if os.path.isdir(dir_path):
                if os.path.isfile(file_path):
                    return dir_path, file_path
                else:
                    return dir_path, None
        return None, None

    def open_shell(self, dir_path, file_path):
        raise NotImplemented()


class open_cmd_here(open_shell_here):

    def is_enabled(self):
        return sys.platform == 'win32' and super(open_cmd_here, self).is_enabled()

    def open_shell(self, dir_path, file_path):
        subprocess.Popen(['cmd.exe', '/k', 'pushd', dir_path], shell=False)


class open_bash_here(open_shell_here):

    def is_enabled(self):
        return sys.platform == 'win32' and super(open_bash_here, self).is_enabled()

    def open_shell(self, dir_path, file_path):
        open_bash(dir_path)


class open_bash_packages(sublime_plugin.ApplicationCommand):

    def run(self):
        packages_path = os.path.abspath(sublime.packages_path())
        open_bash(packages_path)
