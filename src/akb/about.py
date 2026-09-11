"""Local desktop product information and packaged licence reader."""
from pathlib import Path

GITHUB = 'https://github.com/NikhilDhanda/Auto-Kanji-Breakdown'
ROOT = Path(__file__).resolve().parents[1]
# Source-checkout previews use the same canonical files as the release builder.
if ROOT.name == 'src' and (ROOT.parent / 'VERSION').is_file():
    ROOT = ROOT.parent

DOCUMENTS = (
    ('Sources and attribution', 'THIRD_PARTY_LICENSES.md'),
    ('Project credits', 'AUTHORS'),
    ('Software licence — AGPL v3 or later', 'LICENSE'),
    ('Data licence — CC BY-SA 4.0', 'licenses/CC-BY-SA-4.0.txt'),
    ('Data licence — CC BY-SA 3.0', 'licenses/CC-BY-SA-3.0.txt'),
    ('KanjiVG source notice', 'licenses/KanjiVG-source-notice.txt'),
)


def local_text(name):
    try:
        return (ROOT / name).read_text(encoding='utf8')
    except OSError:
        return 'Packaged information is unavailable. Reinstall the add-on to restore it.'


def show_licences(parent):
    from aqt.qt import QComboBox, QDialog, QPushButton, QTextEdit, QVBoxLayout, qconnect
    dialog = QDialog(parent)
    dialog.setWindowTitle('Auto Kanji Breakdown: Sources & Licences')
    area = dialog.screen().availableGeometry()
    dialog.resize(min(640, area.width() - 40), min(520, area.height() - 40))
    layout = QVBoxLayout(dialog)
    choices = QComboBox()
    for label, path in DOCUMENTS:
        choices.addItem(label, path)
    layout.addWidget(choices)
    view = QTextEdit()
    view.setReadOnly(True)
    layout.addWidget(view)
    # Plain text prevents bundled markup from loading external resources.
    qconnect(choices.currentIndexChanged, lambda _index: view.setPlainText(local_text(choices.currentData())))
    view.setPlainText(local_text(choices.currentData()))
    close = QPushButton('Close')
    qconnect(close.clicked, dialog.accept)
    layout.addWidget(close)
    dialog.exec()


def show_about(parent):
    from aqt.qt import QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, Qt, qconnect
    from aqt.utils import openLink
    dialog = QDialog(parent)
    dialog.setWindowTitle('About Auto Kanji Breakdown')
    layout = QVBoxLayout(dialog)
    text = QLabel('Auto Kanji Breakdown\nVersion ' + local_text('VERSION').strip() +
                  '\n\nCreated by Nik Dhanda\n\nGitHub:\n' + GITHUB +
                  '\n\nFree and open-source software.\nSoftware licence: AGPL-3.0-or-later')
    text.setTextFormat(Qt.TextFormat.PlainText)
    text.setWordWrap(True)
    layout.addWidget(text)
    actions = QHBoxLayout()
    github = QPushButton('GitHub')
    github.setAutoDefault(False)
    qconnect(github.clicked, lambda: openLink(GITHUB))
    actions.addWidget(github)
    licences = QPushButton('Sources & Licences')
    licences.setAutoDefault(False)
    qconnect(licences.clicked, lambda: show_licences(dialog))
    actions.addWidget(licences)
    layout.addLayout(actions)
    close = QPushButton('Close')
    close.setDefault(True)
    qconnect(close.clicked, dialog.accept)
    layout.addWidget(close)
    dialog.resize(min(440, dialog.screen().availableGeometry().width() - 40), dialog.sizeHint().height())
    dialog.exec()
