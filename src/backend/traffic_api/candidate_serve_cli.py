"""Trusted-terminal launcher for existing synthetic saved-result packages.

Admission verifies stored relations; serving consumes immutable snapshots.
The optional lifetime requests graceful shutdown, not a hard execution limit.
"""
import asyncio
from contextlib import contextmanager
import json
import logging
import os
from pathlib import Path
import re
import socket
import sys

import uvicorn
from traffic_anomaly.candidate_cli import _Parser, _SafeError
from traffic_anomaly.candidate_artifacts import CandidateArtifactError, load_verified_candidate_artifacts, _same, _deep_thaw
from traffic_anomaly.candidate_run_artifacts import CandidateRunArtifactError, load_verified_candidate_if_run
from traffic_anomaly.candidate_ae_run_artifacts import CandidateAERunArtifactError, load_verified_candidate_ae_run
from traffic_anomaly.candidate_comparison import CandidateComparisonError, CandidateComparisonRun, compare_candidate_runs
from traffic_anomaly.candidate_capacity_contract import CandidateCapacityComparisonError, SAFE_ERROR_CODES as _CAPACITY_CODES
from .candidate_app import CandidateRegistration, CandidateRegistrationError
from .candidate_viewer import CandidateViewerError, create_candidate_viewer_app
from .candidate_capacity_view import CandidateCapacityViewError, create_candidate_capacity_app

_ARTIFACT_CODES = {'INPUT_UNAVAILABLE', 'INVALID_PACKAGE', 'INCOMPATIBLE_PACKAGE', 'INTEGRITY_MISMATCH',
                   'REPLAY_MISMATCH', 'RESOURCE_LIMIT', 'INVALID_RUN_ARTIFACTS', 'INCOMPATIBLE_RUN'}
_COMPARISON_CODES = _ARTIFACT_CODES | {'INVALID_COMPARISON', 'DUPLICATE_RUN_DIRECTORY', 'DUPLICATE_RUN_ID',
    'DUPLICATE_RUN_SLOT', 'CHANGED_DURING_COMPARISON', 'INCOMPARABLE_UPSTREAM',
    'INCOMPARABLE_QUALIFICATION', 'INCONSISTENT_VERIFICATION_SCOPE'}
_LOGGERS = ('uvicorn', 'uvicorn.error', 'uvicorn.access', 'uvicorn.asgi')


def _error(code):
    print(json.dumps({'error': code}, separators=(',', ':')), file=sys.stderr)
    return 2


class _SafeFormatter(logging.Formatter):
    def format(self, record):
        # Do not invoke the default formatter: it appends exc_info/stack_info.
        return '{"error":"SERVER_DIAGNOSTIC"}'


@contextmanager
def _safe_uvicorn_logging():
    saved = []
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(_SafeFormatter())
    for name in _LOGGERS:
        logger = logging.getLogger(name)
        saved.append((logger, logger.handlers, logger.filters, logger.level, logger.propagate, logger.disabled))
        logger.handlers, logger.filters = [handler], []
        logger.setLevel(logging.WARNING)
        logger.propagate, logger.disabled = False, False
    try:
        yield
    finally:
        for logger, handlers, filters, level, propagate, disabled in saved:
            logger.handlers, logger.filters = handlers, filters
            logger.setLevel(level)
            logger.propagate, logger.disabled = propagate, disabled
        handler.close()


def _event(event, port, run_ids, *, page_path='/candidate'):
    value = dict(schema_version=1, event=event, evidence_kind='SYNTHETIC_ONLY', policy_status='AUDIT_ONLY',
        scope='SYNTHETIC_SAVED_RUN_VIEWER', host='127.0.0.1', port=port,
        url=f'http://127.0.0.1:{port}{page_path}', run_ids=run_ids, pid=os.getpid(), parent_pid=os.getppid())
    payload = (json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(',', ':')) + '\n').encode('utf-8')
    sys.stdout.buffer.write(payload)
    sys.stdout.buffer.flush()


