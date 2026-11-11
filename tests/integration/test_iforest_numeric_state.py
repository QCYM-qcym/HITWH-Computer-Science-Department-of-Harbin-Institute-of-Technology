"""In-memory artificial numeric-state integration; never a fitted-model fixture."""
from __future__ import annotations

import importlib
import builtins
from contextlib import contextmanager
from dataclasses import FrozenInstanceError, asdict, replace
import io
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
from types import ModuleType
import warnings

import numpy as np
import pytest


_MODEL_ROOTS = {"sklearn", "joblib", "torch", "tensorflow", "xgboost", "pandas"}


def _api_and_manual():
    before = {name: id(module) for name, module in sys.modules.items()
              if name.split(".", 1)[0] in _MODEL_ROOTS}
    real_import = builtins.__import__
    real_import_module = importlib.import_module

    def check(name):
        if name.lstrip(".").split(".", 1)[0] in _MODEL_ROOTS:
            raise AssertionError("numeric setup attempted a forbidden model import")

    def guarded_import(name, *args, **kwargs):
        check(name)
        return real_import(name, *args, **kwargs)

    def guarded_import_module(name, package=None):
        check(name)
        return real_import_module(name, package)

    builtins.__import__ = guarded_import
    importlib.import_module = guarded_import_module
    try:
        api = importlib.import_module("traffic_anomaly.iforest_numeric_state")
        cases = importlib.import_module("tests.core.iforest_numeric_state_cases")
        # Python source imports are setup, outside the no-I/O operation guard.
        importlib.import_module("traffic_anomaly._iforest_numeric_score")
    finally:
        builtins.__import__ = real_import
        importlib.import_module = real_import_module
    after = {name: id(module) for name, module in sys.modules.items()
             if name.split(".", 1)[0] in _MODEL_ROOTS}
    assert after == before
    return api, cases.manual_numeric_state


@contextmanager
def _pure_operation(monkeypatch):
    """High-level I/O/model/producer guard; does not claim OS syscall mediation."""
    violations = []
    modules_before = set(sys.modules)
    real_import = builtins.__import__
    real_import_module = importlib.import_module

    def blocked(name):
        def reject(*args, **kwargs):
            violations.append(name)
            raise AssertionError("numeric-state operation attempted a forbidden side effect")
        return reject

    def forbidden_import(name):
        return (name.split(".", 1)[0] in _MODEL_ROOTS
                or (name.startswith("traffic_anomaly.") and name not in {
                    "traffic_anomaly.iforest_numeric_state",
                    "traffic_anomaly._iforest_numeric_score",
                })
                or name.startswith(("release_", "candidate_", "historical_")))

    def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
        if forbidden_import(name):
            return blocked("import:" + name)()
        return real_import(name, globals, locals, fromlist, level)

    def guarded_import_module(name, package=None):
        if forbidden_import(name.lstrip(".")):
            return blocked("import_module:" + name)()
        return real_import_module(name, package)

    with monkeypatch.context() as patch:
        patch.setattr(builtins, "__import__", guarded_import)
        patch.setattr(importlib, "import_module", guarded_import_module)
        for owner, names in (
            (builtins, ("open",)),
            (io, ("open",)),
            (os, ("open", "read", "write", "listdir", "scandir", "stat", "lstat", "getcwd", "mkdir", "makedirs", "remove", "unlink", "rmdir", "rename", "replace")),
            (Path, ("open", "read_bytes", "read_text", "write_bytes", "write_text", "iterdir", "glob", "rglob", "stat", "lstat", "exists", "is_file", "is_dir", "resolve", "mkdir", "unlink", "rename", "replace", "touch")),
            (socket, ("socket", "create_connection")),
            (subprocess, ("Popen", "run")),
        ):
            for name in names:
                patch.setattr(owner, name, blocked(f"{owner.__name__}.{name}"))
        yield violations
    assert violations == []
    assert not {name for name in set(sys.modules) - modules_before
                if name.split(".", 1)[0] in _MODEL_ROOTS}


def _canonical_document(width):
    # This independently stated JSON shape does not use the production encoder.
    return {
        "version": 1,
        "profile_id": "iforest-numeric-state-v1",
        "algorithm_id": "iforest16-m32-f32route-f64path-numpy254-v1",
        "input_width": width,
        "feature_order": list(range(width)),
        "max_samples": 1,
        "trees": [{"nodes": [{"left": None, "right": None, "feature": None,
                                "threshold": None, "sample_count": 1}]} for _ in range(16)],
    }


