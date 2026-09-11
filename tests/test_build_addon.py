"""Release packaging safety and reproducibility, without a personal Anki profile."""
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest
import zipfile

from tools import build_addon as release


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        for folder in ('src', 'licenses', 'generated'):
            shutil.copytree(release.ROOT / folder, self.root / folder,
                            ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        for name in ('LICENSE', 'AUTHORS', 'THIRD_PARTY_LICENSES.md', 'VERSION'):
            shutil.copyfile(release.ROOT / name, self.root / name)

    def tearDown(self):
        self.temp.cleanup()

    def test_repeat_build_root_layout_exclusions_and_installed_loader(self):
        for name in ('src/__pycache__/bad.pyc', 'src/meta.json', 'src/.env',
                     'src/tests/test_private.py', 'src/scratch.py', 'artifacts/image.png',
                     'src/user_files/akb_updates/current.json', 'user_files/private.txt'):
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('must not ship')
        first, report = release.build(self.root)
        second, _ = release.build(self.root, self.root / 'other.ankiaddon')
        self.assertEqual(first.read_bytes(), second.read_bytes())
        self.assertEqual(report['version'], (self.root / 'VERSION').read_text().strip())
        with zipfile.ZipFile(first) as archive:
            self.assertIn('__init__.py', archive.namelist())
            self.assertNotIn('src/__init__.py', archive.namelist())
            self.assertEqual(json.loads(archive.read('manifest.json')), release.MANIFEST)
            self.assertEqual(archive.read('data/kanji_db.json'), (self.root / 'generated/kanji_db.json').read_bytes())
            self.assertIn('data/manifest.json', archive.namelist())
            self.assertIn(b'GNU AFFERO GENERAL PUBLIC LICENSE', archive.read('LICENSE'))
            self.assertIn(b'AGPL-3.0-or-later', archive.read('AUTHORS'))
            self.assertNotIn(b'Apache', archive.read('AUTHORS'))
            self.assertNotIn('NOTICE', archive.namelist())
            self.assertTrue(all('user_files/' not in n for n in archive.namelist()))
            installed = self.root / 'installed'
            archive.extractall(installed)  # Archive is our validated allowlist.
        spec = importlib.util.spec_from_file_location('src.akb.bundled_database', installed / 'akb/database.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        database = module.Database()
        self.assertEqual(database.path, installed / 'data/kanji_db.json')
        self.assertIn('𠮟', database.load())
        self.assertEqual(database.origin, 'Bundled')
        self.assertEqual(database.manifest['sources']['kanjidic2']['snapshot'], '2026-09-10')
        self.assertEqual(database.manifest['sources']['kanjivg']['release'], 'r20250816')
        self.assertEqual(database.load().provenance,
                         {'kd':'2026-09-10', 'vg':'r20250816', 'db':'cf90012dabe9'})
        self.assertFalse((installed / 'user_files').exists())

    def test_missing_input_and_invalid_database_fail_before_replacing_release(self):
        path, _ = release.build(self.root)
        before = path.read_bytes()
        (self.root / 'generated/kanji_db.json').write_text('{}')
        with self.assertRaises(ValueError):
            release.build(self.root)
        self.assertEqual(path.read_bytes(), before)
        (self.root / 'src/akb/runtime.py').unlink()
        with self.assertRaises(FileNotFoundError):
            release.build(self.root)

    def test_rejects_extra_duplicate_and_modified_archive_content(self):
        for name, data in [('tests/private.py', b'private'), ('__init__.py', b'changed')]:
            with self.subTest(name=name):
                path, _ = release.build(self.root)
                with zipfile.ZipFile(path, 'a') as archive:
                    archive.writestr(name, data)
                with self.assertRaises(ValueError):
                    release.validate_archive(path, self.root)

    def test_rejects_personal_defaults_and_runtime_credentials(self):
        config = self.root / 'src/config.json'
        config.write_text('{"version":1,"mappings":[{"notetype_id":123}]}')
        with self.assertRaises(ValueError):
            release.build(self.root)
        config.write_text('{"version":1,"mappings":[]}')
        (self.root / 'src/akb/runtime.py').write_text('# ' + 'ghp_' + 'a' * 36)
        with self.assertRaises(ValueError):
            release.build(self.root)

    def test_legal_checksums_and_version_are_enforced(self):
        (self.root / 'licenses/CC-BY-SA-4.0.txt').write_text('altered')
        with self.assertRaises(ValueError):
            release.build(self.root)
        (self.root / 'VERSION').write_text('../bad')
        with self.assertRaises(ValueError):
            release.version(self.root)

    def test_allowlist_accounts_for_all_current_runtime_sources(self):
        actual = {p.relative_to(release.ROOT / 'src').as_posix()
                  for p in (release.ROOT / 'src').rglob('*') if p.is_file()
                  and '__pycache__' not in p.parts and p.suffix in ('.py', '.json', '.js', '.css')}
        self.assertEqual(actual, set(release.RUNTIME))


if __name__ == '__main__':
    unittest.main()
