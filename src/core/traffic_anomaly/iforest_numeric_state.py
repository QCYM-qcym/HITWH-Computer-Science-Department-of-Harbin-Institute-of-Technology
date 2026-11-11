"""Bounded, canonical, in-memory numeric IF state; no model or source identity.

The codec needs only the standard library. Numerical scoring is imported lazily
after the single structural validator accepts the exact immutable state.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import math

NUMERIC_STATE_VERSION = 1
NUMERIC_STATE_PROFILE_ID = 'iforest-numeric-state-v1'
NUMERIC_STATE_ALGORITHM_ID = 'iforest16-m32-f32route-f64path-numpy254-v1'
NUMERIC_STATE_BYTE_LIMIT = 262144
NUMERIC_STATE_MAX_ROWS = 10000

_CODES = frozenset(('INVALID_STATE_ARGUMENTS', 'INVALID_STATE',
    'INCOMPATIBLE_STATE', 'RESOURCE_LIMIT', 'INVALID_MATRIX',
    'INCOMPATIBLE_RUNTIME', 'NUMERIC_STATE_ERROR'))
_STATE_FIELDS = frozenset(('version', 'profile_id', 'algorithm_id',
    'input_width', 'feature_order', 'max_samples', 'trees'))
_NODE_FIELDS = frozenset(('left', 'right', 'feature', 'threshold', 'sample_count'))


class IForestNumericStateError(ValueError):
    """One finite code, without input values, paths or original exceptions."""

    def __init__(self, code):
        self.code = code if type(code) is str and code in _CODES else 'NUMERIC_STATE_ERROR'
        super().__init__(self.code)


@dataclass(frozen=True, slots=True)
class IForestNumericNode:
    left: int | None
    right: int | None
    feature: int | None
    threshold: float | None
    sample_count: int


@dataclass(frozen=True, slots=True)
class IForestNumericTree:
    nodes: tuple[IForestNumericNode, ...]


@dataclass(frozen=True, slots=True)
class IForestNumericState:
    version: int
    profile_id: str
    algorithm_id: str
    input_width: int
    feature_order: tuple[int, ...]
    max_samples: int
    trees: tuple[IForestNumericTree, ...]


def _fail(code):
    raise IForestNumericStateError(code)


def _require_fields(value, names):
    try:
        for name in names:
            object.__getattribute__(value, name)
    except AttributeError:
        # Only a missing slot on an already exact class is an input error.
        _fail('INVALID_STATE')


def _validate_state(state: IForestNumericState) -> None:
    """The sole state validator, shared by codec and public score forwarding."""
    if type(state) is not IForestNumericState:
        _fail('INVALID_STATE_ARGUMENTS')
    _require_fields(state, ('version', 'profile_id', 'algorithm_id', 'input_width',
        'feature_order', 'max_samples', 'trees'))
    try:
        if (type(state.version) is not int or type(state.profile_id) is not str
                or type(state.algorithm_id) is not str or type(state.input_width) is not int
                or type(state.feature_order) is not tuple or type(state.max_samples) is not int
                or type(state.trees) is not tuple):
            _fail('INVALID_STATE')
        width, m, trees = state.input_width, state.max_samples, state.trees
        if m > 32 or len(trees) > 16:
            _fail('RESOURCE_LIMIT')
        if (state.version != NUMERIC_STATE_VERSION
                or state.profile_id != NUMERIC_STATE_PROFILE_ID
                or state.algorithm_id != NUMERIC_STATE_ALGORITHM_ID
                or width not in (13, 26)):
            _fail('INCOMPATIBLE_STATE')
        # Length is checked before any element traversal, including exact types.
        if len(state.feature_order) != width:
            _fail('INCOMPATIBLE_STATE')
        if any(type(value) is not int for value in state.feature_order):
            _fail('INVALID_STATE')
        if state.feature_order != tuple(range(width)):
            _fail('INCOMPATIBLE_STATE')
        if m < 1 or len(trees) != 16:
            _fail('INVALID_STATE')
        total_nodes = 0
        # Bound all tree containers before accessing any individual node.
        for tree in trees:
            if type(tree) is not IForestNumericTree:
                _fail('INVALID_STATE')
            _require_fields(tree, ('nodes',))
            if type(tree.nodes) is not tuple:
                _fail('INVALID_STATE')
            if len(tree.nodes) > 63:
                _fail('RESOURCE_LIMIT')
            total_nodes += len(tree.nodes)
        if total_nodes > 1008:
            _fail('RESOURCE_LIMIT')
        depth_limit = (max(m, 2) - 1).bit_length()
        for tree in trees:
            nodes = tree.nodes
            count = len(nodes)
            if not count or count > 2 * m - 1:
                _fail('INVALID_STATE')
            indegree = [0] * count
            for index, node in enumerate(nodes):
                if type(node) is not IForestNumericNode:
                    _fail('INVALID_STATE')
                _require_fields(node, ('left', 'right', 'feature', 'threshold', 'sample_count'))
                if type(node.sample_count) is not int or not 1 <= node.sample_count <= m:
                    _fail('INVALID_STATE')
                parts = (node.left, node.right, node.feature, node.threshold)
                if all(value is None for value in parts):
                    continue
                if any(value is None for value in parts):
                    _fail('INVALID_STATE')
                if (type(node.left) is not int or type(node.right) is not int
                        or type(node.feature) is not int or type(node.threshold) is not float):
                    _fail('INVALID_STATE')
                if (not index < node.left < count or not index < node.right < count
                        or node.left == node.right or not 0 <= node.feature < width
                        or not math.isfinite(node.threshold)):
                    _fail('INVALID_STATE')
                indegree[node.left] += 1
                indegree[node.right] += 1
            if nodes[0].sample_count != m or indegree[0] != 0:
                _fail('INVALID_STATE')
            if any(degree != 1 for degree in indegree[1:]):
                _fail('INVALID_STATE')
            seen = set()
            pending = [(0, 0)]
            while pending:
                index, depth = pending.pop()
                if index in seen or depth > depth_limit:
                    _fail('INVALID_STATE')
                seen.add(index)
                node = nodes[index]
                if node.left is not None:
                    if (nodes[node.left].sample_count + nodes[node.right].sample_count
                            != node.sample_count):
                        _fail('INVALID_STATE')
                    pending.append((node.right, depth + 1))
                    pending.append((node.left, depth + 1))
            if len(seen) != count:
                _fail('INVALID_STATE')
    except AttributeError:
        # Missing slots were handled at their exact object boundary above.
        # An unrelated implementation failure remains an unknown error.
        _fail('NUMERIC_STATE_ERROR')


def _projection(state):
    return {'version': state.version, 'profile_id': state.profile_id,
        'algorithm_id': state.algorithm_id, 'input_width': state.input_width,
        'feature_order': list(state.feature_order), 'max_samples': state.max_samples,
        'trees': [{'nodes': [{'left': node.left, 'right': node.right,
            'feature': node.feature, 'threshold': node.threshold,
            'sample_count': node.sample_count} for node in tree.nodes]}
            for tree in state.trees]}


def _canonical_bytes(value, *, limit_error='RESOURCE_LIMIT'):
    encoder = json.JSONEncoder(ensure_ascii=False, sort_keys=True,
        separators=(',', ':'), allow_nan=False)
    chunks = []
    size = 1  # The final LF is part of the complete payload budget.
    for chunk in encoder.iterencode(value):
        encoded = chunk.encode('utf-8')
        size += len(encoded)
        if size > NUMERIC_STATE_BYTE_LIMIT:
            _fail(limit_error)
        chunks.append(encoded)
    return b''.join(chunks) + b'\n'


def encode_iforest_numeric_state(state: IForestNumericState) -> bytes:
    """Validate and encode one canonical UTF-8 JSON value ending in one LF."""
    try:
        _validate_state(state)
        return _canonical_bytes(_projection(state))
    except MemoryError:
        raise IForestNumericStateError('RESOURCE_LIMIT') from None
    except Exception as error:
        if type(error) is IForestNumericStateError:
            raise
        raise IForestNumericStateError('NUMERIC_STATE_ERROR') from None


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            _fail('INVALID_STATE')
        result[key] = value
    return result


def _integer(token):
    if len(token) > 8:
        _fail('INVALID_STATE')
    return int(token)


def _floating(token):
    if len(token) > 32:
        _fail('INVALID_STATE')
    value = float(token)
    if not math.isfinite(value):
        _fail('INVALID_STATE')
    return value


def _constant(_token):
    _fail('INVALID_STATE')


def _from_projection(value):
    if type(value) is not dict or value.keys() != _STATE_FIELDS:
        _fail('INVALID_STATE')
    if type(value['feature_order']) is not list or type(value['trees']) is not list:
        _fail('INVALID_STATE')
    # No supported width can accept more than 26 indices. Bound this list
    # before converting it to a tuple or constructing any nested objects.
    if len(value['feature_order']) > 26:
        _fail('INCOMPATIBLE_STATE')
    if len(value['trees']) > 16:
        _fail('RESOURCE_LIMIT')
    # Check every tree's container shape and hard limit before allocating nodes.
    for tree in value['trees']:
        if type(tree) is not dict or tree.keys() != {'nodes'} or type(tree['nodes']) is not list:
            _fail('INVALID_STATE')
        if len(tree['nodes']) > 63:
            _fail('RESOURCE_LIMIT')
    trees = []
    for tree in value['trees']:
        nodes = []
        for node in tree['nodes']:
            if type(node) is not dict or node.keys() != _NODE_FIELDS:
                _fail('INVALID_STATE')
            nodes.append(IForestNumericNode(node['left'], node['right'],
                node['feature'], node['threshold'], node['sample_count']))
        trees.append(IForestNumericTree(tuple(nodes)))
    return IForestNumericState(value['version'], value['profile_id'], value['algorithm_id'],
        value['input_width'], tuple(value['feature_order']), value['max_samples'], tuple(trees))


def decode_iforest_numeric_state(payload: bytes) -> IForestNumericState:
    """Reject noncanonical, oversized or inconsistent JSON without reading files."""
    try:
        if type(payload) is not bytes:
            _fail('INVALID_STATE_ARGUMENTS')
        if len(payload) > NUMERIC_STATE_BYTE_LIMIT:
            _fail('RESOURCE_LIMIT')
        try:
            value = json.loads(payload.decode('utf-8'), object_pairs_hook=_object,
                parse_int=_integer, parse_float=_floating, parse_constant=_constant)
            # An in-budget input whose canonical spelling would exceed the
            # budget is noncanonical, not an oversized input. Keep this check
            # bounded while leaving encode's actual output budget unchanged.
            if _canonical_bytes(value, limit_error='INVALID_STATE') != payload:
                _fail('INVALID_STATE')
        except (ValueError, TypeError, UnicodeError, RecursionError, OverflowError) as error:
            if type(error) is IForestNumericStateError:
                raise
            if type(error) in (json.JSONDecodeError, UnicodeDecodeError,
                    UnicodeEncodeError, RecursionError, OverflowError):
                _fail('INVALID_STATE')
            # Unknown exceptions, including subclasses of our finite domain,
            # are never trusted as parser errors and their .code is not read.
            _fail('NUMERIC_STATE_ERROR')
        state = _from_projection(value)
        _validate_state(state)
        return state
    except MemoryError:
        raise IForestNumericStateError('RESOURCE_LIMIT') from None
    except Exception as error:
        if type(error) is IForestNumericStateError:
            raise
        raise IForestNumericStateError('NUMERIC_STATE_ERROR') from None


def score_iforest_numeric_state(state: IForestNumericState, matrix) -> tuple[float, ...]:
    """Validate state before importing the NumPy scorer and forwarding the matrix."""
    try:
        _validate_state(state)
        from ._iforest_numeric_score import _score_validated_state
        return _score_validated_state(state, matrix)
    except MemoryError:
        raise IForestNumericStateError('RESOURCE_LIMIT') from None
    except Exception as error:
        if type(error) is IForestNumericStateError:
            raise
        raise IForestNumericStateError('NUMERIC_STATE_ERROR') from None
