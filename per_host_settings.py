import json
import os
import socket

import sublime
import sublime_plugin

class per_host_settings(sublime_plugin.EventListener):
    def __init__(self):
        self._applying = False

    def install_callbacks(self):
        callbacks = []
        if '_per_host_settings_callbacks_installed' not in globals():
            try:
                host_settings_file = 'per_host_settings.sublime-settings'
                all_host_settings = sublime.load_settings(host_settings_file)
                hostname = socket.gethostname().lower()
                host_settings = all_host_settings.get(hostname)
                if host_settings is None:
                    return callbacks
                if not isinstance(host_settings, dict):
                    sublime.error_message('Settings for host "%s" is not a dict in "%s".' % (hostname, host_settings_file))
                    return callbacks

                universal_settings = host_settings.get('universal', {})
                if not isinstance(universal_settings, dict):
                    sublime.error_message('"universal" host settings is not a dict in "%s".' % host_settings_file)
                    return callbacks

                platform_settings = host_settings.get(sublime.platform(), {})
                if not isinstance(platform_settings, dict):
                    sublime.error_message('"%s" host settings is not a dict in "%s".' % (host_settings_file, sublime.platform()))
                    return callbacks

                composite_settings = universal_settings
                for settings_file, overlay_settings in platform_settings.items():
                    settings_values = composite_settings.setdefault(settings_file, {})
                    settings_values.update(overlay_settings)
                    for key in list(settings_values.keys()):
                        if settings_values[key] is None:
                            del settings_values[key]

                for settings_file in list(composite_settings.keys()):
                    if not composite_settings[settings_file]:
                        del composite_settings[settings_file]
                if not composite_settings:
                    return callbacks

                print('Installing per-host settings for "%s"' % hostname)
                for settings_file, settings_values in composite_settings.items():
                    settings = sublime.load_settings(settings_file)
                    for name, value in settings_values.items():
                        print('  "{0}, {1} = {2}"'.format(settings_file, name, value))
                        def make_callback(settings, name, value):
                            return lambda: self.apply_value(settings, name, value)
                        callback = make_callback(settings, name, value)
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
        for callback in callbacks:
            callback()
        sublime_plugin.all_callbacks['on_activated'].remove(self)

    def apply_value(self, settings, name, value):
        if not self._applying:
            try:
                self._applying = True
                print('Applying per-host setting "{0} = {1}"'.format(name, value))
                settings.set(name, value)
            finally:
                self._applying = False
