"""
tests/test_witnessfield.py
==========================
Tests for witnessfield v1.0.0.

Run: pytest tests/test_witnessfield.py -v
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import math
import time
import unittest.mock
import pytest

from witnessfield import Claim, Witness, CustodyHop, WitnessStructure, FIDELITY_DIMS
from witnessfield.core import _assert_no_cycles
from witnessfield.policy import DefaultPolicy, geometric_mean, log_corroboration, Policy


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

FIXED_NOW  = 1_745_000_000.0          # 2025-04-18 approx
FIXED_THEN = FIXED_NOW - 365.25 * 86_400  # exactly 1 year ago


def make_claim(**kw) -> Claim:
    defaults = {"id": "c1", "content": "Test claim.", "observed_at": FIXED_THEN}
    return Claim(**{**defaults, **kw})


def make_witness(wid: str = "w1", wclass: str = "journalist_primary") -> Witness:
    return Witness(
        id=wid,
        witness_class=wclass,
        attested_content="Test.",
        observed_at=FIXED_THEN,
    )


def make_structure(
    witnesses=None,
    hops=None,
    claim=None,
) -> WitnessStructure:
    return WitnessStructure(
        claim=claim or make_claim(),
        witnesses=witnesses or [make_witness()],
        hops=hops or [],
    )


def all_dims(val: float) -> dict[str, float]:
    return {dim: val for dim in FIDELITY_DIMS}


# ---------------------------------------------------------------------------
# FIDELITY_DIMS constant
# ---------------------------------------------------------------------------

def test_fidelity_dims_is_tuple_of_seven():
    assert isinstance(FIDELITY_DIMS, tuple)
    assert len(FIDELITY_DIMS) == 7


def test_fidelity_dims_contains_expected_keys():
    for dim in ("reversibility", "accountability", "physical_trace",
                "independence", "specificity", "motivation_clean",
                "cross_referenceable"):
        assert dim in FIDELITY_DIMS


# ---------------------------------------------------------------------------
# CustodyHop validation
# ---------------------------------------------------------------------------

def test_custody_hop_valid():
    hop = CustodyHop(
        source="origin", destination="w1",
        fidelity={"reversibility": 0.9, "accountability": 0.8},
    )
    assert hop.fidelity["reversibility"] == 0.9


def test_custody_hop_unknown_dim_raises():
    with pytest.raises(ValueError, match="Unknown fidelity dimension"):
        CustodyHop(source="a", destination="b", fidelity={"nonexistent_dim": 0.5})


def test_custody_hop_value_above_1_raises():
    with pytest.raises(ValueError, match="must be in"):
        CustodyHop(source="a", destination="b", fidelity={"reversibility": 1.1})


def test_custody_hop_value_below_0_raises():
    with pytest.raises(ValueError, match="must be in"):
        CustodyHop(source="a", destination="b", fidelity={"reversibility": -0.1})


def test_custody_hop_empty_fidelity_allowed():
    hop = CustodyHop(source="a", destination="b", fidelity={})
    assert hop.fidelity == {}


def test_custody_hop_all_dims_allowed():
    hop = CustodyHop(source="a", destination="b", fidelity=all_dims(0.7))
    assert len(hop.fidelity) == 7


# ---------------------------------------------------------------------------
# WitnessStructure construction + cycle detection
# ---------------------------------------------------------------------------

def test_witness_structure_basic_construction():
    s = make_structure()
    assert s.claim.id == "c1"
    assert len(s.witnesses) == 1
    assert len(s.hops) == 0


def test_circular_witness_graph_raises():
    """A -> B -> A is a cycle; construction should raise."""
    claim = make_claim()
    w1 = make_witness("w1")
    w2 = make_witness("w2")
    hop1 = CustodyHop(source="w1", destination="w2", fidelity={})
    hop2 = CustodyHop(source="w2", destination="w1", fidelity={})
    with pytest.raises(ValueError, match="[Cc]ircular"):
        WitnessStructure(claim=claim, witnesses=[w1, w2], hops=[hop1, hop2])


def test_self_loop_raises():
    claim = make_claim()
    w = make_witness("w1")
    hop = CustodyHop(source="w1", destination="w1", fidelity={})
    with pytest.raises(ValueError, match="[Cc]ircular"):
        WitnessStructure(claim=claim, witnesses=[w], hops=[hop])


def test_three_node_cycle_raises():
    """A -> B -> C -> A is a cycle."""
    claim = make_claim()
    witnesses = [make_witness(f"w{i}") for i in range(3)]
    hops = [
        CustodyHop(source="w0", destination="w1", fidelity={}),
        CustodyHop(source="w1", destination="w2", fidelity={}),
        CustodyHop(source="w2", destination="w0", fidelity={}),
    ]
    with pytest.raises(ValueError, match="[Cc]ircular"):
        WitnessStructure(claim=claim, witnesses=witnesses, hops=hops)


def test_linear_hop_chain_allowed():
    """origin -> w1 -> w2 -> engine is a valid DAG, not a cycle."""
    claim = make_claim()
    w1 = make_witness("w1")
    w2 = make_witness("w2")
    hops = [
        CustodyHop(source="origin", destination="w1", fidelity={}),
        CustodyHop(source="w1",     destination="w2", fidelity={}),
        CustodyHop(source="w2",     destination="engine", fidelity={}),
    ]
    s = WitnessStructure(claim=claim, witnesses=[w1, w2], hops=hops)
    assert s is not None


# ---------------------------------------------------------------------------
# WitnessStructure.describe() — policy-free and deterministic
# ---------------------------------------------------------------------------

def test_describe_is_policy_free():
    """describe() requires no policy argument and returns a dict."""
    s = make_structure()
    desc = s.describe()
    assert isinstance(desc, dict)
    assert "n_witnesses" in desc
    assert "n_independent" in desc
    assert "hop_count" in desc


def test_describe_structural_fields_are_deterministic():
    """Calling describe() twice returns the same structural fields."""
    s = make_structure()
    d1 = s.describe()
    d2 = s.describe()
    for key in ("n_witnesses", "n_independent", "hop_count",
                "witness_class_counts", "fidelity_profile"):
        assert d1[key] == d2[key]


def test_describe_does_not_require_policy():
    """describe() must work with no policy in scope."""
    s = make_structure()
    # This should not import or call any Policy object
    desc = s.describe()
    assert desc["n_witnesses"] == 1


def test_describe_n_witnesses_correct():
    witnesses = [make_witness(f"w{i}") for i in range(4)]
    s = make_structure(witnesses=witnesses)
    assert s.describe()["n_witnesses"] == 4


def test_describe_n_independent_no_hops():
    """With no hops, all witnesses are independent."""
    witnesses = [make_witness(f"w{i}") for i in range(3)]
    s = make_structure(witnesses=witnesses, hops=[])
    assert s.describe()["n_independent"] == 3


def test_describe_n_independent_with_hops():
    """A witness that is a hop destination is NOT independent."""
    w1 = make_witness("w1")
    w2 = make_witness("w2")
    hop = CustodyHop(source="w1", destination="w2", fidelity={})
    s = make_structure(witnesses=[w1, w2], hops=[hop])
    # w2 is a destination => not independent; w1 is not a destination => independent
    assert s.describe()["n_independent"] == 1


def test_describe_witness_class_counts():
    witnesses = [
        make_witness("w1", "journalist_primary"),
        make_witness("w2", "journalist_primary"),
        make_witness("w3", "licensed_professional"),
    ]
    s = make_structure(witnesses=witnesses)
    counts = s.describe()["witness_class_counts"]
    assert counts["journalist_primary"] == 2
    assert counts["licensed_professional"] == 1


def test_describe_fidelity_profile_empty_when_no_hops():
    s = make_structure(hops=[])
    assert s.describe()["fidelity_profile"] == {}


def test_describe_fidelity_profile_per_dim():
    hop1 = CustodyHop(source="origin", destination="w1",
                      fidelity={"reversibility": 0.8, "accountability": 0.6})
    hop2 = CustodyHop(source="w1", destination="engine",
                      fidelity={"reversibility": 0.4, "accountability": 0.9})
    w1 = make_witness("w1")
    s = make_structure(witnesses=[w1], hops=[hop1, hop2])
    profile = s.describe()["fidelity_profile"]
    assert abs(profile["reversibility"]["min"]  - 0.4) < 1e-9
    assert abs(profile["reversibility"]["max"]  - 0.8) < 1e-9
    assert abs(profile["reversibility"]["mean"] - 0.6) < 1e-9
    assert abs(profile["accountability"]["mean"] - 0.75) < 1e-9


def test_describe_fidelity_profile_omits_unspecified_dims():
    hop = CustodyHop(source="origin", destination="w1",
                     fidelity={"reversibility": 0.7})
    s = make_structure(witnesses=[make_witness("w1")], hops=[hop])
    profile = s.describe()["fidelity_profile"]
    assert "reversibility" in profile
    assert "accountability" not in profile


# ---------------------------------------------------------------------------
# WitnessStructure.score() — delegates to policy
# ---------------------------------------------------------------------------

def test_score_delegates_to_policy():
    """score() must call policy.score() and return its result."""
    s = make_structure()

    class ConstantPolicy:
        def score(self, structure) -> float:
            return 0.42

    assert s.score(ConstantPolicy()) == 0.42


def test_swapping_policies_changes_score_not_structure():
    """Different policies give different scores; describe() is unchanged."""
    s = make_structure()

    class LowPolicy:
        def score(self, structure) -> float: return 0.1

    class HighPolicy:
        def score(self, structure) -> float: return 0.9

    desc1 = s.describe()
    s1 = s.score(LowPolicy())
    s2 = s.score(HighPolicy())
    desc2 = s.describe()

    assert s1 != s2
    for key in ("n_witnesses", "n_independent", "hop_count"):
        assert desc1[key] == desc2[key]


# ---------------------------------------------------------------------------
# Policy utilities
# ---------------------------------------------------------------------------

def test_geometric_mean_all_ones():
    assert abs(geometric_mean([1.0, 1.0, 1.0]) - 1.0) < 1e-9


def test_geometric_mean_collapses_on_zero():
    assert geometric_mean([0.8, 0.0, 0.9]) == 0.0


def test_geometric_mean_empty_returns_zero():
    assert geometric_mean([]) == 0.0


def test_geometric_mean_known_value():
    # sqrt(0.25) = 0.5
    assert abs(geometric_mean([0.25, 1.0]) - 0.5) < 1e-9


def test_log_corroboration_single_witness():
    assert log_corroboration(1, 0.75) == 1.0


def test_log_corroboration_increases_with_n():
    q1 = log_corroboration(1,  0.75)
    q5 = log_corroboration(5,  0.75)
    q10 = log_corroboration(10, 0.75)
    assert q10 > q5 > q1


# ---------------------------------------------------------------------------
# DefaultPolicy
# ---------------------------------------------------------------------------

def test_default_policy_from_legacy_priors_loads():
    policy = DefaultPolicy.from_legacy_priors()
    assert isinstance(policy, DefaultPolicy)
    assert "journalist_primary" in policy.w_base


def test_default_policy_score_returns_float():
    policy = DefaultPolicy.from_legacy_priors()
    s = make_structure()
    with unittest.mock.patch("time.time", return_value=FIXED_NOW):
        result = s.score(policy)
    assert isinstance(result, float)
    assert 0.001 <= result <= 0.999


def test_default_policy_score_clamped():
    """V is always in [0.001, 0.999]."""
    policy = DefaultPolicy(w_base={}, decay_lambda={})  # W=0 for all classes
    s = make_structure()
    with unittest.mock.patch("time.time", return_value=FIXED_NOW):
        result = s.score(policy)
    assert result == 0.001


def test_default_policy_higher_credibility_class_scores_higher():
    """journalist_primary (0.75) should score higher than anonymous_internet (0.01)."""
    policy = DefaultPolicy.from_legacy_priors()
    s_high = make_structure(witnesses=[make_witness("w1", "journalist_primary")])
    s_low  = make_structure(witnesses=[make_witness("w1", "anonymous_internet")])
    with unittest.mock.patch("time.time", return_value=FIXED_NOW):
        v_high = s_high.score(policy)
        v_low  = s_low.score(policy)
    assert v_high > v_low


def test_default_policy_older_claim_scores_lower():
    """Temporal decay: a 2-year-old claim should score lower than 1-year-old."""
    policy = DefaultPolicy.from_legacy_priors()
    claim_1yr = make_claim(observed_at=FIXED_NOW - 1 * 365.25 * 86400)
    claim_2yr = make_claim(observed_at=FIXED_NOW - 2 * 365.25 * 86400)
    s1 = make_structure(claim=claim_1yr)
    s2 = make_structure(claim=claim_2yr)
    with unittest.mock.patch("time.time", return_value=FIXED_NOW):
        v1 = s1.score(policy)
        v2 = s2.score(policy)
    assert v1 > v2


def test_default_policy_hop_fidelity_lowers_score():
    """A low-fidelity hop should lower C and thus V."""
    policy = DefaultPolicy.from_legacy_priors()
    s_no_hops   = make_structure(hops=[])
    s_low_hops  = make_structure(
        witnesses=[make_witness("w1")],
        hops=[CustodyHop(source="origin", destination="w1",
                         fidelity=all_dims(0.1))],
    )
    with unittest.mock.patch("time.time", return_value=FIXED_NOW):
        v_clean = s_no_hops.score(policy)
        v_low   = s_low_hops.score(policy)
    assert v_clean > v_low


# ---------------------------------------------------------------------------
# DefaultPolicy.from_legacy_priors() migration bridge
# ---------------------------------------------------------------------------

def test_legacy_priors_migration_fixture():
    """
    from_legacy_priors() must reproduce v0.x formula output for the
    canonical migration fixture: one journalist_primary witness, no hops,
    claim age = exactly 1 year.

    v0.x formula: V = W * Q * D * C
      W = 0.75  (journalist_primary)
      Q = 1.0   (N=1 independent)
      D = exp(-0.15 * 1.0)
      C = 1.0   (no hops)
    """
    policy = DefaultPolicy.from_legacy_priors()
    claim = Claim(id="migrate", content="Test.", observed_at=FIXED_THEN)
    w = Witness(id="w1", witness_class="journalist_primary",
                attested_content="Test.", observed_at=FIXED_THEN)
    structure = WitnessStructure(claim=claim, witnesses=[w], hops=[])

    with unittest.mock.patch("time.time", return_value=FIXED_NOW):
        actual = structure.score(policy)

    W = 0.75
    Q = 1.0
    D = math.exp(-0.15 * 1.0)
    C = 1.0
    expected = max(0.001, min(0.999, W * Q * D * C))

    assert abs(actual - expected) < 1e-4, (
        f"Migration fixture: expected {expected:.6f}, got {actual:.6f}"
    )


# ---------------------------------------------------------------------------
# Grep invariant: no blessed witness class names in protocol or policy code
# ---------------------------------------------------------------------------

def test_no_blessed_witness_class_in_core():
    """
    core.py must not contain strings 'helixhash', 'helix_anchored',
    or 'blockchain' as hardcoded witness class names.
    """
    import pathlib
    core_text = (
        pathlib.Path(__file__).parent.parent / "witnessfield" / "core.py"
    ).read_text()

    for bad in ("helixhash", "helix_anchored", "blockchain"):
        assert bad not in core_text, (
            f"core.py contains blessed witness class name '{bad}'"
        )


def test_no_blessed_witness_class_in_policy():
    """
    policy.py must not contain strings 'helixhash', 'helix_anchored',
    or 'blockchain' as hardcoded witness class names.
    """
    import pathlib
    policy_text = (
        pathlib.Path(__file__).parent.parent / "witnessfield" / "policy.py"
    ).read_text()

    for bad in ("helixhash", "helix_anchored", "blockchain"):
        assert bad not in policy_text, (
            f"policy.py contains blessed witness class name '{bad}'"
        )
