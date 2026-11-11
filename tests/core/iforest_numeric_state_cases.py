"""Only literal, bounded manual numeric trees; no model or score oracle."""
from traffic_anomaly.iforest_numeric_state import (
    IForestNumericNode as Node, IForestNumericTree as Tree, IForestNumericState,
    NUMERIC_STATE_VERSION, NUMERIC_STATE_PROFILE_ID, NUMERIC_STATE_ALGORITHM_ID,
)


def manual_numeric_state(*, width=13, pattern='root_leaf', max_samples=1):
    """Construct one fixed legal tree pattern, repeated in a 16-tree forest.

    Node IDs are preorder. In balanced32, recursively bisect [0,32] in feature
    zero so every leaf has a nonempty numeric region. Nonroot patterns require
    their declared sample count; the helper never changes it implicitly.
    """
    if type(width) is not int or width not in (13, 26):
        raise ValueError('unsupported manual width')
    if type(max_samples) is not int or not 1 <= max_samples <= 32:
        raise ValueError('unsupported manual sample count')
    if type(pattern) is not str:
        raise ValueError('unsupported manual pattern')
    leaf = lambda count: Node(None, None, None, None, count)
    if pattern == 'root_leaf':
        nodes = (leaf(max_samples),)
    elif pattern == 'split2' and max_samples == 2:
        nodes = (Node(1, 2, 0, 0.0, 2), leaf(1), leaf(1))
    elif pattern == 'asymmetric4' and max_samples == 4:
        nodes = (Node(1, 2, 0, 0.0, 4), leaf(1), leaf(3))
    elif pattern == 'three_leaf4' and max_samples == 4:
        nodes = (Node(1, 2, 0, 0.0, 4), leaf(1),
            Node(3, 4, 0, 2.0, 3), leaf(1), leaf(2))
    elif pattern == 'balanced32' and max_samples == 32:
        buffer = []

        def bounded_tree(low, high):
            index = len(buffer)
            buffer.append(None)
            count = high - low
            if count == 1:
                buffer[index] = leaf(1)
            else:
                middle = (low + high) // 2
                left = bounded_tree(low, middle)
                right = bounded_tree(middle, high)
                buffer[index] = Node(left, right, 0, float(middle), count)
            return index

        bounded_tree(0, 32)
        nodes = tuple(buffer)
    else:
        raise ValueError('manual pattern requires its explicit sample count')
    return IForestNumericState(NUMERIC_STATE_VERSION, NUMERIC_STATE_PROFILE_ID,
        NUMERIC_STATE_ALGORITHM_ID, width, tuple(range(width)), max_samples,
        tuple(Tree(nodes) for _ in range(16)))
