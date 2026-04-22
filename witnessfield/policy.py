"""
witnessfield.policy
===================
Scoring policy layer — separate from the protocol.

The protocol (witnessfield.core) describes witness structure. This module
provides a Policy interface and one concrete DefaultPolicy implementation.
DefaultPolicy's priors, weights, and thresholds are opinion, not protocol.
Replace or subclass it with your own.

Nothing in this file names or privileges any specific witness class.
Witness class strings appear only in _legacy/legacy_priors.json as
opaque keys in a data file, not in protocol or policy source code.
"""

from __future__ import annotations

import json
import math
import time
from pathlib import Path
from typing import Callable, Protocol

from witnessfield.core import WitnessStructure


# ---------------------------------------------------------------------------
# Utility functions (exported — use these in your own Policy if useful)
# ---------------------------------------------------------------------------

def geometric_mean(values: list[float]) -> float:
    """
    Geometric mean of a list of floats.

    Returns 0.0 if any value is <= 0 or if the list is empty.
    The zero-collapse is intentional: a single dimension at 0
    (e.g. no physical trace) collapses the entire hop fidelity.
    """
    if not values:
        return 0.0
    product = 1.0
    for v in values:
        if v <= 0.0:
            return 0.0
        product *= v
    return product ** (1.0 / len(values))


def log_corroboration(n: int, w_base: float) -> float:
    """
    Logarithmic quantity factor: 1 + log10(n) * w_base.

    One independent witness (n=1) returns 1.0. Additional witnesses
    provide logarithmically diminishing corroboration, scaled by the
    witness class's prior credibility.
    """
    if n <= 1:
        return 1.0
    return 1.0 + math.log10(n) * w_base


# ---------------------------------------------------------------------------
# Policy Protocol
# ---------------------------------------------------------------------------

class Policy(Protocol):
    """
    Minimal interface a scoring policy must implement.

    Any callable object with this signature qualifies; no base class
    or registration required.
    """

    def score(self, structure: WitnessStructure) -> float:
        """Return a score in [0.001, 0.999] for the given structure."""
        ...


# ---------------------------------------------------------------------------
# DefaultPolicy
# ---------------------------------------------------------------------------

class DefaultPolicy:
    """
    One opinionated scoring policy. NOT the protocol.

    Formula
    -------
    V = W x Q x D x C, clamped to [0.001, 0.999]

    Where:
      W = mean of w_base[witness_class] across all witnesses
          (0.0 for classes not in w_base)
      Q = quantity_fn(n_independent, W)
      D = exp(-lambda * age_years)
          lambda = decay_lambda.get("default", 0.15)
      C = product over hops of fidelity_aggregator(hop.fidelity.values())

    The formula omits v0.x concepts (anchor boost, asymmetry discount)
    that depended on fields not present in WitnessStructure. Subclass
    and override score() if you need them.

    Parameters
    ----------
    w_base : dict[str, float]
        Maps witness_class strings to prior credibility in [0, 1].
        Classes absent from this dict score 0.0.
    decay_lambda : dict[str, float]
        Maps claim type labels to temporal decay rate per year.
        Key "default" is the fallback. If absent, 0.15 is used.
    fidelity_aggregator : Callable[[list[float]], float]
        Aggregates a hop's fidelity values into a single float.
        Default: geometric_mean (zero-collapse on any zero dimension).
    quantity_fn : Callable[[int, float], float]
        Maps (n_independent, w_base_mean) to a corroboration multiplier.
        Default: log_corroboration.
    """

    def __init__(
        self,
        w_base: dict[str, float],
        decay_lambda: dict[str, float],
        fidelity_aggregator: Callable[[list[float]], float] = geometric_mean,
        quantity_fn: Callable[[int, float], float] = log_corroboration,
    ) -> None:
        self.w_base = w_base
        self.decay_lambda = decay_lambda
        self.fidelity_aggregator = fidelity_aggregator
        self.quantity_fn = quantity_fn

    def score(self, structure: WitnessStructure) -> float:
        """
        Score a WitnessStructure. Returns V in [0.001, 0.999].

        Calls structure.describe() internally to extract n_independent
        and age_seconds. The formula is fully determined by the
        constructor parameters.
        """
        desc = structure.describe()

        # W: mean prior credibility across all witnesses
        w_values = [
            self.w_base.get(w.witness_class, 0.0)
            for w in structure.witnesses
        ]
        W = sum(w_values) / len(w_values) if w_values else 0.0

        # Q: quantity corroboration
        n_ind = max(1, desc["n_independent"])
        Q = self.quantity_fn(n_ind, W)

        # D: temporal decay (uses "default" lambda; subclass for per-claim-type)
        lam = self.decay_lambda.get("default", 0.15)
        age_years = max(0.0, desc["age_seconds"]) / (365.25 * 86400)
        D = math.exp(-lam * age_years)

        # C: product of per-hop fidelity aggregation
        C = 1.0
        for hop in structure.hops:
            if hop.fidelity:
                C *= self.fidelity_aggregator(list(hop.fidelity.values()))

        V_raw = W * Q * D * C
        return max(0.001, min(0.999, V_raw))

    # ------------------------------------------------------------------
    # Migration bridge from v0.x
    # ------------------------------------------------------------------

    @classmethod
    def from_legacy_priors(cls) -> "DefaultPolicy":
        """
        Load the v0.x priors from _legacy/legacy_priors.json.

        The priors, decay lambdas, and witness class names in that file
        are the calibration values from witnessfield v0.x. They are
        stored in a data file (not in source code) so that policy.py
        contains no hardcoded witness class strings.

        Use this for migration only. Replace with your own calibrated
        priors for production use.
        """
        priors_path = Path(__file__).parent / "_legacy" / "legacy_priors.json"
        priors = json.loads(priors_path.read_text(encoding="utf-8"))
        return cls(
            w_base=priors["w_base"],
            decay_lambda=priors["decay_lambda"],
        )
