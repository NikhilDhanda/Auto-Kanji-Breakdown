"""Recover field text without markup, ruby annotations, or media filenames."""
from html.parser import HTMLParser
import re


class FieldText(HTMLParser):
    IGNORED = {'rt', 'rp', 'script', 'style', 'template'}
    BLOCKS = {'br', 'div', 'p', 'li', 'tr'}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.hidden = []
        self.text = []

    def handle_starttag(self, tag, attrs):
        if tag in self.IGNORED:
            self.hidden.append(tag)
        elif not self.hidden and tag in self.BLOCKS:
            self.text.append('\n')

    def handle_startendtag(self, tag, attrs):
        if not self.hidden and tag in self.BLOCKS:
            self.text.append('\n')

    def handle_endtag(self, tag):
        if tag in self.hidden:
            self.hidden = self.hidden[:self.hidden.index(tag)]
        if not self.hidden and tag in self.BLOCKS:
            self.text.append('\n')

    def handle_data(self, data):
        if not self.hidden:
            self.text.append(data)


def plain_text(field):
    parser = FieldText()
    parser.feed(field)
    parser.close()
    return re.sub(r'\[sound:[^\]]*\]', '', ''.join(parser.text))


def extract(fields, entries):
    seen = set()
    result = []
    for field in fields:
        for char in plain_text(field):
            if char in entries and char not in seen:
                seen.add(char)
                result.append(char)
    return result
