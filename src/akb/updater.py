"""Optional official-source updates. No Qt, collection access or downloaded code."""
import json
from pathlib import Path
import re
import tempfile
from threading import Lock
import time
import urllib.error
import urllib.parse
import urllib.request
from . import build_data
from .data_store import Store, digest, manifest

KANJIDIC = 'https://www.edrdg.org/kanjidic/kanjidic2.xml.gz'
RELEASES = 'https://api.github.com/repos/KanjiVG/kanjivg/releases?per_page=100'
DAY = 86400
MAX_KD = 16 * 1024 * 1024
MAX_VG = 64 * 1024 * 1024
MAX_API = 4 * 1024 * 1024
HOSTS = {'www.edrdg.org', 'edrdg.org', 'api.github.com', 'github.com',
         'release-assets.githubusercontent.com', 'objects.githubusercontent.com'}
_JOB = Lock()


def allowed_url(url):
    parts = urllib.parse.urlsplit(url)
    if (parts.scheme != 'https' or parts.hostname not in HOSTS or parts.username
            or parts.password or parts.port not in (None, 443)):
        raise ValueError('Untrusted update URL')


class Redirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        allowed_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def download(url, headers, limit):
    allowed_url(url)
    request = urllib.request.Request(url, headers=dict(headers, **{
        'User-Agent': 'Auto-Kanji-Breakdown/0.9 source-data-updater', 'Accept-Encoding': 'identity'}))
    try:
        response = urllib.request.build_opener(Redirects()).open(request, timeout=15)
    except urllib.error.HTTPError as error:
        if error.code == 304:
            return 304, b'', {}
        raise
    with response:
        allowed_url(response.url)
        if response.status != 200:
            raise ValueError('Unexpected HTTP status')
        if int(response.headers.get('Content-Length', '0')) > limit:
            raise ValueError('Download too large')
        body = bytearray()
        deadline = time.monotonic() + 120
        while True:
            chunk = response.read1(min(65536, limit + 1 - len(body)))
            body.extend(chunk)
            if len(body) > limit or time.monotonic() > deadline:
                raise ValueError('Download size/time limit')
            if not chunk:
                break
        return 200, bytes(body), {k: response.headers[k] for k in ('ETag', 'Last-Modified')
                                   if response.headers.get(k) and len(response.headers[k]) < 500}


def enabled(config):
    return not isinstance(config, dict) or config.get('auto_data_updates', True) is not False


def due(state, now, manual=False):
    if manual:
        return True
    try:
        success, attempt = float(state.get('last_success', 0)), float(state.get('last_attempt', 0))
        return (state.get('last_failure') or not success or now - success >= 28 * DAY) and (not attempt or now - attempt >= DAY)
    except (TypeError, ValueError):
        return True


def select_release(releases):
    if not isinstance(releases, list):
        raise ValueError('Expected release list')
    stable = [r for r in releases if isinstance(r, dict) and r.get('draft') is False
              and r.get('prerelease') is False and isinstance(r.get('published_at'), str)]
    if not stable:
        raise ValueError('No stable KanjiVG release')
    release = max(stable, key=lambda r: r['published_at'])
    tag = release.get('tag_name', '')
    if not re.fullmatch(r'r?\d{8}', tag):
        raise ValueError('Unsupported KanjiVG tag')
    assets = [a for a in release.get('assets', []) if a.get('name') == 'kanjivg-' + tag.lstrip('r') + '-main.zip']
    if len(assets) != 1:
        raise ValueError('Stable release missing unique main ZIP')
    asset = assets[0]
    url = asset.get('browser_download_url', '')
    expected = 'https://github.com/KanjiVG/kanjivg/releases/download/' + tag + '/' + asset['name']
    if url != expected or asset.get('size', MAX_VG + 1) > MAX_VG:
        raise ValueError('Unexpected KanjiVG asset URL/size')
    return tag, asset


