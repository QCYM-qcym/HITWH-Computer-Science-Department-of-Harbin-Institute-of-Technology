"""A fresh interpreter must serve capacity responses without package reads."""
import json
import os
from pathlib import Path
import subprocess
import sys


def _probe():
    import importlib.abc
    import linecache

    model_attempts = []

    class NoModels(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None):
            if fullname.split('.')[0] in {'torch', 'sklearn', 'joblib'}:
                model_attempts.append(fullname)
                raise RuntimeError('model imports prohibited')

    sys.meta_path.insert(0, NoModels())
    import fastapi.routing
    from fastapi.testclient import TestClient
    import traffic_api.candidate_capacity_view as view
    import traffic_anomaly.candidate_capacity_snapshot as core

    source = os.path.normcase(os.path.abspath(view.__file__))
    roots = tuple(os.path.normcase(os.path.abspath(Path(module.__file__).parent)) + os.sep
                  for module in (view, core))
    assert source not in {os.path.normcase(os.path.abspath(p)) for p in linecache.cache}
    assert not fastapi.routing._endpoint_context_cache
    phase = 'startup'
    opens = {'startup': [], 'request': []}

    def guard(event, args):
        if event != 'open' or not isinstance(args[0], (str, bytes, os.PathLike)):
            return
        path = os.path.normcase(os.path.abspath(os.fsdecode(args[0])))
        if path.startswith(roots):
            opens[phase].append(Path(path).name)
            if phase == 'request':
                raise RuntimeError('request package read prohibited')

    sys.addaudithook(guard)
    payload = b'{"evidence_kind":"SYNTHETIC_ONLY"}\n'
    app = view.create_candidate_capacity_app(core.CandidateCapacitySnapshot(payload, ('a', 'b')))
    cache_entries_after_factory = sum(id(route.endpoint) in fastapi.routing._endpoint_context_cache
                                      for route in app.routes)
    phase = 'request'
    client = TestClient(app, raise_server_exceptions=False)
    routes = ['/candidate/v1/capacity-comparison', '/candidate/capacity',
              '/candidate/capacity.mjs', '/candidate/viewer.css']
    statuses = []
    with client:
        for path in routes:
            response = client.get(path)
            statuses.append(response.status_code)
            assert response.status_code == 200 and response.content
            if path == routes[0]:
                assert response.content == payload
        for path in routes:
            response = client.get(path + '?unexpected=1')
            assert response.status_code == 422 and response.content == b'{"error":"INVALID_QUERY"}\n'
            response = client.post(path)
            assert response.status_code == 405 and response.headers['allow'] == 'GET'
            assert response.content == b'{"error":"METHOD_NOT_ALLOWED"}\n'
            assert client.head(path).status_code == 405
        response = client.get('/candidate/missing')
        assert response.status_code == 404 and response.content == b'{"error":"NOT_FOUND"}\n'
        original_response = view.Response

        def injected_failure(content, *args, **kwargs):
            if content == payload:
                raise RuntimeError('private exception must not be returned')
            return original_response(content, *args, **kwargs)

        view.Response = injected_failure
        response = client.get(routes[0])
        assert response.status_code == 500 and response.content == b'{"error":"INTERNAL_ERROR"}\n'
        view.Response = original_response
        for path in routes:
            assert client.get(path).status_code == 200
        assert client.get(routes[0]).content == payload
    print(json.dumps({'cold_process': True, 'initial_endpoint_cache_size': 0,
                      'factory_cache_entries': cache_entries_after_factory,
                      'first_get_statuses': statuses, 'package_opens': opens,
                      'model_import_attempts': model_attempts,
                      'loaded_model_modules': sorted(name for name in sys.modules
                          if name.split('.')[0] in {'torch', 'sklearn', 'joblib'})}))


def test_first_capacity_requests_do_not_open_packages_in_cold_process():
    result = subprocess.run([sys.executable, '-X', 'utf8', str(Path(__file__).resolve()), '--probe'],
                            capture_output=True, text=True, timeout=30,
                            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    assert result.returncode == 0, result.stdout + result.stderr
    evidence = json.loads(result.stdout)
    assert evidence['package_opens']['request'] == [], evidence
    assert evidence['factory_cache_entries'] == 4, evidence
    assert 'candidate_capacity_view.py' in evidence['package_opens']['startup'], evidence
    assert all(asset in evidence['package_opens']['startup']
               for asset in ('capacity.html', 'capacity.mjs', 'viewer.css')), evidence
    assert evidence['model_import_attempts'] == [], evidence
    assert evidence['loaded_model_modules'] == [], evidence


if __name__ == '__main__' and sys.argv[1:] == ['--probe']:
    _probe()
