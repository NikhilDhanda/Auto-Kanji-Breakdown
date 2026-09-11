"""Shipped Python compatibility gate; run on 3.9 as well as newer test Pythons.

Grammar parsing alone misses PEP 604 (valid older bitwise-expression syntax).
Explicit annotation/alias checks and a reviewed stdlib surface supplement it.
This conservative gate is not a replacement for execution on Python 3.9.
"""
import ast
import importlib
from pathlib import Path
import unittest
from unittest.mock import patch
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
REVIEWED_STDLIB = {
    'collections', 'contextlib', 'contextvars', 'copy', 'dataclasses', 'hashlib',
    'html', 'html.parser', 'gzip', 'tempfile', 'xml.etree.ElementTree', 'zipfile', 'shutil', 'time', 'urllib.request', 'urllib.error', 'urllib.parse', 'json', 'logging', 'pathlib', 're', 'threading', 'typing', 'uuid',
}
TYPING_39 = {'Optional', 'Union', 'Any', 'Callable', 'Iterable', 'Iterator',
             'Sequence', 'Mapping', 'TypeVar', 'Generic', 'Protocol', 'Literal',
             'Final', 'ClassVar', 'TypedDict', 'TYPE_CHECKING', 'cast', 'overload',
             'List', 'Dict', 'Tuple', 'Set', 'FrozenSet', 'Type', 'NoReturn'}
NEW_NAMES = {'ExceptionGroup', 'BaseExceptionGroup', 'aiter', 'anext'}
REVIEWED_FROM = {
    'html': {'escape'},  # Available since Python 3.2; used for native tooltip text.
    'collections': {'Counter'}, 'contextlib': {'contextmanager', 'nullcontext'},
    'contextvars': {'ContextVar'}, 'copy': {'deepcopy'},
    'dataclasses': {'dataclass', 'field'}, 'html.parser': {'HTMLParser'},
    'pathlib': {'Path'}, 'threading': {'Event', 'Lock'}, 'typing': TYPING_39,
}
NEW_ATTRIBUTES = {
    'walk', 'is_junction', 'full_match', 'isreserved', 'isdevdrive',
    'aclosing', 'chdir', 'KW_ONLY', 'kw_only', 'Self', 'TypeAlias', 'ParamSpec',
    'TypeVarTuple', 'Concatenate', 'Required', 'NotRequired', 'Never', 'LiteralString',
    'Unpack', 'TypeGuard', 'TypeIs', 'ReadOnly', 'override', 'is_typeddict',
}
NEW_KEYWORDS = {'slots', 'kw_only', 'weakref_slot', 'match_args', 'strict',
                'case_sensitive', 'recurse_symlinks', 'walk_up', 'process_group'}


def issues(source):
    try:
        tree = ast.parse(source, feature_version=(3, 9))
    except SyntaxError as error:
        return ['Python 3.9 grammar: ' + str(error)]
    errors = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            if isinstance(node, ast.ImportFrom) and node.level:
                continue
            modules = [n.name for n in node.names] if isinstance(node, ast.Import) else [node.module]
            for module in modules:
                if module.split('.')[0] not in ('anki', 'aqt') and module not in REVIEWED_STDLIB:
                    errors.append('Unreviewed runtime import: ' + module)
            if isinstance(node, ast.ImportFrom) and node.module in REVIEWED_STDLIB:
                allowed = REVIEWED_FROM.get(node.module, set())
                errors.extend('Post-3.9/unreviewed import: ' + n.name for n in node.names if n.name not in allowed)
        annotations = []
        if isinstance(node, ast.AnnAssign):
            annotations.append(node.annotation)
        if isinstance(node, ast.arg) and node.annotation:
            annotations.append(node.annotation)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.returns:
            annotations.append(node.returns)
        # Type aliases are evaluated at import time too. Plain Qt flag expressions
        # in call arguments remain valid bitwise operations and are not rejected.
        if isinstance(node, ast.Assign):
            annotations.append(node.value)
        for expression in annotations:
            if isinstance(expression, ast.Constant) and isinstance(expression.value, str):
                try:
                    expression = ast.parse(expression.value, mode='eval')
                except SyntaxError:
                    continue
            if any(isinstance(n, ast.BinOp) and isinstance(n.op, ast.BitOr) for n in ast.walk(expression)):
                errors.append('PEP 604 annotation/type alias: use Optional/Union')
        if isinstance(node, ast.Name) and node.id in NEW_NAMES:
            errors.append('Post-3.9 builtin: ' + node.id)
        if isinstance(node, ast.Attribute) and node.attr in NEW_ATTRIBUTES:
            errors.append('Post-3.9/unreviewed API: ' + node.attr)
        if isinstance(node, ast.Call):
            errors.extend('Post-3.9/unreviewed keyword: ' + k.arg for k in node.keywords if k.arg in NEW_KEYWORDS)
            method = node.func.attr if isinstance(node.func, ast.Attribute) else ''
            if method == 'total':
                errors.append('Counter.total requires Python 3.10; review the receiver')
            if method in ('read_text', 'write_text') and any(k.arg == 'newline' for k in node.keywords):
                errors.append('Path text newline keyword requires newer Python')
            if method in ('stat', 'chmod', 'exists', 'is_file', 'is_dir') and any(k.arg == 'follow_symlinks' for k in node.keywords):
                errors.append('Path follow_symlinks keyword requires newer Python')
    return errors


