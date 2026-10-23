"""Synthetic edge cases for the offline prefix audit; no network or model fitting."""
import unittest

try:
    from tools.data_audit.c18_prefix import audit_prefix
except ModuleNotFoundError:
    audit_prefix = None

HEADER = b'Timestamp,Flow Duration,Protocol,Tot Fwd Pkts,Tot Bwd Pkts,TotLen Fwd Pkts,TotLen Bwd Pkts,Flow Byts/s,Label\n'


class PrefixAuditTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(callable(audit_prefix), 'Offline prefix auditor has not been implemented')

    def test_partial_last_record_is_excluded_without_claiming_full_file(self):
        data = HEADER + b'14/02/2018 09:01:00,10,6,1,0,4,0,1,BENIGN\n14/02/2018 09:00:00,20,17,1,1,4,8,2,DoS attacks-Hulk\n14/02/2018 09:'
        report = audit_prefix(data)
        self.assertEqual(report['complete_data_rows'], 2)
        self.assertEqual(report['discarded_tail_bytes'], 14)
        self.assertEqual(report['timestamp']['raw_order_inversions'], 1)
        self.assertFalse(report['can_estimate_four_split_supply'])
        self.assertEqual(report['labels']['observed_counts'], {'BENIGN': 1, 'DoS attacks-Hulk': 1})

    def test_nonfinite_numeric_values_remain_invalid_and_are_counted(self):
        report = audit_prefix(HEADER + b'14/02/2018 09:00:00,0,6,1,0,4,0,Infinity,BENIGN\n')
        self.assertEqual(report['numeric']['nonfinite_cells'], {'Flow Byts/s': 1})
        self.assertEqual(report['numeric']['rows_with_issue'], 1)
        self.assertEqual(report['required_source_fields']['rows_with_issue'], 0)

    def test_missing_and_unknown_labels_never_become_benign(self):
        data = HEADER + b'14/02/2018 09:00:00,1,6,1,0,4,0,1,\n14/02/2018 09:00:01,1,6,1,0,4,0,1,unrecognised\n'
        report = audit_prefix(data)
        self.assertEqual(report['labels']['missing_rows'], 1)
        self.assertEqual(report['labels']['unmapped_non_benign_rows'], 1)
        self.assertEqual(report['labels']['benign_flow_rows'], 0)

    def test_observed_benign_spelling_is_counted_without_changing_minute_truth(self):
        report = audit_prefix(HEADER + b'14/02/2018 09:00:00,1,6,1,0,4,0,1,Benign\n')
        self.assertEqual(report['labels']['benign_flow_rows'], 1)
        self.assertEqual(report['labels']['unmapped_non_benign_rows'], 0)
        self.assertEqual(report['labels']['observed_counts'], {'Benign': 1})
        self.assertFalse(report['labels']['minute_truth_verified'])

    def test_protocol_zero_stays_unresolved_instead_of_becoming_other_traffic(self):
        report = audit_prefix(HEADER + b'14/02/2018 09:00:00,1,0,1,0,4,0,1,Benign\n')
        self.assertEqual(report.get('protocol_zero_semantics'), 'UNVERIFIED_SOURCE_ENCODING')
        self.assertEqual(report['protocol_value_counts'], {'0': 1})

    def test_duplicate_fields_are_rejected_before_row_mapping(self):
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            audit_prefix(b'Timestamp,Label,Label\n14/02/2018 09:00:00,BENIGN,BENIGN\n')

    def test_ragged_complete_row_is_rejected_instead_of_silently_skipped(self):
        with self.assertRaisesRegex(ValueError, 'column count'):
            audit_prefix(HEADER + b'14/02/2018 09:00:00,1,BENIGN\n')

    def test_wall_clock_parse_never_assigns_timezone_or_resolves_am_pm(self):
        report = audit_prefix(HEADER + b'14/02/2018 09:00:00,1,6,1,0,4,0,1,BENIGN\n')
        self.assertEqual(report['timestamp']['parsed_rows'], 1)
        self.assertIsNone(report['timestamp']['timezone'])
        self.assertEqual(report['timestamp']['hour_ambiguity'], 'ALL_VALUES_01_TO_12_WITHOUT_AM_PM')
        self.assertIsNone(report['four_split_supply'])

    def test_negative_required_duration_is_not_a_valid_zero(self):
        report = audit_prefix(HEADER + b'14/02/2018 09:00:00,-1,6,1,0,4,0,1,BENIGN\n')
        self.assertEqual(report['required_source_fields']['invalid_counts'], {'Flow Duration': 1})
        self.assertEqual(report['required_source_fields']['rows_with_issue'], 1)

    def test_input_larger_than_approved_per_object_limit_is_rejected(self):
        with self.assertRaisesRegex(ValueError, '4 MiB'):
            audit_prefix(b'x' * (4194304 + 1))


if __name__ == '__main__':
    unittest.main()
