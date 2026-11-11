"""Manual forest routes and strict matrix boundaries; no learned model oracle."""

from contextlib import ExitStack
from dataclasses import replace
import builtins
import importlib
import importlib.util
import io
import os
from pathlib import Path
import warnings
from unittest.mock import patch

import numpy as np
import pytest


def api():
    try:
        module = importlib.import_module('traffic_anomaly.iforest_numeric_state')
    except ModuleNotFoundError as error:
        if error.name != 'traffic_anomaly.iforest_numeric_state':
            raise
        pytest.fail('public numeric-state scoring seam is missing')
    assert callable(getattr(module, 'score_iforest_numeric_state', None))
    assert importlib.util.find_spec('traffic_anomaly._iforest_numeric_score') is not None, (
        'private numeric scorer seam is missing')
    return module


def manual_state(**kwargs):
    from tests.core.iforest_numeric_state_cases import manual_numeric_state
    return manual_numeric_state(**kwargs)


def declared_score(max_samples, paths):
    """Independent arithmetic on declared (decision depth, leaf count) pairs.

    This never discovers a route or reads a product node/coefficient. Root
    depth is 1; paths are listed explicitly at each assertion. The adopted
    Windows reference literals below are evidence from the pre-product probe;
    this local formula is the strict arbiter if platform log/power differs.
    """
    n = np.arange(1, 33, dtype=np.int64)
    coefficient = np.zeros(32, dtype=np.float64)
    coefficient[1] = 1.0
    selected = n[2:]
    coefficient[2:] = (2.0 * (np.log(selected - 1.0) + np.euler_gamma)
                       - 2.0 * (selected - 1.0) / selected)
    depth = np.zeros(1, dtype=np.float64)
    for decision_depth, leaf_count in paths:
        depth += (np.asarray([decision_depth], dtype=np.int64)
                  + coefficient[leaf_count - 1] - 1.0)
    denominator = 16 * coefficient[max_samples - 1]
    score = 2 ** (-np.divide(depth, denominator, out=np.ones_like(depth),
                            where=denominator != 0))
    return float(score[0])


# Pre-product probe: left singleton, right count=3, balanced m32, then
# eight-left/eight-right versus alternating. No product/helper created these.
WINDOWS_PROBE_HEX = {
    'm4_left': '0x1.601ff02248482p-1',
    'm4_right': '0x1.c029e83c3a48ap-2',
    'm32_depth6': '0x1.21acf7189617bp-1',
    'm4_grouped': '0x1.18e6616710a0fp-1',
    'm4_alternating': '0x1.18e6616710a0ep-1',
}


def asymmetric(*, width=13, threshold=0.0, feature=0, max_samples=4):
    c = api()
    state = manual_state(width=width, pattern='asymmetric4', max_samples=4)
    # The two leaf populations are 1 and m-1; both are depth 2.
    nodes = (c.IForestNumericNode(1, 2, feature, threshold, max_samples),
             c.IForestNumericNode(None, None, None, None, 1),
             c.IForestNumericNode(None, None, None, None, max_samples - 1))
    return replace(state, max_samples=max_samples,
                   trees=(c.IForestNumericTree(nodes),) * 16)


def assert_error(c, expected, state, matrix):
    with pytest.raises(c.IForestNumericStateError) as caught:
        c.score_iforest_numeric_state(state, matrix)
    assert type(caught.value) is c.IForestNumericStateError
    assert caught.value.code == expected
    assert str(caught.value) == expected


@pytest.mark.parametrize('width', [13, 26])
def test_single_sample_state_scores_exact_half_in_both_widths(width):
    c = api()  # Valid RED points at the real public/private scoring seam.
    state = manual_state(width=width)
    result = c.score_iforest_numeric_state(state, np.zeros((3, width), np.float32))
    assert type(result) is tuple
    assert result == (.5, .5, .5)
    assert all(type(value) is float for value in result)


@pytest.mark.parametrize('width', [13, 26])
@pytest.mark.parametrize('max_samples', [1, 2, 32])
def test_root_leaf_reference_cases_return_exact_half(width, max_samples):
    c = api()
    state = manual_state(width=width, max_samples=max_samples)
    assert c.score_iforest_numeric_state(state, np.zeros((2, width), np.float64)) == (.5, .5)


