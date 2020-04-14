import os
import subprocess
import sys

import sublime, sublime_plugin


def platform():
    # sys.platform is 'linux' in Python3, but 'linux2' in Python2...
    # using this to normalize across versions
    if sys.platform == 'win32':
        return 'windows'
    elif sys.platform.startswith('linux'):
        return 'linux'
    else:
        return None


def open_winterm(profile_name, dir_path):
    subprocess.Popen(['wt', '-p', profile_name, '-d', dir_path], shell=False)


def open_bash(dir_path):
    cmds = []
    if platform() == 'windows':
        open_winterm('git bash', dir_path)
    elif platform() == 'linux':
        cmds.append(['/usr/bin/tilix', '--working-directory', dir_path])
        cmds.append(['/usr/bin/gnome-terminal', '--working-directory', dir_path])
        for cmd in cmds:
            try:
                subprocess.Popen(cmd)
                break
            except OSError:
                pass


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
            if platform() == 'windows':
                dir_path = os.environ.get('USERPROFILE', dir_path)

        return dir_path, file_name

    def open_shell(self, dir_path, file_name):
        raise NotImplemented()


class open_cmd_here(open_shell_here):

    def is_enabled(self):
        return platform() == 'windows' and super(open_cmd_here, self).is_enabled()

    def open_shell(self, dir_path, file_name):
        open_winterm('cmd', dir_path)


class open_powershell_here(open_shell_here):

    def is_enabled(self):
        return platform() == 'windows' and super(open_powershell_here, self).is_enabled()

    def open_shell(self, dir_path, file_name):
        open_winterm('Windows PowerShell', dir_path)


class open_file_browser_here(open_shell_here):

    def is_enabled(self):
        return (platform() in ('windows', 'linux')) and super(self.__class__, self).is_enabled()

    def open_shell(self, dir_path, file_name):
        if platform() == 'windows':
            explorer = os.path.join(os.environ['SYSTEMROOT'], 'explorer.exe')
            if file_name:
                file_path = os.path.join(dir_path, file_name)
                subprocess.Popen([explorer, '/select,', file_path])
            else:
                subprocess.Popen([explorer, dir_path])
        elif platform() == 'linux':
            subprocess.Popen(['nemo', dir_path])


class open_bash_here(open_shell_here):

    def is_enabled(self):
        return (platform() in ('windows', 'linux')) and super(open_bash_here, self).is_enabled()

    def open_shell(self, dir_path, file_name):
        open_bash(dir_path)


class open_bash_packages(sublime_plugin.ApplicationCommand):

    def run(self):
        packages_path = os.path.abspath(sublime.packages_path())
        open_bash(packages_path)
