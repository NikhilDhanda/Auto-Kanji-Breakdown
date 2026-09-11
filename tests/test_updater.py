"""Network-free source update and fallback regression tests."""
from copy import deepcopy
import gzip
import io
import json
from pathlib import Path
import socket
import tempfile
import unittest
from unittest.mock import patch
import urllib.error
import zipfile
from src.akb import build_data as builder
from src.akb import updater
from src.akb.data_store import Store, manifest, digest, validate_pair, provenance
from src.akb.database import Entries
from src.akb.payload import build_payload, serialize, deserialize


def kd(meaning='person'):
    return gzip.compress(('<kanjidic2><header><file_version>4</file_version><date_of_creation>2026-09-10</date_of_creation></header>'
                         '<character><literal>人</literal><misc><stroke_count>2</stroke_count></misc>'
                         '<reading_meaning><rmgroup><meaning>' + meaning + '</meaning></rmgroup></reading_meaning>'
                         '</character></kanjidic2>').encode(), mtime=0)


def vg(extra='', name='kanji/04eba.svg'):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w') as archive:
        archive.writestr(name, '<svg xmlns="http://www.w3.org/2000/svg" xmlns:kvg="http://kanjivg.tagaini.net">'
                         '<g id="kvg:StrokePaths_04eba"><g kvg:element="人">' + extra + '</g></g></svg>')
    return stream.getvalue()


def release(tag='r20250816', prerelease=False):
    name = 'kanjivg-' + tag[1:] + '-main.zip'
    return {'draft': False, 'prerelease': prerelease, 'tag_name': tag, 'published_at': tag[1:],
            'assets': [{'name': name, 'size': 1000,
                        'browser_download_url': 'https://github.com/KanjiVG/kanjivg/releases/download/' + tag + '/' + name}]}


class UpdateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.kd, self.vg = kd(), vg()
        self.kpath, self.vpath = self.root/'kanjidic2.xml.gz', self.root/'kanjivg-20250816-main.zip'
        self.kpath.write_bytes(self.kd); self.vpath.write_bytes(self.vg)
        self.baseline, _ = builder.build(self.kpath, self.vpath)
        self.raw = builder.encode(self.baseline)
        self.bundled = self.root/'data/kanji_db.json'
        self.bundled.parent.mkdir(); self.bundled.write_bytes(self.raw)
        self.meta = manifest(self.baseline, self.raw)
        self.bundled.with_name('manifest.json').write_bytes(builder.encode(self.meta))
        self.store = Store(self.bundled, self.root/'user_files/akb_updates')
        self.now = 10000000
        self.responses = {updater.KANJIDIC: self.kd, updater.RELEASES: json.dumps([release()]).encode(),
                          release()['assets'][0]['browser_download_url']: self.vg}
        self.calls = []

    def tearDown(self):
        self.temp.cleanup()

    def fetch(self, url, headers, limit):
        self.calls.append((url, headers))
        data = self.responses[url]
        tag = digest(data)
        if headers.get('If-None-Match') == tag:
            return 304, b'', {}
        return 200, data, {'ETag': tag, 'Last-Modified': 'Thu, 10 Sep 2026 00:00:00 GMT'}

    def run_update(self, manual=False):
        return updater.Updater(self.store, self.fetch, lambda: self.now).run(manual)

    def changed(self):
        self.responses[updater.KANJIDIC] = kd('human being')

    def test_bundled_fallback_and_valid_user_preference(self):
        self.assertEqual(self.store.load()[2], 'Bundled')
        self.changed()
        result = self.run_update()
        self.assertEqual(result['status'], 'updated')
        data, meta, origin = self.store.load()
        self.assertEqual(origin, 'Updated')
        self.assertEqual(data['entries']['人']['meanings'], ['human being'])
        self.assertEqual(meta['sha256'], digest(builder.encode(data)))
        self.assertEqual(self.bundled.read_bytes(), self.raw)

    def test_corrupt_or_incompatible_user_database_falls_back(self):
        self.changed(); self.run_update()
        generation = self.store.read_json('current.json')['generation']
        path = self.store.root/'database'/generation/'kanji_db.json'
        for content in [b'bad', builder.encode(dict(self.baseline, schema_version=99))]:
            path.write_bytes(content)
            self.assertEqual(self.store.load()[2], 'Bundled')

    def test_scheduling_manual_bypass_and_state_persistence(self):
        self.assertEqual(self.run_update()['status'], 'unchanged')
        self.assertEqual(self.run_update()['status'], 'not_due')
        self.assertEqual(len(self.calls), 3)
        self.now += 27 * updater.DAY
        self.assertEqual(self.run_update()['status'], 'not_due')
        self.assertEqual(self.run_update(True)['status'], 'unchanged')
        self.now += 28 * updater.DAY
        self.assertEqual(self.run_update()['status'], 'unchanged')
        self.assertEqual(self.store.read_json('update_state.json')['last_success'], self.now)

    def test_offline_timeout_dns_http_failures_are_silent_results_and_back_off(self):
        for error in [OSError('offline'), TimeoutError(), socket.gaierror(),
                      urllib.error.HTTPError(updater.KANJIDIC, 503, 'unavailable', {}, None)]:
            with self.subTest(error=type(error).__name__):
                service = updater.Updater(self.store, lambda *a: (_ for _ in ()).throw(error), lambda: self.now)
                self.assertEqual(service.run(True)['status'], 'failed')
                state = self.store.read_json('update_state.json')
                self.assertEqual(state['last_failure'], type(error).__name__)
                self.assertFalse(updater.due(state, self.now+23*3600))
                self.assertTrue(updater.due(state, self.now+updater.DAY))
                self.assertEqual(self.store.load()[2], 'Bundled')

    def test_conditional_not_modified_and_no_change(self):
        self.run_update()
        result = self.run_update(True)
        self.assertEqual(result['status'], 'unchanged')
        self.assertTrue(all('If-None-Match' in headers and 'If-Modified-Since' in headers for _,headers in self.calls[-3:]))
        self.assertFalse((self.store.root/'current.json').exists())

    def test_not_modified_without_cache_is_rejected(self):
        service = updater.Updater(self.store, lambda *a: (304,b'',{}), lambda: self.now)
        self.assertEqual(service.run()['status'], 'failed')

    def test_changed_stable_kanjivg_ignores_prerelease(self):
        stable = release('r20260909')
        self.responses[updater.RELEASES] = json.dumps([release('r20260910',True),stable]).encode()
        self.responses[stable['assets'][0]['browser_download_url']] = vg('<g kvg:element="一"/>')
        result = self.run_update()
        self.assertEqual(result['status'], 'updated')
        self.assertEqual(result['manifest']['sources']['kanjivg']['release'],'r20260909')

    def test_unsafe_source_selection_and_urls(self):
        for bad in ['http://www.edrdg.org/a','https://evil.example/a','https://user@github.com/a','https://github.com:444/a']:
            with self.assertRaises(ValueError): updater.allowed_url(bad)
        for field,value in [('name','kanjivg-20250816-all.zip'),('browser_download_url','https://evil.example/a')]:
            row=release();row['assets'][0][field]=value
            with self.assertRaises(ValueError): updater.select_release([row])

    def test_download_limit_and_bad_zip_gzip_xml_svg(self):
        bad_inputs = [(updater.KANJIDIC,b'not gzip'),(updater.KANJIDIC,gzip.compress(b'<broken>')),
                      (updater.KANJIDIC,gzip.compress(b'<!ENTITY x "bad"><kanjidic2/>')),
                      (release()['assets'][0]['browser_download_url'],b'not zip'),
                      (release()['assets'][0]['browser_download_url'],vg(name='../escape.svg')),
                      (release()['assets'][0]['browser_download_url'],vg('<unclosed>'))]
        for url,body in bad_inputs:
            original=self.responses[url];self.responses[url]=body
            self.assertEqual(self.run_update(True)['status'],'failed')
            self.assertEqual(self.store.load()[2],'Bundled')
            self.responses[url]=original
        with patch.object(updater,'MAX_KD',2):
            self.assertEqual(self.run_update(True)['status'],'failed')

    def test_archive_limits(self):
        with self.assertRaises(ValueError):
            builder.parse_kanjidic(b'<kanjidic2><header><sha256>forged</sha256></header></kanjidic2>')
        with patch.object(builder,'MAX_ZIP_TOTAL',2):
            with self.assertRaises(ValueError): builder.parse_kanjivg(self.vpath)
        with patch.object(builder,'MAX_ZIP_ENTRIES',0):
            with self.assertRaises(ValueError): builder.parse_kanjivg(self.vpath)
        with patch.object(builder,'MAX_SVG',2):
            with self.assertRaises(ValueError): builder.parse_kanjivg(self.vpath)
        with patch.object(builder,'MAX_XML',2):
            with self.assertRaises(ValueError): builder.build(self.kpath,self.vpath)

    def test_incomplete_selection_manifest_and_saved_state_fall_back(self):
        self.changed(); self.run_update()
        pointer = (self.store.root/'current.json').read_bytes()
        for broken in [b'[]', b'null', b'{', b'{"generation":null}']:
            (self.store.root/'current.json').write_bytes(broken)
            self.assertEqual(self.store.load()[2], 'Bundled')
        (self.store.root/'current.json').write_bytes(pointer)
        folder = self.store.root/'database'/json.loads(pointer)['generation']
        with patch('src.akb.data_store.MAX_DATABASE', len(self.raw)):
            self.assertEqual(self.store.load()[2], 'Bundled')
        for broken in [b'[]', b'null', b'{}']:
            (folder/'manifest.json').write_bytes(broken)
            self.assertEqual(self.store.load()[2], 'Bundled')
        (folder/'manifest.json').unlink()
        self.assertEqual(self.store.load()[2], 'Bundled')
        bad = deepcopy(self.meta)
        bad['sources']['kanjidic2']['snapshot'] = '1900-01-01'
        with self.assertRaises(ValueError): validate_pair(self.raw, bad)

    def test_storage_paths_cannot_escape_owned_namespace(self):
        with self.assertRaises(ValueError):
            self.store.checked_path(self.store.root/'..'/'unrelated')

    def test_failure_preserves_installed_update_and_retries_after_success(self):
        self.changed(); self.run_update()
        before = (self.store.root/'current.json').read_bytes()
        self.now += 28 * updater.DAY
        self.responses[updater.KANJIDIC] = b'broken'
        self.assertEqual(self.run_update()['status'], 'failed')
        self.assertEqual((self.store.root/'current.json').read_bytes(), before)
        self.assertEqual(self.store.load()[2], 'Updated')
        state = self.store.read_json('update_state.json')
        self.assertTrue(state['last_success'])
        self.assertTrue(state['failure_stage'])
        self.assertFalse(updater.due(state, self.now + updater.DAY - 1))
        self.assertTrue(updater.due(state, self.now + updater.DAY))

    def test_headers_optional_and_source_cache_pruned(self):
        self.changed()
        fetch = lambda url, headers, limit: (200, self.responses[url], {})
        result = updater.Updater(self.store, fetch, lambda: self.now).run(True)
        self.assertEqual(result['status'], 'updated')
        obsolete = self.store.root/'sources'/('0'*64)
        obsolete.write_bytes(b'obsolete')
        self.run_update(True)
        self.assertFalse(obsolete.exists())

    def test_transport_enforces_https_timeout_and_stream_limits(self):
        from types import SimpleNamespace
        class Response(io.BytesIO):
            url = updater.KANJIDIC
            status = 200
            headers = {}
        captured = []
        def opening(request, timeout):
            captured.append((request, timeout))
            return Response(b'12345')
        with patch.object(updater.urllib.request, 'build_opener', return_value=SimpleNamespace(open=opening)):
            self.assertEqual(updater.download(updater.KANJIDIC, {}, 5)[1], b'12345')
            with self.assertRaises(ValueError): updater.download(updater.KANJIDIC, {}, 4)
        self.assertEqual(captured[0][1], 15)
        self.assertIn('Auto-Kanji-Breakdown', captured[0][0].get_header('User-agent'))
        with self.assertRaises(ValueError):
            updater.Redirects().redirect_request(None, None, 302, '', {}, 'http://github.com/a')

    def test_builder_validator_and_atomic_install_failures_keep_previous(self):
        self.changed()
        for target in ['build','validate']:
            with patch.object(builder,target,side_effect=ValueError('rejected')):
                self.assertEqual(self.run_update(True)['status'],'failed')
            self.assertEqual(self.store.load()[2],'Bundled')
        original=builder.write_atomic
        def fail_pointer(path, raw):
            if path.name=='current.json':raise OSError('replace failed')
            original(path,raw)
        with patch.object(builder,'write_atomic',side_effect=fail_pointer):
            self.assertEqual(self.run_update(True)['status'],'failed')
        self.assertEqual(self.store.load()[2],'Bundled')
        self.assertNotIn('last_update',self.store.read_json('update_state.json'))
        self.assertEqual(self.run_update(True)['status'],'updated')

    def test_temporary_sources_cleaned_up(self):
        self.changed()
        original=builder.build; directories=[]
        def wrapped(k,v):
            directories.append(k.parent)
            return original(k,v)
        with patch.object(builder,'build',side_effect=wrapped):self.run_update()
        self.assertTrue(directories)
        self.assertTrue(all(not p.exists() for p in directories))

    def test_concurrent_job_does_not_call_http_or_collection(self):
        with updater._JOB:
            self.assertEqual(self.run_update(True)['status'],'busy')
        self.assertEqual(self.calls,[])
        # Updater accepts filesystem/transport/time only, never a collection.
        self.assertEqual(self.run_update()['status'],'unchanged')

    def test_cleanup_only_owned_namespace(self):
        other=self.store.root.parent/'personal.txt';other.parent.mkdir(parents=True);other.write_text('keep')
        self.run_update();self.store.clear()
        self.assertTrue(other.exists());self.assertFalse(self.store.root.exists())
        self.store.root.mkdir();(self.store.root/'unknown').write_text('keep')
        with self.assertRaises(ValueError):self.store.clear()

    def test_optional_provenance_and_default_setting(self):
        plain=build_payload(['人'],self.baseline['entries'])
        self.assertNotIn('provenance',plain)
        entries=Entries(self.baseline['entries']);entries.provenance=provenance(self.meta)
        payload=build_payload(['人'],entries)
        self.assertEqual(deserialize(serialize(payload)),payload)
        self.assertEqual(payload['provenance']['kd'],'2026-09-10')
        self.assertEqual(payload['version'],1)
        self.assertTrue(updater.enabled({}));self.assertTrue(updater.enabled(None))
        self.assertFalse(updater.enabled({'auto_data_updates':False}))

    def test_background_control_settings_diagnostics_and_no_collection_access(self):
        from types import SimpleNamespace
        from src.akb.update_service import UpdateService
        from src.akb import update_service
        raw={'version':1,'mappings':[], 'auto_data_updates':False}
        manager=SimpleNamespace(writeConfig=lambda name,value:raw.update(value))
        adapter=SimpleNamespace(mw=SimpleNamespace(addonManager=manager),addon_name='test',
                                database_path=None,generation=1,running=False,loading=False,
                                runtime=None,legacy_config=lambda:raw)
        service=UpdateService(adapter)
        calls=[]
        class Query:
            def __init__(inner,parent,op,success):inner.op,inner.success=op,success
            def failure(inner,callback):return inner
            def without_collection(inner):calls.append('without_collection');return inner
            def run_in_background(inner):inner.success(inner.op(None))
        with patch.dict('sys.modules',{'aqt.operations':SimpleNamespace(QueryOp=Query)}), patch.object(
                updater.Updater,'run',return_value={'status':'unchanged'}) as run:
            service.start();run.assert_not_called()
            service.start(manual=True);run.assert_called_once_with(True)
            service.busy=True;service.start(manual=True);self.assertEqual(run.call_count,1)
        self.assertEqual(calls,['without_collection'])
        service.set_enabled(True)
        self.assertTrue(raw['auto_data_updates']);self.assertEqual(raw['mappings'],[])
        with patch.object(update_service,'Store',return_value=self.store):
            info=service.diagnostics()
        self.assertIn('Bundled',info);self.assertIn(self.meta['sha256'],info)
        self.assertIn('Regenerate Breakdowns',info)

    def test_adoption_waits_for_collection_operation_without_regenerating(self):
        from types import SimpleNamespace
        from src.akb.update_service import UpdateService
        old={};new={'人':{}}
        adapter=SimpleNamespace(running=True,loading=False,runtime=SimpleNamespace(entries=old))
        service=UpdateService(adapter);service.pending=SimpleNamespace(load=lambda:new)
        service.adopt();self.assertIs(adapter.runtime.entries,old)
        adapter.running=False;service.adopt()
        self.assertIs(adapter.runtime.entries,new);self.assertIsNone(service.pending)

    def test_updated_snapshot_refreshes_only_requested_notes(self):
        from types import SimpleNamespace
        from src.akb.update_service import UpdateService
        from src.akb.runtime import Runtime
        from src.akb.config import parse_config
        class Note(dict):
            mid = 1
            def note_type(self):
                return {'id':1, 'flds':[{'name':name} for name in self.keys()]}
        runtime = Runtime(self.baseline['entries'], parse_config({'version':1,'mappings':[
            {'enabled':True,'notetype_id':1,'source_fields':['Text'],'output_field':'Output'}]}))
        untouched = Note(Text='人',Output='')
        runtime.refresh(untouched)
        before = dict(untouched)
        self.changed(); result = self.run_update()
        entries = Entries(result['data']['entries']); entries.provenance = provenance(result['manifest'])
        adapter = SimpleNamespace(running=False,loading=False,runtime=runtime)
        service = UpdateService(adapter); service.pending = SimpleNamespace(load=lambda:entries)
        service.adopt()
        self.assertEqual(dict(untouched), before)
        for manual in [False, True]:
            note = Note(Text='人',Output=before['Output'] if manual else '')
            self.assertTrue(runtime.refresh(note,manual=manual).changed)
            self.assertEqual(deserialize(note['Output'])['entries'][0]['meanings'], ['human being'])
            self.assertEqual(deserialize(note['Output'])['provenance'], entries.provenance)

    def test_notifications_only_on_successful_update_and_not_stale_profile(self):
        from types import SimpleNamespace
        from src.akb.update_service import UpdateService
        adapter = SimpleNamespace(mw=object(),database_path=None,generation=1,running=False,
                                  loading=False,runtime=SimpleNamespace(entries={}),legacy_config=lambda:{})
        service = UpdateService(adapter)
        queued = []
        class Query:
            def __init__(inner,parent,op,success): inner.op,inner.success=op,success
            def failure(inner,callback): return inner
            def without_collection(inner): return inner
            def run_in_background(inner): queued.append(inner)
        messages = []
        modules = {'aqt.operations':SimpleNamespace(QueryOp=Query),
                   'aqt.utils':SimpleNamespace(tooltip=lambda message,**kw:messages.append(message))}
        with patch.dict('sys.modules',modules):
            for status in ['unchanged','failed','not_due','busy','updated']:
                result = {'status':status,'data':self.baseline,'manifest':self.meta}
                with patch.object(updater.Updater,'run',return_value=result):
                    service.start(True)
                    job = queued.pop()
                    self.assertTrue(service.busy)
                    job.success(job.op(None))
                self.assertFalse(service.busy)
            self.assertEqual(len(messages),1)
            self.assertIn('Regenerate Breakdowns',messages[0])
            with patch.object(updater.Updater,'run',return_value={'status':'updated','data':self.baseline,'manifest':self.meta}):
                service.start(True); job = queued.pop(); adapter.generation += 1
                job.success(job.op(None))
            self.assertEqual(len(messages),1)