class Updater:
    def __init__(self, store=None, fetch=download, clock=time.time):
        self.store = store or Store()
        self.fetch, self.clock = fetch, clock

    def run(self, manual=False):
        if not _JOB.acquire(blocking=False):
            return {'status': 'busy'}
        state = {}
        committed = {}
        initialized = False
        stage = 'initialize storage'
        now = self.clock()
        try:
            self.store.initialize()
            initialized = True
            state = self.store.read_json('update_state.json')
            if not isinstance(state, dict):
                state = {}
            committed = dict(state)
            now = self.clock()
            if not due(state, now, manual):
                return {'status': 'not_due'}
            state['last_attempt'] = now
            build_data.write_atomic(self.store.root / 'update_state.json', build_data.encode(state))
            self.store.prune(state)
            current, current_meta, _ = self.store.load()
            cache = state.get('http', {})
            fresh_cache = {}
            with tempfile.TemporaryDirectory(prefix='akb-source-') as temporary:
                work = Path(temporary)

                def fetch(key, url, limit):
                    old = cache.get(key, {})
                    body = None
                    headers = {}
                    old_hash = old.get('sha256', '')
                    if old.get('url') == url and re.fullmatch('[a-f0-9]{64}', old_hash):
                        cached = self.store.checked_path(self.store.root / 'sources' / old_hash)
                        if cached.is_file() and cached.stat().st_size <= limit:
                            candidate = cached.read_bytes()
                            if digest(candidate) == old_hash:
                                body = candidate
                                for src, dst in [('etag', 'If-None-Match'), ('last_modified', 'If-Modified-Since')]:
                                    if old.get(src):
                                        headers[dst] = old[src]
                    status, received, response = self.fetch(url, headers, limit)
                    if status == 304:
                        if body is None:
                            raise ValueError('Not-modified response without cached source')
                    elif status == 200 and len(received) <= limit:
                        body = received
                    else:
                        raise ValueError('Invalid HTTP response/size')
                    fresh_cache[key] = {'url': url, 'sha256': digest(body),
                        'etag': response.get('ETag', old.get('etag')) if status == 304 else response.get('ETag'),
                        'last_modified': response.get('Last-Modified', old.get('last_modified')) if status == 304 else response.get('Last-Modified')}
                    (work / digest(body)).write_bytes(body)
                    return body

                stage = 'download KANJIDIC2'
                kd = fetch('kanjidic2', KANJIDIC, MAX_KD)
                stage = 'select stable KanjiVG release'
                releases = json.loads(fetch('releases', RELEASES, MAX_API))
                tag, asset = select_release(releases)
                stage = 'download KanjiVG'
                vg = fetch('kanjivg', asset['browser_download_url'], MAX_VG)
                same = (digest(kd) == current['sources']['kanjidic2']['sha256'] and
                        digest(vg) == current['sources']['kanjivg']['sha256'])
                meta = current_meta
                selected = None
                if not same:
                    stage = 'build and validate database'
                    kd_path, vg_path = work / 'kanjidic2.xml.gz', work / asset['name']
                    kd_path.write_bytes(kd)
                    vg_path.write_bytes(vg)
                    data, stats = build_data.build(kd_path, vg_path)
                    # Fail closed on unexpectedly truncated yet syntactically valid data.
                    previous_structures = sum('structure' in e for e in current['entries'].values())
                    if (len(data['entries']) < len(current['entries']) * .9 or
                            stats['enriched_characters'] < previous_structures * .8):
                        raise ValueError('Unexpected dictionary/structure coverage loss')
                    raw = build_data.encode(data)
                    retrieved = time.strftime('%Y-%m-%d', time.gmtime(now))
                    meta = manifest(data, raw, retrieved, fresh_cache['kanjidic2'], tag)
                    selected = self.store.stage(raw, meta)
                stage = 'install validated update and cache'
                source_dir = self.store.root / 'sources'
                source_dir.mkdir(exist_ok=True)
                for item in fresh_cache.values():
                    build_data.write_atomic(source_dir / item['sha256'], (work / item['sha256']).read_bytes())
                state.update(last_success=now, last_failure=None, failure_stage=None, failure_http_status=None, http=fresh_cache,
                             current_sources=meta['sources'], database_sha256=meta['sha256'])
                if selected:
                    state['last_update'] = now
                # State first; on failure retain the previous selection and reset retry state.
                build_data.write_atomic(self.store.root / 'update_state.json', build_data.encode(state))
                if selected:
                    build_data.write_atomic(self.store.root / 'current.json', build_data.encode({'generation': selected}))
                return {'status': 'updated' if selected else 'unchanged', 'manifest': meta,
                        'data': data if selected else current}
        except Exception as error:
            state = dict(committed, last_attempt=now)
            state['last_failure'] = type(error).__name__
            state['failure_stage'] = stage
            state['failure_http_status'] = error.code if isinstance(error, urllib.error.HTTPError) else None
            try:
                if initialized:
                    build_data.write_atomic(self.store.root / 'update_state.json', build_data.encode(state))
            except OSError:
                pass
            return {'status': 'failed', 'failure': type(error).__name__}
        finally:
            _JOB.release()
