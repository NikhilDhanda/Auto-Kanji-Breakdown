"""Inspect real runtime payloads offline: python -m tools.inspect_payloads."""
import json
from pathlib import Path

from src.akb.database import Database
from src.akb.extractor import extract
from src.akb.payload import build_payload, serialize

CASES = {
    'one_kanji': '人',
    'several_kanji': '階建語人水𠮟',
    'sentence': '新しい図書館の階段を上がり、日本語の本を読みました。',
    'repeated': '人' * 100,
    'deep': '鬱',
    'dictionary_only': '㐆',
}


def inspect():
    entries = Database(Path(__file__).resolve().parents[1] / 'generated/kanji_db.json').load()
    report = {}
    for name, text in CASES.items():
        chars = extract([text], entries)
        payload = build_payload(chars, entries)
        report[name] = {'source': text, 'chars': chars,
                        'utf8_bytes': len(serialize(payload).encode('utf-8')), 'payload': payload}
    for char in '階建語人水𠮟㐆':
        payload = build_payload([char], entries)
        report[char] = {'utf8_bytes': len(serialize(payload).encode('utf-8')), 'payload': payload}
    return report


if __name__ == '__main__':
    print(json.dumps(inspect(), ensure_ascii=True, indent=2))
