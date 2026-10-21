import numpy as np
import pytest
from .conftest import write_csv
from traffic_anomaly.data.reader import load_minutes, load_labels
from traffic_anomaly.data.audit import audit_dataset

def test_sort_deduplicate_and_gap_without_zero_fill(tmp_path, schema):
    p = write_csv(tmp_path / "minutes.csv", [("2026-01-01T00:03:00Z", 3, {}),
        ("2026-01-01T00:00:00Z", 1, {}), ("2026-01-01T00:00:00Z", 1, {})])
    b = load_minutes(p, schema)
    assert b.features[:, 0].tolist() == [1, 3]
    assert b.segment_ids.tolist() == [0, 1]
    r = audit_dataset(p, schema)
    assert r.evidence_kind == "SYNTHETIC_ONLY"
    assert any("duplicate" in f for f in r.findings)
    assert any("gap" in f for f in r.findings)
    assert len(r.source_sha256) == 64

def test_conflicting_minute_is_invalid_and_labels_not_invented(tmp_path, schema):
    p = write_csv(tmp_path / "conflict.csv", [("2026-01-01T00:00:00Z", 1, {}),
        ("2026-01-01T00:00:00Z", 2, {"dos": 1})])
    b = load_minutes(p, schema)
    assert b.row_valid.tolist() == [False]
    assert not audit_dataset(p, schema).passed
    with pytest.raises(ValueError, match="conflict"):
        load_labels(p, schema)

@pytest.mark.parametrize("value", ["NaN", "inf", -1])
def test_invalid_counts_reset_segments(tmp_path, schema, value):
    p = write_csv(tmp_path / "bad.csv", [("2026-01-01T00:00:00Z", 1, {}),
        ("2026-01-01T00:01:00Z", value, {}), ("2026-01-01T00:02:00Z", 2, {})])
    b = load_minutes(p, schema)
    assert b.row_valid.tolist() == [True, False, True]
    assert b.segment_ids.tolist() == [0, 1, 2]
    assert not audit_dataset(p, schema).passed

def test_unknown_timezone_and_nonminute_rejected(tmp_path, schema):
    p = write_csv(tmp_path / "time.csv", [("2026-01-01T00:00:30Z", 1, {})])
    with pytest.raises(ValueError, match="minute"):
        load_minutes(p, schema)
    p = write_csv(p, [("2026-01-01T00:00:00", 1, {})])
    with pytest.raises(ValueError, match="timezone"):
        load_minutes(p, schema.model_copy(update={"source_timezone": "unknown"}))

def test_missing_columns_or_fractional_labels_rejected(tmp_path, schema):
    p = write_csv(tmp_path / "labels.csv", [("2026-01-01T00:00:00Z", 1, {"dos": 0.5})])
    with pytest.raises(ValueError, match="label"):
        load_labels(p, schema)
    p.write_text("timestamp,value\n2026-01-01T00:00:00Z,1\n", encoding="utf-8")
    with pytest.raises(ValueError, match="columns"):
        load_minutes(p, schema)

def test_nonzero_submicrosecond_timestamp_cannot_be_truncated(tmp_path, schema):
    p = write_csv(tmp_path / 'precision.csv', [('2026-01-01T00:00:00.000000001Z', 1, {})])
    with pytest.raises(ValueError, match='minute'):
        load_minutes(p, schema)
    assert not audit_dataset(p, schema).passed

def test_equivalent_explicit_offsets_deduplicate_by_instant(tmp_path, schema):
    p = write_csv(tmp_path / 'offsets.csv', [('2026-01-01T00:00:00Z', 1, {}),
        ('2026-01-01T01:00:00+01:00', 1, {})])
    b = load_minutes(p, schema)
    assert len(b.timestamps) == 1 and b.row_valid.tolist() == [True]
    assert load_labels(p, schema).labels['dos'].tolist() == [0]
    assert audit_dataset(p, schema).passed

def test_audit_retains_original_order_before_sorting(tmp_path, schema):
    p = write_csv(tmp_path / 'order.csv', [
        ('2026-01-01T00:02:00Z', 1, {}), ('2026-01-01T00:00:00Z', 1, {}),
        ('2026-01-01T00:01:00Z', 1, {}), ('2026-01-01T00:00:00Z', 1, {})])
    assert 'original_reverse_steps=2' in audit_dataset(p, schema).findings

def test_source_outside_ns_range_fails_before_grouping(tmp_path, schema):
    from traffic_anomaly.data.reader import read_rows
    p = write_csv(tmp_path / 'range.csv', [('2500-01-01T00:00:00Z', 1, {})])
    with pytest.raises(ValueError, match='range'):
        read_rows(p, schema)
