"""Manual bounded numeric forests: codec contract, without model execution."""
import importlib
import json
from dataclasses import FrozenInstanceError, fields, replace
import builtins
import io
import math
from pathlib import Path
import sys
import types

import pytest

from traffic_anomaly import iforest_numeric_state as contract
from tests.core.iforest_numeric_state_cases import manual_numeric_state


def test_manual_root_leaf_roundtrip_has_exact_seven_fields_and_canonical_bytes():
    # A missing new public seam must fail here, before relying on a shared helper.
    name = 'traffic_anomaly.iforest_numeric_state'
    assert importlib.util.find_spec(name) is not None, 'new public numeric-state seam is missing'
    c = importlib.import_module(name)
    leaf = c.IForestNumericNode(None, None, None, None, 1)
    state = c.IForestNumericState(1, 'iforest-numeric-state-v1',
        'iforest16-m32-f32route-f64path-numpy254-v1', 13, tuple(range(13)),
        1, tuple(c.IForestNumericTree((leaf,)) for _ in range(16)))
    projection = {'version': 1, 'profile_id': 'iforest-numeric-state-v1',
        'algorithm_id': 'iforest16-m32-f32route-f64path-numpy254-v1',
        'input_width': 13, 'feature_order': list(range(13)), 'max_samples': 1,
        'trees': [{'nodes': [{'left': None, 'right': None, 'feature': None,
            'threshold': None, 'sample_count': 1}]} for _ in range(16)]}
    expected = (json.dumps(projection, ensure_ascii=False, sort_keys=True,
        separators=(',', ':'), allow_nan=False) + '\n').encode('utf-8')
    assert len(projection) == 7
    assert c.encode_iforest_numeric_state(state) == expected
    assert c.decode_iforest_numeric_state(expected) == state


def canonical(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True,
        separators=(',', ':'), allow_nan=False) + '\n').encode('utf-8')


def rejection(call, code):
    with pytest.raises(contract.IForestNumericStateError) as caught:
        call()
    assert type(caught.value) is contract.IForestNumericStateError
    assert type(caught.value.code) is str
    assert caught.value.code == code
    assert str(caught.value) == code
    return caught.value


def changed_node(state, index=0, **change):
    tree = state.trees[0]
    nodes = list(tree.nodes)
    nodes[index] = replace(nodes[index], **change)
    return replace(state, trees=(replace(tree, nodes=tuple(nodes)),) + state.trees[1:])


@pytest.mark.parametrize('width', [13, 26])
@pytest.mark.parametrize(('pattern', 'm', 'nodes', 'depth'), [
    ('root_leaf', 1, 1, 0), ('root_leaf', 2, 1, 0),
    ('root_leaf', 4, 1, 0), ('root_leaf', 32, 1, 0),
    ('split2', 2, 3, 1), ('asymmetric4', 4, 3, 1),
    ('three_leaf4', 4, 5, 2), ('balanced32', 32, 63, 5),
])
def test_literal_manual_patterns_roundtrip_both_widths(width, pattern, m, nodes, depth):
    state = manual_numeric_state(width=width, pattern=pattern, max_samples=m)
    payload = contract.encode_iforest_numeric_state(state)
    decoded = contract.decode_iforest_numeric_state(payload)
    assert decoded == state
    assert contract.encode_iforest_numeric_state(decoded) == payload
    assert type(decoded.trees) is tuple
    assert type(decoded.trees[0].nodes) is tuple
    assert len(decoded.trees) == 16
    assert len(decoded.trees[0].nodes) == nodes
    pending = [(0, 0)]
    maximum = 0
    while pending:
        index, level = pending.pop()
        maximum = max(maximum, level)
        node = decoded.trees[0].nodes[index]
        if node.left is not None:
            pending += [(node.left, level + 1), (node.right, level + 1)]
    assert maximum == depth
    assert len(payload) <= 262144


def test_balanced_manual_tree_has_preorder_ids_and_nonempty_numeric_regions():
    state = manual_numeric_state(pattern='balanced32', max_samples=32)
    pending = [(0, 0.0, 32.0)]
    leaves = []
    visited = []
    while pending:
        index, low, high = pending.pop()
        visited.append(index)
        node = state.trees[0].nodes[index]
        if node.left is None:
            leaves.append((low, high))
            assert node.sample_count == 1
        else:
            assert low < node.threshold < high
            assert node.threshold == (low + high) / 2
            pending += [(node.right, node.threshold, high), (node.left, low, node.threshold)]
    assert visited == list(range(63))
    assert leaves == [(float(n), float(n + 1)) for n in range(32)]


