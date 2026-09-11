"""Offline, deterministic Anki release assembly and exact-content validation.

Copyright 2026 Nik Dhanda
SPDX-License-Identifier: AGPL-3.0-or-later
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
MODULES = ('results', 'about', 'build_data', 'data_store', 'updater', 'update_service', '__init__', 'bulk', 'cleanup', 'commands', 'config', 'database',
           'dialogs', 'extractor', 'integration', 'payload', 'runtime',
           'setup', 'setup_ui', 'templates')
RUNTIME = ('__init__.py', 'config.json', 'akb/web/renderer.js', 'akb/web/renderer.css') + tuple(
    'akb/' + name + '.py' for name in MODULES)
LEGAL = ('LICENSE', 'AUTHORS', 'THIRD_PARTY_LICENSES.md',
         'licenses/CC-BY-SA-3.0.txt', 'licenses/CC-BY-SA-4.0.txt',
         'licenses/EDRDG-licence.html', 'licenses/KANJIDIC-documentation.html',
         'licenses/KanjiVG-documentation.html', 'licenses/KanjiVG-source-notice.txt',
         'licenses/README.md', 'licenses/sources.json')
MANIFEST = {'package': 'auto_kanji_breakdown', 'name': 'Auto Kanji Breakdown'}
STAMP = (1980, 1, 1, 0, 0, 0)


def version(root=ROOT):
    value = (root / 'VERSION').read_text(encoding='utf-8').strip()
    if not re.fullmatch(r'\d+\.\d+\.\d+(?:-[a-z]+\.\d+)?', value):
        raise ValueError('Invalid release VERSION')
    return value


def read_file(root, relative):
    path = root / relative
    if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
        raise ValueError('Release input escapes the project: ' + relative)
    return path.read_bytes()


def inputs(root=ROOT):
    """An explicit allowlist prevents new scratch files from entering a release."""
    files = {name: read_file(root, 'src/' + name) for name in RUNTIME}
    # Runtime config is shipped as defaults, never a developer's saved mappings.
    if json.loads(files['config.json']) != {'version': 1, 'mappings': []}:
        raise ValueError('Runtime config.json must contain clean empty defaults')
    for name in RUNTIME:
        if re.search(rb'(?:-----BEGIN [A-Z ]*PRIVATE KEY-----|gh[pousr]_[A-Za-z0-9]{20,}|AKIA[A-Z0-9]{16}|[A-Za-z]:[\\/]Users[\\/])', files[name]):
            raise ValueError('Potential secret or personal path in runtime file: ' + name)
    files.update({name: read_file(root, name) for name in LEGAL})
    if (b'GNU AFFERO GENERAL PUBLIC LICENSE' not in files['LICENSE']
            or b'AGPL-3.0-or-later' not in files['AUTHORS']):
        raise ValueError('Missing project AGPL licence/declaration')
    files['VERSION'] = (version(root) + '\n').encode('utf-8')
    files['manifest.json'] = (json.dumps(MANIFEST, sort_keys=True, separators=(',', ':')) + '\n').encode('utf-8')
    files['data/manifest.json'] = read_file(root, 'generated/manifest.json')
    files['data/kanji_db.json'] = read_file(root, 'generated/kanji_db.json')
    # Use both the builder's full schema check and the runtime consumer check.
    from tools.build_database import validate as validate_master
    from src.akb.database import validate as validate_runtime
    data = json.loads(files['data/kanji_db.json'])
    validate_master(data)
    validate_runtime(data)
    from src.akb.data_store import validate_pair
    validate_pair(files['data/kanji_db.json'], json.loads(files['data/manifest.json']))
    for name, source in json.loads(files['licenses/sources.json']).items():
        if name not in files or hashlib.sha256(files[name]).hexdigest() != source['sha256']:
            raise ValueError('Upstream license/documentation checksum mismatch: ' + name)
    return files


def validate_archive(path, root=ROOT):
    expected = inputs(root)
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)) or set(names) != set(expected):
            raise ValueError('Package contains missing, duplicate or unexpected files')
        if names != sorted(names) or archive.comment or archive.testzip() is not None:
            raise ValueError('Invalid package ordering, comment or CRC')
        for info in archive.infolist():
            if (info.date_time != STAMP or info.compress_type != zipfile.ZIP_STORED
                    or info.create_system != 3 or info.external_attr != (0o100644 << 16)
                    or info.extra or info.comment):
                raise ValueError('Noncanonical ZIP metadata: ' + info.filename)
            if archive.read(info) != expected[info.filename]:
                raise ValueError('Package bytes differ from release inputs: ' + info.filename)
    return {'version': version(root), 'files': names, 'bytes': path.stat().st_size,
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'database_sha256': hashlib.sha256(expected['data/kanji_db.json']).hexdigest()}


def build(root=ROOT, output=None):
    files = inputs(root)
    output = Path(output) if output else root / 'dist' / ('Auto-Kanji-Breakdown-' + version(root) + '.ankiaddon')
    # Do not let a custom destination overwrite source or the master database.
    if output.suffix != '.ankiaddon':
        raise ValueError('Output must end in .ankiaddon')
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=output.parent, suffix='.tmp', delete=False) as handle:
        staged = Path(handle.name)
    try:
        with zipfile.ZipFile(staged, 'w', compression=zipfile.ZIP_STORED) as archive:
            for name, data in sorted(files.items()):
                info = zipfile.ZipInfo(name, STAMP)
                info.create_system = 3
                info.external_attr = 0o100644 << 16
                archive.writestr(info, data)
        report = validate_archive(staged, root)
        staged.replace(output)
        return output, report
    finally:
        staged.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--validate', type=Path, help='Validate an existing archive against current release inputs')
    args = parser.parse_args()
    if args.validate:
        report = validate_archive(args.validate)
    else:
        path, report = build(output=args.output)
        print(path)
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