class _ViewerServer(uvicorn.Server):
    def __init__(self, config, *, port, run_ids, shutdown_after_seconds=None, page_path='/candidate'):
        super().__init__(config)
        self.port, self.run_ids = port, list(run_ids)
        self.page_path = page_path
        self.shutdown_after_seconds = shutdown_after_seconds
        self.shutdown_completed = False
        self._timer = None

    def cancel_timer(self):
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None

    async def startup(self, sockets=None):
        await super().startup(sockets=sockets)
        if not self.started:
            raise RuntimeError('STARTUP_FAILED')
        _event('SERVER_READY', self.port, self.run_ids, page_path=self.page_path)
        if self.shutdown_after_seconds is not None:
            self._timer = asyncio.get_running_loop().call_later(
                self.shutdown_after_seconds, lambda: setattr(self, 'should_exit', True))

    async def shutdown(self, sockets=None):
        self.cancel_timer()
        await super().shutdown(sockets=sockets)
        if self.force_exit:
            return  # Uvicorn skipped graceful draining/lifespan completion.
        self.shutdown_completed = True
        _event('SERVER_STOPPED', self.port, self.run_ids, page_path=self.page_path)


def _integer(value):
    if not re.fullmatch('[0-9]+', value, flags=re.ASCII):
        raise _SafeError('INVALID_ARGUMENTS')
    try:
        return int(value)
    except ValueError:
        raise _SafeError('INVALID_ARGUMENTS') from None


def _load_capacity_snapshot(args):
    # Lazy import keeps old modes independent of the capacity admission seam.
    from traffic_anomaly.candidate_capacity_snapshot import load_verified_candidate_capacity_comparison
    return load_verified_candidate_capacity_comparison(args.ae_run, args.records, args.inputs,
                                                      source_fixture=args.source_fixture)


def main(argv=None, *, expected_run_identities=None, expected_source_fixture=None,
         expected_comparison_identities=None):
    """Optionally bind trusted demo identities to the admitted immutable reports.

    This programmatic constraint adds no CLI option and does no extra loading.
    Ordinary callers retain the existing one-to-four arbitrary-run contract.
    """
    parser = _Parser(description='Foreground read-only SYNTHETIC_ONLY candidate viewer', allow_abbrev=False)
    parser.add_argument('--records', type=Path, required=True)
    parser.add_argument('--inputs', type=Path, required=True)
    parser.add_argument('--source-fixture', type=Path)
    parser.add_argument('--if-run', type=Path, action='append', default=[])
    parser.add_argument('--ae-run', type=Path, action='append', default=[])
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument('--comparison', action='store_true', help='Verify same-condition saved-method comparison at startup')
    modes.add_argument('--capacity-comparison', action='store_true', help='View the separate fixed AE capacity comparison')
    parser.add_argument('--port', type=_integer, default=0)
    parser.add_argument('--shutdown-after-seconds', type=_integer)
    try:
        args = parser.parse_args(argv)
        if (not 1 <= len(args.if_run) + len(args.ae_run) <= 4 or not 0 <= args.port <= 65535
                or args.comparison and len(args.if_run) + len(args.ae_run) < 2
                or expected_comparison_identities is not None and not args.comparison
                or args.shutdown_after_seconds is not None and not 1 <= args.shutdown_after_seconds <= 3600):
            raise _SafeError('INVALID_ARGUMENTS')
        if args.capacity_comparison:
            if (args.if_run or not 2 <= len(args.ae_run) <= 4 or any(value is not None for value in
                    (expected_run_identities, expected_source_fixture, expected_comparison_identities))):
                raise _SafeError('INVALID_ARGUMENTS')
            if args.source_fixture is None:
                raise _SafeError('SOURCE_REQUIRED')
    except _SafeError as exc:
        return _error('SOURCE_REQUIRED' if exc.args == ('SOURCE_REQUIRED',) else 'INVALID_ARGUMENTS')
    server_options = {}
    try:
        if args.capacity_comparison:
            snapshot = _load_capacity_snapshot(args)
            app = create_candidate_capacity_app(snapshot)
            run_ids = list(snapshot.run_ids)
            server_options['page_path'] = '/candidate/capacity'
        else:
            app, run_ids = _classic_app(args, expected_run_identities, expected_source_fixture,
                                        expected_comparison_identities)
    except CandidateCapacityComparisonError as exc:
        return _error(exc.code if type(exc.code) is str and exc.code in _CAPACITY_CODES else 'INVALID_CAPACITY_COMPARISON')
    except CandidateCapacityViewError as exc:
        return _error(exc.code if type(exc.code) is str and exc.code in (
            'INVALID_CAPACITY_SNAPSHOT', 'VIEWER_ASSETS_UNAVAILABLE') else 'INVALID_CAPACITY_SNAPSHOT')
    except (CandidateArtifactError, CandidateRunArtifactError, CandidateAERunArtifactError) as exc:
        return _error(exc.code if type(exc.code) is str and exc.code in _ARTIFACT_CODES else 'INVALID_ARTIFACTS')
    except CandidateComparisonError as exc:
        return _error(exc.code if type(exc.code) is str and exc.code in _COMPARISON_CODES else 'INVALID_COMPARISON')
    except CandidateRegistrationError:
        return _error('INVALID_REGISTRATION')
    except CandidateViewerError:
        return _error('VIEWER_ASSETS_UNAVAILABLE')
    except KeyboardInterrupt:
        return 130
    except Exception:
        return _error('STARTUP_FAILED')

    return _serve(app, run_ids, args, server_options)


