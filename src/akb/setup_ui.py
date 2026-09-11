"""Local onboarding copy and setup presentation policy, independent of Qt."""
from copy import deepcopy

TITLE = 'How Auto Kanji Breakdown works'
ONBOARDING_KEY = 'ui_onboarding_completed'
LABELS = {
    'data_updates': 'Automatically keep kanji data up to date',
    'enabled': 'Automatically keep breakdowns updated',
    'sources': 'Japanese fields',
    'output': 'Breakdown data field',
    'theme': 'Appearance / Theme',
    'targets': 'Display breakdown on',
    'initial': 'Generate breakdowns for existing notes now',
}
MOBILE = (
    'Breakdowns are generated and updated using desktop Anki. After syncing, they are '
    'designed to be reviewed on AnkiMobile and AnkiDroid, including offline.\n\n'
    'If you edit Japanese text on mobile, sync with desktop and save or regenerate '
    'the note to refresh its breakdown, then sync again.'
)
CLEANUP = (
    'Removing Auto Kanji Breakdown does not delete your Japanese notes or review history.\n\n'
    'You can choose to:\n• remove the visual breakdown only\n• clear generated kanji data\n'
    '• perform a full cleanup\n\n'
    'Fields you created yourself are never automatically deleted. A field created by '
    'Auto Kanji Breakdown is only offered for deletion when ownership can be proven.'
)
from .update_service import HELP as UPDATE_HELP

HELP = {
    'data_updates': UPDATE_HELP,
    'enabled': (
        'When enabled, Auto Kanji Breakdown updates the breakdown whenever you add or edit '
        'a matching note in the standard desktop Anki editor. Recommended for most users. '
        'After edits through other paths, use Regenerate Kanji Breakdown.'
    ),
    'sources': (
        'Choose the fields that contain the Japanese text you want analysed. You can select '
        'more than one field. Each unique kanji is shown once, in the order it first appears.'
    ),
    'output': (
        'This field stores the generated breakdown information. Using a dedicated field is '
        'recommended. Your Japanese source fields are not modified.'
    ),
    'theme': (
        'Changes how Auto Kanji Breakdown looks. Choose a theme and press Apply to update '
        'all breakdown displays. Changing the theme does not regenerate or modify your study content.'
    ),
    'targets': (
        'Choose which card sides display the kanji breakdown.\n\n'
        'For most cards, displaying the breakdown on the back is recommended so it does not '
        'reveal information before you answer.'
    ),
    'initial': (
        'Recommended during first setup. This generates breakdowns for the notes you already have. '
        'New notes and later desktop edits can be kept updated automatically.\n\n'
        'If this is turned off, existing notes will only receive a breakdown when they are '
        'later edited on desktop or manually regenerated.\n\n'
        'This does not change your Japanese text, cards, scheduling or review history.\n\n'
        'This step requires automatic updates to be on and the kanji database to be loaded. '
        'It runs after setup with progress and cancellation, and has a separate undo step.'
    ),
    'mobile': MOBILE,
    'cleanup': CLEANUP,
}
TUTORIAL = '\n\n'.join([
    'Choose your Japanese fields\nSelect the fields where your Japanese text lives. '
    'Auto Kanji Breakdown finds the kanji for you.',
    'Breakdowns stay updated\nWhen you add or edit notes in the standard desktop Anki editor, '
    'the breakdown can update automatically. Desktop Anki can also check for newer kanji data '
    'about once a month in the background.',
    'Review anywhere\nSync normally. Generated breakdowns are designed to work on desktop, '
    'AnkiMobile and AnkiDroid. The information and display are synced with your notes and cards, '
    'so reviewing does not require the desktop add-on or an internet connection.',
    'Mobile edits\nIf you edit the Japanese source text on mobile, the breakdown cannot '
    'regenerate on the phone itself. Sync the change back to desktop Anki and save or '
    'regenerate the note, then sync again.',
    "You're always in control\nYou can regenerate one note, regenerate selected notes, "
    'regenerate all configured notes, remove the visual breakdown, clear generated data, '
    'or completely clean up Auto Kanji Breakdown later.\n\n'
    'Cleanup does not delete your Japanese source fields, notes, cards, scheduling data '
    'or review history.',
])
TUTORIAL_HEADINGS = ('Choose your Japanese fields', 'Breakdowns stay updated',
                     'Review anywhere', 'Mobile edits', "You're always in control")