@pytest.mark.parametrize('kwargs', [
    {'width': True}, {'width': 14}, {'max_samples': True}, {'max_samples': 0},
    {'max_samples': 33}, {'pattern': []}, {'pattern': 'missing'},
    {'pattern': 'split2'}, {'pattern': 'asymmetric4'}, {'pattern': 'three_leaf4'},
    {'pattern': 'balanced32'}, {'pattern': 'split2', 'max_samples': 4},
])
def test_manual_helper_never_changes_an_invalid_pattern_sample_count(kwargs):
    with pytest.raises(ValueError):
        manual_numeric_state(**kwargs)


def test_exact_field_sets_slots_and_frozen_values():
    state = manual_numeric_state()
    expected = ((state, ['version', 'profile_id', 'algorithm_id', 'input_width',
        'feature_order', 'max_samples', 'trees']), (state.trees[0], ['nodes']),
        (state.trees[0].nodes[0], ['left', 'right', 'feature', 'threshold', 'sample_count']))
    for value, names in expected:
        assert [field.name for field in fields(value)] == names
        assert not hasattr(value, '__dict__')
        with pytest.raises(FrozenInstanceError):
            setattr(value, names[0], None)
    assert contract.NUMERIC_STATE_VERSION == 1
    assert contract.NUMERIC_STATE_PROFILE_ID == 'iforest-numeric-state-v1'
    assert contract.NUMERIC_STATE_ALGORITHM_ID == 'iforest16-m32-f32route-f64path-numpy254-v1'
    assert contract.NUMERIC_STATE_BYTE_LIMIT == 262144
    assert contract.NUMERIC_STATE_MAX_ROWS == 10000


@pytest.mark.parametrize('code', ['INVALID_STATE_ARGUMENTS', 'INVALID_STATE',
    'INCOMPATIBLE_STATE', 'RESOURCE_LIMIT', 'INVALID_MATRIX',
    'INCOMPATIBLE_RUNTIME', 'NUMERIC_STATE_ERROR'])
def test_finite_declared_error_codes(code):
    error = contract.IForestNumericStateError(code)
    assert error.code == str(error) == code


@pytest.mark.parametrize('value', [None, True, 1, [], {}, 'UNKNOWN'])
def test_unknown_error_constructor_values_are_safe(value):
    error = contract.IForestNumericStateError(value)
    assert error.code == str(error) == 'NUMERIC_STATE_ERROR'


def test_error_constructor_rejects_str_subclass_without_comparing_it():
    class Foreign(str):
        def __hash__(self):
            raise AssertionError('foreign hash must not run')
    assert str(contract.IForestNumericStateError(Foreign('INVALID_STATE'))) == 'NUMERIC_STATE_ERROR'


@pytest.mark.parametrize('value', [None, b'{}', {}, (), True])
def test_encode_and_score_reject_nonexact_state_before_matrix_or_import(value):
    rejection(lambda: contract.encode_iforest_numeric_state(value), 'INVALID_STATE_ARGUMENTS')
    rejection(lambda: contract.score_iforest_numeric_state(value, object()), 'INVALID_STATE_ARGUMENTS')


@pytest.mark.parametrize('value', [None, '', bytearray(b'{}'), memoryview(b'{}'), True])
def test_decode_rejects_nonexact_bytes(value):
    rejection(lambda: contract.decode_iforest_numeric_state(value), 'INVALID_STATE_ARGUMENTS')


def test_reject_exact_type_subclasses_and_never_iterate_foreign_containers():
    class State(contract.IForestNumericState):
        pass
    class Tree(contract.IForestNumericTree):
        pass
    class Node(contract.IForestNumericNode):
        pass
    class ForeignTuple(tuple):
        def __iter__(self):
            raise AssertionError('foreign tuple iterator must not run')
    class ForeignBytes(bytes):
        pass
    state = manual_numeric_state()
    rejection(lambda: contract.encode_iforest_numeric_state(State(
        state.version, state.profile_id, state.algorithm_id, state.input_width,
        state.feature_order, state.max_samples, state.trees)), 'INVALID_STATE_ARGUMENTS')
    rejection(lambda: contract.decode_iforest_numeric_state(ForeignBytes(b'{}')), 'INVALID_STATE_ARGUMENTS')
    for bad in [replace(state, trees=ForeignTuple(state.trees)),
            replace(state, feature_order=ForeignTuple(state.feature_order)),
            replace(state, trees=(Tree(state.trees[0].nodes),) + state.trees[1:]),
            replace(state, trees=(contract.IForestNumericTree(ForeignTuple(state.trees[0].nodes)),) + state.trees[1:]),
            replace(state, trees=(contract.IForestNumericTree((Node(None, None, None, None, 1),)),) + state.trees[1:])]:
        rejection(lambda: contract.encode_iforest_numeric_state(bad), 'INVALID_STATE')


