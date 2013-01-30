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
                hostname = socket.gethostname().lower()
                packages_path = sublime.packages_path()
                host_settings_file = os.path.join(packages_path, "User", "per_host_settings.{0}.sublime-settings".format(hostname))
                try:
                    with open(host_settings_file) as f:
                        host_settings = json.load(f)
                except:
                    host_settings = None

                if host_settings:
                    print('Installing per-host settings from "{0}"'.format(host_settings_file))
                    for base_name, settings_values in host_settings.items():
                        settings = sublime.load_settings(base_name)
                        for name, value in settings_values.items():
                            print('  "{0}, {1} = {2}"'.format(base_name, name, value))
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