def _classic_app(args, expected_run_identities, expected_source_fixture, expected_comparison_identities):
    inputs = load_verified_candidate_artifacts(args.records, args.inputs, source_fixture=args.source_fixture)
    if expected_source_fixture is not None:
        if (inputs.report['checks']['source_replay'] != 'VERIFIED'
                or not _same(_deep_thaw(inputs.report['source_fixture']), expected_source_fixture)):
            raise CandidateRegistrationError('INVALID_REGISTRATION')
    registrations = []
    for directories, loader in ((args.if_run, load_verified_candidate_if_run),
                                 (args.ae_run, load_verified_candidate_ae_run)):
        for directory in directories:
            run = loader(directory, args.records, args.inputs, source_fixture=args.source_fixture)
            registrations.append(CandidateRegistration(run, inputs))
    if expected_run_identities is not None:
        actual = tuple((registration.run.report['run_id'], registration.run.report['selected_policy'])
                       for registration in registrations)
        if actual != expected_run_identities:
            raise CandidateRegistrationError('INVALID_REGISTRATION')
    if args.comparison:
        specs = [CandidateComparisonRun(family, directory)
            for family, directories in (('iforest', args.if_run), ('autoencoder', args.ae_run))
            for directory in directories]
        comparison = compare_candidate_runs(specs, args.records, args.inputs, source_fixture=args.source_fixture)
        if expected_comparison_identities is not None:
            actual = [dict(slot=row['slot'], run_id=row['run_id']) for row in comparison['runs']]
            expected = [dict(slot=slot, run_id=run_id) for slot, run_id in expected_comparison_identities]
            if not _same(actual, expected):
                raise CandidateRegistrationError('INVALID_REGISTRATION')
        app = create_candidate_viewer_app(registrations, comparison=comparison)
    else:
        app = create_candidate_viewer_app(registrations)
    return app, [registration.run.report['run_id'] for registration in registrations]

def _serve(app, run_ids, args, server_options):
    listener, server, stage = None, None, 'BIND_FAILED'
    result = 2
    try:
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.bind(('127.0.0.1', args.port))
        port = listener.getsockname()[1]
        stage = 'STARTUP_FAILED'
        with _safe_uvicorn_logging():
            config = uvicorn.Config(app, host='127.0.0.1', port=port, workers=1, reload=False,
                access_log=False, log_config=None, log_level=None, loop='asyncio', http='h11', ws='none', proxy_headers=False)
            server = _ViewerServer(config, port=port, run_ids=run_ids, shutdown_after_seconds=args.shutdown_after_seconds,
                                   **server_options)
            server.run(sockets=[listener])
            result = 0 if server.started and server.shutdown_completed else _error('SERVER_FAILED' if server.started else 'STARTUP_FAILED')
    except KeyboardInterrupt:
        result = 130
    except (Exception, SystemExit):
        result = _error('SERVER_FAILED' if server is not None and server.started else stage)
    finally:
        if server is not None:
            server.cancel_timer()
        if listener is not None:
            try:
                listener.close()
            except OSError:
                result = _error('SERVER_FAILED')
    return result


if __name__ == '__main__':
    raise SystemExit(main())
