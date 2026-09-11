"""Accurate operation summaries, independent of Qt and collection writes."""
from dataclasses import dataclass
from html import escape


@dataclass
class CleanupResult:
    mode: str
    notes_cleared: int = 0
    templates_removed: int = 0
    styling_removed: bool = False
    deleted: tuple = ()
    retained: tuple = ()  # (field name, reason)
    protected: int = 0
    settings_changed: bool = False
    updater_disabled: bool = False


def count(number, singular, plural=None):
    return f'{number:,} {singular if number == 1 else (plural or singular + "s")}'


def cleanup_text(result, files=None):
    changed = (result.notes_cleared or result.templates_removed or result.styling_removed
               or result.deleted or result.settings_changed or result.updater_disabled or files in ('removed', 'removed_reload_failed'))
    lines = ['Cleanup complete' if changed else 'Nothing to clean up', '']
    if result.mode == 'renderer':
        lines.append('Generated breakdown data was kept.')
    elif result.notes_cleared:
        lines.append(count(result.notes_cleared, 'breakdown') + ' removed.')
    else:
        lines.append('No generated breakdown data needed removing.')
    if result.templates_removed:
        lines.append('The breakdown display was removed from ' + count(result.templates_removed, 'card template') + '.')
    elif result.styling_removed:
        lines.append('The remaining breakdown styling was removed.')
    elif result.mode == 'data':
        lines.append('Your card templates were kept.')
    for name in result.deleted:
        lines.append(f'The "{name}" field was deleted.')
    for name, reason in result.retained:
        ending = {'not_created': ' because it was not created by Auto Kanji Breakdown',
                  'unverified': ' because it could not be verified as created by Auto Kanji Breakdown',
                  'not_requested': ' because field deletion was not selected'}.get(reason, '')
        lines.append(f'The "{name}" field was kept' + ending + '.')
    if result.protected:
        lines.append(count(result.protected, 'note') + ' had unsupported field content that was preserved.')
    if result.settings_changed and result.mode != 'renderer':
        lines.append('Automatic breakdown updates are now off for this note type.')
    if files is not None:
        lines.append({'removed': 'Automatic data update files were removed.',
                      'absent': 'No automatic data update files needed removing.',
                      'failed': 'Automatic data update files could not be removed.',
                      'removed_reload_failed': 'Automatic data update files were removed, but the bundled kanji data could not be reloaded. Check Status & Diagnostics.',
                      'absent_reload_failed': 'No automatic data update files needed removing, but the bundled kanji data could not be reloaded. Check Status & Diagnostics.'}[files])
        lines.append('Automatic kanji data updates are off.')
    if changed or result.protected:
        lines.extend(['', 'Your Japanese fields, notes, cards, scheduling, and review history were not deleted.'])
    return '\n'.join(lines)


def regeneration_text(result, setup=False, enabled=True):
    attention = result.skipped or result.failed or result.error or result.diagnostics
    if result.cancelled:
        title = 'Regeneration cancelled'
    elif result.error or attention:
        title = 'Regeneration needs attention'
    elif setup:
        title = 'Setup complete'
    elif result.changed:
        title = 'Breakdowns regenerated'
    else:
        title = 'Breakdowns already up to date' if result.total else 'No notes to regenerate'
    lines = [title, '']
    if result.changed or result.cancelled:
        lines.append(count(result.changed, 'note') + (' updated before cancellation.' if result.cancelled else ' updated.'))
    elif not attention and not result.cancelled:
        lines.append('No notes needed updating.' if result.total else 'No matching notes were found.')
    if result.unchanged:
        lines.append(count(result.unchanged, 'note') + (' was' if result.unchanged == 1 else ' were') + ' already up to date.')
    protected = getattr(result, 'protected', 0)
    if protected:
        lines.append(count(protected, 'note') + (' was' if protected == 1 else ' were') +
                     ' skipped because the breakdown field contained unsupported content.')
    if result.skipped - protected:
        lines.append(count(result.skipped - protected, 'note') + (' was' if result.skipped - protected == 1 else ' were') + ' skipped.')
    if result.failed:
        lines.append(count(result.failed, 'note') + ' could not be updated.')
    if result.pending:
        lines.append('Unfinished changes to ' + count(result.pending, 'note') + ' were not saved.')
    if result.cancelled and result.changed:
        lines.append('Completed changes can be undone in Anki.')
    if result.error:
        lines.append(result.error)
    elif attention:
        lines.append('Check the selected note types and breakdown fields in Settings.')
    if setup:
        lines.append('Settings were saved. ' + ('Future desktop edits will be kept updated automatically.' if enabled else 'Automatic breakdown updates are off.'))
    return '\n'.join(lines)


def notify(text, parent, detailed=False):
    # User-controlled field names stay plain text, including in Anki HTML tooltips.
    if detailed:
        from aqt.utils import showInfo
        showInfo(text, parent=parent, textFormat='plain')
    else:
        from aqt.utils import tooltip
        tooltip(escape(text).replace('\n', '<br>'), parent=parent)


def regeneration_notice(result, parent, setup=False, enabled=True):
    notify(regeneration_text(result, setup, enabled), parent,
           detailed=bool(result.cancelled or result.error or result.failed or result.skipped or result.diagnostics))
