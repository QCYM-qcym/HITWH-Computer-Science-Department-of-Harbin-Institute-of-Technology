"""Immutable, already-checked candidate minute values for replay consumers."""
from collections.abc import Mapping
from dataclasses import dataclass

from .candidate_artifacts import _deep_freeze, _deep_thaw


@dataclass(frozen=True, slots=True)
class VerifiedCandidateRun:
    """Loader result, not an authentication token or approval for real data.

    Retains the report and actual parsed score document only, not raw package
    buffers, weights, models or filesystem paths. Obtain checked values through
    the IF/AE loaders; constructing this value type does not perform validation.
    Constructor inputs must be plain JSON dictionaries containing only JSON
    dictionaries, lists and scalars, as supplied by the loaders' JSON parser.
    """

    report: Mapping
    scores_document: Mapping

    def __post_init__(self):
        if type(self.report) is not dict or type(self.scores_document) is not dict:
            raise TypeError('run snapshot construction requires plain JSON dictionaries')
        object.__setattr__(self, 'report', _deep_freeze(self.report))
        object.__setattr__(self, 'scores_document', _deep_freeze(self.scores_document))

    def report_dict(self):
        """Return an independently mutable copy of the existing verifier report."""
        return _deep_thaw(self.report)

    def scores_dict(self):
        """Return an independently mutable copy of the checked stored values."""
        return _deep_thaw(self.scores_document)
