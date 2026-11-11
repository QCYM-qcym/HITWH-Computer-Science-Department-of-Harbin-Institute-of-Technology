"""Bounded NumPy scoring for the public module's already validated state."""

from .iforest_numeric_state import IForestNumericStateError, NUMERIC_STATE_MAX_ROWS


def _score_validated_state(state, matrix) -> tuple[float, ...]:
    """Score a private float32 snapshot without revalidating the state format."""
    try:
        try:
            import numpy as np
        except ImportError:
            raise IForestNumericStateError('INCOMPATIBLE_RUNTIME') from None
        if type(np.__version__) is not str or np.__version__ != '2.5.4':
            raise IForestNumericStateError('INCOMPATIBLE_RUNTIME')

        if type(matrix) is not np.ndarray or matrix.ndim != 2:
            raise IForestNumericStateError('INVALID_MATRIX')
        row_count, width = matrix.shape
        if row_count > NUMERIC_STATE_MAX_ROWS:
            raise IForestNumericStateError('RESOURCE_LIMIT')
        if (width != state.input_width or not matrix.dtype.isnative
                or matrix.dtype.type not in (np.float32, np.float64)):
            raise IForestNumericStateError('INVALID_MATRIX')
        if not np.isfinite(matrix).all():
            raise IForestNumericStateError('INVALID_MATRIX')
        try:
            with np.errstate(over='raise', invalid='raise', under='ignore'):
                snapshot = np.array(matrix, dtype=np.float32, order='C', copy=True)
        except FloatingPointError:
            raise IForestNumericStateError('INVALID_MATRIX') from None
        if not np.isfinite(snapshot).all():
            raise IForestNumericStateError('INVALID_MATRIX')
        snapshot.setflags(write=False)
        if row_count == 0:
            return ()

        # The coefficient domain is fixed and independent of matrix size.
        samples = np.arange(1, 33, dtype=np.int64)
        coefficients = np.zeros(32, dtype=np.float64)
        coefficients[samples == 2] = 1.0
        larger = samples > 2
        selected = samples[larger]
        coefficients[larger] = (
            2.0 * (np.log(selected - 1.0) + np.euler_gamma)
            - 2.0 * (selected - 1.0) / selected
        )

        depths = np.zeros(row_count, dtype=np.float64)
        for tree in state.trees:
            nodes = tree.nodes
            decision_depth = np.zeros(len(nodes), dtype=np.int64)
            decision_depth[0] = 1
            leaf_correction = np.empty(len(nodes), dtype=np.float64)
            # Validated children have larger IDs, so one forward pass derives
            # every depth without trusting any stored/cache depth field.
            for node_id, node in enumerate(nodes):
                leaf_correction[node_id] = coefficients[node.sample_count - 1]
                if node.left is not None:
                    decision_depth[node.left] = decision_depth[node_id] + 1
                    decision_depth[node.right] = decision_depth[node_id] + 1

            leaves = np.empty(row_count, dtype=np.int64)
            for row_id in range(row_count):
                node_id = 0
                node = nodes[node_id]
                while node.left is not None:
                    # NumPy2 scalar promotion would round a Python threshold
                    # to float32. Promote the feature explicitly instead.
                    value = float(snapshot[row_id, node.feature])
                    node_id = node.left if value <= node.threshold else node.right
                    node = nodes[node_id]
                leaves[row_id] = node_id

            # Preserve both the per-tree grouping and tree 0..15 accumulation.
            contribution = decision_depth[leaves] + leaf_correction[leaves] - 1.0
            depths += contribution

        denominator = 16 * coefficients[state.max_samples - 1]
        scores = 2 ** (-np.divide(depths, denominator, out=np.ones_like(depths),
                                 where=denominator != 0))
        if (type(scores) is not np.ndarray or scores.shape != (row_count,)
                or not np.isfinite(scores).all()
                or not ((scores > 0.0) & (scores <= 1.0)).all()):
            raise IForestNumericStateError('NUMERIC_STATE_ERROR')
        result = tuple(float(score) for score in scores)
        if len(result) != row_count:
            raise IForestNumericStateError('NUMERIC_STATE_ERROR')
        return result
    except MemoryError:
        raise IForestNumericStateError('RESOURCE_LIMIT') from None
    except IForestNumericStateError as error:
        if type(error) is IForestNumericStateError:
            raise
        raise IForestNumericStateError('NUMERIC_STATE_ERROR') from None
    except Exception:
        raise IForestNumericStateError('NUMERIC_STATE_ERROR') from None