@pytest.mark.parametrize(('field', 'value', 'code'), [
    ('version', True, 'INVALID_STATE'), ('version', 1.0, 'INVALID_STATE'),
    ('version', 2, 'INCOMPATIBLE_STATE'), ('profile_id', 1, 'INVALID_STATE'),
    ('profile_id', 'unknown', 'INCOMPATIBLE_STATE'), ('algorithm_id', None, 'INVALID_STATE'),
    ('algorithm_id', 'unknown', 'INCOMPATIBLE_STATE'), ('input_width', True, 'INVALID_STATE'),
    ('input_width', 13.0, 'INVALID_STATE'), ('input_width', 14, 'INCOMPATIBLE_STATE'),
    ('feature_order', list(range(13)), 'INVALID_STATE'),
    ('feature_order', (True,) + tuple(range(1, 13)), 'INVALID_STATE'),
    ('feature_order', tuple(range(12)), 'INCOMPATIBLE_STATE'),
    ('feature_order', tuple(reversed(range(13))), 'INCOMPATIBLE_STATE'),
    ('max_samples', True, 'INVALID_STATE'), ('max_samples', 1.0, 'INVALID_STATE'),
    ('max_samples', 0, 'INVALID_STATE'), ('max_samples', 33, 'RESOURCE_LIMIT'),
    ('trees', [], 'INVALID_STATE'), ('trees', (), 'INVALID_STATE'),
])
def test_state_field_types_and_fixed_compatibility(field, value, code):
    bad = replace(manual_numeric_state(), **{field: value})
    rejection(lambda: contract.encode_iforest_numeric_state(bad), code)


def test_every_public_entry_revalidates_missing_exact_object_fields():
    state = manual_numeric_state()
    absent_state = object.__new__(contract.IForestNumericState)
    absent_tree = object.__new__(contract.IForestNumericTree)
    absent_node = object.__new__(contract.IForestNumericNode)
    cases = [absent_state, replace(state, trees=(absent_tree,) + state.trees[1:]),
        replace(state, trees=(contract.IForestNumericTree((absent_node,)),) + state.trees[1:])]
    for bad in cases:
        rejection(lambda: contract.encode_iforest_numeric_state(bad), 'INVALID_STATE')
        rejection(lambda: contract.score_iforest_numeric_state(bad, object()), 'INVALID_STATE')
    payload = contract.encode_iforest_numeric_state(state)
    object.__setattr__(state, 'max_samples', False)
    rejection(lambda: contract.encode_iforest_numeric_state(state), 'INVALID_STATE')
    rejection(lambda: contract.score_iforest_numeric_state(state, object()), 'INVALID_STATE')
    assert contract.decode_iforest_numeric_state(payload).max_samples == 1


@pytest.mark.parametrize('field,value', [
    ('left', -1), ('right', -2), ('feature', 0), ('threshold', 0.0),
    ('sample_count', True), ('sample_count', 0), ('sample_count', 2),
])
def test_leaf_has_exactly_four_none_fields_and_positive_bounded_count(field, value):
    bad = changed_node(manual_numeric_state(), **{field: value})
    rejection(lambda: contract.encode_iforest_numeric_state(bad), 'INVALID_STATE')


@pytest.mark.parametrize('change', [
    {'left': True}, {'right': 2.0}, {'feature': True}, {'feature': -1},
    {'feature': 13}, {'threshold': 0}, {'threshold': True},
    {'threshold': float('nan')}, {'threshold': float('inf')},
    {'threshold': float('-inf')}, {'sample_count': 3}, {'sample_count': 5},
    {'left': None}, {'right': None}, {'feature': None}, {'threshold': None},
    {'left': 0}, {'left': -1}, {'right': 3}, {'left': 2}, {'right': 1},
])
def test_internal_node_types_sentinels_bounds_and_root_count(change):
    bad = changed_node(manual_numeric_state(pattern='asymmetric4', max_samples=4), **change)
    rejection(lambda: contract.encode_iforest_numeric_state(bad), 'INVALID_STATE')


