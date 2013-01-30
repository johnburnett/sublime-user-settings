"""Show current file info in the status bar (line ending, encoding, etc)."""

if __name__ != '__main__':
    import sublime_plugin

    class file_info_status_bar(sublime_plugin.EventListener):
        def _update(self, view):
            view.set_status('file_info', view.line_endings() + ', ' + view.encoding())

    for meth in ('on_modified', 'on_load', 'on_post_save'):
        setattr(file_info_status_bar, meth, file_info_status_bar._update)
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
            with open('line-{0}.dat'.format(endings), 'wb') as hfile:
                hfile.write('x'.join([endtypes[e] for e in endings]))
        for test in ['uu', 'ww', 'mm', 'wu', 'wm', 'mu', 'mw', 'um', 'uw']:
            writefile(test)
    else:
        import glob
        for fname in glob.glob('*.dat'):
            print('{0!s}: {1!r}'.format(fname, open(fname,'rb').read()))
