"""
witnessfield
============
Witness Field Protocol v2.1 — computable evidence scoring.

Formula:
  V = W_provenance x Q x D x C x Anchor_boost x Asymmetry_discount
  V clamped to [0.001, 0.999]

Axiom: not all witnesses are equal.
       Kirandeep Kaur, 2026

Quick start
-----------
>>> from witnessfield import score, list_witness_types
>>> v = score({"witness_type": "blockchain", "anchor_strength": 1.0})
>>> print(f"V = {v['V']:.3f}")
V = 0.999

>>> from witnessfield import vault_outcome_stats
>>> stats = vault_outcome_stats(records)
>>> print(f"Track record: {stats['track_record']:.2%}")
"""

from .core import (
    # Constants
    WITNESS_TYPES,
    CLAIM_TYPE_LAMBDAS,
    FIDELITY_DIMS,
    DEFAULT_HOP_VECTORS,
    # Functions
    geometric_mean_7,
    wallet_track_record,
    vault_outcome_stats,
    helix_hop_fidelity,
    score,
    score_commit,
    score_commits_file,
    witness_mean,
    list_witness_types,
)

from .analysis import (
    score_report,
    calibration_table,
    compare_anchoring,
    decay_curve,
    track_record_report,
)

__version__ = "0.1.0"
__author__  = "Kirandeep Kaur"
__all__ = [
    # Constants
    "WITNESS_TYPES",
    "CLAIM_TYPE_LAMBDAS",
    "FIDELITY_DIMS",
    "DEFAULT_HOP_VECTORS",
    # Core scoring
    "geometric_mean_7",
    "wallet_track_record",
    "vault_outcome_stats",
    "helix_hop_fidelity",
    "score",
    "score_commit",
    "score_commits_file",
    "witness_mean",
    "list_witness_types",
    # Analysis
    "score_report",
    "calibration_table",
    "compare_anchoring",
    "decay_curve",
    "track_record_report",
]