@pytest.mark.parametrize('which', ['too_few', 'too_many', 'empty_nodes', 'oversize_nodes',
    'too_many_for_m', 'list_nodes', 'foreign_node', 'count_mismatch', 'orphan',
    'duplicate_parent', 'cycle', 'too_deep'])
def test_forest_bounds_topology_reachability_and_conservation(which):
    c = contract
    leaf = lambda n: c.IForestNumericNode(None, None, None, None, n)
    state = manual_numeric_state(pattern='three_leaf4', max_samples=4)
    code = 'INVALID_STATE'
    if which == 'too_few':
        bad = replace(state, trees=state.trees[:-1])
    elif which == 'too_many':
        bad = replace(state, trees=state.trees + state.trees[:1])
        code = 'RESOURCE_LIMIT'
    elif which == 'oversize_nodes':
        bad = replace(state, trees=(c.IForestNumericTree((object(),) * 64),) + state.trees[1:])
        code = 'RESOURCE_LIMIT'
    else:
        alternatives = {
            'empty_nodes': (), 'too_many_for_m': (leaf(1),) * 9,
            'list_nodes': list(state.trees[0].nodes), 'foreign_node': (object(),),
            'count_mismatch': (c.IForestNumericNode(1, 2, 0, 0.0, 4), leaf(2), leaf(3)),
            'orphan': (c.IForestNumericNode(1, 2, 0, 0.0, 4), leaf(1), leaf(3), leaf(1)),
            'duplicate_parent': (c.IForestNumericNode(1, 2, 0, 0.0, 4),
                c.IForestNumericNode(3, 4, 0, -1.0, 2), c.IForestNumericNode(3, 4, 0, 1.0, 2), leaf(1), leaf(1)),
            'cycle': (c.IForestNumericNode(1, 2, 0, 0.0, 4), leaf(1),
                c.IForestNumericNode(0, 3, 0, 1.0, 3), leaf(1)),
            'too_deep': (c.IForestNumericNode(1, 2, 0, 0.0, 4), leaf(1),
                c.IForestNumericNode(3, 4, 0, 1.0, 3), leaf(1),
                c.IForestNumericNode(5, 6, 0, 2.0, 2), leaf(1), leaf(1)),
        }
        bad = replace(state, trees=(c.IForestNumericTree(alternatives[which]),) + state.trees[1:])
    rejection(lambda: c.encode_iforest_numeric_state(bad), code)


def test_negative_zero_and_extreme_finite_float_thresholds_keep_their_bits():
    state = manual_numeric_state(pattern='asymmetric4', max_samples=4)
    for threshold in [-0.0, -sys.float_info.max, sys.float_info.max, 5e-324]:
        loaded = contract.decode_iforest_numeric_state(contract.encode_iforest_numeric_state(
            changed_node(state, threshold=threshold)))
        assert loaded.trees[0].nodes[0].threshold.hex() == threshold.hex()
    loaded = contract.decode_iforest_numeric_state(contract.encode_iforest_numeric_state(
        changed_node(state, threshold=-0.0)))
    assert math.copysign(1.0, loaded.trees[0].nodes[0].threshold) == -1.0


