import sublime
import sublime_plugin


_PREFS_FILENAME = "Preferences.sublime-settings"


class DefaultFontSizeCommand(sublime_plugin.ApplicationCommand):
    def run(self):
        settings = sublime.load_settings(_PREFS_FILENAME)
        default_font_size = settings.get("font_size_default", 10)
        settings.set("font_size", default_font_size)
        sublime.save_settings(_PREFS_FILENAME)
