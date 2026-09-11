"""Write a local renderer fixture; never changes a collection or the master DB."""
import argparse
from pathlib import Path

from src.akb.database import Database
from src.akb.extractor import extract
from src.akb.payload import build_payload, serialize
from src.akb.templates import html_block, css_block, THEMES

SENTENCE = '新しい図書館の階段を上がり、日本語の本を読みました。'


def preview(theme='classic'):
    entries = Database(Path(__file__).resolve().parents[1] / 'generated/kanji_db.json').load()
    samples = [('Representative characters', '階建語人水𠮟㐆鬱'), ('Realistic sentence', SENTENCE),
               ('Visual polish inspection', '麗麻薬常習学校娘息蹴磨風邪'), ('Long readings and senses', '生息')]
    sections = []
    for index, (title, text) in enumerate(samples):
        value = serialize(build_payload(extract([text], entries), entries))
        block = html_block('Generated', str(index + 1) * 32, theme).replace('{{Generated}}', value)
        sections.append(f'<h2>{title}</h2><p>{text}</p>' + block)
    return ('<!doctype html><html lang="en"><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            '<title>Auto Kanji Breakdown renderer preview</title><style>'
            'body{margin:16px;background:#1d2030;color:#c3c9ed;font:16px system-ui}h2,p{max-width:780px;margin:16px auto}'
            + css_block('1' * 32) + '</style><body class="nightMode">' + ''.join(sections) + '</body></html>')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    parser.add_argument('--theme', choices=THEMES, default='classic')
    args = parser.parse_args()
    args.output.write_text(preview(args.theme), encoding='utf-8')
    print(args.output.resolve())
