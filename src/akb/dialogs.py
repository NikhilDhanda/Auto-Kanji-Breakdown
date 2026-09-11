"""Small Qt forms; planning/scanning and collection writes run in Anki operations."""
from aqt.qt import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout,
                    QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QMessageBox,
                    QPushButton, QScrollArea, QTextEdit, QVBoxLayout, QWidget, Qt, qconnect)
from aqt.operations import CollectionOp, QueryOp
from aqt.utils import showInfo, showWarning

from .setup import (Request, apply_plan, apply_theme, plan_setup, proven_created, read_config, row_for)
from .cleanup import plan_cleanup
from .templates import IntegrationError, RENDERER_VERSION, THEMES, THEME_LABELS, parse_theme, status
from . import setup_ui

CHECKED = Qt.CheckState.Checked
ROLE = Qt.ItemDataRole.UserRole


def text_dialog(parent, title, text, button='Close', confirm=False, headings=(), credit=False):
    """Native, scrollable local help; no HTML interpretation or external links."""
    dialog = QDialog(parent)
    dialog.setWindowTitle(title)
    area = dialog.screen().availableGeometry()
    dialog.resize(min(560, area.width() - 40), min(480, area.height() - 40))
    layout = QVBoxLayout(dialog)
    view = QTextEdit()
    view.setReadOnly(True)
    view.setPlainText(text)
    # Native character formatting inherits the active palette in both themes.
    # Only trusted tutorial headings are emphasized; body/help stays normal.
    for heading in headings:
        cursor = view.document().find(heading)
        if not cursor.isNull():
            style = cursor.charFormat()
            style.setFontWeight(700)
            cursor.mergeCharFormat(style)
    layout.addWidget(view)
    if credit:
        author = QLabel('Created by Nik Dhanda')
        font = author.font()
        font.setPointSizeF(max(8, font.pointSizeF() - 1))
        author.setFont(font)
        layout.addWidget(author)
    if confirm:
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        apply = buttons.addButton('Apply', QDialogButtonBox.ButtonRole.AcceptRole)
        apply.setAutoDefault(False)
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setDefault(True)
        qconnect(buttons.accepted, dialog.accept)
        qconnect(buttons.rejected, dialog.reject)
        layout.addWidget(buttons)
    else:
        close = QPushButton(button)
        close.setDefault(True)
        qconnect(close.clicked, dialog.accept)
        layout.addWidget(close)
    return dialog.exec() == QDialog.DialogCode.Accepted


def show_tutorial(adapter, first_time=False):
    accepted = text_dialog(adapter.mw, setup_ui.TITLE, setup_ui.TUTORIAL,
                           'Continue' if first_time else 'Close', headings=setup_ui.TUTORIAL_HEADINGS, credit=True)
    if first_time:
        # This UI-only flag must not create/clear collection undo history. Merge
        # into the latest add-on settings without changing any legacy mappings.
        raw = adapter.legacy_config()
        try:
            adapter.mw.addonManager.writeConfig(adapter.addon_name, setup_ui.completed_onboarding(raw))
        except Exception:
            showWarning('Could not remember the tutorial dismissal. Please reopen Settings and try again.', parent=adapter.mw)
            return False
    return accepted


def show_guide(adapter):
    return text_dialog(adapter.mw, 'Help & Guide', setup_ui.GUIDE,
                       headings=setup_ui.GUIDE_HEADINGS, credit=True)


def with_help(parent, widget, key, recommended=None):
    row = QHBoxLayout()
    row.addWidget(widget, 1)
    if recommended is not None:
        row.addWidget(recommended)
    button = QPushButton('?')
    button.setAutoDefault(False)
    title = setup_ui.LABELS.get(key, {'mobile': 'Works across your devices',
                                     'cleanup': 'Removing Auto Kanji Breakdown'}.get(key, key))
    button.setAccessibleName('Help: ' + title)
    button.setToolTip('Help: ' + title)
    button.setFixedWidth(button.fontMetrics().horizontalAdvance('?') + 24)
    qconnect(button.clicked, lambda: text_dialog(parent, title, setup_ui.HELP[key]))
    row.addWidget(button)
    return row


