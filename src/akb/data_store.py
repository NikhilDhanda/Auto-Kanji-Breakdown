"""Immutable database generations, atomic selection and bundled fallback."""
import hashlib
import json
from pathlib import Path
import re
import shutil
import tempfile
from .build_data import encode, validate, write_atomic

COMPATIBILITY = 1
OWNER = 'Auto Kanji Breakdown database updates v1'
MAX_DATABASE = 64 * 1024 * 1024


def digest(data):
    return hashlib.sha256(data).hexdigest()


def manifest(data, raw, retrieved=None, http=None, release=None):
    sources = data['sources']
    kd = dict(sources['kanjidic2'])
    kd.update(snapshot=kd.get('date_of_creation'), retrieved=retrieved)
    if http:
        kd.update({k: http[k] for k in ('etag', 'last_modified') if http.get(k)})
    vg = dict(sources['kanjivg'])
    match = re.fullmatch(r'kanjivg-(\d{8})-main.zip', vg['file'])
    vg['release'] = release or ('r' + match[1] if match else None)
    return {'manifest_version': 1, 'builder': COMPATIBILITY, 'schema_version': 1,
            'sha256': digest(raw), 'retrieved': retrieved,
            'sources': {'kanjidic2': kd, 'kanjivg': vg}}


def validate_pair(raw, meta):
    if len(raw) > MAX_DATABASE:
        raise ValueError('Database size limit')
    if not isinstance(meta, dict):
        raise ValueError('Invalid database manifest')
    if (type(meta.get('manifest_version')) is not int or meta.get('manifest_version') != 1 or meta.get('builder') != COMPATIBILITY
            or meta.get('schema_version') != 1 or meta.get('sha256') != digest(raw)):
        raise ValueError('Database manifest/hash is incompatible')
    data = json.loads(raw)
    validate(data)
    for name in ('kanjidic2', 'kanjivg'):
        if not isinstance(meta.get('sources'), dict) or not isinstance(meta['sources'].get(name), dict):
            raise ValueError('Missing source manifest')
        if meta['sources'][name]['sha256'] != data['sources'][name]['sha256']:
            raise ValueError('Source manifest mismatch')
    if meta['sources']['kanjidic2'].get('snapshot') != data['sources']['kanjidic2'].get('date_of_creation'):
        raise ValueError('Snapshot manifest mismatch')
    return data


def provenance(meta):
    kd, vg = meta['sources']['kanjidic2'], meta['sources']['kanjivg']
    return {k: v for k, v in {'kd': kd.get('snapshot'), 'vg': vg.get('release'),
                              'db': meta['sha256'][:12]}.items() if v}


class Store:
    def __init__(self, bundled=None, user=None):
        base = Path(__file__).resolve().parents[1]
        self.bundled = Path(bundled) if bundled else base / 'data/kanji_db.json'
        self.root = Path(user) if user else base / 'user_files/akb_updates'
        self.fallback_reason = ''

    def read_json(self, name, default=None):
        try:
            path = self.checked_path(self.root / name)
            if path.stat().st_size > 256 * 1024:
                raise ValueError('Update metadata size limit')
            return json.loads(path.read_text(encoding='utf8'))
        except (OSError, ValueError):
            return {} if default is None else default

    def checked_path(self, path):
        root = self.root.resolve()
        if (root != self.root.parent.resolve() / self.root.name
                or path.is_symlink() or not path.resolve().is_relative_to(root)):
            raise ValueError('Unsafe update path')
        return path

    def initialize(self):
        for name in ('owner.json', 'current.json', 'update_state.json', 'database', 'sources'):
            self.checked_path(self.root / name)
        if self.root.is_symlink():
            raise ValueError('Unsafe update directory')
        marker = self.root / 'owner.json'
        if self.root.exists() and not marker.exists() and any(self.root.iterdir()):
            raise ValueError('Update directory is not owned by this add-on')
        self.root.mkdir(parents=True, exist_ok=True)
        if marker.exists() and json.loads(marker.read_text(encoding='utf8')) != OWNER:
            raise ValueError('Unknown update directory owner')
        write_atomic(marker, encode(OWNER))

    def load(self):
        try:
            pointer = self.read_json('current.json')
            if not isinstance(pointer, dict):
                raise ValueError('Invalid database selection')
            name = pointer.get('generation', '')
            if not re.fullmatch('[a-f0-9]{64}', name):
                raise ValueError('No compatible user database selected')
            folder = self.root / 'database' / name
            path = self.checked_path(folder / 'kanji_db.json')
            sidecar = self.checked_path(folder / 'manifest.json')
            if path.stat().st_size > MAX_DATABASE or sidecar.stat().st_size > 256 * 1024:
                raise ValueError('Database/manifest size limit')
            raw = path.read_bytes()
            meta = json.loads(sidecar.read_text(encoding='utf8'))
            return validate_pair(raw, meta), meta, 'Updated'
        except (OSError, ValueError, KeyError, TypeError, RecursionError) as error:
            self.fallback_reason = type(error).__name__
        raw = self.bundled.read_bytes()
        sidecar = self.bundled.with_name('manifest.json')
        meta = json.loads(sidecar.read_text(encoding='utf8')) if sidecar.exists() else manifest(json.loads(raw), raw)
        return validate_pair(raw, meta), meta, 'Bundled'

    def stage(self, raw, meta):
        validate_pair(raw, meta)
        self.initialize()
        parent = self.root / 'database'
        parent.mkdir(exist_ok=True)
        target = parent / digest(raw)
        self.checked_path(target)
        if target.exists():
            # Never trust an existing hash-named directory merely by its name.
            validate_pair((target / 'kanji_db.json').read_bytes(),
                          json.loads((target / 'manifest.json').read_text(encoding='utf8')))
            return target.name
        with tempfile.TemporaryDirectory(dir=parent) as temporary:
            folder = Path(temporary)
            (folder / 'kanji_db.json').write_bytes(raw)
            (folder / 'manifest.json').write_bytes(encode(meta))
            folder.rename(target)
        return target.name

    def clear(self):
        """Only explicit cleanup of our marked namespace; unrelated user_files stay."""
        if not self.root.exists():
            return
        self.checked_path(self.root)
        if self.root.is_symlink() or self.read_json('owner.json') != OWNER:
            raise ValueError('Cannot prove ownership of update files')
        for path in self.root.rglob('*'):
            if path.is_symlink() or not path.resolve().is_relative_to(self.root.resolve()):
                raise ValueError('Unsafe path in update files')
        shutil.rmtree(self.root)

    def prune(self, state):
        """Bound cache growth, retaining only the active validated generation."""
        pointer = self.read_json('current.json')
        keep = {pointer.get('generation')} if isinstance(pointer, dict) else set()
        parent = self.root / 'database'
        if parent.exists() and not parent.is_symlink():
            for folder in parent.iterdir():
                if (folder.name in keep or not re.fullmatch('[a-f0-9]{64}', folder.name)
                        or not folder.is_dir() or folder.is_symlink()):
                    continue
                children = list(folder.iterdir())
                if {p.name for p in children} == {'kanji_db.json', 'manifest.json'} and all(p.is_file() and not p.is_symlink() for p in children):
                    for path in children:
                        path.unlink()
                    folder.rmdir()
        keep_sources = {v.get('sha256') for v in state.get('http', {}).values() if isinstance(v, dict)}
        parent = self.root / 'sources'
        if parent.exists() and not parent.is_symlink():
            for path in parent.iterdir():
                if re.fullmatch('[a-f0-9]{64}', path.name) and path.name not in keep_sources and path.is_file() and not path.is_symlink():
                    path.unlink()
