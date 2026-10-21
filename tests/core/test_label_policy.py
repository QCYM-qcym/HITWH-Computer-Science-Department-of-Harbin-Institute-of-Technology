from conftest import batch, labels_for
from traffic_anomaly.data.labels import classify_labels, align_labels

def test_normal_background_overlap_and_missing_label_identity():
    b = batch([1, 2, 3, 4])
    labels = labels_for(batch([1, 2, 3]), {"spam": {1: 1, 2: 1}, "dos": {2: 1}})
    normal, attack, background = classify_labels(align_labels(b.timestamps, labels))
    assert normal.tolist() == [True, False, False, False]
    assert attack.tolist() == [False, False, True, False]
    assert background.tolist() == [False, True, False, False]
