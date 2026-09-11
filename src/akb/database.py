"""Load and validate only the generated runtime JSON, never upstream archives."""
import json
from pathlib import Path
from threading import Lock


class DatabaseError(ValueError):
    pass


def validate(data):
    def require(ok):
        if not ok:
            raise DatabaseError('The kanji database is invalid. Rebuild or reinstall the database.')

    def strings(value):
        return isinstance(value, list) and all(isinstance(v, str) and v for v in value)

    require(isinstance(data, dict))
    if type(data.get('schema_version')) is not int or data['schema_version'] != 1:
        raise DatabaseError('Unsupported kanji database schema; this runtime requires version 1.')
    require(data.get('generated') is True and isinstance(data.get('sources'), dict))
    entries = data.get('entries')
    require(isinstance(entries, dict) and bool(entries))

    def node(value, depth=0):
        require(isinstance(value, dict) and depth < 100)
        for key, item in value.items():
            if key == 'children':
                require(isinstance(item, list))
                for child in item:
                    node(child, depth + 1)
            elif key in {'variant', 'partial', 'tradForm', 'radicalForm'}:
                require(type(item) is bool)
            elif key in {'char', 'base', 'position', 'radical', 'phon', 'part', 'number'}:
                require(isinstance(item, str) and bool(item))
            else:
                require(False)

    for char, entry in entries.items():
        require(len(char) == 1 and not 0xD800 <= ord(char) <= 0xDFFF and isinstance(entry, dict))
        require(strings(entry.get('meanings')))
        readings = entry.get('readings')
        require(isinstance(readings, dict) and set(readings) == {'on', 'kun'})
        require(all(strings(v) for v in readings.values()))
        for key in ('strokes', 'frequency'):
            if key in entry:
                require(type(entry[key]) is int and entry[key] > 0)
        if 'structure' in entry:
            node(entry['structure'])
            require(entry['structure'].get('char') == char)
    return entries


class Database:
    def __init__(self, path=None):
        self.path = Path(path) if path is not None else Path(__file__).resolve().parents[1] / 'data/kanji_db.json'
        self._entries = None
        self._lock = Lock()
        self.explicit = path is not None
        self.manifest = None
        self.origin = 'Bundled'
        self.fallback_reason = ''

    def load(self):
        with self._lock:
            if self._entries is None:
                try:
                    from .data_store import Store, manifest, provenance
                    if self.explicit:
                        raw = self.path.read_bytes()
                        data = json.loads(raw)
                        validate(data)
                        if {'kanjidic2', 'kanjivg'} <= data['sources'].keys():
                            self.manifest = manifest(data, raw)
                    else:
                        store = Store(self.path, self.path.parent.parent / 'user_files/akb_updates')
                        data, self.manifest, self.origin = store.load()
                        self.fallback_reason = store.fallback_reason
                    self._entries = Entries(validate(data))
                    self._entries.provenance = provenance(self.manifest) if self.manifest else None
                except (OSError, UnicodeError, json.JSONDecodeError, RecursionError) as error:
                    raise DatabaseError('Cannot read the kanji database. Rebuild or reinstall it.') from error
            return self._entries


class Entries(dict):
    """One immutable-in-use entry snapshot, with compact provenance alongside it."""
    provenance = None
