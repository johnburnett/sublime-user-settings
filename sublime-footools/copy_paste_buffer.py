import sublime
import sublime_plugin


class CopyEntireBufferCommand(sublime_plugin.TextCommand):
    def description(self):
        return 'Copy Entire Buffer'

    def run(self, edit):
        if self.view.settings().get('is_widget'):
            return

        region = sublime.Region(0, self.view.size())
        text = self.view.substr(region)
        sublime.set_clipboard(text)


class PasteEntireBufferCommand(sublime_plugin.TextCommand):
    def description(self):
        return 'Paste Entire Buffer'

    def run(self, edit):
        if self.view.settings().get('is_widget'):
            return

        text = sublime.get_clipboard()
        if text:
            selected_regions = tuple([region for region in self.view.sel()])
            entire_buffer = sublime.Region(0, self.view.size())
            self.view.replace(edit, entire_buffer, text)
            self.view.sel().clear()
            self.view.sel().add_all(selected_regions)
