import sublime
import sublime_plugin
import socket

class per_host_settings(sublime_plugin.EventListener):
    def __init__(self):
        self._per_host_settings = {
            'lapmonkey': {
                'Base File.sublime-settings': {
                    'font_size': 14
                }
            }
        }
        self._applying = False

    def install_callbacks(self):
        callbacks = []
        print "Installing per-host settings callbacks"
        if not globals().has_key('_per_host_settings_callbacks_installed'):
            try:
                hostname = socket.gethostname().lower()
                host_settings = self._per_host_settings.get(hostname, None)
                if host_settings:
                    for base_name, settings_values in host_settings.iteritems():
                        settings = sublime.load_settings(base_name)
                        for name, value in settings_values.iteritems():
                            print '  "%s, %s = %s"' % (base_name, name, value)
                            callback = lambda: self.apply_value(settings, name, value)
                            callbacks.append(callback)
                            settings.add_on_change(name, callback)
            finally:
                global _per_host_settings_callbacks_installed
                _per_host_settings_callbacks_installed = True
        return callbacks

    def on_activated(self, view):
        # Apply once on startup, before the settings on_change callbacks
        # have a chance to run.
        callbacks = self.install_callbacks()
        print "Applying all per-host settings"
        for callback in callbacks:
            callback()
        sublime_plugin.all_callbacks['on_activated'].remove(self)

    def apply_value(self, settings, name, value):
        if not self._applying:
            try:
                self._applying = True
                print 'Applying per-host setting "%s = %s"' % (name, value)
                settings.set(name, value)
            finally:
                self._applying = False
