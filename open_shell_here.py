import os
import subprocess
import sys

import sublime, sublime_plugin


def open_bash(dir_path):
    if sys.platform == 'win32':
        cmd_path = os.path.join(os.environ.get('SystemRoot', ''), r'SysWOW64\cmd.exe')
        bash_path = os.path.join(os.environ.get('ProgramFiles(x86)', ''), r'Git\bin\sh.exe')

        cmd = '{cmd_path} /c "pushd "{dir_path}" && "{bash_path}" --login -i"'.format(**locals())
    elif sys.platform == 'linux2':
        cmd = ['gnome-terminal', '--working-directory', dir_path]
    subprocess.Popen(cmd)


class open_shell_here(sublime_plugin.ApplicationCommand):

    def run(self):
        dir_path, file_name = self.get_dir_and_file()
        if dir_path:
            self.open_shell(dir_path, file_name)

    def is_enabled(self):
        return bool(self.get_dir_and_file()[0])

    def get_dir_and_file(self):
        """Returns (dir_path, file_name) tuple.  file_name may be None."""

        file_path = None
        win = sublime.active_window()
        if win:
            view = win.active_view()
            if view:
                file_path = view.file_name()

        dir_path = None
        file_name = None
        if file_path:
            dir_path = os.path.dirname(file_path)
            if os.path.isfile(file_path):
                file_name = os.path.basename(file_path)

        if not dir_path or not os.path.isdir(dir_path):
            dir_path = os.path.expanduser('~')
            if sys.platform == 'win32':
                dir_path = os.environ.get('USERPROFILE', dir_path)

        return dir_path, file_name

    def open_shell(self, dir_path, file_name):
        raise NotImplemented()


class open_cmd_here(open_shell_here):

    def is_enabled(self):
        return sys.platform == 'win32' and super(open_cmd_here, self).is_enabled()

    def open_shell(self, dir_path, file_name):
        subprocess.Popen(['cmd.exe', '/k', 'pushd', dir_path], shell=False)


class open_file_browser_here(open_shell_here):

    def is_enabled(self):
        return (sys.platform in ('win32', 'linux2')) and super(self.__class__, self).is_enabled()

    def open_shell(self, dir_path, file_name):
        if sys.platform == 'win32':
            explorer = os.path.join(os.environ['SYSTEMROOT'], 'explorer.exe')
            if file_name:
                file_path = os.path.join(dir_path, file_name)
                subprocess.Popen([explorer, '/select,', file_path])
            else:
                subprocess.Popen([explorer, dir_path])
        elif sys.platform == 'linux2':
            subprocess.Popen(['nautilus', dir_path])


class open_bash_here(open_shell_here):

    def is_enabled(self):
        return (sys.platform in ('win32', 'linux2')) and super(open_bash_here, self).is_enabled()

    def open_shell(self, dir_path, file_name):
        open_bash(dir_path)


class open_bash_packages(sublime_plugin.ApplicationCommand):

    def run(self):
        packages_path = os.path.abspath(sublime.packages_path())
        open_bash(packages_path)
