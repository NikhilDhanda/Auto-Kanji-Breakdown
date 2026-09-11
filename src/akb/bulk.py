"""Background worker logic using public collection methods; no GUI access."""
from dataclasses import dataclass, field
import logging

from .config import validate_mapping
from .runtime import PROTECTED_OUTPUT

logger = logging.getLogger(__name__)


@dataclass
class BulkResult:
    changes: object
    scanned: int = 0
    changed: int = 0
    skipped: int = 0
    cancelled: bool = False
    diagnostics: list[str] = field(default_factory=list)
    error: str = ''
    total: int = 0
    processed: int = 0
    unchanged: int = 0
    failed: int = 0
    pending: int = 0
    protected: int = 0


def regenerate(col, runtime, empty_changes, progress=lambda done, total: None,
               cancelled=lambda: False, batch_size=100, *, note_ids=None):
    if batch_size <= 0:
        raise ValueError('batch_size must be positive')
    result = BulkResult(empty_changes)
    target = None
    selected = note_ids is not None
    pending = []
    try:
        ids = set(note_ids) if selected else set()
        if not selected:
            for mapping in runtime.mappings.values():
                if cancelled():
                    result.cancelled = True
                    return result
                problem = validate_mapping(mapping, col.models.get(mapping.notetype_id))
                if problem:
                    result.diagnostics.append(f'Note type {mapping.notetype_id}: {problem}')
                    continue
                # Numeric, validated ID: no user-provided search syntax or SQL.
                ids.update(col.find_notes(f'mid:{mapping.notetype_id}'))
        ids = sorted(ids)
        result.total = len(ids)
        progress(0, len(ids))
        with runtime.suspend_hook():
            for start in range(0, len(ids), batch_size):
                pending = []
                for nid in ids[start:start + batch_size]:
                    if cancelled():
                        result.cancelled = True
                        result.pending = len(pending)
                        return result  # unsaved current batch is discarded
                    result.scanned += 1
                    try:
                        note = col.get_note(nid)
                        if note.mid in runtime.mappings:
                            result.processed += 1
                        refreshed = runtime.refresh(note, manual=True) if selected else runtime.refresh(note)
                    except Exception as error:
                        if not selected:
                            raise
                        # Read/generation failed before committing: other notes
                        # remain independent. A write/undo failure below stops work.
                        result.failed += 1
                        logger.error('Selected note regeneration failed (%s)', type(error).__name__)
                        progress(result.scanned, len(ids))
                        continue
                    if refreshed.diagnostic:
                        result.skipped += 1
                        result.protected += refreshed.diagnostic == PROTECTED_OUTPUT
                        if refreshed.diagnostic not in result.diagnostics:
                            result.diagnostics.append(refreshed.diagnostic)
                    if refreshed.changed:
                        pending.append(note)
                    elif not refreshed.diagnostic:
                        result.unchanged += 1
                    progress(result.scanned, len(ids))
                if cancelled():
                    result.cancelled = True
                    result.pending = len(pending)
                    return result
                if pending:
                    changes = col.update_notes(pending)
                    result.changed += len(pending)
                    result.changes = changes
                    pending.clear()
                    if target is None:
                        # First successful batch is the undo anchor; no empty undo
                        # entry when nothing changes or the first update fails.
                        target = col.undo_status().last_step
                    else:
                        result.changes = col.merge_undo_entries(target)
    except Exception as error:
        # Preserve committed batches and report partial completion to the UI.
        # Do not log note contents, SQL, or exception messages from other add-ons.
        logger.error('Bulk regeneration stopped (%s)', type(error).__name__)
        result.error = 'Regeneration stopped after an error. Completed batches remain undoable; retry after checking configuration.'
        result.pending = len(pending)
    return result
