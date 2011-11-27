"""Show the current line ending mode in the status bar."""

if __name__ != '__main__':
    import sublime, sublime_plugin

    class file_info_status_bar(sublime_plugin.EventListener):
        def on_modified(self, view):
            view.set_status('file_info', view.line_endings() + ', ' + view.encoding())
    file_info_status_bar.on_load = file_info_status_bar.on_modified
    file_info_status_bar.on_post_save = file_info_status_bar.on_modified
else:
    # Test to see how Sublime deals with files containing mixed line endings.
    # Behavior seems to be:
    # On open, a file's line ending mode is auto-detected:
    # - If the file has any LF's, it's Unix
    # - If the file is all CR's, it's Mac
    # - Any other combo is Windows
    # On save, all line endings are converted to the detected type.
    if False:
        CR = chr(0x0D)
        LF = chr(0x0A)
        endtypes = {'u':LF, 'w':CR+LF, 'm':CR}
        def writefile(endings):
            with open('line-%s.dat' % endings, 'wb') as hfile:
                hfile.write('x'.join([endtypes[e] for e in endings]))
        for test in ['uu', 'ww', 'mm', 'wu', 'wm', 'mu', 'mw', 'um', 'uw']:
            writefile(test)
    else:
        import glob
        for fname in glob.glob('*.dat'):
            print '%s: %r' % (fname, open(fname,'rb').read())