def _canonical_bytes(document):
    return (json.dumps(document, ensure_ascii=False, sort_keys=True, allow_nan=False,
                       separators=(",", ":")) + "\n").encode("utf-8")


def _manual_path_score(max_samples, paths):
    """Independent normative arithmetic on hand-declared (depth, leaf n), no tree walk.

    Each call receives exactly sixteen literal paths, not product-derived nodes.
    NumPy's specified operation order is intentional; cross-platform last-bit
    portability of precomputed Windows literals is not assumed.
    """
    assert len(paths) == 16

    def correction(n):
        counts = np.asarray([n], dtype=np.int64)
        output = np.zeros(1, dtype=np.float64)
        if n == 2:
            output[:] = 1.0
        elif n > 2:
            output[:] = (2.0 * (np.log(counts - 1.0) + np.euler_gamma)
                         - 2.0 * (counts - 1.0) / counts)
        return output

    depth_sum = np.zeros(1, dtype=np.float64)
    for decision_depth, leaf_samples in paths:
        contribution = np.asarray([decision_depth], dtype=np.int64) + correction(leaf_samples) - 1.0
        depth_sum += contribution
    denominator = 16 * correction(max_samples)
    return float((2 ** (-np.divide(depth_sum, denominator, out=np.ones_like(depth_sum),
                                  where=denominator != 0)))[0])


def _snapshot(matrix):
    return (matrix.tobytes(order="A"), matrix.shape, matrix.strides, matrix.dtype,
            tuple(bool(matrix.flags[key]) for key in (
                "C_CONTIGUOUS", "F_CONTIGUOUS", "OWNDATA", "WRITEABLE", "ALIGNED", "WRITEBACKIFCOPY")))


def _roundtrip_score(api, state, matrix, monkeypatch):
    original_fields = asdict(state)
    original_matrix = _snapshot(matrix)
    reference_count = sys.getrefcount(matrix)
    floating_environment = np.geterr()
    with _pure_operation(monkeypatch):
        payload = api.encode_iforest_numeric_state(state)
        decoded = api.decode_iforest_numeric_state(payload)
        repeated = api.encode_iforest_numeric_state(decoded)
        scores = api.score_iforest_numeric_state(decoded, matrix)
    assert repeated == payload
    assert asdict(state) == original_fields == asdict(decoded)
    assert _snapshot(matrix) == original_matrix
    assert sys.getrefcount(matrix) == reference_count
    assert np.geterr() == floating_environment
    assert type(scores) is tuple and len(scores) == len(matrix)
    assert all(type(score) is float and np.isfinite(score) and 0.0 < score <= 1.0 for score in scores)
    return payload, decoded, scores


@pytest.mark.parametrize("width", [13, 26])
def test_canonical_manual_forest_roundtrips_then_scores_without_model_or_io(width, monkeypatch):
    api, _ = _api_and_manual()
    payload = _canonical_bytes(_canonical_document(width))
    matrix = np.zeros((3, width), dtype=np.float64)
    with _pure_operation(monkeypatch):
        state = api.decode_iforest_numeric_state(payload)
        repeated = api.encode_iforest_numeric_state(state)
        scores = api.score_iforest_numeric_state(state, matrix)
    assert repeated == payload
    assert scores == (0.5, 0.5, 0.5)
    with pytest.raises(FrozenInstanceError):
        state.max_samples = 2
    with pytest.raises(FrozenInstanceError):
        state.trees[0].nodes[0].sample_count = 2
    with pytest.raises(TypeError):
        state.feature_order[0] = 2
    assert api.encode_iforest_numeric_state(state) == payload


