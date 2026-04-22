"""
witnessfield.core
=================
Witness structure protocol — data structures only.

witnessfield describes the external witness structure around a claim.
The structure is the protocol. Scores are policy — one plausible
policy ships as DefaultPolicy in witnessfield.policy, but the priors,
weights, and thresholds it uses are opinion, not measurement. Swap it
for your own.

This module defines:
- FIDELITY_DIMS: the seven dimensions on which a custody hop is rated
- Claim, Witness, CustodyHop: immutable structural facts
- WitnessStructure: the graph; describe() returns structural summary,
  score() delegates to any Policy-conforming object

No scoring, no priors, no weights live here.
"""

from __future__ import annotations

import time
from collections import Counter
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from witnessfield.policy import Policy


# ---------------------------------------------------------------------------
# Fidelity dimensions
# ---------------------------------------------------------------------------

FIDELITY_DIMS: tuple[str, ...] = (
    "reversibility",        # can the record be altered without detection?
    "accountability",       # is the witness identifiable and answerable?
    "physical_trace",       # does a tamper-evident physical record exist?
    "independence",         # is the witness free from the claim's beneficiary?
    "specificity",          # does the witness address this claim specifically?
    "motivation_clean",     # does the witness have clean motive (no conflict)?
    "cross_referenceable",  # can the claim be confirmed from an independent source?
)

_FIDELITY_DIM_SET: frozenset[str] = frozenset(FIDELITY_DIMS)


# ---------------------------------------------------------------------------
# Claim
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Claim:
    """
    The thing being witnessed.

    ``id`` must be unique within a system. ``content`` is a human-readable
    description of what is claimed. ``observed_at`` is the unix-second
    timestamp when the claim was originally made or observed.
    """

    id:          str
    content:     str
    observed_at: float


# ---------------------------------------------------------------------------
# Witness
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Witness:
    """
    One attestation of a claim by an external party.

    ``witness_class`` is a free-form string; the policy object decides
    what prior credibility to assign each class. The library makes no
    assumption about which classes exist or what they mean.

    ``signature`` is optional bytes, e.g. an Ed25519 signature over
    ``attested_content``. The library does not verify it; a policy may.
    """

    id:               str
    witness_class:    str
    attested_content: str
    observed_at:      float
    signature:        Optional[bytes] = None


# ---------------------------------------------------------------------------
# CustodyHop
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CustodyHop:
    """
    A directed edge in the witness custody chain.

    ``source`` and ``destination`` are witness ids, or the special
    strings "origin" (the original claim event) and "engine" (the
    consuming system). ``fidelity`` is a dict of dimension-name to
    float in [0.0, 1.0]. Only keys from FIDELITY_DIMS are accepted;
    aggregation is left to the policy.

    Raises ``ValueError`` at construction if any fidelity key is not
    in FIDELITY_DIMS, or if any value is outside [0.0, 1.0].
    """

    source:      str
    destination: str
    fidelity:    dict[str, float]

    def __post_init__(self) -> None:
        unknown = set(self.fidelity) - _FIDELITY_DIM_SET
        if unknown:
            raise ValueError(
                f"Unknown fidelity dimension(s): {sorted(unknown)}. "
                f"Allowed: {sorted(_FIDELITY_DIM_SET)}"
            )
        for dim, val in self.fidelity.items():
            if not (0.0 <= val <= 1.0):
                raise ValueError(
                    f"Fidelity value for '{dim}' is {val}; must be in [0.0, 1.0]"
                )


# ---------------------------------------------------------------------------
# WitnessStructure
# ---------------------------------------------------------------------------

@dataclass
class WitnessStructure:
    """
    The complete witness graph for one claim.

    ``describe()`` returns a pure structural summary with no scoring.
    ``score(policy)`` delegates entirely to the supplied policy object.

    Raises ``ValueError`` at construction if the hop graph contains a cycle.
    """

    claim:     Claim
    witnesses: list[Witness]
    hops:      list[CustodyHop]

    def __post_init__(self) -> None:
        _assert_no_cycles(self.hops)

    # ------------------------------------------------------------------
    # Structural summary — no policy, no scoring
    # ------------------------------------------------------------------

    def describe(self) -> dict:
        """
        Return a deterministic structural summary of the witness graph.

        Keys
        ----
        n_witnesses          : total witness count
        n_independent        : witnesses whose id is not a hop destination
                               (they observed the claim directly, not via relay)
        hop_count            : number of custody hops
        age_seconds          : time.time() - claim.observed_at
        witness_class_counts : {class_name: count}
        fidelity_profile     : {dim: {min, mean, max}} across all hops
                               that specify that dimension (omitted if none do)
        """
        hop_destinations = {h.destination for h in self.hops}
        n_independent = sum(
            1 for w in self.witnesses if w.id not in hop_destinations
        )

        # fidelity profile: aggregate per dim across hops that specify it
        fidelity_profile: dict[str, dict[str, float]] = {}
        for dim in FIDELITY_DIMS:
            vals = [h.fidelity[dim] for h in self.hops if dim in h.fidelity]
            if vals:
                fidelity_profile[dim] = {
                    "min":  min(vals),
                    "mean": sum(vals) / len(vals),
                    "max":  max(vals),
                }

        return {
            "n_witnesses":          len(self.witnesses),
            "n_independent":        n_independent,
            "hop_count":            len(self.hops),
            "age_seconds":          time.time() - self.claim.observed_at,
            "witness_class_counts": dict(Counter(w.witness_class for w in self.witnesses)),
            "fidelity_profile":     fidelity_profile,
        }

    def score(self, policy: "Policy") -> float:
        """Delegate scoring entirely to the supplied policy object."""
        return policy.score(self)


# ---------------------------------------------------------------------------
# Cycle detection (DFS)
# ---------------------------------------------------------------------------

def _assert_no_cycles(hops: list[CustodyHop]) -> None:
    adj: dict[str, list[str]] = {}
    nodes: set[str] = set()
    for hop in hops:
        adj.setdefault(hop.source, []).append(hop.destination)
        nodes.add(hop.source)
        nodes.add(hop.destination)

    visited: set[str] = set()
    rec_stack: set[str] = set()

    def _dfs(v: str) -> bool:
        visited.add(v)
        rec_stack.add(v)
        for u in adj.get(v, []):
            if u not in visited:
                if _dfs(u):
                    return True
            elif u in rec_stack:
                return True
        rec_stack.discard(v)
        return False

    for node in nodes:
        if node not in visited:
            if _dfs(node):
                raise ValueError(
                    "Circular witness graph: cycles are not permitted in a custody chain"
                )
