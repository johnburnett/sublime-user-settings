import sublime, sublime_plugin

class toggle_command_logging(sublime_plugin.WindowCommand):
    def __init__(self, window):
        super(toggle_command_logging, self).__init__(window)
        self.logEnabled = False

    def run(self):
        self.logEnabled = not self.logEnabled
        sublime.log_commands(self.logEnabled)
        if self.logEnabled:
            self.window.run_command('show_panel', {'panel': 'console', 'toggle': False} )
        else:
            self.window.run_command('hide_panel', {'panel': 'console'} )

    def description(self):
        state = 'Disable' if self.logEnabled else 'Enable'
        return state + ' Command Logging'