def checked_items(widget):
    return [widget.item(i) for i in range(widget.count()) if widget.item(i).checkState() == CHECKED]


def item(widget, label, data, checked=False):
    result = QListWidgetItem(label, widget)
    result.setData(ROLE, data)
    result.setFlags(result.flags() | Qt.ItemFlag.ItemIsUserCheckable)
    result.setCheckState(CHECKED if checked else Qt.CheckState.Unchecked)
    return result


class SetupDialog(QDialog):
    def __init__(self, adapter, raw, models, cleanup=False):
        super().__init__(adapter.mw)
        self.adapter, self.raw, self.models, self.cleanup = adapter, raw, models, cleanup
        self._populating = False
        self._initial_choices = {}  # Explicit choices, scoped to this open dialog.
        self.setWindowTitle('Auto Kanji Breakdown: ' + ('Cleanup' if cleanup else 'Settings'))
        area = self.screen().availableGeometry()
        self.resize(min(620, area.width() - 40), min(680 if not cleanup else 370, area.height() - 40))
        layout = QVBoxLayout(self)
        content = QWidget()
        body = QVBoxLayout(content)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(content)
        layout.addWidget(scroll)
        intro = QLabel('Choose a note type and the Japanese text you want to break down.' if not cleanup
                       else 'Remove only the integration and generated content you choose. Source notes and reviews are kept.')
        intro.setWordWrap(True)
        body.addWidget(intro)
        form = QFormLayout()
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        body.addLayout(form)
        self.types = QComboBox()
        for model in models:
            row = row_for(raw, model['id'])
            if cleanup and not row:
                continue
            label = model['name'] + (' (configured)' if row else '')
            self.types.addItem(label, model['id'])
        form.addRow('Note type', self.types)
        self.enabled = QCheckBox(setup_ui.LABELS['enabled'])
        self.sources, self.targets = QListWidget(), QListWidget()
        self.sources.setMinimumHeight(80)
        self.sources.setMaximumHeight(120)
        self.targets.setMinimumHeight(70)
        self.targets.setMaximumHeight(90)
        self.output = QComboBox()
        self.theme = QComboBox()
        for name in THEMES:
            self.theme.addItem(THEME_LABELS[name], name)
        self.initial = QCheckBox(setup_ui.LABELS['initial'])
        self.initial_recommended = QLabel('Recommended')
        self.initial_hint = QLabel()
        self.initial_hint.setWordWrap(True)
        self.mode = QComboBox()
        for label, value in [('Remove visual breakdown only', 'renderer'), ('Clear breakdown data', 'data'), ('Full cleanup', 'full')]:
            self.mode.addItem(label, value)
        self.delete = QCheckBox('Also delete proven add-on-created fields (optional)')
        self.remove_updates = QCheckBox('Also remove downloaded kanji databases for all note types')
        self.remove_updates.setToolTip('Full cleanup only. Disables automatic data checks and removes only add-on-owned update files. This file removal is not undoable.')
        if cleanup:
            form.addRow('Action', self.mode)
            form.addRow(self.delete)
            form.addRow(self.remove_updates)
            qconnect(self.mode.currentIndexChanged, self.update_delete)
        else:
            form.addRow(with_help(self, self.enabled, 'enabled', QLabel('Recommended')))
            form.addRow(with_help(self, QLabel(setup_ui.LABELS['sources']), 'sources'))
            helper = QLabel('Select the fields containing the Japanese text you want analysed.')
            helper.setWordWrap(True)
            form.addRow(helper)
            form.addRow(self.sources)
            order = QHBoxLayout()
            for label, delta in [('Move up', -1), ('Move down', 1)]:
                button = QPushButton(label)
                qconnect(button.clicked, lambda _checked=False, d=delta: self.move_source(d))
                order.addWidget(button)
            form.addRow('', order)
            form.addRow(with_help(self, QLabel(setup_ui.LABELS['output']), 'output'))
            form.addRow(self.output)
            form.addRow(with_help(self, QLabel(setup_ui.LABELS['targets']), 'targets'))
            form.addRow(self.targets)
            appearance = QHBoxLayout()
            appearance.addWidget(self.theme, 1)
            self.theme_apply = QPushButton('Apply')
            self.theme_apply.setAutoDefault(False)
            self.theme_apply.setToolTip('Apply this theme to all Auto Kanji Breakdown displays.')
            qconnect(self.theme_apply.clicked, self.apply_appearance)
            appearance.addWidget(self.theme_apply)
            appearance_widget = QWidget()
            appearance_widget.setLayout(appearance)
            appearance.setContentsMargins(0, 0, 0, 0)
            form.addRow(setup_ui.LABELS['theme'], with_help(self, appearance_widget, 'theme'))
            from .updater import enabled as data_updates_enabled
            self.data_updates = QCheckBox(setup_ui.LABELS['data_updates'])
            self.data_updates.setChecked(data_updates_enabled(adapter.legacy_config()))
            qconnect(self.data_updates.clicked, lambda checked: adapter.updates.set_enabled(checked))
            form.addRow(with_help(self, self.data_updates, 'data_updates'))
            form.addRow(with_help(self, self.initial, 'initial', self.initial_recommended))
            form.addRow(self.initial_hint)
            mobile = QLabel('Works across your devices, sync to review on mobile, including offline.')
            mobile.setWordWrap(True)
            body.addLayout(with_help(self, mobile, 'mobile'))
            footer = QLabel('Want to remove this later? Use Tools → Auto Kanji Breakdown → Cleanup.')
            footer.setWordWrap(True)
            body.addLayout(with_help(self, footer, 'cleanup'))
        body.addStretch()
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        preview = self.buttons.addButton('Review changes…', QDialogButtonBox.ButtonRole.ActionRole)
        qconnect(preview.clicked, self.preview)
        qconnect(self.buttons.rejected, self.reject)
        layout.addWidget(self.buttons)
        qconnect(self.types.currentIndexChanged, self.populate)
        qconnect(self.enabled.toggled, self.update_initial)
        qconnect(self.sources.itemChanged, self.update_initial)
        qconnect(self.output.currentIndexChanged, self.update_initial)
        qconnect(self.initial.clicked, self.choose_initial)
        self.populate()

    def model(self):
        return next((m for m in self.models if m['id'] == self.types.currentData()), None)

    def populate(self, _index=None):
        model = self.model()
        self.buttons.setEnabled(bool(model))
        if not model:
            return
        row = row_for(self.raw, model['id'])
        self._populating = True
        choices = setup_ui.defaults(row)
        self.theme.setCurrentIndex(self.theme.findData(parse_theme(row.get('theme', self.raw.get('default_theme')))))
        self.enabled.setChecked(choices['enabled'])
        self.initial.setChecked(choices['initial'])
        self.sources.clear()
        names = [f['name'] for f in model['flds']]
        ordered = [n for n in row.get('source_fields', []) if n in names]
        for name in ordered + [n for n in names if n not in ordered]:
            item(self.sources, name, name, name in ordered)
        self.output.clear()
        self.output.addItem('Create a new dedicated field (recommended)', None)
        for name in names:
            self.output.addItem(name + (' (existing field)'), name)
        if row.get('output_field') in names:
            self.output.setCurrentIndex(self.output.findData(row['output_field']))
        self.targets.clear()
        existing = choices['targets']
        for t in model['tmpls']:
            for side, label in [('qfmt', 'front'), ('afmt', 'back')]:
                selected = (t['id'], side) in existing if existing is not None else side == 'afmt'
                item(self.targets, f"{t['name']}: {label}", (t['id'], side), selected)
        for index in range(self.targets.count()):
            if self.targets.item(index).checkState() == CHECKED:
                self.targets.setCurrentRow(index)
                break
        self.update_delete()
        self._populating = False
        self.update_initial()

    def choose_initial(self, checked):
        self._initial_choices[self.types.currentData()] = checked

    def update_initial(self, _checked=None):
        if self.cleanup or self._populating or not self.model():
            return
        row = row_for(self.raw, self.types.currentData())
        recommended = setup_ui.recommend_regeneration(
            row, [i.data(ROLE) for i in checked_items(self.sources)],
            self.output.currentData(), self.enabled.isChecked())
        self.initial.setChecked(self._initial_choices.get(self.types.currentData(), recommended))
        available = self.adapter.runtime is not None and self.enabled.isChecked()
        self.initial_recommended.setVisible(recommended and available)
        self.initial.setEnabled(available)
        message = ''
        if self.adapter.runtime is None:
            message = 'To generate existing notes now, first load the database in Status & Diagnostics.'
        elif not self.enabled.isChecked():
            message = 'Turn on automatic updates to generate existing notes during setup.'
        self.initial_hint.setText(message)
        self.initial_hint.setVisible(bool(message))

    def update_delete(self, _index=None):
        self.remove_updates.setEnabled(self.mode.currentData() == 'full')
        if self.mode.currentData() != 'full':
            self.remove_updates.setChecked(False)
        model = self.model()
        row = row_for(self.raw, model['id']) if model else {}
        allowed = bool(model and self.mode.currentData() == 'full'
                       and any(proven_created(row, f) for f in model['flds']))
        self.delete.setEnabled(allowed)
        if not allowed:
            self.delete.setChecked(False)

    def move_source(self, delta):
        index = self.sources.currentRow()
        destination = index + delta
        if index >= 0 and 0 <= destination < self.sources.count():
            selected = self.sources.takeItem(index)
            self.sources.insertItem(destination, selected)
            self.sources.setCurrentRow(destination)
            self.update_initial()

    def apply_appearance(self):
        if self.adapter.running or self.adapter.loading:
            return
        theme = self.theme.currentData()
        legacy = self.adapter.legacy_config()
        self.adapter.running = True
        self.setEnabled(False)

        def work(col):
            result = apply_theme(col, theme, self.raw, legacy)
            self._theme_snapshot = (read_config(col, legacy), col.models.all())
            return result

        def done(result):
            self.adapter.running = False
            self.setEnabled(True)
            if result.error:
                self.failure(IntegrationError(result.error))
                return
            self.raw, self.models = self._theme_snapshot
            self.adapter.sync_config()
            from aqt.utils import tooltip
            tooltip('Theme applied', parent=self)

        def failed(error):
            self.adapter.running = False
            self.setEnabled(True)
            self.failure(error)

        CollectionOp(parent=self, op=work).success(done).failure(failed).run_in_background()

    def preview(self):
        if self.cleanup and self.remove_updates.isChecked() and self.adapter.updates.busy:
            showWarning('Wait for the kanji database check to finish before removing its files.', parent=self)
            return
        model = self.model()
        if not model or self.adapter.running or self.adapter.loading:
            return
        mid = model['id']
        request = Request(mid, tuple(i.data(ROLE) for i in checked_items(self.sources)),
                          self.output.currentData(), tuple(tuple(i.data(ROLE)) for i in checked_items(self.targets)),
                          self.enabled.isChecked(), self.initial.isChecked(), self.theme.currentData())
        mode, delete = self.mode.currentData(), self.delete.isChecked()
        initial = (self.initial.isChecked() and self.adapter.runtime is not None
                   and not self.cleanup and request.enabled)
        legacy = self.adapter.legacy_config()
        self.buttons.setEnabled(False)

        def work(col):
            raw = read_config(col, legacy)
            # Do not approve a stale form after another setup or an undo.
            if raw != self.raw or col.models.get(mid) != model:
                raise IntegrationError('Settings changed while this dialog was open. Reopen setup.')
            return plan_cleanup(col, raw, mid, mode, delete) if self.cleanup else plan_setup(col, raw, request)

        def ready(plan):
            self.buttons.setEnabled(True)
            message = plan.summary
            if self.cleanup and self.remove_updates.isChecked():
                message += '\nAlso disable automatic data checks and remove downloaded kanji databases for all note types. This file removal cannot be undone. Bundled data remains available; notes follow the cleanup choices above.'
            if not self.cleanup:
                message = setup_ui.review_summary(plan, initial, self.adapter.runtime is not None)
                if text_dialog(self, 'Review Auto Kanji Breakdown changes', message, confirm=True):
                    self.apply(plan, initial)
                return
            box = QMessageBox(self)
            box.setWindowTitle('Review Auto Kanji Breakdown changes')
            box.setTextFormat(Qt.TextFormat.PlainText)
            box.setText(message)
            box.setStandardButtons(QMessageBox.StandardButton.Apply | QMessageBox.StandardButton.Cancel)
            box.setDefaultButton(QMessageBox.StandardButton.Cancel)
            if box.exec() == QMessageBox.StandardButton.Apply:
                self.apply(plan, initial)

        QueryOp(parent=self, op=work, success=ready).failure(self.failure).with_progress('Checking setup and note contents').run_in_background()

    def failure(self, error):
        self.buttons.setEnabled(True)
        message = str(error) if isinstance(error, IntegrationError) else 'Could not complete the operation. Reopen setup and check the note type.'
        showWarning(message, parent=self)

    def apply(self, plan, initial):
        self.buttons.setEnabled(False)
        self.adapter.running = True
        legacy = self.adapter.legacy_config()

        def done(result):
            self.adapter.running = False
            self.adapter.sync_config()
            if result.error:
                self.failure(IntegrationError(result.error))
                return
            self.accept()
            from .results import cleanup_text, notify, regeneration_notice
            if self.adapter.runtime is None:
                self.adapter.prepare()
            if self.cleanup:
                def report(files=None):
                    text = cleanup_text(result.cleanup, files)
                    notify(text, self.adapter.mw, detailed=bool(result.cleanup.protected or files == 'failed' or not text.startswith('Nothing to clean up')))
                if self.remove_updates.isChecked():
                    from .updater import enabled as data_updates_enabled
                    was_enabled = data_updates_enabled(self.adapter.legacy_config())
                    self.adapter.updates.set_enabled(False)
                    result.cleanup.updater_disabled = was_enabled
                    self.adapter.updates.remove_files(finished=report)
                else:
                    report()
            elif initial:
                self.adapter.bulk(plan.request.mid, finished=lambda bulk: regeneration_notice(
                    bulk, self.adapter.mw, setup=True, enabled=plan.request.enabled))
            else:
                notify(('Setup complete' if result.changed else 'Settings already up to date') +
                       '\nExisting notes were not regenerated.', self.adapter.mw)

        def failed(error):
            self.adapter.running = False
            self.failure(error)

        CollectionOp(parent=self, op=lambda col: apply_plan(col, plan, legacy, self.adapter.runtime)).success(done).failure(failed).run_in_background()


