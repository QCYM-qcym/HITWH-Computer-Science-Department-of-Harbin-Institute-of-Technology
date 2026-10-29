"""Bounded, read-only consistency checks for synthetic candidate artifacts.

Hashes identify bytes, not an author. Saved parameters are replayed, never fit;
their statistical fitting provenance is not certified by this verifier.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass, field
import hashlib
import json
import math
from pathlib import Path
import stat
from types import MappingProxyType

import numpy as np

from .candidate_cli import (
    EVIDENCE_KIND, TIME_BASIS, MAX_FIXTURE_BYTES, _TOP_FIELDS, _ROW_FIELDS,
    _TIMESTAMP, _SEGMENT, _number, _unique_object, _reject_constant,
    _digest, _json_value, _candidate_document,
)
from .candidate_inputs import (
    PROFILE_ID, G13U_FEATURE_NAMES, PARTITIONS, MAX_MINUTES,
    CandidateMinuteBatch, CandidatePreprocessor, CandidateInputs,
    build_candidate_history, _eligible, _freeze,
)
from .candidate_records import RECORD_PROFILE_ID, POLICIES, adapt_synthetic_records, _ATTACK

VERIFIER_PROFILE_ID = 'c17-i1-g13u-artifact-verifier-v1'
MAX_MANIFEST_BYTES = 64 * 1024
MAX_AUDIT_BYTES = 16 * 1024 * 1024
MAX_INPUT_BYTES = 64 * 1024 * 1024
MAX_STATE_BYTES = 16384
RTOL = ATOL = 1e-12
_RECORD_FILES = {'manifest.json', 'minute-fixture.json', 'label-audit.json'}
_INPUT_FILES = {'manifest.json', 'candidate-inputs.json', 'preprocess.json'}
_MANIFEST_FIELDS = {'schema_version', 'profile_id', 'evidence_kind', 'time_basis',
                    'status', 'fixture', 'configuration', 'configuration_sha256', 'artifacts'}


class CandidateArtifactError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def _deep_freeze(value):
    if isinstance(value, dict):
        return MappingProxyType({key: _deep_freeze(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_deep_freeze(item) for item in value)
    return value


def _deep_thaw(value):
    if isinstance(value, Mapping):
        return {key: _deep_thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_deep_thaw(item) for item in value]
    return value


@dataclass(frozen=True, slots=True)
class _ArrayBuffer:
    """Immutable values and metadata; consumers receive independent views."""
    payload: bytes = field(repr=False)
    dtype: str
    shape: tuple[int, ...]

    @classmethod
    def copy(cls, values):
        array = np.asarray(values)
        if array.dtype.hasobject:
            raise ValueError('object_arrays_not_supported')
        return cls(array.tobytes(order='C'), array.dtype.str, array.shape)

    def view(self):
        return np.frombuffer(self.payload, dtype=np.dtype(self.dtype)).reshape(self.shape)


@dataclass(frozen=True, slots=True)
class _ArrayMapping(Mapping):
    _buffers: Mapping = field(repr=False)

    def __getitem__(self, key):
        return self._buffers[key].view()

    def __iter__(self):
        return iter(self._buffers)

    def __len__(self):
        return len(self._buffers)


def _array_mapping(values):
    return _ArrayMapping(MappingProxyType({key: _ArrayBuffer.copy(value) for key, value in values.items()}))


@dataclass(frozen=True, slots=True)
class VerifiedCandidateHistory:
    _arrays: _ArrayMapping = field(repr=False)
    invalid_reason: tuple[str | None, ...]

    @property
    def current(self): return self._arrays['current']

    @property
    def residual(self): return self._arrays['residual']

    @property
    def joined(self): return self._arrays['joined']

    @property
    def valid(self): return self._arrays['valid']


@dataclass(frozen=True, slots=True)
class VerifiedCandidateArtifacts:
    """Same-read snapshot of validated artifact values, not fit certification.

    Array contents are bytes-backed; each access has independent view metadata.
    Mutating a local view's shape/dtype cannot change subsequent snapshot reads.
    """
    report: Mapping
    provenance: Mapping
    preprocessing_state: Mapping
    _arrays: _ArrayMapping = field(repr=False)
    histories: Mapping[int, VerifiedCandidateHistory]
    labels: Mapping[str, tuple[str, ...]]
    normal_candidates: _ArrayMapping
    feature_names: tuple[str, ...] = G13U_FEATURE_NAMES
    value_space: str = 'prepared'

    def report_dict(self):
        return _deep_thaw(self.report)

    @property
    def timestamps(self): return self._arrays['timestamps']

    @property
    def segment_ids(self): return self._arrays['segment_ids']

    @property
    def partitions(self): return self._arrays['partitions']

    @property
    def current_values(self): return self._arrays['current_values']

    @property
    def row_valid(self): return self._arrays['row_valid']

    @property
    def raw_values(self): return self._arrays['raw_values']

    @property
    def raw_valid(self): return self._arrays['raw_valid']

    @property
    def common_valid(self): return self._arrays['common_valid']

    @property
    def training_normal(self): return self._arrays['training_normal']

    @property
    def calibration_normal(self): return self._arrays['calibration_normal']

    @property
    def test_normal(self): return self._arrays['test_normal']

    @property
    def source_attack_label_present(self): return self._arrays['source_attack_label_present']


def _snapshot(report, provenance, state, raw, data, label_audit):
    arrays = {key: np.array(data[key], dtype=bool) for key in
              ('row_valid', 'common_valid', 'training_normal', 'calibration_normal', 'test_normal')}
    arrays.update(timestamps=np.array(data['timestamps'], dtype='datetime64[us]'),
        segment_ids=np.array(data['segment_ids']), partitions=np.array(data['partitions']),
        current_values=np.array(data['current_values'], dtype=float), raw_values=raw.values,
        raw_valid=raw.row_valid,
        source_attack_label_present=np.array([row['source_attack_label_present']
            for row in label_audit['audit']['minute_reports']], dtype=bool))
    histories = {}
    for window in (15, 30):
        history = data['histories'][str(window)]
        values = {key: np.array(history[key], dtype=float) for key in ('current', 'residual', 'joined')}
        values['valid'] = np.array(history['valid'], dtype=bool)
        histories[window] = VerifiedCandidateHistory(_array_mapping(values), tuple(history['invalid_reason']))
    return VerifiedCandidateArtifacts(_deep_freeze(report), _deep_freeze(provenance), _deep_freeze(state),
        _array_mapping(arrays), MappingProxyType(histories),
        _deep_freeze(label_audit['labels']), _array_mapping(label_audit['normal_candidates']))


def _require(condition, code='INVALID_PACKAGE'):
    if not condition:
        raise CandidateArtifactError(code)


def _same(actual, expected, *, tolerant=False):
    """JSON structure/types are exact; finite floats have a fixed tolerance."""
    if tolerant and type(expected) is float:
        return (type(actual) in (int, float) and math.isfinite(actual)
                and math.isclose(actual, expected, rel_tol=RTOL, abs_tol=ATOL))
    if type(actual) is not type(expected):
        return False
    if isinstance(expected, dict):
        return actual.keys() == expected.keys() and all(_same(actual[k], v, tolerant=tolerant) for k, v in expected.items())
    if isinstance(expected, list):
        return len(actual) == len(expected) and all(_same(a, b, tolerant=tolerant) for a, b in zip(actual, expected))
    return actual == expected


def _ordinary(path, *, directory=False):
    info = path.lstat()
    _require(not stat.S_ISLNK(info.st_mode)
             and not (getattr(info, 'st_file_attributes', 0) & 1024))
    _require(stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode))
    return info


def _ancestors(path):
    # Inspect lexical parents before resolving: resolve would hide junctions.
    for parent in path.absolute().parents:
        _ordinary(parent, directory=True)


def _directory(path, expected):
    _ancestors(path)
    _ordinary(path, directory=True)
    names = set()
    for entry in path.iterdir():
        names.add(entry.name)
        _require(len(names) <= len(expected))
    _require(names == expected)


def _read(path, limit):
    _ancestors(path)
    before = _ordinary(path)
    _require(before.st_size <= limit, 'RESOURCE_LIMIT')
    with path.open('rb') as stream:
        payload = stream.read(limit + 1)
    _require(len(payload) <= limit, 'RESOURCE_LIMIT')
    after = _ordinary(path)
    identity = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns)
    _require(identity(before) == identity(after) and len(payload) == after.st_size, 'INTEGRITY_MISMATCH')
    value = json.loads(payload.decode('utf-8'), object_pairs_hook=_unique_object,
                       parse_constant=_reject_constant)
    _require(isinstance(value, dict))
    return payload, value


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def _manifest(path, *, record):
    payload, data = _read(path, MAX_MANIFEST_BYTES)
    fields = _MANIFEST_FIELDS | ({'selected_policy', 'policy_status'} if record else set())
    _require(set(data) == fields)
    expected = dict(schema_version=1, profile_id=RECORD_PROFILE_ID if record else PROFILE_ID,
                    evidence_kind=EVIDENCE_KIND, time_basis=TIME_BASIS, status='COMPLETE')
    _require(all(_same(data[k], value) for k, value in expected.items()), 'INCOMPATIBLE_PACKAGE')
    _require(isinstance(data['configuration'], dict))
    _require(data['configuration_sha256'] == hashlib.sha256(_canonical(data['configuration'])).hexdigest(),
             'INTEGRITY_MISMATCH')
    _require(isinstance(data['fixture'], dict) and set(data['fixture']) == {'sha256', 'byte_count'})
    digest = data['fixture']
    _require(isinstance(digest['sha256'], str) and len(digest['sha256']) == 64
             and all(c in '0123456789abcdef' for c in digest['sha256'])
             and type(digest['byte_count']) is int and 0 < digest['byte_count'] <= MAX_FIXTURE_BYTES)
    if record:
        _require(data['selected_policy'] in POLICIES and data['policy_status'] == 'AUDIT_ONLY')
    return payload, data


def _artifacts(directory, manifest, limits):
    _require(isinstance(manifest['artifacts'], dict) and set(manifest['artifacts']) == set(limits))
    result = {}
    for name, limit in limits.items():
        payload, value = _read(directory / name, limit)
        _require(_same(manifest['artifacts'][name], _digest(payload)), 'INTEGRITY_MISMATCH')
        result[name] = (payload, value)
    return result


def _minute_batch(fixture):
    _require(set(fixture) == _TOP_FIELDS and type(fixture['schema_version']) is int
             and fixture['schema_version'] == 1 and fixture['evidence_kind'] == EVIDENCE_KIND
             and fixture['time_basis'] == TIME_BASIS
             and fixture['feature_names'] == list(G13U_FEATURE_NAMES)
             and _number(fixture['epsilon'], positive=True))
    rows, normal = fixture['minutes'], fixture['normal_candidates']
    _require(isinstance(rows, list) and 1 <= len(rows) <= MAX_MINUTES
             and isinstance(normal, list) and len(normal) == len(rows)
             and all(type(value) is bool for value in normal))
    for row in rows:
        _require(isinstance(row, dict) and set(row) == _ROW_FIELDS
                 and type(row['valid']) is bool and isinstance(row['timestamp'], str)
                 and bool(_TIMESTAMP.fullmatch(row['timestamp']))
                 and isinstance(row['segment_id'], str) and bool(_SEGMENT.fullmatch(row['segment_id']))
                 and row['partition'] in PARTITIONS and isinstance(row['features'], list)
                 and len(row['features']) == 13)
        _require((row['valid'] is False and all(value is None for value in row['features']))
                 or all(_number(value) for value in row['features']))
    batch = CandidateMinuteBatch(
        np.array([r['timestamp'] for r in rows], dtype='datetime64[us]'),
        np.array([r['features'] for r in rows], dtype=float),
        np.array([r['valid'] for r in rows], dtype=bool),
        np.array([r['segment_id'] for r in rows]), np.array([r['partition'] for r in rows]))
    return batch, np.array(normal, dtype=bool)


def _counter(value, *, maximum=MAX_MINUTES):
    _require(isinstance(value, dict) and all(isinstance(k, str) and type(v) is int
             and 0 <= v <= maximum for k, v in value.items()))
    return Counter(value)


def _label_audit(data, fixture, batch, policy):
    fields = {'schema_version', 'profile_id', 'evidence_kind', 'time_basis', 'selected_policy',
              'policy_status', 'labels', 'normal_candidates', 'audit'}
    _require(set(data) == fields)
    metadata = dict(schema_version=1, profile_id=RECORD_PROFILE_ID, evidence_kind=EVIDENCE_KIND,
                    time_basis=TIME_BASIS, selected_policy=policy, policy_status='AUDIT_ONLY')
    _require(all(_same(data[k], v) for k, v in metadata.items()))
    _require(isinstance(data['labels'], dict) and set(data['labels']) == set(POLICIES)
             and isinstance(data['normal_candidates'], dict) and set(data['normal_candidates']) == set(POLICIES))
    n = len(batch.timestamps)
    for p in POLICIES:
        labels = data['labels'][p]
        _require(isinstance(labels, list) and len(labels) == n
                 and all(kind in ('normal', 'attack', 'unknown') for kind in labels))
        _require(_same(data['normal_candidates'][p], [kind == 'normal' for kind in labels]))
    _require(data['normal_candidates'][policy] == fixture['normal_candidates'])
    audit = data['audit']
    keys = {'profile_id', 'evidence_kind', 'time_basis', 'policy_status', 'input_records',
            'eligible_records', 'excluded_records', 'outside_records', 'duplicate_key_groups',
            'raw_protocol_channels', 'eligible_protocol_channels', 'source_label_counts',
            'source_category_counts', 'source_label_category_counts', 'record_reason_counts',
            'reason_counts_may_overlap', 'record_conservation', 'channel_conservation',
            'minute_reports', 'policy_label_counts'}
    _require(isinstance(audit, dict) and set(audit) == keys)
    _require(all(_same(audit[k], metadata[k]) for k in ('profile_id', 'evidence_kind', 'time_basis', 'policy_status')))
    for key in ('input_records', 'eligible_records', 'excluded_records', 'outside_records', 'duplicate_key_groups'):
        _require(type(audit[key]) is int and 0 <= audit[key] <= MAX_MINUTES)
    total, eligible = audit['input_records'], audit['eligible_records']
    _require(total == eligible + audit['excluded_records'] and audit['outside_records'] <= audit['excluded_records'])
    _require(all(audit[k] is True for k in ('record_conservation', 'channel_conservation', 'reason_counts_may_overlap')))
    raw = _counter(audit['raw_protocol_channels'])
    good = _counter(audit['eligible_protocol_channels'])
    _require(set(raw) == {'tcp', 'udp', 'known_other', 'unresolved', 'invalid'}
             and set(good) == {'tcp', 'udp', 'known_other', 'unresolved'}
             and sum(raw.values()) == total and sum(good.values()) == eligible
             and all(good[k] <= raw[k] for k in good))
    labels, categories = _counter(audit['source_label_counts']), _counter(audit['source_category_counts'])
    _require(sum(labels.values()) == sum(categories.values()) == total)
    _counter(audit['record_reason_counts'])
    pairs = audit['source_label_category_counts']
    _require(isinstance(pairs, list) and len(pairs) <= total)
    pair_labels, pair_categories, seen = Counter(), Counter(), set()
    for item in pairs:
        _require(isinstance(item, dict) and set(item) == {'label', 'attempted_category', 'records'}
                 and type(item['records']) is int and 0 < item['records'] <= MAX_MINUTES)
        key = (item['label'], item['attempted_category'])
        _require(all(v is None or isinstance(v, str) for v in key) and key not in seen)
        seen.add(key)
        pair_labels['<MISSING>' if key[0] is None else key[0]] += item['records']
        pair_categories['<MISSING>' if key[1] is None else key[1]] += item['records']
    _require(pair_labels == labels and pair_categories == categories)
    _require(_same(audit['policy_label_counts'], {p: dict(Counter(data['labels'][p])) for p in POLICIES}))
    reports = audit['minute_reports']
    _require(isinstance(reports, list) and len(reports) == n)
    minute_raw = minute_eligible = 0
    minute_labels, minute_categories = Counter(), Counter()
    allowed_reasons = {'invalid_protocol', 'invalid_fwd_packets', 'invalid_bwd_packets',
        'invalid_fwd_length', 'invalid_bwd_length', 'cross_candidate_boundary', 'cross_partition',
        'cross_segment', 'cross_time_gap', 'cross_capture_missing', 'duplicate_record_key',
        'conflicting_record_key', 'capture_missing', 'empty_evidence_conflict', 'empty_unconfirmed'}
    for i, report in enumerate(reports):
        _require(isinstance(report, dict) and set(report) == {'timestamp', 'coverage', 'raw_record_count',
                 'eligible_record_count', 'invalid_reasons', 'source_label_counts', 'source_category_counts',
                 'source_attack_label_present', 'labels'})
        stamp = report['timestamp']
        _require(isinstance(stamp, str) and bool(_TIMESTAMP.fullmatch(stamp))
                 and np.datetime64(stamp, 'us') == batch.timestamps[i]
                 and report['coverage'] in ('observed', 'confirmed_empty', 'missing')
                 and type(report['source_attack_label_present']) is bool
                 and _same(report['labels'], {p: data['labels'][p][i] for p in POLICIES}))
        reasons = report['invalid_reasons']
        _require(isinstance(reasons, list) and all(isinstance(v, str) for v in reasons)
                 and reasons == sorted(set(reasons)) and set(reasons) <= allowed_reasons
                 and bool(reasons) == (not bool(batch.row_valid[i])))
        nr, ne = report['raw_record_count'], report['eligible_record_count']
        _require(type(nr) is int and type(ne) is int and 0 <= ne <= nr <= total)
        local_labels = _counter(report['source_label_counts'])
        local_categories = _counter(report['source_category_counts'])
        _require(sum(local_labels.values()) == nr and sum(local_categories.values()) == nr
                 and report['source_attack_label_present'] == any(local_labels[k] > 0 for k in _ATTACK))
        minute_labels.update(local_labels)
        minute_categories.update(local_categories)
        required = set()
        if report['coverage'] == 'missing': required.add('capture_missing')
        if report['coverage'] == 'confirmed_empty' and nr: required.add('empty_evidence_conflict')
        if report['coverage'] == 'observed' and not nr: required.add('empty_unconfirmed')
        _require(required <= set(reasons))
        minute_raw += nr
        minute_eligible += ne
        if not batch.row_valid[i]:
            _require(all(data['labels'][p][i] == 'unknown' for p in POLICIES))
        else:
            values = batch.values[i]
            _require(nr == ne and values[0] == ne
                     and all(values[j] <= ne * 1000000000 for j in (1, 2, 3, 4))
                     and all(float(values[j]).is_integer() for j in (0, 1, 2, 3, 4, 5, 6, 7, 8, 12))
                     and values[5:9].sum() == values[0] and values[12] <= values[0]
                     and 0 <= values[10] <= values[11] <= values[9] <= 86400)
            if not nr:
                _require(report['coverage'] == 'confirmed_empty' and (values == 0).all()
                         and len({data['labels'][p][i] for p in POLICIES}) == 1
                         and data['labels'][policy][i] in ('normal', 'unknown'))
    _require(minute_raw + audit['outside_records'] == total and minute_eligible == eligible)
    _require(all(v <= labels[k] for k, v in minute_labels.items())
             and all(v <= categories[k] for k, v in minute_categories.items()))


def _stored_transform(state, raw, normal):
    expected = {'schema_version', 'profile_id', 'evidence_kind', 'transform', 'feature_names',
                'mean', 'scale', 'n_samples_seen', 'fit_window'}
    _require(set(state) == expected)
    metadata = dict(schema_version=1, profile_id=PROFILE_ID, evidence_kind=EVIDENCE_KIND,
                    transform='log1p_standard_ddof0', feature_names=list(G13U_FEATURE_NAMES), fit_window=30)
    _require(all(_same(state[k], v) for k, v in metadata.items()), 'INCOMPATIBLE_PACKAGE')
    count = int((_eligible(raw, 30, normal) & (raw.partitions == 'train')).sum())
    _require(type(state['n_samples_seen']) is int and 0 < count == state['n_samples_seen'])
    for name in ('mean', 'scale'):
        values = state[name]
        _require(isinstance(values, list) and len(values) == 13 and all(type(v) in (int, float)
                 and math.isfinite(v) and (name != 'scale' or v > 0) for v in values))
    transform = CandidatePreprocessor()
    transform.mean, transform.scale = _freeze(state['mean'], float), _freeze(state['scale'], float)
    transform.n_samples_seen, transform.fit_window = count, 30
    return transform


def _verify(records, inputs, source):
    _directory(records, _RECORD_FILES)
    _directory(inputs, _INPUT_FILES)
    record_manifest_payload, record_manifest = _manifest(records / 'manifest.json', record=True)
    input_manifest_payload, input_manifest = _manifest(inputs / 'manifest.json', record=False)
    record_data = _artifacts(records, record_manifest,
        {'minute-fixture.json': MAX_FIXTURE_BYTES, 'label-audit.json': MAX_AUDIT_BYTES})
    input_data = _artifacts(inputs, input_manifest,
        {'candidate-inputs.json': MAX_INPUT_BYTES, 'preprocess.json': MAX_STATE_BYTES})
    minute_payload, fixture = record_data['minute-fixture.json']
    _require(_same(input_manifest['fixture'], _digest(minute_payload)), 'INTEGRITY_MISMATCH')
    raw, normal = _minute_batch(fixture)
    policy = record_manifest['selected_policy']
    record_config = dict(profile_id=RECORD_PROFILE_ID, evidence_kind=EVIDENCE_KIND, time_basis=TIME_BASIS,
        selected_policy=policy, policy_status='AUDIT_ONLY', epsilon=fixture['epsilon'],
        completion_time='start_plus_duration_us_proxy', max_minutes=MAX_MINUTES,
        max_records=MAX_MINUTES, max_fixture_bytes=MAX_FIXTURE_BYTES)
    input_config = dict(profile_id=PROFILE_ID, feature_names=list(G13U_FEATURE_NAMES), windows=[15, 30],
        epsilon=fixture['epsilon'], evidence_kind=EVIDENCE_KIND, time_basis=TIME_BASIS,
        transform='log1p_standard_ddof0', fit_partition='train', fit_eligibility='current_and_previous_30_normal')
    _require(_same(record_manifest['configuration'], record_config)
             and _same(input_manifest['configuration'], input_config), 'INCOMPATIBLE_PACKAGE')
    label_audit = record_data['label-audit.json'][1]
    _label_audit(label_audit, fixture, raw, policy)
    if source is not None:
        _require(source.suffix.lower() == '.json')
        source_payload, source_data = _read(source, MAX_FIXTURE_BYTES)
        _require(_same(_digest(source_payload), record_manifest['fixture']), 'INTEGRITY_MISMATCH')
        _require(set(source_data) == {'schema_version', 'evidence_kind', 'time_basis', 'minutes', 'records', 'epsilon'}
                 and type(source_data['schema_version']) is int and source_data['schema_version'] == 1
                 and source_data['evidence_kind'] == EVIDENCE_KIND and source_data['time_basis'] == TIME_BASIS
                 and _number(source_data['epsilon'], positive=True) and isinstance(source_data['records'], list))
        adapted = adapt_synthetic_records(source_data['minutes'], source_data['records'])
        _require(_same(fixture['epsilon'], source_data['epsilon'])
                 and _same(fixture, adapted.to_fixture(policy, epsilon=source_data['epsilon']), tolerant=True),
                 'REPLAY_MISMATCH')
        expected_audit = _json_value(dict(schema_version=1, profile_id=RECORD_PROFILE_ID,
            evidence_kind=EVIDENCE_KIND, time_basis=TIME_BASIS, selected_policy=policy, policy_status='AUDIT_ONLY',
            labels=adapted.labels, normal_candidates=adapted.normal_candidates, audit=adapted.audit))
        _require(_same(label_audit, expected_audit), 'REPLAY_MISMATCH')
    transform = _stored_transform(input_data['preprocess.json'][1], raw, normal)
    prepared = transform.transform(raw)
    histories = {w: build_candidate_history(prepared, window=w, epsilon=fixture['epsilon']) for w in (15, 30)}
    common = histories[15].valid & histories[30].valid
    all_normal = _eligible(prepared, 30, normal) & common
    result = CandidateInputs(transform, prepared, histories, common,
        all_normal & (raw.partitions == 'train'), all_normal & (raw.partitions == 'calibration'),
        common & normal & (raw.partitions == 'test'))
    expected = _candidate_document(fixture, raw, result)
    actual = input_data['candidate-inputs.json'][1]
    _require(_same(actual.get('epsilon'), expected['epsilon']) and _same(actual, expected, tolerant=True),
             'REPLAY_MISMATCH')
    report = dict(schema_version=1, verifier_profile_id=VERIFIER_PROFILE_ID, status='VERIFIED',
        evidence_kind=EVIDENCE_KIND, time_basis=TIME_BASIS, selected_policy=policy, policy_status='AUDIT_ONLY',
        checks=dict(byte_integrity='VERIFIED', profile_compatibility='VERIFIED', lineage='VERIFIED',
                    label_separation='VERIFIED', saved_transform_replay='VERIFIED', history_replay='VERIFIED',
                    source_replay='VERIFIED' if source is not None else 'NOT_PROVIDED',
                    fit_parameters='NOT_REESTIMATED'),
        source_fixture=record_manifest['fixture'], minute_fixture=_digest(minute_payload),
        minute_count=len(raw.timestamps), dimensions={'current': 13, 'joined': 26}, windows=[15, 30],
        partition_summary=expected['partition_summary'], numerical_tolerance=dict(rtol=RTOL, atol=ATOL),
        scope='synthetic_internal_consistency_not_source_authentication_or_research_validation')
    provenance = dict(record_manifest=_digest(record_manifest_payload), input_manifest=_digest(input_manifest_payload),
        source_fixture=record_manifest['fixture'], minute_fixture=_digest(minute_payload),
        preprocess=_digest(input_data['preprocess.json'][0]))
    return _snapshot(report, provenance, input_data['preprocess.json'][1], raw, actual, label_audit)


def load_verified_candidate_artifacts(record_directory, input_directory, *, source_fixture=None):
    """Return a bounded same-read snapshot without writing or reestimating fit.

    The optional source is an artificial JSON fixture, never a CSV. Missing it
    leaves source replay explicitly unverified. Exceptions contain safe codes.
    """
    try:
        return _verify(Path(record_directory), Path(input_directory),
                       Path(source_fixture) if source_fixture is not None else None)
    except CandidateArtifactError:
        raise
    except OSError as exc:
        raise CandidateArtifactError('INPUT_UNAVAILABLE') from exc
    except (ValueError, TypeError, KeyError, OverflowError, RecursionError) as exc:
        raise CandidateArtifactError('INVALID_PACKAGE') from exc


def verify_candidate_artifacts(record_directory, input_directory, *, source_fixture=None):
    """Keep the original JSON report API; validation and I/O remain shared."""
    return load_verified_candidate_artifacts(record_directory, input_directory,
        source_fixture=source_fixture).report_dict()
