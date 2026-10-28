"""SYNTHETIC_ONLY G13U source-record population and feature boundary checks."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('payload_cases', Path(__file__).with_name('test_c17_payload.py'))
fixtures = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixtures)

try:
    from tools.data_audit.c17_g13u import aggregate_candidate_records, audit_g13u
except ModuleNotFoundError:
    aggregate_candidate_records = audit_g13u = None


ORDER = ['completed_source_record_count', 'fwd_packet_sum', 'bwd_packet_sum',
         'fwd_source_length_sum', 'bwd_source_length_sum', 'tcp_source_record_count',
         'udp_source_record_count', 'known_other_source_protocol_record_count',
         'unresolved_source_protocol_record_count', 'duration_max_s', 'duration_median_s',
         'duration_p95_s', 'no_backward_packet_source_record_count']


class AggregateTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(callable(aggregate_candidate_records), 'G13U aggregate is not implemented')

    def records(self):
        return [{'protocol': p, 'fwd_packets': i, 'bwd_packets': b, 'fwd_length': i * 10,
                 'bwd_length': b * 5, 'duration_us': i * 1000000, 'label': label}
                for p, i, b, label in [(6, 1, 0, 'BENIGN'), (17, 2, 1, 'BENIGN'),
                                        (1, 3, 2, 'BENIGN'), (0, 4, 0, 'Portscan')]]

    def test_thirteen_features_have_exclusive_known_other_and_unresolved_channels(self):
        r = aggregate_candidate_records(self.records())
        self.assertEqual(list(r['features']), ORDER)
        self.assertEqual(list(r['features'].values())[:9], [4, 10, 3, 100, 15, 1, 1, 1, 1])
        self.assertEqual(r['features']['duration_max_s'], 4)
        self.assertEqual(r['features']['duration_median_s'], 2.5)
        self.assertAlmostEqual(r['features']['duration_p95_s'], 3.85)
        self.assertEqual(r['features']['no_backward_packet_source_record_count'], 2)
        self.assertTrue(r['channel_conservation'])

    def test_labels_never_enter_features_and_zero_is_not_renamed_other(self):
        records = self.records(); a = aggregate_candidate_records(records)
        for row in records:
            row['label'] = 'arbitrary-change'
        self.assertEqual(a['features'], aggregate_candidate_records(records)['features'])
        self.assertEqual(a['channels']['unresolved'], 1)
        self.assertEqual(a['channels']['known_other'], 1)

    def test_invalid_protocol_or_field_prevents_a_partial_valid_minute_vector(self):
        records = self.records()
        records += [{**records[0], 'protocol': 200}, {**records[0], 'fwd_packets': -1}]
        r = aggregate_candidate_records(records)
        self.assertIsNone(r['features'])
        self.assertEqual((r['raw_records'], r['eligible_records'], r['excluded_records']), (6, 4, 2))
        self.assertEqual(sum(r['channels'].values()), 4)

    def test_empty_and_nonfinite_values_never_become_zero_filled_features(self):
        self.assertIsNone(aggregate_candidate_records([])['features'])
        records = self.records(); records[0]['duration_us'] = 'Infinity'
        self.assertIsNone(aggregate_candidate_records(records)['features'])

    def test_sample_quantile_memory_cap_is_enforced(self):
        with self.assertRaisesRegex(ValueError, 'sample_cap'):
            aggregate_candidate_records(self.records(), max_records=3)

    def test_illegal_protocol_shapes_and_noninteger_fields_cannot_enter_features(self):
        for value in [-1, 0.5, 200, 256, 'NaN', 'Infinity', '1e999999999', '', True]:
            with self.subTest(protocol=value):
                r = aggregate_candidate_records([{**self.records()[0], 'protocol': value}])
                self.assertIsNone(r['features'])
                self.assertEqual(r['eligible_records'], 0)
        for field in ['fwd_packets', 'bwd_packets', 'fwd_length', 'bwd_length', 'duration_us']:
            with self.subTest(field=field):
                r = aggregate_candidate_records([{**self.records()[0], field: '0.5'}])
                self.assertIsNone(r['features'])
        self.assertIsNone(aggregate_candidate_records([{**self.records()[0], 'fwd_packets': '1e999999999'}])['features'])


class G13UAuditTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(callable(audit_g13u), 'G13U streaming audit is not implemented')
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.old = self.root / 'old'; self.old.mkdir()
        self.output = self.root / 'new'; self.output.mkdir()
        self.cfg = fixtures.minute_config()
        self.cfg.update(audit_id='C17-I1-G13U', population='HASH_BOUND_RELEASED_CSV_RECORDS',
                        unresolved_source_protocol=0, feature_order=ORDER)
        self.cfg['labels']['attack'].append('Portscan')

    def prepare(self, rows):
        import csv
        p = self.root / 'SYNTHETIC_ONLY.csv'
        with p.open('w', newline='', encoding='utf-8') as f:
            w = csv.writer(f); w.writerow(fixtures.HEADER); w.writerows(rows)
        profile = fixtures.profile_csv([p], self.cfg, self.old)
        self.cfg['expected_inputs'] = [{'bytes': profile['files'][0]['bytes'], 'sha256': profile['files'][0]['sha256']}]
        return p, self.old / 'profile-index.sqlite3'

    def run_rows(self, rows):
        p, index = self.prepare(rows)
        return audit_g13u([p], self.cfg, self.output, index)

    def test_zero_records_remain_eligible_source_records_with_original_attack_labels(self):
        rows = [fixtures.row(fixtures.clock(i)) for i in range(120)]
        rows[1] = fixtures.row(fixtures.clock(1), p='0')
        rows[2] = fixtures.row(fixtures.clock(2), p='0', y='Portscan')
        r = self.run_rows(rows)
        self.assertEqual(r['population'], 'HASH_BOUND_RELEASED_CSV_RECORDS')
        self.assertEqual(r['all_source']['raw_protocol_channels'], {'tcp': 118, 'udp': 0, 'known_other': 0, 'unresolved': 2, 'excluded_protocol': 0})
        self.assertEqual(r['unresolved']['all_source']['original_labels'], {'BENIGN': 1, 'Portscan': 1})
        s = r['policies']['P_U']['segments'][0]
        self.assertEqual((s['input_valid'], s['normal'], s['attack'], s['unknown']), (40, 39, 1, 0))
        self.assertEqual(s['history']['30']['input_valid'], 10)
        self.assertEqual(s['history']['30']['current_label_counts'], {'normal': 10, 'attack': 0, 'unknown': 0})
        self.assertIsNone(r['model_common_valid_minutes'])
        self.assertNotIn('invalid_unsupported_protocol', r['flow_reasons'])

    def test_unknown_protocol_still_invalidates_bucket_and_history(self):
        rows = [fixtures.row(fixtures.clock(i)) for i in range(120)]
        rows[20] = fixtures.row(fixtures.clock(20), p='200')
        r = self.run_rows(rows)
        s = r['policies']['P_U']['segments'][0]
        self.assertEqual(s['input_valid'], 39)
        self.assertEqual(s['history']['30']['input_valid'], 0)
        self.assertEqual(r['flow_reasons']['invalid_unsupported_protocol'], 1)
        self.assertEqual(r['all_source']['raw_protocol_channels']['excluded_protocol'], 1)

    def test_per_segment_raw_eligible_channels_and_exclusion_conserve_records(self):
        rows = [fixtures.row(fixtures.clock(i)) for i in range(120)]
        rows[0] = fixtures.row(fixtures.clock(0), p='0')
        rows[1] = fixtures.row(fixtures.clock(1), p='17')
        rows[2] = fixtures.row(fixtures.clock(2), p='132')
        rows[3] = fixtures.row(fixtures.clock(3), p='200')
        r = self.run_rows(rows)
        s = r['record_channels']['segments'][0]
        self.assertEqual(sum(s['raw_protocol_channels'].values()), 40)
        self.assertEqual(sum(s['eligible_protocol_channels'].values()), s['eligible_completed_records'])
        self.assertEqual(s['raw_completed_records'], s['eligible_completed_records'] + s['excluded_records'])

    def test_three_attempted_policies_preserve_unknown_and_input_history(self):
        rows = [fixtures.row(fixtures.clock(i)) for i in range(120)]
        rows[0] = fixtures.row(fixtures.clock(0), p='0', y='ATTACK - Attempted', a='2')
        rows[1] = fixtures.row(fixtures.clock(1), y='unrecognized')
        r = self.run_rows(rows)
        for p, expected in [('P_U', (38, 0, 2)), ('P_B', (39, 0, 1)), ('P_A', (38, 1, 1))]:
            s = r['policies'][p]['segments'][0]
            self.assertEqual((s['normal'], s['attack'], s['unknown']), expected)
            self.assertEqual(s['history']['30']['input_valid'], 10)

    def test_empty_source_bucket_is_invalid_and_never_normal(self):
        r = self.run_rows([])
        s = r['policies']['P_U']['segments'][0]
        self.assertEqual((s['input_valid'], s['normal'], s['unknown']), (0, 0, 40))
        self.assertIsNone(r['policies']['P_U']['high_completion']['threshold'])

    def test_old_index_and_inputs_are_unchanged_and_no_private_rows_are_exported(self):
        p, index = self.prepare([fixtures.row()])
        before = (p.read_bytes(), index.read_bytes())
        r = audit_g13u([p], self.cfg, self.output, index)
        self.assertEqual(before, (p.read_bytes(), index.read_bytes()))
        self.assertEqual(list(self.output.iterdir()), [])
        text = json.dumps(r)
        self.assertNotIn('192.0.2.1', text)
        self.assertNotIn(str(self.root), text)

    def test_source_receipt_mismatch_and_zero_in_known_set_are_rejected(self):
        p, index = self.prepare([fixtures.row()])
        self.cfg['expected_inputs'][0]['sha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'receipt_identity'):
            audit_g13u([p], self.cfg, self.output, index)
        cfg = deepcopy(self.cfg); cfg['supported_protocols'].append(0)
        with self.assertRaisesRegex(ValueError, 'known_protocol'):
            audit_g13u([p], cfg, self.output, index)

    def test_unresolved_minute_diagnostics_are_bounded_descriptive_counts(self):
        rows = [fixtures.row(fixtures.clock(i), p='0' if i % 10 == 0 else '6') for i in range(120)]
        r = self.run_rows(rows)
        d = r['unresolved']['all_source']
        self.assertEqual(d['record_count'], 12)
        self.assertEqual(d['occupied_minutes'], 12)
        self.assertEqual(d['occupied_bucket_gap_minutes'], {'10': 11})
        self.assertEqual(d['longest_occupied_run_minutes'], 1)
        self.assertEqual(d['count_histogram'], {'0': 108, '1': 12})
        self.assertEqual(d['unresolved_record_fraction']['linear_quantiles']['max'], 1)
        lag = next(x for x in d['descriptive_lags'] if x['lag_minutes'] == 10)
        self.assertEqual(lag['both_occupied_pairs'], 11)

    def test_completion_proxy_is_half_open_and_cross_partition_zero_is_retained_raw(self):
        rows = [fixtures.row(fixtures.clock(i)) for i in range(120)]
        rows += [fixtures.row('2017-07-03 00:39:59.000000', d='1000000', p='0'),
                 fixtures.row('2017-07-03 01:59:59.000000', d='1000000', p='0')]
        r = self.run_rows(rows)
        self.assertEqual(r['flow_reasons']['cross_partition'], 1)
        self.assertEqual(r['flow_reasons']['outside_candidate_ranges'], 1)
        s = r['record_channels']['segments'][1]
        self.assertEqual((s['raw_completed_records'], s['eligible_completed_records']), (41, 40))
        self.assertEqual(s['raw_protocol_channels']['unresolved'], 1)
        self.assertEqual(s['eligible_protocol_channels']['unresolved'], 0)
        u = r['unresolved']['all_source']
        self.assertEqual((u['record_count'], u['eligible_record_count']), (2, 0))
        self.assertEqual(u['excluded_reasons'], {'cross_partition': 1, 'outside_candidate_ranges': 1})
        self.assertEqual(r['policies']['P_U']['segments'][1]['history']['30']['input_valid'], 9)

    def test_train_calibration_require_normal_history_but_test_uses_current_truth(self):
        self.cfg['candidate_registration']['segments'][1]['role'] = 'calibration'
        rows = [fixtures.row(fixtures.clock(i)) for i in range(120)]
        for i in (5, 45, 90):
            rows[i] = fixtures.row(fixtures.clock(i), y='ATTACK')
        r = self.run_rows(rows)
        train, calibration, test = r['policies']['P_U']['segments']
        self.assertEqual((train['common_normal'], calibration['common_normal']), (4, 4))
        self.assertEqual(test['history']['30']['input_valid'], 10)
        self.assertEqual(test['history']['30']['current_label_counts'], {'normal': 10, 'attack': 0, 'unknown': 0})
        self.assertEqual(test['common_normal'], 0)
        self.assertEqual(r['policies']['P_U']['high_completion']['test_normal'], 10)

    def test_completed_count_linear_q90_and_strict_high_group_use_train_only(self):
        rows = [fixtures.row(fixtures.clock(i)) for i in range(120)]
        rows[114] = fixtures.row(fixtures.clock(114), p='0')
        rows[115] = fixtures.row(fixtures.clock(115), p='0')
        # Ten common train counts are nine 1s and one 11: linear Q90 is 2.
        rows += [fixtures.row('2017-07-03 00:39:01.%06d' % i) for i in range(10)]
        rows += [fixtures.row('2017-07-03 01:54:01.000000')]
        rows += [fixtures.row('2017-07-03 01:55:01.%06d' % i) for i in range(2)]
        rows += [fixtures.row('2017-07-03 01:10:02.%06d' % i) for i in range(50)]
        r = self.run_rows(rows)
        high = r['policies']['P_U']['high_completion']
        self.assertAlmostEqual(high['threshold'], 2)
        self.assertEqual((high['test_normal'], high['test_high_normal']), (10, 1))
        self.assertEqual(high['test_ordinary_normal'], 9)
        self.assertEqual(high['high_intervals'], [{'start': '2017-07-03 01:55:00.000000',
                                                 'end': '2017-07-03 01:56:00.000000', 'minutes': 1}])
        self.assertEqual(r['policies']['P_U']['days'][0]['test_high_normal'], 1)
        self.assertEqual(high['unresolved_overlap'], {'test_common_current_normal_with_unresolved': 2,
                         'test_high_normal_with_unresolved': 1, 'test_ordinary_normal_with_unresolved': 1})

    def test_duplicate_zero_copies_are_all_excluded_and_break_history(self):
        rows = [fixtures.row(fixtures.clock(i)) for i in range(120)]
        rows[20] = fixtures.row(fixtures.clock(20), p='0')
        rows.append(rows[20])
        r = self.run_rows(rows)
        self.assertEqual(r['flow_reasons']['duplicate_record'], 2)
        self.assertEqual(r['unresolved']['all_source']['record_count'], 2)
        self.assertEqual(r['unresolved']['all_source']['eligible_record_count'], 0)
        self.assertEqual(r['policies']['P_U']['segments'][0]['history']['30']['input_valid'], 0)

    def test_unknown_timing_quarantines_all_candidates_without_erasing_raw_zero(self):
        rows = [fixtures.row(fixtures.clock(i)) for i in range(120)]
        rows.append(fixtures.row('bad-clock', p='0'))
        r = self.run_rows(rows)
        self.assertEqual(r['unplaced_invalid_rows'], 1)
        self.assertEqual(r['unresolved']['all_source']['original_labels'], {'BENIGN': 1})
        self.assertEqual([s['input_valid'] for s in r['policies']['P_U']['segments']], [0, 0, 0])

    def test_changed_core_config_and_same_length_source_substitution_fail(self):
        p, index = self.prepare([fixtures.row()])
        cfg = deepcopy(self.cfg); cfg['time']['duration_unit'] = 'ms'
        with self.assertRaisesRegex(ValueError, 'core_config'):
            audit_g13u([p], cfg, self.output, index)
        p.write_bytes(p.read_bytes().replace(b'BENIGN', b'ATTACK'))
        with self.assertRaisesRegex(ValueError, 'source_identity'):
            audit_g13u([p], self.cfg, self.output, index)

    def test_unused_field_nonfinite_does_not_remove_valid_zero_record(self):
        rows = [fixtures.row(fixtures.clock(i)) for i in range(120)]
        rows[0] = fixtures.row(fixtures.clock(0), p='0', extra='Infinity')
        r = self.run_rows(rows)
        self.assertEqual(r['policies']['P_U']['segments'][0]['input_valid'], 40)
        self.assertEqual(r['unresolved']['all_source']['eligible_record_count'], 1)
        self.assertEqual(r['all_column_filter_impact']['eligible_records_removed'], 1)

    def test_label_cardinality_caps_apply_outside_registered_ranges(self):
        p, index = self.prepare([fixtures.row('2017-07-03 03:00:00.000000', y='first'),
                                 fixtures.row('2017-07-03 03:01:00.000000', y='second')])
        self.cfg['limits']['max_label_values'] = 1
        with self.assertRaisesRegex(ValueError, 'max_label_values'):
            audit_g13u([p], self.cfg, self.output, index)

    def test_category_caps_apply_even_to_out_of_candidate_known_labels(self):
        p, index = self.prepare([fixtures.row('2017-07-03 03:00:00.000000'),
                                 fixtures.row('2017-07-03 03:01:00.000000', a='2')])
        self.cfg['limits']['max_category_values'] = 1
        with self.assertRaisesRegex(ValueError, 'max_category_values'):
            audit_g13u([p], self.cfg, self.output, index)

    def test_direct_api_refuses_alias_of_old_audit_directory(self):
        p, index = self.prepare([fixtures.row()])
        alias = self.old / '..' / 'old'
        with self.assertRaisesRegex(ValueError, 'new_audit_directory'):
            audit_g13u([p], self.cfg, alias, index)

    def test_workspace_scratch_counts_against_combined_runtime_audit_budget(self):
        import shutil
        p, index = self.prepare([fixtures.row()])
        old = self.root / '.runtime' / 'old' / 'audit'; old.mkdir(parents=True)
        new = self.root / '.runtime' / 'new' / 'audit'; new.mkdir(parents=True)
        copy = old / 'profile-index.sqlite3'; shutil.copyfile(index, copy)
        scratch = self.root / '.superpowers' / 'sdd' / 'previous'; scratch.mkdir(parents=True)
        (scratch / 'notes.txt').write_text('x' * 1000, encoding='utf-8')
        self.cfg['limits']['audit_max_bytes'] = copy.stat().st_size + 100
        with self.assertRaisesRegex(ValueError, 'combined_audit_scratch'):
            audit_g13u([p], self.cfg, new, copy)

    def test_input_history_sets_are_identical_across_three_label_policies(self):
        rows = [fixtures.row(fixtures.clock(i)) for i in range(120)]
        rows[0] = fixtures.row(fixtures.clock(0), y='ATTACK - Attempted', a='2')
        rows[90] = fixtures.row(fixtures.clock(90), y='unrecognized')
        r = self.run_rows(rows)
        for p in ['P_U', 'P_B', 'P_A']:
            for s in r['policies'][p]['segments']:
                self.assertEqual((s['input_valid'], s['history']['15']['input_valid'],
                                  s['history']['30']['input_valid'], s['common_input_valid']), (40, 25, 10, 10))
            test = r['policies'][p]['segments'][2]
            self.assertEqual(test['common_label_counts'], {'normal': 10, 'attack': 0, 'unknown': 0})
            self.assertEqual(test['common_normal'], 0)

    def test_cli_fails_safely_and_refuses_existing_output(self):
        p, index = self.prepare([fixtures.row()])
        cfg = self.root / 'cfg.json'; cfg.write_text(json.dumps(self.cfg), encoding='utf-8')
        out = self.output / 'report.json'
        script = Path(__file__).resolve().parents[2] / 'tools/data_audit/c17_g13u.py'
        args = [sys.executable, '-X', 'utf8', str(script), '--input', str(p), '--config', str(cfg),
                '--audit-dir', str(self.output), '--output', str(out), '--index-path', str(index)]
        first = subprocess.run(args, capture_output=True, text=True)
        self.assertEqual(first.returncode, 0, first.stderr)
        second = subprocess.run(args, capture_output=True, text=True)
        self.assertEqual(second.returncode, 2)
        self.assertNotIn(str(self.root), second.stderr)
        self.assertNotIn('Traceback', second.stderr)


if __name__ == '__main__':
    unittest.main()
