"""SYNTHETIC_ONLY: hand-authored schema and rows, never distribution evidence."""
import copy
import csv
from datetime import datetime, timedelta
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import warnings
import zipfile

try:
    from tools.data_audit.c17_improved import audit_csv, check_archive
except ModuleNotFoundError:
    audit_csv = check_archive = None


BASE = datetime(2017, 7, 3)


def stamp(minute, seconds=0):
    return (BASE + timedelta(minutes=minute, seconds=seconds)).strftime('%Y-%m-%d %H:%M:%S.%f')


def config():
    return {
        'schema': 'C17_IMPROVED_AUDIT_V1', 'identity': 'SYNTHETIC_ONLY',
        'columns': {'start': 's', 'duration': 'd', 'label': 'y', 'attempted': 'a'},
        'time': {'format': '%Y-%m-%d %H:%M:%S.%f', 'timezone': 'UTC',
                 'utc_evidence': 'SYNTHETIC_ONLY fixture definition',
                 'precision_model': 'TRUNCATION', 'precision_evidence': 'SYNTHETIC_ONLY known quanta',
                 'timestamp_precision_us': 1, 'duration_precision_us': 1,
                 'duration_unit': 'us', 'duration_unit_evidence': 'SYNTHETIC_ONLY'},
        'labels': {'normal': ['BENIGN'], 'attack': ['ATTACK'], 'attempted': ['Attempted'],
                   'attempted_empty': [''], 'attempted_categories': ['scan'],
                   'policy': {'status': 'AUDIT_ONLY', 'attempted': 'unknown'}},
        'segments': [{'id': 'train', 'role': 'train', 'start': stamp(0), 'end': stamp(40)},
                     {'id': 'calibration', 'role': 'calibration', 'start': stamp(40), 'end': stamp(80)},
                     {'id': 'test', 'role': 'test', 'start': stamp(80), 'end': stamp(120)}],
        'capture': [{'start': stamp(0), 'end': stamp(120), 'status': 'complete',
                     'evidence': 'SYNTHETIC_ONLY fixture definition'}],
        'empty_normal': [{'start': stamp(0), 'end': stamp(120),
                          'normal_evidence': 'SYNTHETIC_ONLY independent no-attack construction for empty minutes'}],
        'limits': {'max_total_input_bytes': 1000000, 'max_rows': 10000,
                   'max_minutes': 1000, 'max_field_chars': 1024, 'max_duration_seconds': 3600},
    }


ARCHIVE_LIMITS = {'max_archive_bytes': 1000000, 'max_members': 20,
                  'max_member_bytes': 10000, 'max_total_uncompressed_bytes': 20000,
                  'max_compression_ratio': 100}


class ImprovedAuditTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(callable(audit_csv), 'Offline improved auditor has not been implemented')
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def file(self, rows, name='fixture.csv', header=('s', 'd', 'y', 'a')):
        path = self.root / name
        with path.open('w', newline='', encoding='utf-8') as handle:
            writer = csv.writer(handle)
            writer.writerow(header)
            writer.writerows(rows)
        return path

    def audit(self, rows, cfg=None):
        return audit_csv([self.file(rows)], cfg or config())

    def test_mixed_minute_is_attack_and_attempted_unknown_never_normal(self):
        r = self.audit([(stamp(0), 1, 'BENIGN', ''), (stamp(0, 1), 1, 'ATTACK', ''),
                        (stamp(1), 1, 'Attempted', 'scan'), (stamp(2), 1, 'other', '')])
        s = r['segments'][0]['minutes']
        self.assertEqual((s['attack'], s['mixed'], s['attempted'], s['unknown']), (1, 1, 1, 2))
        self.assertEqual(s['normal'], 37)
        self.assertEqual(r['labels']['original'], {'BENIGN': 1, 'ATTACK': 1, 'Attempted': 1, 'other': 1})
        self.assertEqual(r['labels']['attempted_category'], {'': 3, 'scan': 1})
        self.assertEqual(r['identity'], 'SYNTHETIC_ONLY')
        self.assertEqual(r['real_training'], 'NOT_RUN')

    def test_attempted_candidate_policy_is_explicit_audit_only(self):
        cfg = config()
        cfg['labels']['policy']['attempted'] = 'normal'
        r = self.audit([(stamp(0), 1, 'Attempted', 'scan')], cfg)
        self.assertEqual(r['segments'][0]['minutes']['normal'], 40)
        self.assertEqual(r['label_policy'], {'status': 'AUDIT_ONLY', 'attempted': 'normal'})
        cfg['labels']['policy']['status'] = 'APPROVED'
        with self.assertRaisesRegex(ValueError, 'AUDIT_ONLY'):
            self.audit([], cfg)

    def test_end_proxy_buckets_cross_minute_flow_without_backfill(self):
        r = self.audit([(stamp(0, 59), 2000000, 'ATTACK', '')])
        s = r['segments'][0]
        self.assertEqual(s['minutes']['attack'], 1)
        self.assertEqual(s['minutes']['confirmed_empty'], 39)
        self.assertEqual(r['flow_events']['cross_minute'], 1)
        self.assertEqual(s['valid_intervals'], [{'start': stamp(0) + 'Z', 'end': stamp(40) + 'Z', 'minutes': 40}])
        self.assertEqual(s['history']['30']['normal_eligible'], 8)

    def test_cross_partition_and_long_flow_are_excluded_and_taint_destination(self):
        cfg = config()
        cfg['limits']['max_duration_seconds'] = 60
        r = self.audit([(stamp(39, 59), 2000000, 'BENIGN', ''),
                        (stamp(0), 61000000, 'BENIGN', '')], cfg)
        self.assertEqual(r['flows']['invalid'], 2)
        self.assertEqual(r['flows']['reasons'], {'cross_partition': 1, 'long_flow': 1})
        self.assertEqual(r['segments'][1]['minutes']['invalid'], 1)
        self.assertEqual(r['segments'][0]['minutes']['invalid'], 1)

    def test_capture_unknown_gap_and_confirmed_empty_are_distinct(self):
        cfg = config()
        cfg['capture'] = [{'start': stamp(0), 'end': stamp(1), 'status': 'complete', 'evidence': 'fixture'},
                          {'start': stamp(1), 'end': stamp(2), 'status': 'gap', 'evidence': 'fixture'}]
        r = self.audit([(stamp(2), 1, 'BENIGN', '')], cfg)
        s = r['segments'][0]['minutes']
        self.assertEqual((s['confirmed_empty'], s['gap'], s['capture_unknown'], s['normal']), (1, 1, 38, 1))
        self.assertEqual(s['unknown'], 39)

    def test_complete_capture_does_not_prove_empty_minutes_normal(self):
        cfg = config()
        cfg.pop('empty_normal')
        r = self.audit([], cfg)
        s = r['segments'][0]
        self.assertEqual((s['input_valid_minutes'], s['minutes']['confirmed_empty']), (40, 40))
        self.assertEqual((s['minutes']['normal'], s['minutes']['unknown']), (0, 40))
        self.assertEqual(s['history']['30']['valid'], 10)
        self.assertEqual(s['common_normal'], 0)
        self.assertIsNone(r['high_completion']['threshold'])
        self.assertIsNone(r['high_completion']['test_high_normal'])
        self.assertIsNone(r['high_completion']['test_ordinary_normal'])

    def test_empty_normal_interval_requires_its_own_normal_evidence(self):
        cfg = config()
        cfg['empty_normal'][0].pop('normal_evidence')
        with self.assertRaisesRegex(ValueError, 'empty_normal_evidence'):
            self.audit([], cfg)

    def test_flow_spanning_capture_gap_or_unknown_is_excluded_and_taints_completion_bucket(self):
        cfg = config()
        cfg['segments'] = [{'id': 'test', 'role': 'test', 'start': stamp(0), 'end': stamp(40)}]
        cfg['capture'] = [{'start': stamp(0), 'end': stamp(10), 'status': 'complete', 'evidence': 'fixture'},
                          {'start': stamp(10), 'end': stamp(11), 'status': 'gap', 'evidence': 'fixture'},
                          {'start': stamp(11), 'end': stamp(40), 'status': 'complete', 'evidence': 'fixture'}]
        for status in ('gap', 'unknown'):
            cfg['capture'][1]['status'] = status
            with self.subTest(status=status):
                r = self.audit([(stamp(9), 180000000, 'BENIGN', '')], cfg)
                self.assertEqual(r['flows']['valid'], 0)
                self.assertEqual(r['flows']['reasons'], {'cross_capture_boundary': 1})
                self.assertEqual(r['segments'][0]['minutes']['invalid'], 1)
                self.assertEqual(r['segments'][0]['input_valid_minutes'], 38)

    def test_adjacent_complete_capture_epochs_reset_history_and_reject_spanning_flow(self):
        cfg = config()
        cfg['capture'] = [{'start': stamp(0), 'end': stamp(20), 'status': 'complete', 'evidence': 'fixture A'},
                          {'start': stamp(20), 'end': stamp(120), 'status': 'complete', 'evidence': 'fixture B'}]
        r = self.audit([], cfg)
        self.assertEqual(r['segments'][0]['input_valid_minutes'], 40)
        self.assertEqual(r['segments'][0]['history']['15']['valid'], 10)
        self.assertEqual(r['segments'][0]['history']['30']['valid'], 0)
        self.assertEqual(len(r['segments'][0]['valid_intervals']), 2)
        r = self.audit([(stamp(19), 120000000, 'BENIGN', '')], cfg)
        self.assertEqual(r['flows']['reasons'], {'cross_capture_boundary': 1})

    def test_proven_continuous_capture_can_keep_history_across_midnight(self):
        cfg = config()
        cfg['segments'] = [{'id': 'night', 'role': 'test', 'start': '2017-07-03 23:40:00', 'end': '2017-07-04 00:50:00'}]
        cfg['capture'] = [{'start': '2017-07-03 23:40:00', 'end': '2017-07-04 00:50:00', 'status': 'complete', 'evidence': 'SYNTHETIC_ONLY continuous capture'}]
        cfg['empty_normal'] = [{'start': '2017-07-03 23:40:00', 'end': '2017-07-04 00:50:00', 'normal_evidence': 'SYNTHETIC_ONLY no-attack generation'}]
        r = self.audit([], cfg)
        self.assertEqual(r['segments'][0]['history']['30']['valid'], 40)
        self.assertEqual(r['segments'][0]['common_normal'], 40)

    def test_label_policy_extra_private_metadata_is_not_echoed(self):
        cfg = config()
        cfg['labels']['policy']['annotation'] = 'PRIVATE_METADATA_SENTINEL/do-not-export'
        r = self.audit([], cfg)
        self.assertNotIn('PRIVATE_METADATA_SENTINEL', json.dumps(r))
        self.assertEqual(r['label_policy'], {'status': 'AUDIT_ONLY', 'attempted': 'unknown'})

    def test_precision_crossing_bucket_is_invalid_and_not_zero_filled(self):
        cfg = config()
        cfg['time']['timestamp_precision_us'] = 1000000
        cfg['time']['format'] = '%Y-%m-%d %H:%M:%S'
        r = self.audit([('2017-07-03 00:00:59', 500000, 'BENIGN', '')], cfg)
        self.assertEqual(r['flows']['reasons'], {'precision_bucket_ambiguity': 1})
        self.assertEqual(r['segments'][0]['minutes']['invalid'], 2)

    def test_twelve_hour_format_requires_am_pm_and_duration_unit_is_explicit(self):
        cfg = config()
        cfg['time']['format'] = '%Y-%m-%d %I:%M:%S'
        with self.assertRaisesRegex(ValueError, 'AM_PM'):
            self.audit([], cfg)
        cfg['time']['format'] = '%Y-%m-%d %I:%M:%S %p'
        cfg['time']['timestamp_precision_us'] = 1000000
        r = self.audit([('2017-07-03 12:00:00 AM', 1, 'BENIGN', '')], cfg)
        self.assertEqual(r['flows']['valid'], 1)
        cfg['time']['duration_unit'] = 'guess'
        with self.assertRaisesRegex(ValueError, 'duration_unit'):
            self.audit([], cfg)

    def test_unit_mismatch_fails_safe_instead_of_inventing_conversion(self):
        cfg = config()
        cfg['time']['duration_unit'] = 's'
        r = self.audit([(stamp(0), 2000000, 'BENIGN', '')], cfg)
        self.assertEqual(r['flows']['valid'], 0)
        self.assertEqual(r['flows']['reasons']['long_flow'], 1)

    def test_attempted_category_contradictions_and_unknown_codes_remain_unknown(self):
        cfg = config()
        cfg['labels']['attempted_empty'] = ['-1']
        cfg['labels']['attempted_categories'] = ['0', '1', '2', '3', '4', '5', '6']
        cfg['labels']['policy']['attempted'] = 'normal'
        r = self.audit([(stamp(0), 1, 'BENIGN', '2'), (stamp(1), 1, 'Attempted', '-1'),
                        (stamp(2), 1, 'BENIGN', '99')], cfg)
        self.assertEqual(r['segments'][0]['minutes']['unknown'], 3)
        self.assertEqual(r['label_anomalies'], {'attempted_category_conflict': 2, 'unknown_attempted_category': 1})
        self.assertEqual(r['flows']['valid'], 3)

    def test_precision_partition_ambiguity_and_cross_day_are_tracked(self):
        cfg = config()
        cfg['time']['timestamp_precision_us'] = 1000000
        r = self.audit([(stamp(39, 59.5), 1, 'BENIGN', '')], cfg)
        self.assertIn('precision_partition_ambiguity', r['flows']['reasons'])
        cfg = config()
        cfg['segments'] = [{'id': 'night', 'role': 'test', 'start': '2017-07-03 23:59:00', 'end': '2017-07-04 00:02:00'}]
        cfg['capture'] = [{'start': '2017-07-03 23:59:00', 'end': '2017-07-04 00:02:00', 'status': 'complete', 'evidence': 'fixture'}]
        cfg['empty_normal'] = [{'start': '2017-07-03 23:59:00', 'end': '2017-07-04 00:02:00', 'normal_evidence': 'SYNTHETIC_ONLY empty intervals contain no attacks by construction'}]
        r = self.audit([('2017-07-03 23:59:59.000000', 2000000, 'BENIGN', '')], cfg)
        self.assertEqual(r['flow_events']['cross_day'], 1)
        self.assertEqual(r['days'][0]['day'], '2017-07-03')
        self.assertEqual(r['days'][1]['day'], '2017-07-04')
        self.assertEqual(r['days'][1]['minutes']['normal'], 2)

    def test_hostile_label_values_are_hashed_and_never_exported_verbatim(self):
        r = self.audit([(stamp(0), 1, '192.0.2.1', 'sensitive/value')])
        self.assertNotIn('192.0.2.1', json.dumps(r))
        self.assertNotIn('sensitive/value', json.dumps(r))

    def test_precision_model_and_evidence_are_explicit_and_unknown_rounding_is_rejected(self):
        for key, value in [('precision_model', None), ('precision_model', 'ROUNDED'), ('precision_evidence', '')]:
            cfg = config()
            cfg['time'][key] = value
            with self.subTest(key=key, value=value), self.assertRaisesRegex(ValueError, 'precision_model'):
                self.audit([], cfg)

    def test_attack_with_unknown_or_unresolved_attempted_is_unknown_but_input_stays_valid(self):
        for label, category in [('other', ''), ('Attempted', 'scan')]:
            r = self.audit([(stamp(0), 1, 'ATTACK', ''), (stamp(0, 1), 1, label, category)])
            m = r['segments'][0]['minutes']
            self.assertEqual((m['attack'], m['unknown'], m['attack_present'], m['label_incomplete']), (0, 1, 1, 1))
            self.assertEqual(r['segments'][0]['history']['30']['valid'], 10)

    def test_attack_label_with_attempted_code_is_conflict_even_under_normal_policy(self):
        cfg = config()
        cfg['labels']['policy']['attempted'] = 'normal'
        r = self.audit([(stamp(0), 1, 'ATTACK', 'scan')], cfg)
        m = r['segments'][0]['minutes']
        self.assertEqual((m['normal'], m['attack'], m['unknown'], m['attack_present']), (39, 0, 1, 1))
        self.assertEqual(r['label_anomalies'], {'attempted_category_conflict': 1})

    def test_row_minute_field_caps_and_numeric_protocol_bounds(self):
        for key, value in [('max_rows', 1), ('max_minutes', 1), ('max_field_chars', 5)]:
            cfg = config()
            cfg['limits'][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.audit([(stamp(0), 1, 'BENIGN', ''), (stamp(1), 1, 'BENIGN', '')], cfg)
        cfg = config()
        cfg['columns']['protocol'] = 'p'
        p = self.file([(stamp(0), 1, 'BENIGN', '', 256)], header=('s', 'd', 'y', 'a', 'p'))
        r = audit_csv([p], cfg)
        self.assertEqual(r['flows']['reasons'], {'invalid_protocol': 1})

    def test_history_warmup_common_valid_and_segment_reset(self):
        r = self.audit([])
        for segment in r['segments']:
            self.assertEqual(segment['history']['15']['valid'], 25)
            self.assertEqual(segment['history']['30']['valid'], 10)
            self.assertEqual(segment['common_valid'], 10)
            self.assertEqual(segment['common_normal'], 10)
        self.assertEqual(r['high_completion']['training_eligible'], 10)
        self.assertEqual(r['high_completion']['threshold'], 0.0)
        self.assertEqual(r['high_completion']['test_high_normal'], 0)
        self.assertEqual(r['high_completion']['unavailable_reason'], 'NO_TEST_MINUTES_STRICTLY_ABOVE_TRAIN_THRESHOLD')

    def test_invalid_minute_resets_history_without_crossing_capture_gap(self):
        cfg = config()
        cfg['capture'] = [{'start': stamp(0), 'end': stamp(20), 'status': 'complete', 'evidence': 'fixture'},
                          {'start': stamp(21), 'end': stamp(120), 'status': 'complete', 'evidence': 'fixture'}]
        r = self.audit([], cfg)
        self.assertEqual(r['segments'][0]['history']['15']['valid'], 9)
        self.assertEqual(r['segments'][0]['history']['30']['valid'], 0)
        self.assertIsNone(r['high_completion']['threshold'])
        self.assertEqual(r['high_completion']['unavailable_reason'], 'NO_TRAIN_COMMON_NORMAL_MINUTES')

    def test_frozen_train_linear_quantile_uses_common_normal_and_strict_test_exceedance(self):
        rows = []
        for minute, count in [(30, 1), (31, 2), (32, 3), (33, 4), (34, 5), (35, 6),
                              (36, 7), (37, 8), (38, 9), (39, 10), (110, 9), (111, 10), (112, 11)]:
            rows.extend((stamp(minute, i), 1, 'BENIGN', '') for i in range(count))
        r = self.audit(rows)
        self.assertAlmostEqual(r['high_completion']['threshold'], 9.1)
        self.assertEqual(r['high_completion']['test_normal'], 10)
        self.assertEqual(r['high_completion']['test_high_normal'], 2)
        self.assertEqual(r['high_completion']['test_ordinary_normal'], 8)
        self.assertEqual(r['high_completion']['high_intervals'][0]['minutes'], 2)

    def test_duplicate_across_files_excludes_both_and_tracks_out_of_order(self):
        a = self.file([(stamp(2), 1, 'BENIGN', ''), (stamp(1), 1, 'BENIGN', '')], 'one.csv')
        b = self.file([(stamp(2), 1, 'BENIGN', '')], 'two.csv')
        r = audit_csv([a, b], config())
        self.assertEqual(r['flows']['raw'], 3)
        self.assertEqual(r['flows']['valid'], 1)
        self.assertEqual(r['flows']['reasons']['duplicate_record'], 2)
        self.assertEqual(r['flow_events']['duplicate_cross_file_groups'], 1)
        self.assertEqual(r['flow_events']['order_inversions'], 1)

    def test_unknown_labels_do_not_reset_input_history_and_attack_presence_survives(self):
        r = self.audit([(stamp(0), 1, 'other', ''), (stamp(0, 1), 1, 'ATTACK', '')])
        s = r['segments'][0]
        self.assertEqual(s['history']['30']['valid'], 10)
        self.assertEqual(s['minutes']['attack'], 0)
        self.assertEqual(s['minutes']['unknown'], 1)
        self.assertEqual(s['minutes']['label_incomplete'], 1)
        self.assertEqual(s['minutes']['attack_present'], 1)

    def test_repeated_explicit_flow_identity_never_silently_merges_partial_records(self):
        cfg = config()
        cfg['identity_columns'] = ['id']
        a = self.file([(stamp(1), 1, 'BENIGN', '', 'synthetic-flow')], 'one.csv', ('s', 'd', 'y', 'a', 'id'))
        b = self.file([(stamp(2), 1, 'BENIGN', '', 'synthetic-flow')], 'two.csv', ('s', 'd', 'y', 'a', 'id'))
        r = audit_csv([a, b], cfg)
        self.assertEqual(r['flows']['reasons'], {'conflicting_flow_identity': 2})
        self.assertEqual(r['flow_events']['cross_file_identity_groups'], 1)

    def test_bad_time_taints_all_candidate_minutes_instead_of_creating_empty_normal(self):
        r = self.audit([('bad-time', 1, 'BENIGN', '')])
        self.assertEqual(r['flows']['reasons'], {'invalid_timestamp': 1})
        self.assertEqual(r['segments'][0]['minutes']['normal'], 0)
        self.assertEqual(r['segments'][0]['minutes']['invalid'], 40)

    def test_nonfinite_negative_and_fractional_count_fields_are_invalid(self):
        cfg = config()
        cfg['columns']['fwd_packets'] = 'p'
        rows = [(stamp(0), 'NaN', 'BENIGN', '', 1), (stamp(1), -1, 'BENIGN', '', 1),
                (stamp(2), 1, 'BENIGN', '', '0.5')]
        p = self.file(rows, header=('s', 'd', 'y', 'a', 'p'))
        r = audit_csv([p], cfg)
        self.assertEqual(r['flows']['invalid'], 3)
        self.assertEqual(r['flows']['reasons'], {'invalid_duration': 2, 'invalid_fwd_packets': 1})
        self.assertEqual(r['segments'][0]['minutes']['normal'], 0)

    def test_schema_utc_evidence_and_capture_masks_are_never_guessed(self):
        for mutate, error in [(lambda c: c['time'].pop('utc_evidence'), 'utc_evidence'),
                              (lambda c: c['columns'].pop('start'), 'columns'),
                              (lambda c: c['segments'][0].update(end=stamp(0)), 'segment'),
                              (lambda c: c['capture'].append(copy.deepcopy(c['capture'][0])), 'capture_overlap')]:
            cfg = config()
            mutate(cfg)
            with self.subTest(error=error), self.assertRaisesRegex(ValueError, error):
                self.audit([], cfg)
        cfg = config()
        cfg['capture'] = []
        r = self.audit([(stamp(0), 1, 'BENIGN', '')], cfg)
        self.assertEqual(r['segments'][0]['minutes']['normal'], 0)

    def test_candidate_roles_cannot_place_training_after_test_or_calibration(self):
        cfg = config()
        cfg['segments'][0]['role'] = 'test'
        cfg['segments'][2]['role'] = 'train'
        with self.assertRaisesRegex(ValueError, 'segment_role_order'):
            self.audit([], cfg)

    def test_duplicate_header_ragged_rows_and_unmapped_columns_fail_closed(self):
        for content in ['s,d,y,a,y\n', 's,d,y,a\na,b\n', 's,d,z,a\n']:
            p = self.root / 'bad.csv'
            p.write_text(content, encoding='utf-8')
            with self.subTest(content=content), self.assertRaises(ValueError):
                audit_csv([p], config())

    def test_report_contains_no_paths_ips_or_row_details(self):
        p = self.file([(stamp(0), 1, 'BENIGN', '', '192.0.2.1')], header=('s', 'd', 'y', 'a', 'ip'))
        r = audit_csv([p], config())
        text = json.dumps(r)
        self.assertNotIn(str(self.root), text)
        self.assertNotIn('192.0.2.1', text)
        self.assertNotIn('rows', r)
        self.assertEqual(r['files'][0]['file_id'], 'input_1')
        self.assertEqual(r['days'][0]['raw'], 1)

    def test_partial_schema_never_claims_verified_model_common_supply(self):
        r = self.audit([])
        self.assertEqual(r['segments'][0]['common_valid'], 10)
        self.assertEqual(r['model_common_valid_minutes'], {'IF': None, 'current_AE': None,
                                                          'history_AE_H15': None, 'history_AE_H30': None})
        self.assertIn('CONFIGURED_FIELDS_ONLY', r['common_valid_scope'])
        self.assertEqual(r['protocol_semantics'], 'NOT_VERIFIED_NUMERIC_RANGE_ONLY')

    def test_cli_refuses_existing_output_and_input_alias(self):
        p = self.file([])
        c = self.root / 'config.json'
        c.write_text(json.dumps(config()), encoding='utf-8')
        script = Path(__file__).resolve().parents[2] / 'tools/data_audit/c17_improved.py'
        output = self.root / 'report.json'
        args = [sys.executable, str(script), '--input', str(p), '--config', str(c), '--output', str(output)]
        first = subprocess.run(args, capture_output=True, text=True)
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(json.loads(output.read_text())['identity'], 'SYNTHETIC_ONLY')
        repeat = subprocess.run(args, capture_output=True, text=True)
        self.assertNotEqual(repeat.returncode, 0)
        self.assertIn('output_exists_or_aliases_input', repeat.stderr)
        args[-1] = str(p)
        self.assertNotEqual(subprocess.run(args, capture_output=True).returncode, 0)
        self.assertEqual(p.read_text(), 's,d,y,a\n')

    def test_csv_resource_limits_are_enforced_before_aggregating(self):
        cfg = config()
        cfg['limits']['max_total_input_bytes'] = 2
        with self.assertRaisesRegex(ValueError, 'input_bytes'):
            self.audit([], cfg)

    def test_cli_fatal_reasons_distinguish_bad_json_from_output_conflict_without_paths(self):
        p = self.file([])
        c = self.root / 'bad-config.json'
        c.write_text('{bad JSON', encoding='utf-8')
        script = Path(__file__).resolve().parents[2] / 'tools/data_audit/c17_improved.py'
        output = self.root / 'new-output.json'
        args = [sys.executable, str(script), '--input', str(p), '--config', str(c), '--output', str(output)]
        result = subprocess.run(args, capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn('INVALID_JSON', result.stderr)
        self.assertNotIn(str(self.root), result.stderr)
        self.assertFalse(output.exists())

    def test_cli_untrusted_huge_limits_and_nonobject_config_fail_without_traceback(self):
        p = self.file([])
        script = Path(__file__).resolve().parents[2] / 'tools/data_audit/c17_improved.py'
        cfg = config()
        cfg['limits']['max_duration_seconds'] = 10 ** 400
        for value in [cfg, None, []]:
            c = self.root / 'bad-config.json'
            c.write_text(json.dumps(value), encoding='utf-8')
            output = self.root / 'new-output.json'
            args = [sys.executable, str(script), '--input', str(p), '--config', str(c), '--output', str(output)]
            result = subprocess.run(args, capture_output=True, text=True, encoding='utf-8', errors='replace')
            self.assertEqual(result.returncode, 2)
            self.assertIn('AUDIT_FAILED_', result.stderr)
            self.assertNotIn('Traceback', result.stderr)
            self.assertNotIn(str(self.root), result.stderr)
            self.assertFalse(output.exists())


class ArchiveSafetyTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(callable(check_archive), 'Archive central-directory checker has not been implemented')
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'fixture.zip'

    def archive(self, entries, compression=zipfile.ZIP_STORED):
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', UserWarning)
            with zipfile.ZipFile(self.path, 'w', compression=compression) as archive:
                for name, data in entries:
                    archive.writestr(name, data)

    def test_central_directory_only_never_opens_member_content(self):
        self.archive([('safe.csv', b'SYNTHETIC_ONLY')])
        # A bad member CRC would fail if the checker opened member data.
        payload = bytearray(self.path.read_bytes())
        start = payload.index(b'SYNTHETIC_ONLY')
        payload[start] ^= 1
        self.path.write_bytes(payload)
        r = check_archive(self.path, ARCHIVE_LIMITS)
        self.assertEqual(r['members'], 1)
        self.assertEqual(r['total_uncompressed_bytes'], 14)
        self.assertFalse(r['extracted'])
        self.assertFalse(r['member_contents_read'])
        self.assertEqual(r.get('identity'), 'UNCLASSIFIED_LOCAL_ARCHIVE')

    def test_path_traversal_absolute_drive_backslash_and_ambiguous_paths_are_rejected(self):
        for name in ['../evil', '/evil', 'C:/evil', 'dir\\evil', 'a/../b', './a', 'a//b']:
            self.archive([(name, b'x')])
            if '\\' in name:
                # Windows ZipInfo normalizes separators while creating fixtures.
                self.path.write_bytes(self.path.read_bytes().replace(b'dir/evil', b'dir\\evil'))
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, 'member_path'):
                check_archive(self.path, ARCHIVE_LIMITS)

    def test_duplicate_case_collision_and_symlink_are_rejected(self):
        for entries in [[('a.csv', b'x'), ('a.csv', b'y')], [('A.csv', b'x'), ('a.csv', b'y')]]:
            self.archive(entries)
            with self.assertRaisesRegex(ValueError, 'collision'):
                check_archive(self.path, ARCHIVE_LIMITS)
        link = zipfile.ZipInfo('link')
        link.create_system = 3
        link.external_attr = 0o120777 << 16
        self.archive([(link, b'target')])
        with self.assertRaisesRegex(ValueError, 'member_type'):
            check_archive(self.path, ARCHIVE_LIMITS)

    def test_member_count_single_total_ratio_archive_bytes_are_hard_limits(self):
        self.archive([('a', b'x' * 500), ('b', b'y' * 500)], zipfile.ZIP_DEFLATED)
        for key, value in [('max_members', 1), ('max_member_bytes', 499),
                           ('max_total_uncompressed_bytes', 999), ('max_compression_ratio', 2),
                           ('max_archive_bytes', 10)]:
            limits = dict(ARCHIVE_LIMITS, **{key: value})
            with self.subTest(key=key), self.assertRaises(ValueError):
                check_archive(self.path, limits)

    def test_file_directory_prefix_collision_and_zero_compressed_nonempty_member_fail(self):
        self.archive([('a', b'x'), ('a/b', b'x')])
        with self.assertRaisesRegex(ValueError, 'collision'):
            check_archive(self.path, ARCHIVE_LIMITS)
        self.archive([('a', b'x')])
        payload = bytearray(self.path.read_bytes())
        offset = payload.index(b'PK\x01\x02')
        struct.pack_into('<L', payload, offset + 20, 0)
        self.path.write_bytes(payload)
        with self.assertRaisesRegex(ValueError, 'compressed_size'):
            check_archive(self.path, ARCHIVE_LIMITS)

    def test_windows_reserved_names_trailing_space_and_missing_limits_are_rejected(self):
        for name in ['CON.csv', 'a./b', 'a /b', 'a//', 'aux/data']:
            self.archive([(name, b'x')])
            with self.subTest(name=name), self.assertRaises(ValueError):
                check_archive(self.path, ARCHIVE_LIMITS)
        self.archive([('safe.csv', b'x')])
        with self.assertRaises(ValueError):
            check_archive(self.path, {})

    def test_encryption_and_unsupported_compression_fail_without_opening_members(self):
        self.archive([('a', b'x')])
        original = self.path.read_bytes()
        offset = original.index(b'PK\x01\x02')
        for relative, value in [(8, 1), (10, 99)]:
            payload = bytearray(original)
            struct.pack_into('<H', payload, offset + relative, value)
            self.path.write_bytes(payload)
            with self.subTest(relative=relative), self.assertRaises(ValueError):
                check_archive(self.path, ARCHIVE_LIMITS)

    def test_forged_eocd_count_is_rejected_before_bulk_directory_parse(self):
        self.archive([(f'f{i}', b'x') for i in range(1000)])
        payload = bytearray(self.path.read_bytes())
        offset = payload.rindex(b'PK\x05\x06')
        struct.pack_into('<HH', payload, offset + 8, 1, 1)
        self.path.write_bytes(payload)
        limits = dict(ARCHIVE_LIMITS, max_members=1)
        with patch('tools.data_audit.c17_improved.zipfile.ZipFile', side_effect=AssertionError('bulk parse reached')):
            with self.assertRaisesRegex(ValueError, 'max_members|member_count_mismatch|directory_bytes'):
                check_archive(self.path, limits)

    def test_archive_extra_private_metadata_is_not_echoed(self):
        self.archive([('safe.csv', b'x')])
        limits = dict(ARCHIVE_LIMITS, annotation='PRIVATE_METADATA_SENTINEL/do-not-export')
        r = check_archive(self.path, limits)
        self.assertNotIn('PRIVATE_METADATA_SENTINEL', json.dumps(r))
        self.assertEqual(r['limits'], ARCHIVE_LIMITS)

    def test_cli_unsupported_zip_version_and_huge_ratio_fail_without_traceback(self):
        self.archive([('safe.csv', b'x')])
        payload = bytearray(self.path.read_bytes())
        offset = payload.index(b'PK\x01\x02')
        struct.pack_into('<H', payload, offset + 6, 99)
        self.path.write_bytes(payload)
        script = Path(__file__).resolve().parents[2] / 'tools/data_audit/c17_improved.py'
        for ratio in [100, 10 ** 400]:
            limits = dict(ARCHIVE_LIMITS, max_compression_ratio=ratio)
            cfg = self.path.parent / 'config.json'
            cfg.write_text(json.dumps({'identity': 'SYNTHETIC_ONLY', 'archive_limits': limits}), encoding='utf-8')
            output = self.path.parent / 'new-output.json'
            args = [sys.executable, str(script), '--archive-check', str(self.path), '--config', str(cfg), '--output', str(output)]
            result = subprocess.run(args, capture_output=True, text=True, encoding='utf-8', errors='replace')
            self.assertEqual(result.returncode, 2)
            self.assertNotIn('Traceback', result.stderr)
            self.assertNotIn(str(self.path.parent), result.stderr)
            self.assertIn('AUDIT_FAILED_', result.stderr)
            self.assertFalse(output.exists())


if __name__ == '__main__':
    unittest.main()
