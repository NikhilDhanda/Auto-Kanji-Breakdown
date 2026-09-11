"""Strict owned markers. Outside bytes are never normalized or reformatted."""
from pathlib import Path
import re

RENDERER_VERSION = 6
# Keep saved identifiers stable when renaming the visible palettes.
THEME_LABELS = {'light': 'Light', 'dark': 'Dark', 'classic': 'Blue',
                'brown': 'Brown', 'matcha': 'Matcha', 'matcha-dark': 'Matcha Dark',
                'sakura-light': 'Sakura', 'sakura': 'Sakura Dark'}
THEMES = tuple(THEME_LABELS)
WEB = Path(__file__).parent / 'web'


class IntegrationError(ValueError):
    pass


def parse_theme(value):
    """Presentation-only fallback for absent/unknown saved theme names."""
    return value if isinstance(value, str) and value in THEMES else 'classic'


def spans(text, css=False):
    start, end = ('/* ', ' */') if css else ('<!-- ', ' -->')
    pattern = re.compile(re.escape(start) + r'AKB:START owner=([a-f0-9]{32}) renderer=(\d+)' + re.escape(end)
                         + r'.*?' + re.escape(start) + r'AKB:END owner=\1' + re.escape(end), re.S)
    matches = list(pattern.finditer(text))
    if text.count('AKB:') != len(matches) * 2:
        raise IntegrationError('Damaged renderer markers. Restore intact blocks before continuing.')
    if len(matches) > 1:
        raise IntegrationError('Duplicate renderer blocks. Resolve the duplicate before continuing.')
    return matches


def status(text, owner, css=False):
    matches = spans(text, css)
    if not matches:
        return 'not installed'
    match = matches[0]
    if match[1] != owner:
        raise IntegrationError('Renderer block belongs to an unknown ownership record.')
    return 'current' if int(match[2]) == RENDERER_VERSION else 'outdated'


def replace(text, owner, block=None, css=False):
    status(text, owner, css)
    matches = spans(text, css)
    if matches:
        m = matches[0]
        return text[:m.start()] + (block or '') + text[m.end():]
    return text + (block or '')


def wrap(content, owner, css=False):
    if not re.fullmatch('[a-f0-9]{32}', owner):
        raise IntegrationError('Invalid ownership identifier.')
    start, end = ('/* ', ' */') if css else ('<!-- ', ' -->')
    return (f'{start}AKB:START owner={owner} renderer={RENDERER_VERSION}{end}\n'
            + content + f'\n{start}AKB:END owner={owner}{end}')


def html_block(field, owner, theme='classic'):
    # Field names enter Anki template syntax, not arbitrary markup/JS.
    if not field or any(c in field for c in '{}<>:\r\n') or field.startswith(('#', '/', '^', '!')):
        raise IntegrationError('This field name cannot safely be used in a renderer template.')
    if not isinstance(theme, str) or theme not in THEMES:
        raise IntegrationError('Choose a supported appearance theme.')
    js = (WEB / 'renderer.js').read_text(encoding='utf-8')
    return wrap(f'<div class="akb-root" data-akb-owner="{owner}" data-akb-theme="{theme}">\n'
                + '<script type="application/json" class="akb-data">{{' + field + '}}</script>\n</div>\n'
                + '<script>\n' + js + '\n</script>', owner)


def css_block(owner):
    return wrap((WEB / 'renderer.css').read_text(encoding='utf-8'), owner, True)
