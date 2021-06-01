import sublime
import sublime_plugin


class RenameBufferCommand(sublime_plugin.TextCommand):
    def is_enabled(self):
        return self.view.file_name() is None

    def run(self, edit):
        # Prevent the user from attempting to
        # change the name of a panel or overlay.
        if self.view.settings().get("is_widget"):
            msg = "run from an unsaved buffer not a panel or overlay"
            sublime.status_message(msg)
        else:
            msg =  "Buffer name:"
            self.view.window().show_input_panel(msg, "", self.on_panel_done, None, None)

    def on_panel_done(self, buffer_name):
        buffer_name = buffer_name.strip()
        if not buffer_name:
            return
        self.view.set_name(buffer_name)