@pytest.mark.parametrize('mutate,code', [
    (lambda p: p.update(extra=None), 'INVALID_STATE'),
    (lambda p: p.pop('version'), 'INVALID_STATE'),
    (lambda p: p.update(version=True), 'INVALID_STATE'),
    (lambda p: p.update(version=1.0), 'INVALID_STATE'),
    (lambda p: p.update(version=2), 'INCOMPATIBLE_STATE'),
    (lambda p: p.update(profile_id='other'), 'INCOMPATIBLE_STATE'),
    (lambda p: p.update(algorithm_id='other'), 'INCOMPATIBLE_STATE'),
    (lambda p: p.update(input_width=14), 'INCOMPATIBLE_STATE'),
    (lambda p: p.update(feature_order=list(reversed(range(13)))), 'INCOMPATIBLE_STATE'),
    (lambda p: p.update(feature_order=[False] + list(range(1, 13))), 'INVALID_STATE'),
    (lambda p: p.update(feature_order=None), 'INVALID_STATE'),
    (lambda p: p.update(trees=None), 'INVALID_STATE'),
    (lambda p: p.update(max_samples=33), 'RESOURCE_LIMIT'),
    (lambda p: p['trees'].append(p['trees'][0]), 'RESOURCE_LIMIT'),
    (lambda p: p['trees'].pop(), 'INVALID_STATE'),
    (lambda p: p['trees'][0].update(extra=0), 'INVALID_STATE'),
    (lambda p: p['trees'][0].pop('nodes'), 'INVALID_STATE'),
    (lambda p: p['trees'][0].update(nodes=None), 'INVALID_STATE'),
    (lambda p: p['trees'][0].update(nodes=[{}] * 64), 'RESOURCE_LIMIT'),
    (lambda p: p['trees'][0]['nodes'][0].update(extra=0), 'INVALID_STATE'),
    (lambda p: p['trees'][0]['nodes'][0].pop('left'), 'INVALID_STATE'),
    (lambda p: p['trees'][0]['nodes'][0].update(threshold=1), 'INVALID_STATE'),
    (lambda p: p['trees'][0]['nodes'][0].update(sample_count=3), 'INVALID_STATE'),
    (lambda p: p['trees'][0]['nodes'][0].update(left=2), 'INVALID_STATE'),
    (lambda p: p['trees'][0]['nodes'][1].update(sample_count=2), 'INVALID_STATE'),
])
def test_resealed_canonical_json_still_checks_content_and_structure(mutate, code):
    state = manual_numeric_state(pattern='asymmetric4', max_samples=4)
    projection = json.loads(contract.encode_iforest_numeric_state(state))
    mutate(projection)
    payload = canonical(projection)
    assert canonical(json.loads(payload)) == payload
    rejection(lambda: contract.decode_iforest_numeric_state(payload), code)


@pytest.mark.parametrize('transform', [
    lambda p: b'\xef\xbb\xbf' + p, lambda p: p[:-1], lambda p: p + b'\n',
    lambda p: b' ' + p, lambda p: p.replace(b'"version":1', b'"version": 1'),
    lambda p: p + b'{}', lambda p: p + b'junk',
    lambda p: p.replace(b'"version":1', b'"version":1,"version":1'),
    lambda p: p.replace(b'"nodes":', b'"nodes":[],"nodes":', 1),
    lambda p: p.replace(b'"sample_count":4', b'"sample_count":4,"sample_count":4', 1),
    lambda p: p.replace(b'"threshold":0.0', b'"threshold":NaN', 1),
    lambda p: p.replace(b'"threshold":0.0', b'"threshold":Infinity', 1),
    lambda p: p.replace(b'"threshold":0.0', b'"threshold":-Infinity', 1),
    lambda p: p.replace(b'"threshold":0.0', b'"threshold":1e999', 1),
    lambda p: p.replace(b'"threshold":0.0', b'"threshold":0e0', 1),
    lambda p: p.replace(b'"threshold":0.0', b'"threshold":0.000', 1),
    lambda p: p.replace(b'"feature":0', b'"feature":-0', 1),
    lambda p: p.replace(b'"version":1', b'"version":100000000'),
    lambda p: p.replace(b'"threshold":0.0', b'"threshold":0.' + b'0' * 31, 1),
    lambda p: b'{"a":"\\ud800"}\n', lambda p: b'\xff\n',
    lambda p: b'[' * 1500 + b']' * 1500 + b'\n',
    lambda p: b'null\n', lambda p: b'[]\n', lambda p: b'{}\n',
])
def test_json_parser_rejects_malformed_duplicate_nonfinite_tokens_and_noncanonical_bytes(transform):
    payload = contract.encode_iforest_numeric_state(manual_numeric_state(
        pattern='asymmetric4', max_samples=4))
    rejection(lambda: contract.decode_iforest_numeric_state(transform(payload)), 'INVALID_STATE')


def test_decode_key_order_is_canonical_and_not_only_valid_json():
    payload = contract.encode_iforest_numeric_state(manual_numeric_state())
    value = json.loads(payload)
    reordered = dict(reversed(tuple(value.items())))
    changed = (json.dumps(reordered, separators=(',', ':')) + '\n').encode()
    assert changed != payload and json.loads(changed) == value
    rejection(lambda: contract.decode_iforest_numeric_state(changed), 'INVALID_STATE')


