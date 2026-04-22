"""
witnessfield
============
Witness structure protocol — data structures and swappable scoring policy.

witnessfield describes the external witness structure around a claim.
The structure is the protocol. Scores are policy — one plausible
policy ships as DefaultPolicy, but the priors, weights, and thresholds
it uses are opinion, not measurement. Swap it for your own.

Quick start
-----------
>>> from witnessfield import Claim, Witness, WitnessStructure, FIDELITY_DIMS
>>> from witnessfield.policy import DefaultPolicy
>>>
>>> claim = Claim(id="c1", content="The rate changed.", observed_at=1745000000.0)
>>> w = Witness(id="w1", witness_class="journalist_primary",
...             attested_content="Rate changed.", observed_at=1745000000.0)
>>> structure = WitnessStructure(claim=claim, witnesses=[w], hops=[])
>>> structure.describe()["n_independent"]
1
>>> policy = DefaultPolicy.from_legacy_priors()
>>> structure.score(policy)
0.6455   # approximate — depends on age at call time
"""

from .core import (
    FIDELITY_DIMS,
    Claim,
    Witness,
    CustodyHop,
    WitnessStructure,
)

__version__ = "1.0.0"
__author__  = "Kirandeep Kaur"
__all__ = [
    "FIDELITY_DIMS",
    "Claim",
    "Witness",
    "CustodyHop",
    "WitnessStructure",
]
