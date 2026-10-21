"""Real HTTP + abrupt process termination, using only synthetic execution."""
import json
from pathlib import Path
import socket
import subprocess
import sys
from time import monotonic, sleep
from urllib.error import URLError
from urllib.request import Request, ProxyHandler, build_opener

from .conftest import FIXTURE, ROOT


def test_http_crash_recovery_and_new_submission(tmp_path, fixture_data):
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        port = listener.getsockname()[1]
    base = f'http://127.0.0.1:{port}/api/v1'
    local_http = build_opener(ProxyHandler({}))
    settings_path = tmp_path / 'settings.json'
    settings_path.write_text(json.dumps({'database': str(tmp_path / 'tasks.sqlite3'), 'output': str(tmp_path / 'runs')}), encoding='utf-8')
    code = '''
import sys, time, uvicorn
from pathlib import Path
from traffic_api.app import create_app
from traffic_api.schemas import Settings
class Block:
    def execute(self, config, workspace):
        while True:
            time.sleep(1)
settings = Settings.model_validate_json(Path(sys.argv[1]).read_bytes())
uvicorn.run(create_app(settings, fixture_path=Path(sys.argv[2]), executor=Block()), host='127.0.0.1', port=int(sys.argv[3]))
'''
    def request(path, body=None):
        data = json.dumps(body).encode() if body is not None else None
        with local_http.open(Request(base + path, data=data, headers={'Content-Type': 'application/json'}), timeout=2) as response:
            return json.load(response)
    def until(check):
        deadline = monotonic() + 15
        while monotonic() < deadline:
            try:
                value = check()
                if value:
                    return value
            except (URLError, TimeoutError, ConnectionError):
                pass
            sleep(0.05)
        raise AssertionError('HTTP server did not reach expected state')
    def launch(args, log):
        return subprocess.Popen([sys.executable, *args], cwd=ROOT, stdout=log, stderr=log,
                                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    with (tmp_path / 'process.log').open('wb') as log:
        child = launch(['-c', code, str(settings_path), str(FIXTURE), str(port)], log)
        try:
            until(lambda: request('/datasets'))
            run_id = request('/runs', fixture_data['request'])['run_id']
            until(lambda: request('/runs/' + run_id)['status'] == 'running')
        finally:
            child.terminate()
            child.wait(timeout=10)
        child = launch(['-m', 'traffic_api.app', '--settings', str(settings_path), '--fixture', str(FIXTURE), '--port', str(port)], log)
        try:
            until(lambda: request('/datasets'))
            recovered = request('/runs/' + run_id)
            assert recovered['status'] == 'failed'
            assert recovered['error']['code'] == 'WORKER_INTERRUPTED'
            fresh = request('/runs', fixture_data['request'])['run_id']
            until(lambda: request('/runs/' + fresh)['status'] == 'succeeded')
            assert request('/runs/' + fresh + '/series')['total'] == 4
        finally:
            child.terminate()
            child.wait(timeout=10)