def test_payload_budget_includes_lf_and_never_returns_a_truncation(monkeypatch):
    state = manual_numeric_state()
    payload = contract.encode_iforest_numeric_state(state)
    monkeypatch.setattr(contract, 'NUMERIC_STATE_BYTE_LIMIT', len(payload))
    assert contract.encode_iforest_numeric_state(state) == payload
    assert contract.decode_iforest_numeric_state(payload) == state
    monkeypatch.setattr(contract, 'NUMERIC_STATE_BYTE_LIMIT', len(payload) - 1)
    rejection(lambda: contract.encode_iforest_numeric_state(state), 'RESOURCE_LIMIT')
    rejection(lambda: contract.decode_iforest_numeric_state(payload), 'RESOURCE_LIMIT')
    rejection(lambda: contract.decode_iforest_numeric_state(b'x' * len(payload)), 'RESOURCE_LIMIT')


def test_full_payload_limit_is_checked_before_utf8_or_json():
    rejection(lambda: contract.decode_iforest_numeric_state(b'\xff' * 262145), 'RESOURCE_LIMIT')


def test_codec_does_not_import_numpy_or_models_or_open_paths(monkeypatch):
    state = manual_numeric_state(pattern='balanced32', max_samples=32)
    original = builtins.__import__
    observed = []

    def guarded_import(name, *args, **kwargs):
        observed.append(name)
        if name.split('.')[0] in {'numpy', 'sklearn', 'joblib', 'torch'}:
            raise AssertionError('codec attempted a numerical or model import')
        return original(name, *args, **kwargs)

    def denied(*args, **kwargs):
        raise AssertionError('codec attempted file I/O')

    monkeypatch.setattr(builtins, '__import__', guarded_import)
    monkeypatch.setattr(builtins, 'open', denied)
    monkeypatch.setattr(io, 'open', denied)
    monkeypatch.setattr(Path, 'open', denied)
    monkeypatch.setattr(Path, 'read_bytes', denied)
    monkeypatch.setattr(Path, 'read_text', denied)
    payload = contract.encode_iforest_numeric_state(state)
    assert contract.decode_iforest_numeric_state(payload) == state
    assert not any(name.split('.')[0] in {'numpy', 'sklearn', 'joblib', 'torch'} for name in observed)


def test_score_checks_state_before_even_attempting_private_import(monkeypatch):
    attempted = []
    original = builtins.__import__

    def import_spy(name, *args, **kwargs):
        attempted.append(name)
        return original(name, *args, **kwargs)

    monkeypatch.setattr(builtins, '__import__', import_spy)
    rejection(lambda: contract.score_iforest_numeric_state(
        replace(manual_numeric_state(), max_samples=False), object()), 'INVALID_STATE')
    assert not any('_iforest_numeric_score' in name for name in attempted)


def test_public_score_forwards_only_the_validated_exact_objects(monkeypatch):
    state, matrix = manual_numeric_state(), object()
    calls = []
    module = types.ModuleType('traffic_anomaly._iforest_numeric_score')

    def scorer(received_state, received_matrix):
        calls.append((received_state is state, received_matrix is matrix))
        return (0.5,)

    module._score_validated_state = scorer
    monkeypatch.setitem(sys.modules, module.__name__, module)
    assert contract.score_iforest_numeric_state(state, matrix) == (0.5,)
    assert calls == [(True, True)]


@pytest.mark.parametrize('entry', ['encode', 'decode', 'score'])
@pytest.mark.parametrize('kind,code', [('ordinary', 'NUMERIC_STATE_ERROR'),
    ('foreign_domain_subclass', 'NUMERIC_STATE_ERROR'), ('memory', 'RESOURCE_LIMIT')])
def test_public_failure_mapping_is_finite_without_foreign_code_access(monkeypatch, entry, kind, code):
    class Foreign(contract.IForestNumericStateError):
        def __init__(self):
            ValueError.__init__(self, 'secret')

        @property
        def code(self):
            raise AssertionError('foreign code getter must not run')

    failure = {'ordinary': RuntimeError('secret'), 'foreign_domain_subclass': Foreign(),
        'memory': MemoryError('secret')}[kind]

    def broken(*args, **kwargs):
        raise failure

    state = manual_numeric_state()
    payload = contract.encode_iforest_numeric_state(state)
    monkeypatch.setattr(contract, '_validate_state', broken)
    call = {'encode': lambda: contract.encode_iforest_numeric_state(state),
        'decode': lambda: contract.decode_iforest_numeric_state(payload),
        'score': lambda: contract.score_iforest_numeric_state(state, object())}[entry]
    error = rejection(call, code)
    assert error.__cause__ is None