@pytest.mark.parametrize('width', [13, 26])
def test_two_singleton_children_have_one_edge_and_exact_half(width):
    c = api()
    state = manual_state(width=width, pattern='split2', max_samples=2)
    matrix = np.zeros((3, width), np.float32)
    matrix[:, 0] = (-1, 0, 1)
    assert c.score_iforest_numeric_state(state, matrix) == (.5, .5, .5)


@pytest.mark.parametrize('width', [13, 26])
def test_asymmetric_leaf_populations_set_positive_anomaly_direction(width):
    c = api()
    state = asymmetric(width=width)
    matrix = np.zeros((3, width), np.float64)
    matrix[:, 0] = (-1, 0, 1)
    left = declared_score(4, [(2, 1)] * 16)
    right = declared_score(4, [(2, 3)] * 16)
    assert left > right
    assert c.score_iforest_numeric_state(state, matrix) == (left, left, right)


@pytest.mark.parametrize('max_samples', range(3, 33))
def test_all_bounded_sample_coefficients_use_the_approximate_log_formula(max_samples):
    c = api()
    state = asymmetric(max_samples=max_samples)
    matrix = np.zeros((2, 13), np.float64)
    matrix[:, 0] = (-1, 1)
    expected = (declared_score(max_samples, [(2, 1)] * 16),
                declared_score(max_samples, [(2, max_samples - 1)] * 16))
    assert c.score_iforest_numeric_state(state, matrix) == expected


def test_float32_feature_is_promoted_before_binary64_threshold_comparison():
    c = api()
    # x32=1 is greater than t in binary64, so it must reach count=3/right.
    # NumPy2's direct np.float32(1) <= t incorrectly rounds t to float32 1.
    state = asymmetric(threshold=1.0 - 2.0 ** -26)
    matrix = np.ones((2, 13), np.float32)
    matrix[1, 0] = np.nextafter(np.float32(1), np.float32(0))
    assert c.score_iforest_numeric_state(state, matrix) == (
        declared_score(4, [(2, 3)] * 16), declared_score(4, [(2, 1)] * 16))


def test_float64_inputs_route_after_float32_rounding_and_equal_threshold_goes_left():
    c = api()
    state = asymmetric(threshold=1.0)
    matrix = np.zeros((4, 13), np.float64)
    # 1+2^-25 is greater than the threshold originally, but rounds to f32 1.
    matrix[:, 0] = (1.0 + 2.0 ** -25, 1.0, 1.0 + 2.0 ** -23, 1.0 - 2.0 ** -24)
    left = declared_score(4, [(2, 1)] * 16)
    right = declared_score(4, [(2, 3)] * 16)
    assert c.score_iforest_numeric_state(state, matrix) == (left, left, right, left)


@pytest.mark.parametrize('threshold,left', [(np.finfo(np.float64).max.item(), True),
                                            (-np.finfo(np.float64).max.item(), False),
                                            (-0.0, True)])
def test_finite_binary64_threshold_is_not_cast_to_float32(threshold, left):
    c = api()
    state = asymmetric(threshold=threshold)
    expected = declared_score(4, [(2, 1 if left else 3)] * 16)
    with warnings.catch_warnings():
        warnings.simplefilter('error', RuntimeWarning)
        assert c.score_iforest_numeric_state(state, np.zeros((1, 13), np.float32)) == (expected,)


def test_feature_25_of_width_26_controls_routing():
    c = api()
    state = asymmetric(width=26, feature=25)
    matrix = np.ones((2, 26), np.float32)
    matrix[0, 25] = -1
    assert c.score_iforest_numeric_state(state, matrix) == (
        declared_score(4, [(2, 1)] * 16), declared_score(4, [(2, 3)] * 16))


def test_three_leaf_tree_preserves_depth_and_leaf_sample_correction():
    c = api()
    base = manual_state(pattern='three_leaf4', max_samples=4)
    # Handwritten topology: root(4) -> leaf(1) / split(3) -> leaf(1)/leaf(2).
    nodes = (c.IForestNumericNode(1, 2, 0, 0.0, 4),
             c.IForestNumericNode(None, None, None, None, 1),
             c.IForestNumericNode(3, 4, 1, 0.0, 3),
             c.IForestNumericNode(None, None, None, None, 1),
             c.IForestNumericNode(None, None, None, None, 2))
    state = replace(base, trees=(c.IForestNumericTree(nodes),) * 16)
    matrix = np.zeros((3, 13), np.float32)
    matrix[:, :2] = ((-1, 1), (1, -1), (1, 1))
    # Rows: depth2/count1; depth3/count1; depth3/count2.
    expected = tuple(declared_score(4, [path] * 16) for path in [(2, 1), (3, 1), (3, 2)])
    assert c.score_iforest_numeric_state(state, matrix) == expected


