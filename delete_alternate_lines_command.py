import sublime
import sublime_plugin


class delete_alternate_lines_command(sublime_plugin.TextCommand):
    def run(self, edit):
        sel = self.view.sel()
        if not sel:
            return

        cur_line = self.view.full_line(sel[0].begin())

        while True:
            kill_line = self.view.full_line(cur_line.end())
            self.view.erase(edit, kill_line)
            cur_line = self.view.full_line(kill_line.begin())
            if cur_line.end() == self.view.size():
                break