COMMON_TASKS = (
    ('Set up or change a note type',
     'Open Tools > Auto Kanji Breakdown > Settings. Choose your note type, Japanese fields, '
     'breakdown data field and card sides, then review and apply.'),
    ('Refresh one note',
     'While editing a note, right-click a field and choose Regenerate Kanji Breakdown.'),
    ('Refresh selected notes',
     'In Browse, select the notes you want, then choose Notes > Regenerate Kanji Breakdown.'),
    ('Refresh all configured notes',
     'Open Tools > Auto Kanji Breakdown > Regenerate Breakdowns. '
     'Notes with automatic updates turned off are skipped.'),
    ('Change the appearance',
     'Open Settings, choose a theme and press Apply. This updates all breakdown displays '
     'without regenerating your notes.'),
    ('Check for newer kanji data',
     'Open Tools > Auto Kanji Breakdown > Status & Diagnostics and choose '
     'Check for database updates now. Automatic checks normally happen quietly in the background.'),
    ('Using mobile',
     'Sync normally. Breakdowns work offline after syncing. If you edit Japanese text on mobile, '
     'sync back to desktop and regenerate the note, then sync again.'),
    ('Remove Auto Kanji Breakdown',
     'Open Tools > Auto Kanji Breakdown > Cleanup. You can remove the visual breakdown, '
     'clear generated breakdown data, or remove all Auto Kanji Breakdown integration. '
     'Cleanup does not delete your Japanese source fields, notes, cards, scheduling or review history. '
     'Remove the add-on through Anki after cleanup if you no longer want it.'),
)
GUIDE = TITLE + '\n\n' + TUTORIAL + '\n\nCommon tasks\n\n' + '\n\n'.join(
    heading + '\n' + body for heading, body in COMMON_TASKS)
GUIDE_HEADINGS = (TITLE,) + TUTORIAL_HEADINGS + ('Common tasks',) + tuple(h for h, _ in COMMON_TASKS)


def needs_onboarding(raw):
    return not isinstance(raw, dict) or raw.get(ONBOARDING_KEY) is not True


def completed_onboarding(raw):
    """Preserve add-on settings, including legacy mappings and unrelated keys."""
    if raw is not None and not isinstance(raw, dict):
        raise ValueError('Cannot update malformed add-on settings')
    result = deepcopy(raw) if isinstance(raw, dict) else {'version': 1, 'mappings': []}
    result[ONBOARDING_KEY] = True
    return result


def defaults(row):
    # A previous one-time run is not a request to repeat it on every reopening.
    return {'enabled': row.get('enabled', True),
            'initial': not bool(row),
            'targets': None if 'templates' not in row else
                {(t['id'], t['side']) for t in row['templates']}}


def recommend_regeneration(row, sources, output, enabled):
    """Compare generation inputs only; display-side changes do not require a run."""
    return (not row or tuple(sources) != tuple(row.get('source_fields', ()))
            or output != row.get('output_field')
            or (enabled and not row.get('enabled', True)))


def setup_summary(model, sources, output, targets, enabled, count, create=False):
    sides = [f"• {t['name']}: {'Front' if side == 'qfmt' else 'Back'}"
             for t in model['tmpls'] for side in ('qfmt', 'afmt') if (t['id'], side) in targets]
    return '\n'.join([
        'Ready to set up Auto Kanji Breakdown', '', f"Note type: {model['name']}", '',
        'Japanese fields:', *['• ' + name for name in sources], '', 'Breakdown appears on:',
        *(sides or ['• No card sides selected: the breakdown will not be displayed.']), '',
        'Breakdown data field:', '• ' + output + (' (create a dedicated field)' if create else ' (use existing field)'), '',
        ('✓ Keep breakdowns updated automatically' if enabled else 'Automatic updates are off'),
        f'Existing notes: {count:,}',
        'The breakdown will appear only on the selected sides. Other card content is kept.',
    ])


def review_summary(plan, initial, runtime_ready=True):
    if initial and plan.request.enabled and runtime_ready:
        line = f'✓ Generate breakdowns for {plan.notes:,} existing notes'
    elif not runtime_ready:
        line = 'Existing notes will not be generated now: load the database in Status & Diagnostics first.'
    elif not plan.request.enabled:
        line = 'Existing notes will not be generated now: automatic updates are off.'
    else:
        line = 'Existing notes will not be generated now. Edit or manually regenerate them later.'
    return plan.summary + '\n' + line + '\n\n' + (
        'Your Japanese source fields, cards, scheduling and review history will not be deleted or replaced.'
    )