def test_full_63_node_tree_reaches_five_edge_depth_in_both_widths():
    c = api()
    for width in (13, 26):
        state = manual_state(width=width, pattern='balanced32', max_samples=32)
        assert all(len(tree.nodes) == 63 for tree in state.trees)
        # Midpoint thresholds partition [0,32); every half-integer reaches a
        # distinct singleton at decision depth 6, hence contribution 5.
        matrix = np.zeros((32, width), np.float32)
        matrix[:, 0] = np.arange(32, dtype=np.float32) + .5
        expected = declared_score(32, [(6, 1)] * 16)
        assert c.score_iforest_numeric_state(state, matrix) == (expected,) * 32


def test_fixed_tree_order_is_sequential_contribution_accumulation():
    c = api()
    left_tree = asymmetric(threshold=1.0).trees[0]  # x=0 -> depth2/count1.
    right_tree = asymmetric(threshold=-1.0).trees[0]  # x=0 -> depth2/count3.
    base = asymmetric()
    grouped = replace(base, trees=(left_tree,) * 8 + (right_tree,) * 8)
    alternating = replace(base, trees=(left_tree, right_tree) * 8)
    matrix = np.zeros((1, 13), np.float64)
    grouped_expected = declared_score(4, [(2, 1)] * 8 + [(2, 3)] * 8)
    alternating_expected = declared_score(4, [(2, 1), (2, 3)] * 8)
    assert c.score_iforest_numeric_state(grouped, matrix) == (grouped_expected,)
    assert c.score_iforest_numeric_state(alternating, matrix) == (alternating_expected,)
    # Adopted local probe differs by one ULP; arithmetic above remains strict
    # on another platform without assuming its log/power's final bit.
    if (grouped_expected.hex(), alternating_expected.hex()) == (
            WINDOWS_PROBE_HEX['m4_grouped'], WINDOWS_PROBE_HEX['m4_alternating']):
        assert grouped_expected != alternating_expected


@pytest.mark.parametrize('width', [13, 26])
@pytest.mark.parametrize('dtype', [np.float32, np.float64])
def test_zero_rows_and_maximum_rows_are_legal(width, dtype):
    c = api()
    state = manual_state(width=width)
    assert c.score_iforest_numeric_state(state, np.zeros((0, width), dtype)) == ()
    result = c.score_iforest_numeric_state(state, np.zeros((10000, width), dtype))
    assert type(result) is tuple and len(result) == 10000
    assert result == (.5,) * 10000


def array_identity(matrix):
    return (matrix.tobytes(order='A'), matrix.shape, matrix.strides, matrix.dtype,
            tuple(matrix.flags[name] for name in ('C_CONTIGUOUS', 'F_CONTIGUOUS',
                  'OWNDATA', 'WRITEABLE', 'ALIGNED', 'WRITEBACKIFCOPY')))


@pytest.mark.parametrize('layout', ['c', 'fortran', 'strided', 'reverse', 'readonly'])
@pytest.mark.parametrize('dtype', [np.float32, np.float64])
def test_legal_array_layouts_preserve_source_bytes_and_flags(layout, dtype):
    c = api()
    matrix = np.zeros((4, 13), dtype)
    matrix[:, 0] = (-1, 1, -1, 1)
    if layout == 'fortran':
        matrix = np.asfortranarray(matrix)
    elif layout == 'strided':
        matrix = np.repeat(matrix, 2, axis=1)[:, ::2]
    elif layout == 'reverse':
        matrix = matrix[::-1]
    elif layout == 'readonly':
        matrix.setflags(write=False)
    before = array_identity(matrix)
    left = declared_score(4, [(2, 1)] * 16)
    right = declared_score(4, [(2, 3)] * 16)
    expected = (right, left, right, left) if layout == 'reverse' else (left, right, left, right)
    assert c.score_iforest_numeric_state(asymmetric(), matrix) == expected
    assert array_identity(matrix) == before


@pytest.mark.parametrize('dtype', ['int64', 'bool', 'object', 'complex64', 'float16',
                                   np.longdouble, [('value', 'f4')],
                                   np.dtype('f4').newbyteorder('S'),
                                   np.dtype('f8').newbyteorder('S')])
