import sublime
import sublime_plugin

_COLOR_STRINGS = ('<b><color=#b0cdac>', '</color></b>')

class StripColorFromUnityLogCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        for string in _COLOR_STRINGS:
            regions = self.view.find_all(string, sublime.LITERAL)
            for region in reversed(regions):
                self.view.erase(edit, region)