@pytest.mark.parametrize('entry', ['encode', 'decode', 'score'])
def test_keyboard_interrupt_always_propagates(monkeypatch, entry):
    state = manual_numeric_state()
    payload = contract.encode_iforest_numeric_state(state)

    def interrupted(*args, **kwargs):
        raise KeyboardInterrupt

    monkeypatch.setattr(contract, '_validate_state', interrupted)
    call = {'encode': lambda: contract.encode_iforest_numeric_state(state),
        'decode': lambda: contract.decode_iforest_numeric_state(payload),
        'score': lambda: contract.score_iforest_numeric_state(state, object())}[entry]
    with pytest.raises(KeyboardInterrupt):
        call()


def test_decoder_parser_domain_subclass_is_unknown_not_a_parse_error(monkeypatch):
    class Foreign(contract.IForestNumericStateError):
        def __init__(self):
            ValueError.__init__(self, 'private parser details')

        @property
        def code(self):
            raise AssertionError('foreign code getter must not run')

    def parser(*args, **kwargs):
        raise Foreign()

    monkeypatch.setattr(contract.json, 'loads', parser)
    rejection(lambda: contract.decode_iforest_numeric_state(b'{}\n'), 'NUMERIC_STATE_ERROR')


@pytest.mark.parametrize('exception', [RuntimeError, ValueError, TypeError, AttributeError])
def test_unknown_parser_exceptions_are_not_trusted_as_input_errors(monkeypatch, exception):
    def parser(*args, **kwargs):
        raise exception('private parser details')

    monkeypatch.setattr(contract.json, 'loads', parser)
    rejection(lambda: contract.decode_iforest_numeric_state(b'{}\n'), 'NUMERIC_STATE_ERROR')


def test_unknown_attribute_error_inside_validation_is_not_a_missing_field(monkeypatch):
    state = manual_numeric_state(pattern='asymmetric4', max_samples=4)

    def unknown(*args, **kwargs):
        raise AttributeError('private unrelated details')

    monkeypatch.setattr(contract.math, 'isfinite', unknown)
    rejection(lambda: contract.encode_iforest_numeric_state(state), 'NUMERIC_STATE_ERROR')


def test_numpy_field_scalars_are_rejected_without_coercion():
    import numpy as np

    state = manual_numeric_state(pattern='asymmetric4', max_samples=4)
    changes = [replace(state, version=np.int64(1)),
        replace(state, max_samples=np.int64(4)),
        replace(state, input_width=np.int64(13)),
        replace(state, feature_order=(np.int64(0),) + tuple(range(1, 13))),
        changed_node(state, threshold=np.float64(0.0)),
        changed_node(state, sample_count=np.int64(4)),
        changed_node(state, left=np.int64(1)),
        changed_node(state, feature=np.int64(0)),
        changed_node(state, sample_count=np.bool_(True))]
    for bad in changes:
        rejection(lambda: contract.encode_iforest_numeric_state(bad), 'INVALID_STATE')


def test_builtin_scalar_subclasses_are_rejected_without_conversion():
    class Integer(int):
        def __int__(self):
            raise AssertionError('foreign conversion must not run')
    class Floating(float):
        def __float__(self):
            raise AssertionError('foreign conversion must not run')
    class Text(str):
        pass
    state = manual_numeric_state(pattern='asymmetric4', max_samples=4)
    for bad in [replace(state, version=Integer(1)),
            replace(state, profile_id=Text(state.profile_id)),
            changed_node(state, threshold=Floating(0.0))]:
        rejection(lambda: contract.encode_iforest_numeric_state(bad), 'INVALID_STATE')


def test_all_tree_container_bounds_precede_access_to_any_nodes():
    state = manual_numeric_state(max_samples=32)
    trees = (contract.IForestNumericTree((object(),)),
        contract.IForestNumericTree((object(),) * 64)) + state.trees[2:]
    rejection(lambda: contract.encode_iforest_numeric_state(replace(state, trees=trees)), 'RESOURCE_LIMIT')


def test_noncanonical_bytes_rejected_before_version_compatibility():
    payload = contract.encode_iforest_numeric_state(manual_numeric_state()).replace(
        b'"version":1', b'"version": 2')
    rejection(lambda: contract.decode_iforest_numeric_state(payload), 'INVALID_STATE')


@pytest.mark.parametrize('kind,code', [('exact', 'INVALID_MATRIX'),
    ('subclass', 'NUMERIC_STATE_ERROR'), ('ordinary', 'NUMERIC_STATE_ERROR'),
    ('memory', 'RESOURCE_LIMIT')])
