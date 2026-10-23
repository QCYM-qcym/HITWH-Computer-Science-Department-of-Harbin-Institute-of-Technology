"""SYNTHETIC_ONLY streaming payload boundary tests; no source dataset values."""
import csv
from contextlib import closing
from datetime import datetime, timedelta
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

try:
    from tools.data_audit.c17_payload import profile_csv
    from tools.data_audit import c17_payload as payload
    audit_minutes = getattr(payload, 'audit_minutes', None)
except ModuleNotFoundError:
    profile_csv = audit_minutes = None


HEADER = ['s', 'd', 'y', 'a', 'p', 'fp', 'bp', 'fl', 'bl', 'extra', 'src']


def config():
    return {'identity': 'SYNTHETIC_ONLY', 'expected_header': HEADER,
            'numeric_columns': ['d', 'p', 'fp', 'bp', 'fl', 'bl', 'extra'],
            'columns': {'start': 's', 'duration': 'd', 'label': 'y', 'attempted': 'a',
                        'protocol': 'p', 'fwd_packets': 'fp', 'bwd_packets': 'bp',
                        'fwd_length': 'fl', 'bwd_length': 'bl'},
            'time': {'formats': ['%Y-%m-%d %H:%M:%S.%f', '%Y-%m-%d %H:%M:%S'], 'duration_unit': 'us'},
            'limits': {'max_total_input_bytes': 1000000, 'max_rows': 10000, 'max_days': 7,
                       'max_fields': 100, 'max_field_chars': 2048, 'max_label_values': 100,
                       'max_category_values': 32, 'max_minutes': 10080,
                       'index_max_bytes': 1048576, 'audit_max_bytes': 2097152, 'max_duration_seconds': 86400}}


def row(clock='2017-07-03 00:00:00.000000', **changes):
    values = dict(zip(HEADER, [clock, '1', 'BENIGN', '-1', '6', '1', '0', '4', '0', '3', '192.0.2.1']))
    values.update(changes)
    return [values[k] for k in HEADER]


def minute_config():
    cfg = config()
    cfg['supported_protocols'] = [1, 2, 6, 17, 132]
    cfg['labels'] = {'normal': ['BENIGN'], 'attack': ['ATTACK'], 'attempted': ['ATTACK - Attempted'],
                     'attempted_empty': ['-1'], 'attempted_categories': ['0', '1', '2', '3', '4', '5', '6'],
                     'policy': {'status': 'AUDIT_ONLY', 'attempted': 'unknown'}}
    cfg['candidate_registration'] = {'status': 'AUDIT_CANDIDATE_ONLY_NOT_APPROVED_PROTOCOL',
        'label_values_seen_before_registration': False, 'model_results_seen': False,
        'segments': [{'id': 'train', 'role': 'train', 'start': '2017-07-03 00:00:00', 'end': '2017-07-03 00:40:00'},
                     {'id': 'validation', 'role': 'validation', 'start': '2017-07-03 00:40:00', 'end': '2017-07-03 01:20:00'},
                     {'id': 'test', 'role': 'test', 'start': '2017-07-03 01:20:00', 'end': '2017-07-03 02:00:00'}]}
    return cfg


def clock(minute):
    return (datetime(2017, 7, 3) + timedelta(minutes=minute)).strftime('%Y-%m-%d %H:%M:%S.%f')


class PayloadProfileTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(callable(profile_csv), 'Streaming profile has not been implemented')
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.audit_dir = self.root / 'audit'
        self.audit_dir.mkdir()

    def file(self, rows, name='one.csv', header=HEADER):
        path = self.root / name
        with path.open('w', newline='', encoding='utf-8') as f:
            w = csv.writer(f); w.writerow(header); w.writerows(rows)
        return path

    def test_full_fields_missing_nonfinite_and_g12_invalid_are_separate(self):
        p = self.file([row(extra=''), row('2017-07-03 00:01:00', extra='Infinity'),
                       row('2017-07-03 00:02:00', fp='-1'), row('2017-07-03 00:03:00', bl='0.5')])
        r = profile_csv([p], config(), self.audit_dir)
        f = r['files'][0]
        self.assertEqual(f['rows'], 4)
        self.assertEqual(f['fields']['extra']['missing'], 1)
        self.assertEqual(f['fields']['extra']['nonfinite'], 1)
        self.assertEqual(f['g12_invalid'], {'fwd_packets': 1, 'bwd_length': 1})
        self.assertEqual(f['source_field_issue_rows'], 2)
        self.assertEqual(f['g12_valid_rows'], 2)
        self.assertEqual(f['g12_valid_with_other_field_issue_rows'], 2)
        self.assertEqual(r['identity'], 'SYNTHETIC_ONLY')
        self.assertEqual(r['minute_audit'], 'NOT_RUN')

    def test_exact_duplicate_index_counts_all_copies_and_cross_file_groups(self):
        a = self.file([row(), row('2017-07-03 00:01:00')])
        b = self.file([row()], 'two.csv')
        r = profile_csv([a, b], config(), self.audit_dir)
        self.assertEqual(r['duplicates'], {'unique_rows': 2, 'groups': 1, 'rows_in_groups': 2, 'cross_file_groups': 1})
        with closing(sqlite3.connect(self.audit_dir / 'profile-index.sqlite3')) as db:
            names = [v[1] for v in db.execute('PRAGMA table_info(fingerprints)')]
            self.assertEqual(names, ['digest', 'n', 'first_file', 'cross_file'])
        self.assertNotIn('192.0.2.1', json.dumps(r))
        self.assertNotIn(str(self.root), json.dumps(r))

    def test_bad_time_is_counted_without_implying_coverage_or_utc(self):
        r = profile_csv([self.file([row('bad-clock'), row()])], config(), self.audit_dir)
        self.assertEqual(r['files'][0]['time']['invalid'], 1)
        self.assertEqual(r['files'][0]['time']['parsed'], 1)
        self.assertEqual(r['time_semantics'], 'SOURCE_CLOCK_ONLY_TIMEZONE_AND_RELEASE_BINDING_NOT_CERTIFIED')
        self.assertEqual(r['real_training'], 'NOT_RUN')

    def test_all_source_labels_and_attempted_categories_aggregate_verbatim(self):
        r = profile_csv([self.file([row(), row(y='Attack - Attempted', a='2'), row(y='unknown')])], config(), self.audit_dir)
        self.assertEqual(r['labels'], {'BENIGN': 1, 'Attack - Attempted': 1, 'unknown': 1})
        self.assertEqual(r['attempted_categories'], {'-1': 2, '2': 1})

    def test_caps_fail_instead_of_returning_partial_full_audit(self):
        for key, value in [('max_rows', 1), ('max_total_input_bytes', 1), ('max_label_values', 1),
                           ('max_category_values', 1), ('max_field_chars', 2)]:
            cfg = config(); cfg['limits'][key] = value
            directory = self.audit_dir / key; directory.mkdir()
            with self.subTest(key=key), self.assertRaises(ValueError):
                profile_csv([self.file([row(), row(y='other', a='2')])], cfg, directory)

    def test_duration_over_one_day_is_fatal_and_negative_duration_is_reported(self):
        with self.assertRaisesRegex(ValueError, 'duration_cap'):
            profile_csv([self.file([row(d='86400000001')])], config(), self.audit_dir)
        other = self.audit_dir / 'negative'; other.mkdir()
        r = profile_csv([self.file([row(d='-1')])], config(), other)
        self.assertEqual(r['files'][0]['g12_invalid'], {'duration': 1})

    def test_index_file_is_new_and_hard_page_budget_is_enforced(self):
        cfg = config(); cfg['limits']['index_max_bytes'] = 12288
        p = self.file([row(f'2017-07-03 00:00:00.{i:06d}') for i in range(300)])
        with self.assertRaisesRegex(ValueError, 'index_byte_cap'):
            profile_csv([p], cfg, self.audit_dir)
        self.assertLessEqual((self.audit_dir / 'profile-index.sqlite3').stat().st_size, 12288)
        with self.assertRaisesRegex(ValueError, 'index_exists'):
            profile_csv([p], config(), self.audit_dir)

    def test_unknown_extra_metadata_is_not_echoed(self):
        cfg = config(); cfg['annotation'] = 'PRIVATE_SENTINEL/do-not-export'
        cfg['limits']['annotation'] = 'PRIVATE_SENTINEL/do-not-export'
        r = profile_csv([self.file([row()])], cfg, self.audit_dir)
        self.assertNotIn('PRIVATE_SENTINEL', json.dumps(r))

    def test_wrong_or_duplicate_header_and_ragged_record_are_rejected(self):
        for header, values in [(HEADER[:-1], row()[:-1]), (HEADER + ['s'], row() + ['x']), (HEADER, row()[:-1])]:
            directory = self.audit_dir / str(len(list(self.audit_dir.iterdir()))); directory.mkdir()
            with self.subTest(header=header), self.assertRaises(ValueError):
                profile_csv([self.file([values], header=header)], config(), directory)

    def test_days_and_minute_cardinality_are_bounded(self):
        cfg = config(); cfg['limits']['max_days'] = 1
        with self.assertRaisesRegex(ValueError, 'max_days'):
            profile_csv([self.file([row(), row('2017-07-04 00:00:00')])], cfg, self.audit_dir)

    def test_audit_budget_cannot_be_exceeded_before_post_write_check(self):
        cfg = config(); cfg['limits']['audit_max_bytes'] = 8192
        p = self.file([row(f'2017-07-03 00:00:00.{i:06d}') for i in range(300)])
        with self.assertRaises(ValueError):
            profile_csv([p], cfg, self.audit_dir)
        self.assertLessEqual(sum(v.stat().st_size for v in self.audit_dir.iterdir()), 8192)

    def minute_audit(self, rows, cfg=None):
        self.assertTrue(callable(audit_minutes), 'Second streaming pass has not been implemented')
        cfg = cfg or minute_config()
        path = self.file(rows)
        profile_csv([path], cfg, self.audit_dir)
        return audit_minutes([path], cfg, self.audit_dir)

    def test_three_label_policies_and_strict_unknown_stay_separate(self):
        rows = [row(clock(i)) for i in range(120)]
        rows[1] = row(clock(1), y='ATTACK - Attempted', a='2')
        rows[2] = row(clock(2), y='unknown')
        rows.append(row('2017-07-03 00:00:01.000000', y='ATTACK'))
        r = self.minute_audit(rows)
        self.assertIsNone(r['strict']['actual_input_valid_minutes'])
        self.assertEqual(r['strict']['certified_input_valid_minutes'], 0)
        for policy, expected in [('P_U', (37, 1, 2)), ('P_B', (38, 1, 1)), ('P_A', (37, 2, 1))]:
            s = r['conditional'][policy]['segments'][0]
            self.assertEqual((s['normal'], s['attack'], s['unknown']), expected)
            self.assertEqual(s['history']['30']['input_valid'], 10)
            self.assertIsNone(r['model_common_valid_minutes'])

    def test_unused_rate_nonfinite_does_not_drop_a_g12_valid_flow(self):
        rows = [row(clock(i)) for i in range(120)]
        rows[0] = row(clock(0), extra='Infinity')
        r = self.minute_audit(rows)
        self.assertEqual(r['conditional']['P_U']['segments'][0]['input_valid'], 40)
        self.assertEqual(r['conditional']['P_U']['segments'][0]['normal'], 40)
        self.assertEqual(r['profile']['files'][0]['g12_valid_with_other_field_issue_rows'], 1)
        impact = r['all_column_filter_impact']
        self.assertEqual(impact['eligible_records_removed'], 1)
        self.assertEqual(impact['completed_count_changed_buckets'], 1)
        self.assertEqual(impact['buckets_becoming_empty'], 1)

    def test_g12_invalid_bucket_resets_history_without_dropping_label_counters(self):
        rows = [row(clock(i)) for i in range(120)]
        rows[20] = row(clock(20), fp='-1')
        r = self.minute_audit(rows)
        s = r['conditional']['P_U']['segments'][0]
        self.assertEqual((s['input_valid'], s['normal'], s['unknown']), (39, 39, 1))
        self.assertEqual(s['history']['15']['input_valid'], 9)
        self.assertEqual(s['history']['30']['input_valid'], 0)
        self.assertEqual(r['profile']['labels'], {'BENIGN': 120})

    def test_second_pass_rejects_mutated_input_even_with_same_byte_size(self):
        self.assertTrue(callable(audit_minutes), 'Second streaming pass has not been implemented')
        cfg = minute_config(); p = self.file([row()])
        profile_csv([p], cfg, self.audit_dir)
        before = p.stat().st_size
        p.write_text(p.read_text().replace('BENIGN', 'ATTACK', 1), encoding='utf-8', newline='')
        # Preserve CSV newline spelling so the payload-size comparison cannot be the only guard.
        if p.stat().st_size != before:
            with p.open('wb') as f:
                f.write(('s,d,y,a,p,fp,bp,fl,bl,extra,src\r\n2017-07-03 00:00:00.000000,1,ATTACK,-1,6,1,0,4,0,3,192.0.2.1\r\n').encode())
        self.assertEqual(p.stat().st_size, before)
        with self.assertRaisesRegex(ValueError, 'source_identity'):
            audit_minutes([p], cfg, self.audit_dir)

    def test_second_pass_rejects_changed_core_configuration(self):
        self.assertTrue(callable(audit_minutes), 'Second streaming pass has not been implemented')
        cfg = minute_config(); p = self.file([row()]); profile_csv([p], cfg, self.audit_dir)
        cfg['time']['duration_unit'] = 'ms'
        with self.assertRaisesRegex(ValueError, 'core_config'):
            audit_minutes([p], cfg, self.audit_dir)

    def test_duplicate_copies_are_all_excluded_on_second_pass(self):
        self.assertTrue(callable(audit_minutes), 'Second streaming pass has not been implemented')
        cfg = minute_config()
        a = self.file([row(clock(i)) for i in range(120)])
        b = self.file([row(clock(2))], 'two.csv')
        profile_csv([a, b], cfg, self.audit_dir)
        r = audit_minutes([a, b], cfg, self.audit_dir)
        self.assertEqual(r['flow_reasons']['duplicate_record'], 2)
        self.assertEqual(r['conditional']['P_U']['segments'][0]['input_valid'], 39)

    def test_cross_split_flow_pollutes_completion_minute(self):
        rows = [row(clock(i)) for i in range(120)]
        rows.append(row('2017-07-03 00:39:59.000000', d='2000000'))
        r = self.minute_audit(rows)
        self.assertEqual(r['flow_reasons']['cross_partition'], 1)
        self.assertEqual(r['conditional']['P_U']['segments'][1]['input_valid'], 39)
        self.assertEqual(r['conditional']['P_U']['segments'][1]['history']['30']['input_valid'], 9)

    def test_empty_released_record_bucket_does_not_manufacture_normal(self):
        r = self.minute_audit([])
        s = r['conditional']['P_U']['segments'][0]
        self.assertEqual((s['normal'], s['unknown'], s['input_valid']), (0, 40, 0))
        self.assertEqual(s['history']['30']['input_valid'], 0)
        self.assertIsNone(r['conditional']['P_U']['high_completion']['threshold'])
        self.assertIsNone(r['conditional']['P_U']['high_completion']['test_high_normal'])

    def test_attack_with_unknown_truth_is_unknown_but_history_input_stays_valid(self):
        rows = [row(clock(i)) for i in range(120)]
        rows[0] = row(clock(0), y='unknown')
        rows.append(row('2017-07-03 00:00:01.000000', y='ATTACK'))
        r = self.minute_audit(rows)
        s = r['conditional']['P_U']['segments'][0]
        self.assertEqual((s['unknown'], s['attack_present']), (1, 1))
        self.assertEqual(s['history']['30']['input_valid'], 10)

    def test_protocol_frequencies_label_category_conflicts_and_daily_counters(self):
        rows = [row(clock(i)) for i in range(120)]
        rows[0] = row(clock(0), y='ATTACK', a='2', p='17')
        r = self.minute_audit(rows)
        self.assertEqual(r['protocol_counts'], {'17': 1, '6': 119})
        self.assertEqual(r['label_anomalies'], {'label_category_conflict': 1})
        pair = [p for p in r['label_category_counts'] if p['label'] == 'ATTACK'][0]
        self.assertEqual((pair['attempted_category'], pair['rows']), ('2', 1))
        self.assertEqual(r['conditional']['P_B']['segments'][0]['unknown'], 1)
        self.assertEqual(r['conditional']['P_U']['days'][0]['attack_present'], 1)

    def test_receipt_binding_is_checked_separately_from_first_pass_identity(self):
        self.assertTrue(callable(audit_minutes), 'Second streaming pass has not been implemented')
        cfg = minute_config(); p = self.file([row()]); profile_csv([p], cfg, self.audit_dir)
        cfg['expected_inputs'] = [{'bytes': p.stat().st_size, 'sha256': '0' * 64}]
        with self.assertRaisesRegex(ValueError, 'receipt_identity'):
            audit_minutes([p], cfg, self.audit_dir)

    def test_first_pass_detects_mutation_between_final_stat_and_hash(self):
        cfg = config(); p = self.file([row()])
        original = payload.rules._digest_file
        def changed(path, cap):
            path.write_bytes(path.read_bytes().replace(b'BENIGN', b'ATTACK'))
            return original(path, cap)
        with patch('tools.data_audit.c17_payload.rules._digest_file', side_effect=changed):
            with self.assertRaisesRegex(ValueError, 'input_changed'):
                profile_csv([p], cfg, self.audit_dir)

    def test_test_current_normal_common_denominator_is_separate_from_normal_history(self):
        rows = [row(clock(i)) for i in range(120)]
        rows[90] = row(clock(90), y='ATTACK')
        r = self.minute_audit(rows)
        s = r['conditional']['P_U']['segments'][2]
        self.assertEqual(s['common_normal'], 0)
        self.assertEqual(s['common_label_counts'], {'normal': 10, 'attack': 0, 'unknown': 0})
        self.assertEqual(r['conditional']['P_U']['high_completion']['test_normal'], 10)

    def test_protocol_numeric_range_does_not_certify_unsupported_zero_or_200(self):
        rows = [row(clock(i)) for i in range(120)]
        rows[0] = row(clock(0), p='0'); rows[1] = row(clock(1), p='200')
        r = self.minute_audit(rows)
        self.assertEqual(r['flow_reasons']['invalid_unsupported_protocol'], 2)
        self.assertEqual(r['conditional']['P_U']['segments'][0]['input_valid'], 38)


if __name__ == '__main__':
    unittest.main()
