"""Explicit saved-state inspection, replay and two-output learned fit adapter.

Receipts describe internal consistency, never source authentication. Imports are
staged so help is stdlib-only and inspection needs only the learned disk codec.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import fields
import importlib
import json
import os
import re
import sys

_HELP = (
    'usage: python -m traffic_anomaly.release_if_learned_cli COMMAND OPTIONS\n'
    '\ncommands:\n'
    '  inspect --learned-package ABS\n'
    '  replay --learned-package ABS --result-package ABS --raw-package ABS --prepared-package ABS\n'
    '  fit-save --raw-package ABS --prepared-package ABS --view {current13,h30_26} --result-output NEW_ABS --learned-output NEW_ABS\n'
    '\nChecks saved internal consistency; explicit replay checks numerical agreement.\n'
    '  -h, --help   show this fixed usage\n'
).encode('utf-8')
_OUTPUT_LIMIT = 32768
_OPTIONS = {
    'inspect': ('--learned-package',),
    'replay': ('--learned-package', '--result-package', '--raw-package', '--prepared-package'),
    'fit-save': ('--raw-package', '--prepared-package', '--view', '--result-output', '--learned-output'),
}
_LEARNED_CODES = frozenset(('INVALID_LEARNED_ARGUMENTS INVALID_LEARNED_PACKAGE '
    'INCOMPATIBLE_LEARNED_PACKAGE RESOURCE_LIMIT INTEGRITY_MISMATCH INPUT_BINDING_MISMATCH '
    'NO_TRAINING_NORMAL NO_CALIBRATION_NORMAL INVALID_INPUT_NUMERIC MODEL_UNAVAILABLE MODEL_ERROR '
    'INVALID_MODEL_STATE INVALID_MODEL_SCORES SCORE_MISMATCH CALIBRATION_MISMATCH PREDICTION_MISMATCH '
    'INCOMPATIBLE_RUNTIME INVALID_PACKAGE_PATH INPUT_UNAVAILABLE OUTPUT_EXISTS PACKAGE_CHANGED '
    'OUTPUT_ERROR LEARNED_ERROR').split())
_PACKAGE_CODES = frozenset(('INVALID_PACKAGE_ARGUMENTS INVALID_PACKAGE INCOMPATIBLE_PACKAGE '
    'RESOURCE_LIMIT INTEGRITY_MISMATCH INCONSISTENT_PACKAGE INVALID_PACKAGE_PATH INPUT_UNAVAILABLE '
    'OUTPUT_EXISTS PACKAGE_CHANGED OUTPUT_ERROR').split())
_CLI_CODES = frozenset(('INVALID_ARGUMENTS INVALID_PATH_LAYOUT INVALID_RESULT INTERRUPTED '
    'INTERNAL_ERROR OUTPUT_ERROR OUTPUT_EXISTS INVALID_PACKAGE_PATH INPUT_UNAVAILABLE PACKAGE_CHANGED '
    'RESOURCE_LIMIT INCOMPATIBLE_RUNTIME').split())
_ERROR_CODES = {}
_FIELDS = ('profile_id', 'context_sha256', 'manifest_sha256', 'manifest_byte_count')
_SHA = re.compile(r'[0-9a-f]{64}\Z')


class _CLIError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


class _AdmittedFailure(ValueError):
    """Carry a classified dependency code without rereading its getter."""
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def _need(condition, code='INVALID_RESULT'):
    if not condition:
        raise _CLIError(code) from None


def _import(name):
    try:
        return importlib.import_module('.' + name, __package__)
    except ModuleNotFoundError as error:
        if (type(error) is ModuleNotFoundError and type(error.name) is str
                and error.name.split('.')[0] == 'numpy'):
            raise _CLIError('INCOMPATIBLE_RUNTIME') from None
        raise


def _learned_disk():
    module = _import('release_if_learned_package')
    _ERROR_CODES[module.ReleaseIFLearnedError] = _LEARNED_CODES
    return module


def _arguments(argv):
    if argv is None:
        argv = sys.argv[1:]
    _need(not isinstance(argv, (str, bytes)) and isinstance(argv, Sequence), 'INVALID_ARGUMENTS')
    values = list(argv)
    _need(all(type(value) is str and not value.startswith('@') for value in values), 'INVALID_ARGUMENTS')
    if values in (['-h'], ['--help']):
        return None
    _need(bool(values) and values[0] in _OPTIONS, 'INVALID_ARGUMENTS')
    command, options, index = values[0], {}, 1
    while index < len(values):
        name, equals, value = values[index].partition('=')
        _need(name in _OPTIONS[command] and name not in options, 'INVALID_ARGUMENTS')
        if not equals:
            index += 1
            _need(index < len(values) and not values[index].startswith('-'), 'INVALID_ARGUMENTS')
            value = values[index]
        _need(bool(value) and not value.startswith('@'), 'INVALID_ARGUMENTS')
        options[name] = value
        index += 1
    _need(len(options) == len(_OPTIONS[command]), 'INVALID_ARGUMENTS')
    if command == 'fit-save':
        _need(options['--view'] in ('current13', 'h30_26'), 'INVALID_ARGUMENTS')
    return command, options


def _paths(command, options):
    disk = _learned_disk()
    return {name: disk._lexical(options[name]) for name in _OPTIONS[command] if name != '--view'}


def _outputs(paths):
    return paths['--result-output'], paths['--learned-output']


def _output_preflight(paths):
    outputs = _outputs(paths)
    for index, output in enumerate(outputs):
        others = outputs[index + 1:] + (paths['--raw-package'], paths['--prepared-package'])
        for other in others:
            _need(output != other and output not in other.parents and other not in output.parents,
                  'INVALID_PATH_LAYOUT')
    disk = _learned_disk()
    observations = {}
    for output in outputs:
        ancestors = []
        try:
            for parent in reversed(output.parents):
                ancestors.append((parent, disk._signature(parent.lstat(), directory=True)))
        except OSError:
            raise _CLIError('OUTPUT_ERROR') from None
        observations[output] = tuple(ancestors)
        _absent(output)
        _need(bool(ancestors), 'OUTPUT_ERROR')
    a, b = outputs
    _need(not (observations[a][-1][1][:2] == observations[b][-1][1][:2]
        and os.path.normcase(a.name) == os.path.normcase(b.name)), 'INVALID_PATH_LAYOUT')
    return observations


def _absent(output):
    try:
        output.lstat()
    except FileNotFoundError:
        return
    except OSError:
        raise _CLIError('OUTPUT_ERROR') from None
    raise _CLIError('OUTPUT_EXISTS') from None


def _recheck(observations, outputs):
    disk = _learned_disk()
    for output in outputs:
        for parent, expected in observations[output]:
            try:
                actual = disk._signature(parent.lstat(), directory=True)
            except (FileNotFoundError, NotADirectoryError):
                raise _CLIError('PACKAGE_CHANGED') from None
            except OSError:
                raise _CLIError('OUTPUT_ERROR') from None
            except disk.ReleaseIFLearnedError as error:
                if type(error) is not disk.ReleaseIFLearnedError:
                    raise
                code = _safe_code(error)
                raise _AdmittedFailure('PACKAGE_CHANGED' if code == 'INVALID_PACKAGE_PATH'
                    else code) from None
            _need(actual == expected, 'PACKAGE_CHANGED')
        _absent(output)


def _input_alias_preflight(paths, observations):
    disk = _learned_disk()
    try:
        roots = [disk._directory(paths[name])[:2] for name in ('--raw-package', '--prepared-package')]
    except OSError:
        raise _CLIError('INPUT_UNAVAILABLE') from None
    for chain in observations.values():
        _need(all(signature[:2] not in roots for _, signature in chain), 'INVALID_PATH_LAYOUT')


def _load_pair(paths):
    raw_module = _import('release_minute_package')
    _ERROR_CODES[raw_module.ReleaseMinutePackageError] = _PACKAGE_CODES
    raw = raw_module.load_release_minute_package(paths['--raw-package'])
    prepared_module = _import('release_input_package')
    _ERROR_CODES[prepared_module.ReleaseInputPreparationError] = _PACKAGE_CODES | frozenset((
        'INVALID_PREPARATION_CONFIG', 'UPSTREAM_IDENTITY_MISMATCH', 'NO_TRAINING_NORMAL_MINUTES',
        'NONFINITE_FIT_STATE', 'DERIVATION_MISMATCH'))
    prepared = prepared_module.load_release_input_package(paths['--prepared-package'])
    pairing = _import('release_model_inputs')
    _ERROR_CODES[pairing.ReleaseModelInputPairError] = frozenset(('INVALID_PAIR_ARGUMENTS',
        'INVALID_PAIR_STRUCTURE', 'INCOMPATIBLE_PAIR', 'RESOURCE_LIMIT',
        'UPSTREAM_IDENTITY_MISMATCH', 'PAIR_ALIGNMENT_MISMATCH'))
    return pairing.pair_release_model_inputs(raw, prepared)


def _result_disk():
    module = _import('release_if_result_package')
    _ERROR_CODES[module.ReleaseIFResultPackageError] = _PACKAGE_CODES | {'INPUT_BINDING_MISMATCH'}
    return module


def _identity(value, kind):
    _need(type(value) is kind)
    try:
        values = tuple(getattr(value, name) for name in _FIELDS)
    except AttributeError:
        raise _CLIError('INVALID_RESULT') from None
    profile, context, manifest, count = values
    _need(type(profile) is str and type(context) is str and _SHA.fullmatch(context) is not None
        and type(manifest) is str and _SHA.fullmatch(manifest) is not None
        and type(count) is int and 1 <= count <= 65536)
    return values


def _slots(value, kind):
    _need(type(value) is kind)
    try:
        for field in fields(kind):
            getattr(value, field.name)
    except AttributeError:
        raise _CLIError('INVALID_RESULT') from None


def _validate_packages(learned, result):
    c = _import('release_if_learned_contract')
    r = _import('release_if_result_contract')
    old = _import('release_iforest')
    _ERROR_CODES[r.ReleaseIFResultPackageError] = _PACKAGE_CODES | {'INPUT_BINDING_MISMATCH'}
    _slots(learned, c.ReleaseIFLearnedPackage)
    _slots(learned.context, c.ReleaseIFLearnedContext)
    _slots(learned.load_report, c.ReleaseIFLearnedLoadReport)
    _slots(learned.identity, c.ReleaseIFLearnedReference)
    _slots(result, r.ReleaseIFResultPackage)
    _slots(result.context, r.ReleaseIFResultContext)
    _slots(result.result, old.ReleaseIFResult)
    _slots(result.load_report, r.ReleaseIFResultLoadReport)
    _slots(result.identity, r.ReleaseIFResultIdentity)
    # Native codecs retain authority for each format, including finite errors.
    r.encode_release_if_result_package(result)
    c.encode_release_if_learned_package(learned)
    return c, r


def _validate_fit(run, pair, view, operation):
    _slots(run, operation.ReleaseIFLearnedRun)
    learned, result = run.learned_package, run.result_package
    c, r = _validate_packages(learned, result)
    pair_module = _import('release_model_inputs')
    _slots(pair, pair_module.ReleaseModelInputPair)
    raw_kind = _import('release_minute_contract').ReleaseMinutePackageIdentity
    prepared_kind = _import('release_inputs').ReleaseInputIdentity
    lc, rc, values = learned.context, result.context, result.result
    _need(type(lc.view) is str and lc.view == view and rc.view == view and values.view == view)
    _need(_identity(lc.result_identity, c.ReleaseIFLearnedReference) == _identity(result.identity, r.ReleaseIFResultIdentity))
    for learned_ref, result_ref, pair_ref, kind in (
            (lc.raw_identity, rc.raw_identity, pair.raw_identity, raw_kind),
            (lc.prepared_identity, rc.prepared_identity, pair.prepared_identity, prepared_kind)):
        _need(_identity(learned_ref, c.ReleaseIFLearnedReference) == _identity(result_ref, kind)
              == _identity(pair_ref, kind))
    _need(type(pair.configuration_sha256) is str and _SHA.fullmatch(pair.configuration_sha256) is not None)
    _need(lc.configuration_sha256 == rc.configuration_sha256 == pair.configuration_sha256)
    counts = (len(values.scored_mask), len(values.train_indices), len(values.calibration_indices),
              len(values.preprocessing_fit_indices))
    _need((lc.minute_count, lc.train_count, lc.calibration_count, lc.preprocessing_fit_count) == counts)
    digest = c._population_sha256(minute_count=len(values.scored_mask), scored_mask=values.scored_mask,
        train_indices=values.train_indices, calibration_indices=values.calibration_indices,
        preprocessing_fit_indices=values.preprocessing_fit_indices)
    _need(lc.population_sha256 == digest)


def _replay_projection(report, learned, result, operation):
    _slots(report, operation.ReleaseIFLearnedReplayReport)
    c, r = _validate_packages(learned, result)
    reference = c.ReleaseIFLearnedReference
    learned_identity = _identity(report.learned_identity, reference)
    result_identity = _identity(report.result_identity, reference)
    _need(learned_identity == _identity(learned.identity, reference))
    _need(result_identity == _identity(result.identity, r.ReleaseIFResultIdentity)
          == _identity(learned.context.result_identity, reference))
    fixed = dict(profile_id='c17-release-iforest-learned-package-v1',
        scope='EXPLICIT_INPUT_NUMERICAL_REPLAY_ONLY', score_replay='MATCHED',
        calibration_replay='MATCHED', prediction_replay='MATCHED',
        source_authentication='NOT_AUTHENTICATED', derivation_replay='NOT_PERFORMED')
    for name, expected in fixed.items():
        value = getattr(report, name)
        _need(type(value) is str and value == expected)
    for value in (report.scored_count, report.calibration_count):
        _need(type(value) is int and 1 <= value <= 10000)
    _need(report.scored_count == sum(result.result.scored_mask))
    _need(report.calibration_count == learned.context.calibration_count
          == len(result.result.calibration_indices))
    return dict(fixed, learned_identity=dict(zip(_FIELDS, learned_identity)),
        result_identity=dict(zip(_FIELDS, result_identity)), scored_count=report.scored_count,
        calibration_count=report.calibration_count)


def _receipt(command, package, replay=None):
    summary = _import('release_if_learned_summary').summarize_release_if_learned(package)
    return dict(version=1, profile_id='c17-release-iforest-learned-cli-v1', command=command,
        status={'inspect': 'INTERNAL_CONSISTENCY_CHECKED', 'replay': 'NUMERICAL_REPLAY_MATCHED',
                'fit-save': 'SAVED'}[command], summary=summary, replay=replay,
        operations=dict(fresh_fit_calls=int(command == 'fit-save'),
            numerical_replay_calls=int(command == 'replay'), result_save_calls=int(command == 'fit-save'),
            learned_save_calls=int(command == 'fit-save')))


def _encode(receipt):
    payload = bytearray()
    encoder = json.JSONEncoder(ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(',', ':'))
    for chunk in encoder.iterencode(receipt):
        encoded = chunk.encode('utf-8')
        _need(len(payload) + len(encoded) + 1 <= _OUTPUT_LIMIT, 'RESOURCE_LIMIT')
        payload.extend(encoded)
    _need(len(payload) + 1 <= _OUTPUT_LIMIT, 'RESOURCE_LIMIT')
    payload.extend(b'\n')
    return bytes(payload)


def _execute(command, paths, options):
    if command == 'fit-save':
        observations = _output_preflight(paths)
        pair = _load_pair(paths)
        _input_alias_preflight(paths, observations)
        _recheck(observations, _outputs(paths))
        operation = _import('release_if_learned')
        run = operation.fit_release_iforest_learned(pair, view=options['--view'])
        _validate_fit(run, pair, options['--view'], operation)
        package = run.learned_package
        _encode(_receipt(command, package))
        _recheck(observations, _outputs(paths))
        saved = _result_disk().save_release_if_result_package(run.result_package, paths['--result-output'])
        kind = _import('release_if_result_contract').ReleaseIFResultIdentity
        _need(_identity(saved, kind) == _identity(run.result_package.identity, kind))
        _recheck(observations, (paths['--learned-output'],))
        saved = _learned_disk().save_release_if_learned_package(package, paths['--learned-output'])
        kind = _import('release_if_learned_contract').ReleaseIFLearnedReference
        _need(_identity(saved, kind) == _identity(package.identity, kind))
        return _encode(_receipt(command, package))
    package = _learned_disk().load_release_if_learned_package(paths['--learned-package'])
    report = None
    if command == 'replay':
        result = _result_disk().load_release_if_result_package(paths['--result-package'])
        pair = _load_pair(paths)
        operation = _import('release_if_learned')
        returned = operation.replay_release_iforest_learned(package, pair, result)
        report = _replay_projection(returned, package, result, operation)
    return _encode(_receipt(command, package, report))


def _write(stream, payload):
    try:
        binary = stream.buffer
        count = binary.write(payload)
        _need(type(count) is int and count == len(payload), 'OUTPUT_ERROR')
        binary.flush()
    except (MemoryError, KeyboardInterrupt):
        raise
    except Exception:
        raise _CLIError('OUTPUT_ERROR') from None


def _error(code):
    try:
        _write(sys.stderr, ('{"error":"' + code + '"}\n').encode('ascii'))
    except (Exception, KeyboardInterrupt):
        pass
    return 2


def _safe_code(error):
    kind = type(error)
    if kind is _CLIError:
        allowed = _CLI_CODES
    elif kind is _AdmittedFailure:
        allowed = _CLI_CODES | _LEARNED_CODES
    else:
        # A foreign exception metaclass can customize hashing and equality.
        # Identity iteration admits only the actual registered owning classes.
        allowed = ()
        for registered, codes in _ERROR_CODES.items():
            if kind is registered:
                allowed = codes
                break
    if not allowed:
        return 'INTERNAL_ERROR'
    try:
        code = getattr(error, 'code', None)
    except (MemoryError, KeyboardInterrupt):
        raise
    except Exception:
        return 'INTERNAL_ERROR'
    return code if type(code) is str and code in allowed else 'INTERNAL_ERROR'


def main(argv: Sequence[str] | None = None) -> int:
    try:
        arguments = _arguments(argv)
        if arguments is None:
            payload = _HELP
        else:
            command, options = arguments
            payload = _execute(command, _paths(command, options), options)
        _write(sys.stdout, payload)
    except KeyboardInterrupt:
        return _error('INTERRUPTED')
    except MemoryError:
        return _error('RESOURCE_LIMIT')
    except Exception as error:
        try:
            code = _safe_code(error)
        except KeyboardInterrupt:
            code = 'INTERRUPTED'
        except MemoryError:
            code = 'RESOURCE_LIMIT'
        except Exception:
            code = 'INTERNAL_ERROR'
        return _error(code)
    return 0


def _cli_entrypoint() -> int:
    status = main()
    if status != 0:
        for stream in (sys.stdout, sys.stderr):
            try:
                target = stream.fileno()
                null_fd = os.open(os.devnull, os.O_WRONLY)
                try:
                    os.dup2(null_fd, target)
                finally:
                    if null_fd != target:
                        os.close(null_fd)
            except (Exception, KeyboardInterrupt):
                pass
    return status


if __name__ == '__main__':
    raise SystemExit(_cli_entrypoint())
