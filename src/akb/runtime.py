"""In-memory updates only: this module never saves a note or imports Qt."""
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass

from .config import validate_mapping
from .extractor import extract
from .payload import build_payload, serialize, safe_payload


PROTECTED_OUTPUT = 'The output contains non-generated content and was preserved. Check the dedicated output field in Setup.'


@dataclass(frozen=True)
class Refresh:
    changed: bool = False
    diagnostic: str = ''


class Runtime:
    def __init__(self, entries, config):
        self.entries = entries
        self.mappings = {m.notetype_id: m for m in config.mappings}
        self._paused = ContextVar('akb_paused', default=False)

    def check(self, note, *, manual=False):
        """Validate a target without altering it, including before an editor flush."""
        mapping = self.mappings.get(note.mid)
        if mapping is None:
            return 'This note type is not configured or is disabled.' if manual else ''
        problem = validate_mapping(mapping, note.note_type())
        if problem:
            return problem
        # Also verify the note object's name/index map, which may predate a rename.
        names = list(note.keys())
        current = [f['name'] for f in note.note_type()['flds']]
        if names != current:
            return 'Note field layout changed; reopen the editor before updating.'
        if manual and not safe_payload(note[mapping.output_field]):
            return PROTECTED_OUTPUT
        return ''

    def refresh(self, note, *, manual=False):
        problem = self.check(note, manual=manual)
        if problem:
            return Refresh(diagnostic=problem)
        mapping = self.mappings.get(note.mid)
        if mapping is None:
            return Refresh()
        chars = extract([note[name] for name in mapping.source_fields], self.entries)
        value = serialize(build_payload(chars, self.entries)) if chars else ''
        if note[mapping.output_field] == value:
            return Refresh()
        note[mapping.output_field] = value
        return Refresh(changed=True)

    def before_save(self, note):
        if self._paused.get():
            return Refresh()
        return self.refresh(note)

    @contextmanager
    def suspend_hook(self):
        token = self._paused.set(True)
        try:
            yield
        finally:
            self._paused.reset(token)