def test_non_native_or_non_float32_float64_dtypes_are_rejected(dtype):
    c = api()
    matrix = np.zeros((1, 13), dtype=dtype)
    assert_error(c, 'INVALID_MATRIX', manual_state(), matrix)


@pytest.mark.parametrize('shape', [(13,), (1, 1, 13), (1, 12), (0, 26), (0, 0)])
def test_bad_dimension_or_width_is_invalid_matrix_even_for_zero_rows(shape):
    c = api()
    assert_error(c, 'INVALID_MATRIX', manual_state(), np.zeros(shape, np.float32))


def test_more_than_10000_rows_is_resource_limit_before_reading_values():
    c = api()
    assert_error(c, 'RESOURCE_LIMIT', manual_state(), np.full((10001, 13), np.nan, np.float32))


@pytest.mark.parametrize('kind', ['list', 'tuple', 'subclass', 'memmap', 'masked', 'foreign'])
def test_only_exact_ndarray_is_accepted_without_foreign_getters(kind):
    c = api()
    class ArraySubclass(np.ndarray):
        pass
    class Foreign:
        def __getattribute__(self, name):
            raise AssertionError('foreign matrix getter was read')
    matrices = {'list': [[0.0] * 13], 'tuple': ((0.0,) * 13,),
                'subclass': np.zeros((1, 13), np.float32).view(ArraySubclass),
                'memmap': np.zeros((1, 13), np.float32).view(np.memmap),
                'masked': np.ma.array(np.zeros((1, 13), np.float32)), 'foreign': Foreign()}
    assert_error(c, 'INVALID_MATRIX', manual_state(), matrices[kind])


@pytest.mark.parametrize('value', [np.nan, np.inf, -np.inf])
@pytest.mark.parametrize('dtype', [np.float32, np.float64])
def test_non_finite_original_values_are_rejected_without_mutation(value, dtype):
    c = api()
    matrix = np.zeros((2, 13), dtype)
    matrix[1, 12] = value
    before = array_identity(matrix)
    assert_error(c, 'INVALID_MATRIX', manual_state(), matrix)
    assert array_identity(matrix) == before


def test_float32_cast_overflow_is_invalid_matrix_without_warning_or_errstate_leak():
    c = api()
    matrix = np.full((1, 13), np.finfo(np.float64).max, np.float64)
    before = array_identity(matrix)
    with np.errstate(all='raise'):
        configured = np.geterr()
        with warnings.catch_warnings():
            warnings.simplefilter('error', RuntimeWarning)
            assert_error(c, 'INVALID_MATRIX', manual_state(), matrix)
        assert np.geterr() == configured
    assert array_identity(matrix) == before


def test_float32_cast_underflow_is_legal_under_strict_caller_errstate():
    c = api()
    state = asymmetric()
    # A finite positive binary64 value becomes float32 zero and therefore
    # goes left at threshold=0. Underflow is not overflow/non-finiteness.
    matrix = np.full((1, 13), np.finfo(np.float64).tiny, np.float64)
    before = array_identity(matrix)
    expected = declared_score(4, [(2, 1)] * 16)
    with np.errstate(all='raise'):
        configured = np.geterr()
        with warnings.catch_warnings():
            warnings.simplefilter('error', RuntimeWarning)
            assert c.score_iforest_numeric_state(state, matrix) == (expected,)
        assert np.geterr() == configured
    assert array_identity(matrix) == before


@pytest.mark.parametrize('version', ['2.5.3', '2.5.4+local', None, 254])
def test_runtime_version_must_be_exact_before_matrix_validation(monkeypatch, version):
    c = api()
    state = manual_state()
    monkeypatch.setattr(np, '__version__', version)
    assert_error(c, 'INCOMPATIBLE_RUNTIME', state, None)


def test_numpy_unavailable_at_scoring_time_is_incompatible_runtime(monkeypatch):
    c = api()
    state = manual_state()
    original_import = builtins.__import__
    def unavailable(name, *args, **kwargs):
        if name == 'numpy' or name.startswith('numpy.'):
            raise ModuleNotFoundError('unavailable')
        return original_import(name, *args, **kwargs)
    monkeypatch.setattr(builtins, '__import__', unavailable)
    assert_error(c, 'INCOMPATIBLE_RUNTIME', state, None)