@pytest.mark.parametrize("width", [13, 26])
def test_distinct_tree_shapes_roundtrip_with_hand_declared_leaf_paths(width, monkeypatch):
    api, manual = _api_and_manual()
    root = manual(width=width, pattern="root_leaf", max_samples=4).trees[0]
    asymmetric = manual(width=width, pattern="asymmetric4", max_samples=4).trees[0]
    three = manual(width=width, pattern="three_leaf4", max_samples=4).trees[0]
    state = replace(manual(width=width, pattern="root_leaf", max_samples=4),
                    trees=(root, asymmetric, three, asymmetric) * 4)
    matrix = np.zeros((3, width), dtype=np.float64)
    matrix[:, 0] = (-1.0, 1.0, 3.0)
    # x=-1: all splits left; x=1: second split left; x=3: second split right.
    expected = tuple(_manual_path_score(4, paths * 4) for paths in (
        ((1, 4), (2, 1), (2, 1), (2, 1)),
        ((1, 4), (2, 3), (3, 1), (2, 3)),
        ((1, 4), (2, 3), (3, 2), (2, 3)),
    ))
    _, _, scores = _roundtrip_score(api, state, matrix, monkeypatch)
    assert scores == expected


def _asymmetric_threshold(api, manual, width, threshold):
    base = manual(width=width, pattern="asymmetric4", max_samples=4)
    tree = base.trees[0]
    root = replace(tree.nodes[0], feature=width - 1, threshold=threshold)
    return replace(base, trees=(api.IForestNumericTree((root, *tree.nodes[1:])),) * 16)


@pytest.mark.parametrize("width", [13, 26])
def test_nep50_double_threshold_and_f64_to_f32_rounding_change_the_observable_path(width, monkeypatch):
    api, manual = _api_and_manual()
    state = _asymmetric_threshold(api, manual, width, 1.0 - 2.0 ** -26)
    matrix = np.zeros((3, width), dtype=np.float64)
    matrix[:, -1] = (1.0, 1.0 - 2.0 ** -25, float(np.nextafter(np.float32(1), np.float32(0))))
    # First two round to x32=1 (> double threshold); third is the previous f32 (< t).
    expected = (_manual_path_score(4, ((2, 3),) * 16),
                _manual_path_score(4, ((2, 3),) * 16),
                _manual_path_score(4, ((2, 1),) * 16))
    _, _, scores = _roundtrip_score(api, state, matrix, monkeypatch)
    assert scores == expected
    assert scores[0] != scores[2]


@pytest.mark.parametrize("width", [13, 26])
def test_threshold_equality_routes_left_and_extreme_finite_threshold_stays_double(width, monkeypatch):
    api, manual = _api_and_manual()
    matrix = np.zeros((2, width), dtype=np.float32)
    matrix[:, -1] = (1.0, np.nextafter(np.float32(1), np.float32(2)))
    left = _manual_path_score(4, ((2, 1),) * 16)
    right = _manual_path_score(4, ((2, 3),) * 16)
    for threshold, expected in ((1.0, (left, right)),
                                (float(np.finfo(np.float64).max), (left, left)),
                                (-float(np.finfo(np.float64).max), (right, right))):
        state = _asymmetric_threshold(api, manual, width, threshold)
        _, _, scores = _roundtrip_score(api, state, matrix, monkeypatch)
        assert scores == expected


@pytest.mark.parametrize("width", [13, 26])
def test_fixed_tree_order_is_not_replaced_by_a_reduction_or_score_average(width, monkeypatch):
    api, manual = _api_and_manual()
    left_tree = _asymmetric_threshold(api, manual, width, 1.0).trees[0]
    right_tree = _asymmetric_threshold(api, manual, width, -1.0).trees[0]
    base = manual(width=width, pattern="root_leaf", max_samples=4)
    matrix = np.zeros((1, width), dtype=np.float64)
    cases = (
        ((left_tree,) * 8 + (right_tree,) * 8, ((2, 1),) * 8 + ((2, 3),) * 8),
        ((left_tree, right_tree) * 8, ((2, 1), (2, 3)) * 8),
    )
    actual = []
    for trees, paths in cases:
        _, _, scores = _roundtrip_score(api, replace(base, trees=trees), matrix, monkeypatch)
        assert scores == (_manual_path_score(4, paths),)
        actual.append(scores[0])
    # Last-bit separation occurs locally; strict formula equality above is portable
    # without assuming that every NumPy build must separate these two orders.
    if _manual_path_score(4, cases[0][1]) != _manual_path_score(4, cases[1][1]):
        assert actual[0] != actual[1]


