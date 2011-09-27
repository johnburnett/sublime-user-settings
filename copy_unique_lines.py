import sublime, sublime_plugin

class copy_unique_lines(sublime_plugin.TextCommand):
    """For a given view (or selected part of a view), copy all the unique lines into the clipboard."""

    def run(self, edit):
        lineSet = set()
        lines = []
        for ln in self.iterLines():
            if ln not in lineSet:
                lineSet.add(ln)
                lines.append(ln)
        sublime.set_clipboard('\n'.join(lines))

    def iterLines(self):
        regions = self.view.sel()
        if len(regions) == 1 and regions[0].empty():
            regions = (sublime.Region(0, self.view.size()),)

        for region in regions:
            if region.empty():
                continue
            for ln in self.view.lines(region):
                if ln.empty():
                    continue
                ln = self.view.line(ln)
                yield self.view.substr(ln)