def test_invalid_state_is_rejected_before_runtime_or_matrix(monkeypatch):
    c = api()
    monkeypatch.setattr(np, '__version__', 'unavailable')
    assert_error(c, 'INVALID_STATE_ARGUMENTS', object(), object())
    state = replace(manual_state(), max_samples=0)
    assert_error(c, 'INVALID_STATE', state, object())


def test_snapshot_is_independent_of_source_alias_write_during_scoring(monkeypatch):
    c = api()
    state = asymmetric()
    matrix = np.full((2, 13), -1.0, np.float32)
    original_array = np.array
    def copy_then_alias_write(value, *args, **kwargs):
        result = original_array(value, *args, **kwargs)
        if value is matrix:
            matrix[:] = 1.0
        return result
    monkeypatch.setattr(np, 'array', copy_then_alias_write)
    assert c.score_iforest_numeric_state(state, matrix) == (declared_score(4, [(2, 1)] * 16),) * 2
    assert np.all(matrix == 1.0)  # The deliberate alias write happened after copy.


@pytest.mark.parametrize('exception,expected', [(MemoryError, 'RESOURCE_LIMIT'),
                                                (RuntimeError, 'NUMERIC_STATE_ERROR')])
def test_unexpected_allocation_failure_has_only_a_finite_code(monkeypatch, exception, expected):
    c = api()
    state = manual_state()
    matrix = np.zeros((1, 13), np.float32)
    class HostileError(exception):
        @property
        def code(self):
            raise AssertionError('foreign error code was read')
    def fail(*args, **kwargs):
        raise HostileError('private contents must not escape')
    monkeypatch.setattr(np, 'array', fail)
    assert_error(c, expected, state, matrix)


def test_keyboard_interrupt_from_numeric_operation_propagates(monkeypatch):
    c = api()
    state = manual_state()
    matrix = np.zeros((1, 13), np.float32)
    def interrupted(*args, **kwargs):
        raise KeyboardInterrupt
    monkeypatch.setattr(np, 'array', interrupted)
    with pytest.raises(KeyboardInterrupt):
        c.score_iforest_numeric_state(state, matrix)


@pytest.mark.parametrize('divide_result', [np.array([np.nan]), np.array([np.inf]),
                                         np.array([-1.0]), np.zeros(2)])
def test_invalid_internal_result_is_rejected_as_numeric_state_error(monkeypatch, divide_result):
    c = api()
    state = manual_state()
    matrix = np.zeros((1, 13), np.float32)
    monkeypatch.setattr(np, 'divide', lambda *args, **kwargs: divide_result)
    assert_error(c, 'NUMERIC_STATE_ERROR', state, matrix)


def test_scoring_has_no_file_or_model_operations_and_does_not_cache_input():
    c = api()
    state = asymmetric()
    matrix = np.zeros((1, 13), np.float32)
    left = declared_score(4, [(2, 1)] * 16)
    right = declared_score(4, [(2, 3)] * 16)
    original_import = builtins.__import__
    def guarded_import(name, *args, **kwargs):
        if name.split('.')[0] in {'sklearn', 'joblib', 'torch'}:
            raise AssertionError('model import is forbidden')
        return original_import(name, *args, **kwargs)
    def forbidden(*args, **kwargs):
        raise AssertionError('file operation is forbidden')
    with ExitStack() as stack:
        for owner, attribute in ((builtins, 'open'), (io, 'open'), (os, 'open'),
                                 (os, 'stat'), (os, 'listdir'), (os, 'scandir'),
                                 (Path, 'open'), (Path, 'stat'), (Path, 'iterdir'),
                                 (Path, 'read_bytes'), (Path, 'read_text')):
            stack.enter_context(patch.object(owner, attribute, forbidden))
        stack.enter_context(patch.object(builtins, '__import__', guarded_import))
        assert c.score_iforest_numeric_state(state, matrix) == (left,)
        matrix[0, 0] = 1.0
        assert c.score_iforest_numeric_state(state, matrix) == (right,)


def test_private_module_import_does_not_import_numpy_or_models(monkeypatch):
    api()
    scorer = importlib.import_module('traffic_anomaly._iforest_numeric_score')
    original_import = builtins.__import__
    def guarded_import(name, *args, **kwargs):
        if name.split('.')[0] in {'numpy', 'sklearn', 'joblib', 'torch'}:
            raise AssertionError('numeric/model import during module initialization')
        return original_import(name, *args, **kwargs)
    monkeypatch.setattr(builtins, '__import__', guarded_import)
    importlib.reload(scorer)