def test_public_score_normalizes_private_scorer_failures(monkeypatch, kind, code):
    class Foreign(contract.IForestNumericStateError):
        def __init__(self):
            ValueError.__init__(self, 'private scorer details')

        @property
        def code(self):
            raise AssertionError('foreign code getter must not run')

    failure = {'exact': contract.IForestNumericStateError('INVALID_MATRIX'),
        'subclass': Foreign(), 'ordinary': RuntimeError('private scorer details'),
        'memory': MemoryError('private scorer details')}[kind]
    module = types.ModuleType('traffic_anomaly._iforest_numeric_score')

    def scorer(*args, **kwargs):
        raise failure

    module._score_validated_state = scorer
    monkeypatch.setitem(sys.modules, module.__name__, module)
    rejection(lambda: contract.score_iforest_numeric_state(manual_numeric_state(), object()), code)


@pytest.mark.parametrize('version', [True, 2])
def test_decode_projection_hard_limits_precede_state_type_and_compatibility(version):
    value = json.loads(contract.encode_iforest_numeric_state(manual_numeric_state()))
    value['version'] = version
    value['trees'][0]['nodes'] = [{}] * 64
    rejection(lambda: contract.decode_iforest_numeric_state(canonical(value)), 'RESOURCE_LIMIT')


@pytest.mark.parametrize('version,code', [(True, 'INVALID_STATE'), (2, 'INCOMPATIBLE_STATE')])
def test_decode_without_projection_error_preserves_state_type_and_compatibility(version, code):
    value = json.loads(contract.encode_iforest_numeric_state(manual_numeric_state()))
    value['version'] = version
    rejection(lambda: contract.decode_iforest_numeric_state(canonical(value)), code)


@pytest.mark.parametrize('kind,code', [('feature_order', 'INCOMPATIBLE_STATE'),
    ('trees', 'RESOURCE_LIMIT'), ('first_tree_nodes', 'RESOURCE_LIMIT'),
    ('last_tree_nodes', 'RESOURCE_LIMIT')])
def test_decode_checks_all_projection_container_limits_before_constructing_nodes(monkeypatch, kind, code):
    value = json.loads(contract.encode_iforest_numeric_state(manual_numeric_state()))
    if kind == 'feature_order':
        value['feature_order'] = list(range(27))
    elif kind == 'trees':
        value['trees'].append(value['trees'][0])
    else:
        value['trees'][0 if kind == 'first_tree_nodes' else -1]['nodes'] = [{}] * 64
    payload = canonical(value)

    def forbidden_constructor(*args, **kwargs):
        raise AssertionError('node allocation occurred before hard projection limits')

    monkeypatch.setattr(contract, 'IForestNumericNode', forbidden_constructor)
    rejection(lambda: contract.decode_iforest_numeric_state(payload), code)


def test_typed_state_combined_errors_keep_exact_type_before_container_limit():
    state = manual_numeric_state()
    bad = replace(state, version=True, trees=state.trees + state.trees[:1])
    rejection(lambda: contract.encode_iforest_numeric_state(bad), 'INVALID_STATE')
    rejection(lambda: contract.score_iforest_numeric_state(bad, object()), 'INVALID_STATE')


def test_json_container_shapes_precede_state_semantics():
    value = json.loads(contract.encode_iforest_numeric_state(manual_numeric_state()))
    value['version'] = 2
    value['feature_order'] = None
    rejection(lambda: contract.decode_iforest_numeric_state(canonical(value)), 'INVALID_STATE')


def test_in_budget_noncanonical_float_expansion_is_invalid_state_not_resource_limit():
    payload = b'[' + b','.join([b'1e4'] * 40000) + b']\n'
    assert len(payload) == 160002 <= contract.NUMERIC_STATE_BYTE_LIMIT
    assert len(canonical(json.loads(payload))) == 320002 > contract.NUMERIC_STATE_BYTE_LIMIT
    rejection(lambda: contract.decode_iforest_numeric_state(payload), 'INVALID_STATE')


def test_canonical_check_memory_error_still_has_resource_code(monkeypatch):
    payload = contract.encode_iforest_numeric_state(manual_numeric_state())

    def exhausted(*args, **kwargs):
        raise MemoryError('private allocator details')

    monkeypatch.setattr(contract.json.JSONEncoder, 'iterencode', exhausted)
    rejection(lambda: contract.decode_iforest_numeric_state(payload), 'RESOURCE_LIMIT')
