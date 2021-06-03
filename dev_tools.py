import sublime
import sublime_plugin


class ToggleCommandLoggingCommand(sublime_plugin.WindowCommand):
    def __init__(self, window):
        super(ToggleCommandLoggingCommand, self).__init__(window)
        self.logEnabled = False

    def run(self):
        self.logEnabled = not self.logEnabled
        sublime.log_commands(self.logEnabled)
        if self.logEnabled:
            self.window.run_command('show_panel', {'panel': 'console', 'toggle': False} )
        else:
            self.window.run_command('hide_panel', {'panel': 'console'} )

    def is_checked(self):
        return self.logEnabled

    def description(self):
        return 'Command Logging'


class ToggleIndexingCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        settings = sublime.load_settings('Preferences.sublime-settings')
        settings.set('index_files', not settings.get('index_files', True))

    def is_checked(self):
        return bool(sublime.load_settings('Preferences.sublime-settings').get('index_files', True))

    def description(self):
        return 'Indexing'
