import re
import webbrowser

import sublime, sublime_plugin

# URL regex from http://daringfireball.net/2010/07/improved_regex_for_matching_urls
url_re = re.compile(r"""
(?P<url>                                # Capture 1: entire matched URL
  (?:
    [a-z][\w-]+:                        # URL protocol and colon
    (?:
      /{1,3}                            # 1-3 slashes
      |                                 #   or
      [a-z0-9%]                         # Single letter or digit or '%'
                                        # (Trying not to match e.g. "URI::Escape")
    )
    |                                   #   or
    www\d{0,3}[.]                       # "www.", "www1.", "www2." ... "www999."
    |                                   #   or
    [a-z0-9.\-]+[.][a-z]{2,4}/          # looks like domain name followed by a slash
  )
  (?:                                   # One or more:
    [^\s()<>]+                          # Run of non-space, non-()<>
    |                                   #   or
    \(([^\s()<>]+|(\([^\s()<>]+\)))*\)  # balanced parens, up to 2 levels
  )+
  (?:                                   # End with:
    \(([^\s()<>]+|(\([^\s()<>]+\)))*\)  # balanced parens, up to 2 levels
    |                                   #   or
    [^\s`!()\[\]{};:'".,<>?]            # not a space or one of these punct chars
  )
)""", re.VERBOSE | re.MULTILINE)

class open_url_in_selection(sublime_plugin.TextCommand):

    def run(self, edit):
        url = self.get_url_in_sel()
        if url:
            webbrowser.open_new_tab(url)

    def is_enabled(self):
        return True if self.get_url_in_sel() else False

    def get_url_in_sel(self):
        for region in self.view.sel():
            fullRegion = self.view.line(region)
            for lineRegion in self.view.split_by_newlines(fullRegion):
                line = self.view.substr(lineRegion)
                for match in url_re.finditer(line):
                    span = match.span('url')
                    matchRegion = sublime.Region(span[0] + lineRegion.begin(), span[1] + lineRegion.begin())
                    if region.intersects(matchRegion):
                        return match.group('url')