class Python39Tests(unittest.TestCase):
    def test_all_shipped_python_uses_reviewed_39_surface(self):
        files = sorted((ROOT / 'src').rglob('*.py'))
        self.assertTrue(files)
        for path in files:
            with self.subTest(file=str(path.relative_to(ROOT))):
                self.assertEqual(issues(path.read_text(encoding='utf-8')), [])

    def test_gate_catches_original_failure_and_later_features(self):
        for source in ['x: int | None = None', 'def f(x: str | int) -> int | None: pass',
                       'Alias = int | str', 'x: "int | None"',
                       'match x:\n case 1: pass', 'try: pass\nexcept* ValueError: pass',
                       'import tomllib', 'from typing import Self', 'from dataclasses import KW_ONLY',
                       'import typing as t\nx: t.Self', 'counter.total()',
                       '@dataclass(slots=True)\nclass X: pass', 'zip(a, b, strict=True)',
                       'path.write_text("a", newline="")', 'path.stat(follow_symlinks=False)']:
            with self.subTest(source=source):
                self.assertTrue(issues(source))

    def test_39_generics_and_qt_flags_are_allowed(self):
        self.assertEqual(issues('from typing import Optional\nx: Optional[list[str]] = None\n'
                                'button.setFlags(button.flags() | Qt.ItemFlag.ItemIsUserCheckable)'), [])

    def test_pure_runtime_imports_evaluate_annotations(self):
        # On 3.9 this catches evaluated annotation/import failures, not only syntax.
        for path in sorted((ROOT / 'src' / 'akb').glob('*.py')):
            if path.stem not in ('dialogs', '__init__'):
                importlib.import_module('src.akb.' + path.stem)

    def test_standard_editor_without_experimental_class(self):
        from src.akb.integration import Integration
        adapter = Integration(None, 'test')
        messages = []
        adapter.diagnostic = messages.append
        class NewEditor:
            pass
        for editor_module in [SimpleNamespace(), SimpleNamespace(NewEditor=NewEditor)]:
            with patch.dict('sys.modules', {'aqt': SimpleNamespace(editor=editor_module)}):
                adapter.editor_opened(object())
        self.assertEqual(messages, [])
        with patch.dict('sys.modules', {'aqt': SimpleNamespace(editor=SimpleNamespace(NewEditor=NewEditor))}):
            adapter.editor_opened(NewEditor())
        self.assertEqual(len(messages), 1)

    def test_dialog_module_import_with_qt_boundary_stubbed(self):
        names = ('QCheckBox QComboBox QDialog QDialogButtonBox QFormLayout QHBoxLayout '
                 'QLabel QListWidget QListWidgetItem QMessageBox QPushButton QScrollArea QTextEdit QVBoxLayout QWidget qconnect').split()
        qt = SimpleNamespace(**{name: object for name in names})
        qt.Qt = SimpleNamespace(CheckState=SimpleNamespace(Checked=2), ItemDataRole=SimpleNamespace(UserRole=256))
        modules = {'aqt.qt': qt,
                   'aqt.operations': SimpleNamespace(CollectionOp=object, QueryOp=object),
                   'aqt.utils': SimpleNamespace(showInfo=object, showWarning=object)}
        spec = importlib.util.spec_from_file_location('src.akb._compat_dialogs', ROOT / 'src/akb/dialogs.py')
        with patch.dict('sys.modules', modules):
            spec.loader.exec_module(importlib.util.module_from_spec(spec))