@pytest.mark.parametrize("width", [13, 26])
def test_full_63_node_tree_preserves_depth_and_leaf_correction_through_codec(width, monkeypatch):
    api, manual = _api_and_manual()
    state = manual(width=width, pattern="balanced32", max_samples=32)
    matrix = np.zeros((6, width), dtype=np.float64)
    matrix[:, 0] = (-0.5, 0.5, 1.5, 15.5, 31.5, 33.0)
    # Every explicitly balanced route has root-inclusive depth6 and one sample.
    expected = (_manual_path_score(32, ((6, 1),) * 16),) * 6
    _, decoded, scores = _roundtrip_score(api, state, matrix, monkeypatch)
    assert len(decoded.trees[0].nodes) == 63
    assert scores == expected


@pytest.mark.parametrize("width", [13, 26])
@pytest.mark.parametrize("layout", ["readonly", "fortran", "slice"])
def test_legal_array_layout_is_not_mutated_or_retained(width, layout, monkeypatch):
    api, manual = _api_and_manual()
    state = manual(width=width, pattern="split2", max_samples=2)
    backing = np.arange(6 * width * 2, dtype=np.float64).reshape(6, width * 2)
    if layout == "slice":
        matrix = backing[::2, ::2]
    elif layout == "fortran":
        matrix = np.asfortranarray(backing[:3, :width])
    else:
        matrix = backing[:3, :width].copy()
        matrix.flags.writeable = False
    backing_snapshot = backing.tobytes()
    _, _, scores = _roundtrip_score(api, state, matrix, monkeypatch)
    assert scores == (0.5,) * 3
    assert backing.tobytes() == backing_snapshot


@pytest.mark.parametrize("width", [13, 26])
@pytest.mark.parametrize("rows", [0, 10000])
def test_empty_and_maximum_bounded_matrices_return_complete_immutable_tuples(width, rows, monkeypatch):
    api, manual = _api_and_manual()
    state = manual(width=width, pattern="root_leaf", max_samples=1)
    matrix = np.zeros((rows, width), dtype=np.float32)
    _, _, scores = _roundtrip_score(api, state, matrix, monkeypatch)
    assert scores == (0.5,) * rows


def _error_under_guard(api, monkeypatch, action):
    caught = None
    with _pure_operation(monkeypatch):
        try:
            action()
        except BaseException as error:
            caught = error
    assert type(caught) is api.IForestNumericStateError
    return str(caught)


@pytest.mark.parametrize("bad_kind,code", [
    ("list", "INVALID_MATRIX"), ("subclass", "INVALID_MATRIX"),
    ("int_dtype", "INVALID_MATRIX"), ("one_dimension", "INVALID_MATRIX"),
    ("wrong_width", "INVALID_MATRIX"), ("nan", "INVALID_MATRIX"),
    ("inf", "INVALID_MATRIX"), ("cast_overflow", "INVALID_MATRIX"),
    ("foreign_endian", "INVALID_MATRIX"), ("too_many_rows", "RESOURCE_LIMIT"),
])
def test_decoded_state_rejects_bad_matrix_without_partial_output_or_side_effects(bad_kind, code, monkeypatch):
    api, manual = _api_and_manual()
    state = api.decode_iforest_numeric_state(api.encode_iforest_numeric_state(manual()))
    matrix = np.zeros((2, 13), dtype=np.float64)
    if bad_kind == "list":
        matrix = matrix.tolist()
    elif bad_kind == "subclass":
        class ArraySubclass(np.ndarray):
            pass
        matrix = matrix.view(ArraySubclass)
    elif bad_kind == "int_dtype":
        matrix = matrix.astype(np.int64)
    elif bad_kind == "one_dimension":
        matrix = matrix[0]
    elif bad_kind == "wrong_width":
        matrix = np.zeros((2, 26), dtype=np.float64)
    elif bad_kind in {"nan", "inf", "cast_overflow"}:
        matrix[0, 0] = {"nan": float("nan"), "inf": float("inf"), "cast_overflow": np.finfo(np.float64).max}[bad_kind]
    elif bad_kind == "foreign_endian":
        matrix = matrix.astype(np.dtype(">f8" if np.little_endian else "<f8"))
    elif bad_kind == "too_many_rows":
        matrix = np.zeros((10001, 13), dtype=np.float32)
    before = _snapshot(matrix) if isinstance(matrix, np.ndarray) else [row[:] for row in matrix]
    with warnings.catch_warnings(record=True) as warnings_seen:
        actual = _error_under_guard(api, monkeypatch, lambda: api.score_iforest_numeric_state(state, matrix))
    assert actual == code
    assert warnings_seen == []
    assert (_snapshot(matrix) if isinstance(matrix, np.ndarray) else matrix) == before