def open_dialog(adapter, cleanup=False):
    if adapter.running or adapter.loading or adapter.mw.col is None:
        adapter.diagnostic('Wait for the current operation and open a profile before configuring.')
        return
    legacy = adapter.legacy_config()

    def loaded(value):
        raw, models = value
        if not cleanup and setup_ui.needs_onboarding(adapter.legacy_config()):
            if not show_tutorial(adapter, first_time=True):
                return
            # The tutorial flag may have changed the legacy config envelope.
            # Refresh the read-only snapshot before the stale-preview comparison.
            open_dialog(adapter, cleanup)
            return
        dialog = SetupDialog(adapter, raw, models, cleanup)
        dialog.exec()

    QueryOp(parent=adapter.mw, op=lambda col: (read_config(col, legacy), col.models.all()), success=loaded).failure(
        lambda error: showWarning(str(error) if isinstance(error, IntegrationError) else 'Could not load settings.', parent=adapter.mw)
    ).run_in_background()


def show_status(adapter):
    if adapter.mw.col is None:
        adapter.diagnostic('Open a profile to view status.')
        return
    legacy = adapter.legacy_config()

    def inspect(col):
        raw = read_config(col, legacy)
        lines = [f"Breakdowns: {'ready' if adapter.runtime else 'not ready'}", 'Technical details: database format 1 (validated on load)',
                 f'Renderer version: {RENDERER_VERSION}', f"Configuration version: {raw['version']}"]
        from .updater import enabled as data_updates_enabled
        lines.extend(['', adapter.updates.diagnostics(),
                      'Automatic data updates: ' + ('On' if data_updates_enabled(legacy) else 'Off'),
                      'Apply the theme or reapply Settings to install the current Sources panel in existing templates.'])
        for row in raw['mappings']:
            if not isinstance(row, dict):
                lines.append('Invalid note type settings; skipped.')
                continue
            model = col.models.get(row.get('notetype_id', 0))
            lines.extend(['', f"{row.get('notetype_name', 'Note type')}, ID {row.get('notetype_id')}",
                          f"Generation: {'enabled' if row.get('enabled', True) else 'disabled'}",
                          'Sources: ' + ', '.join(row.get('source_fields', [])), 'Output: ' + str(row.get('output_field', 'missing'))])
            if not model:
                lines.append('Note type missing.')
                continue
            names = {f['name'] for f in model['flds']}
            for name in [*row.get('source_fields', []), row.get('output_field')]:
                if name not in names:
                    lines.append(f'Missing/renamed field: {name}')
            actual = {(t['id'], side) for t in model['tmpls'] for side in ('qfmt', 'afmt')}
            for target in row.get('templates', []):
                if (target['id'], target['side']) not in actual:
                    lines.append('Previously selected card type missing.')
            for t in model['tmpls']:
                for side, label in [('qfmt', 'front'), ('afmt', 'back')]:
                    try:
                        state = status(t[side], row.get('owner'))
                    except IntegrationError as error:
                        state = str(error)
                    lines.append(f"{t['name']} {label}: {state}")
            try:
                lines.append('Styling: ' + status(model['css'], row.get('owner'), True))
            except IntegrationError as error:
                lines.append('Styling: ' + str(error))
        lines.extend(['', 'Experimental Svelte editor: automatic save hooks unavailable. Use the standard editor or Regenerate.',
                      'Mobile: breakdowns work offline after syncing; source edits on mobile require desktop regeneration.'])
        return '\n'.join(lines)

    def display(text):
        dialog = QDialog(adapter.mw)
        dialog.setWindowTitle('Auto Kanji Breakdown: Status')
        dialog.resize(660, 580)
        layout = QVBoxLayout(dialog)
        view = QTextEdit()
        view.setReadOnly(True)
        view.setPlainText(text)
        layout.addWidget(view)
        check = QPushButton('Check for database updates now')
        qconnect(check.clicked, lambda: adapter.updates.start(manual=True))
        layout.addWidget(check)
        from .updater import enabled as data_updates_enabled
        automatic = QCheckBox(setup_ui.LABELS['data_updates'])
        automatic.setChecked(data_updates_enabled(adapter.legacy_config()))
        qconnect(automatic.clicked, adapter.updates.set_enabled)
        layout.addLayout(with_help(dialog, automatic, 'data_updates'))
        reload = QPushButton('Reload database and settings')
        qconnect(reload.clicked, lambda: (dialog.accept(), adapter.prepare()))
        layout.addWidget(reload)
        dialog.exec()

    QueryOp(parent=adapter.mw, op=inspect, success=display).failure(
        lambda error: adapter.diagnostic('Could not read configuration status. Restore valid settings.')
    ).run_in_background()