@pytest.mark.parametrize("bad_kind,code", [
    ("duplicate_key", "INVALID_STATE"), ("whitespace", "INVALID_STATE"),
    ("invalid_utf8", "INVALID_STATE"), ("nonfinite", "INVALID_STATE"),
    ("semantic_count", "INVALID_STATE"), ("extra_field", "INVALID_STATE"),
    ("incompatible_version", "INCOMPATIBLE_STATE"), ("oversized", "RESOURCE_LIMIT"),
])
def test_bad_json_and_resealed_bad_state_are_rejected_before_any_matrix_work(bad_kind, code, monkeypatch):
    api, _ = _api_and_manual()
    document = _canonical_document(13)
    if bad_kind == "semantic_count":
        document["trees"][0]["nodes"][0]["sample_count"] = 2
    elif bad_kind == "extra_field":
        document["path"] = "not-a-path-entry"
    elif bad_kind == "incompatible_version":
        document["version"] = 2
    payload = _canonical_bytes(document)
    if bad_kind == "duplicate_key":
        payload = payload.replace(b'"version":1', b'"version":1,"version":1')
    elif bad_kind == "whitespace":
        payload = b" " + payload
    elif bad_kind == "invalid_utf8":
        payload = b"\xff\n"
    elif bad_kind == "nonfinite":
        payload = b"NaN\n"
    elif bad_kind == "oversized":
        payload = b" " * 262145
    original = payload
    assert _error_under_guard(api, monkeypatch, lambda: api.decode_iforest_numeric_state(payload)) == code
    assert payload == original


def test_wrong_state_precedes_bad_matrix_and_does_not_create_a_partial_tuple(monkeypatch):
    api, manual = _api_and_manual()
    state = replace(manual(), max_samples=True)
    assert _error_under_guard(api, monkeypatch, lambda: api.score_iforest_numeric_state(state, [])) == "INVALID_STATE"
    assert _error_under_guard(api, monkeypatch, lambda: api.score_iforest_numeric_state(None, [])) == "INVALID_STATE_ARGUMENTS"


def test_preexisting_model_module_is_allowed_but_operation_import_attempts_stay_forbidden(monkeypatch):
    # Preserve any module legitimately loaded by previous tests. The standalone
    # reproduction inserts only its own sentinel, never loads a model library.
    if "torch" not in sys.modules:
        monkeypatch.setitem(sys.modules, "torch", ModuleType("torch"))
    before = {name: id(module) for name, module in sys.modules.items()
              if name.split(".", 1)[0] in _MODEL_ROOTS}
    api, manual = _api_and_manual()
    _, _, scores = _roundtrip_score(api, manual(), np.zeros((1, 13)), monkeypatch)
    assert scores == (0.5,)
    for requested in ("torch", "torch.__numeric_state_unloaded_sentinel__"):
        with pytest.raises(AssertionError, match="forbidden side effect"):
            with _pure_operation(monkeypatch):
                builtins.__import__(requested)
    after = {name: id(module) for name, module in sys.modules.items()
             if name.split(".", 1)[0] in _MODEL_ROOTS}
    assert after == before


@pytest.mark.parametrize("requested", ["torch", "torch.__numeric_state_unloaded_sentinel__"])
def test_setup_rejects_fresh_and_cached_model_import_attempts(requested, monkeypatch):
    if "torch" not in sys.modules:
        monkeypatch.setitem(sys.modules, "torch", ModuleType("torch"))
    before = {name: id(module) for name, module in sys.modules.items()
              if name.split(".", 1)[0] in _MODEL_ROOTS}
    real_import_module = importlib.import_module

    def importing_entry(name, package=None):
        if name == "traffic_anomaly.iforest_numeric_state":
            builtins.__import__(requested)
        return real_import_module(name, package)

    monkeypatch.setattr(importlib, "import_module", importing_entry)
    with pytest.raises(AssertionError, match="setup attempted a forbidden model import"):
        _api_and_manual()
    after = {name: id(module) for name, module in sys.modules.items()
             if name.split(".", 1)[0] in _MODEL_ROOTS}
    assert after == before
