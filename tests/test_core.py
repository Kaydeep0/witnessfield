"""
tests/test_core.py
==================
Unit tests for witnessfield.core and witnessfield.analysis.

Each test maps to a specific claim in the Witness Field Protocol spec.
Tests mirror the wfp.py test suite used in the GeniusFlow engine.

Run: pytest tests/test_core.py -v
"""

import sys, os, math, json, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from witnessfield.core import (
    WITNESS_TYPES, CLAIM_TYPE_LAMBDAS, FIDELITY_DIMS, DEFAULT_HOP_VECTORS,
    geometric_mean_7, wallet_track_record, vault_outcome_stats,
    helix_hop_fidelity, score, score_commit, score_commits_file,
    witness_mean, list_witness_types,
)
from witnessfield.analysis import (
    score_report, calibration_table, compare_anchoring,
    decay_curve, track_record_report,
)


# ---------------------------------------------------------------------------
# WITNESS TYPE CONSTANTS
# ---------------------------------------------------------------------------

def test_witness_types_has_12_entries():
    assert len(WITNESS_TYPES) == 12


def test_blockchain_highest_mean():
    """blockchain witness type should have the highest W_base."""
    means = {k: v["alpha"] / (v["alpha"] + v["beta"]) for k, v in WITNESS_TYPES.items()}
    assert max(means, key=means.get) == "blockchain"
    assert abs(means["blockchain"] - 0.98) < 0.01


def test_anonymous_internet_lowest_mean():
    means = {k: v["alpha"] / (v["alpha"] + v["beta"]) for k, v in WITNESS_TYPES.items()}
    assert min(means, key=means.get) == "anonymous_internet"
    assert means["anonymous_internet"] < 0.02


def test_llm_helix_anchored_above_unanchored():
    """Anchored LLM should have higher W_base than unanchored LLM."""
    w_anch = WITNESS_TYPES["llm_helix_anchored"]
    w_bare = WITNESS_TYPES["llm_unanchored"]
    mean_anch = w_anch["alpha"] / (w_anch["alpha"] + w_anch["beta"])
    mean_bare = w_bare["alpha"] / (w_bare["alpha"] + w_bare["beta"])
    assert mean_anch > mean_bare


def test_claim_type_lambdas_has_default():
    assert "default" in CLAIM_TYPE_LAMBDAS


def test_on_chain_commit_lowest_lambda():
    """on_chain_commit decays slowest (lowest lambda)."""
    assert CLAIM_TYPE_LAMBDAS["on_chain_commit"] < CLAIM_TYPE_LAMBDAS["prediction"]


def test_fidelity_dims_has_seven():
    assert len(FIDELITY_DIMS) == 7


# ---------------------------------------------------------------------------
# geometric_mean_7
# ---------------------------------------------------------------------------

def test_geometric_mean_7_all_ones():
    v = {dim: 1.0 for dim in FIDELITY_DIMS}
    assert abs(geometric_mean_7(v) - 1.0) < 1e-9


def test_geometric_mean_7_collapses_on_zero():
    v = {dim: 0.8 for dim in FIDELITY_DIMS}
    v["physical_trace"] = 0.0
    assert geometric_mean_7(v) == 0.0


def test_geometric_mean_7_missing_dim_defaults_to_half():
    """Missing dimensions default to 0.5, not 0."""
    # Only provide 1 dimension; rest default to 0.5
    result = geometric_mean_7({"reversibility": 1.0})
    assert result > 0.0
    expected = (1.0 * 0.5 ** 6) ** (1 / 7)
    assert abs(result - expected) < 1e-9


def test_geometric_mean_7_unit_vectors():
    """Known vector — all dims = 0.5, geometric mean = 0.5."""
    v = {dim: 0.5 for dim in FIDELITY_DIMS}
    assert abs(geometric_mean_7(v) - 0.5) < 1e-9


# ---------------------------------------------------------------------------
# wallet_track_record
# ---------------------------------------------------------------------------

def test_wallet_track_record_no_history():
    """Zero commits => prior = 0.50."""
    result = wallet_track_record("0xABC", [])
    assert abs(result - 0.50) < 1e-9


def test_wallet_track_record_prior_caps_at_075():
    """50 commits with no outcomes => prior = 0.75 (capped)."""
    history = [{"wallet": "0xABC", "outcome": None} for _ in range(50)]
    result = wallet_track_record("0xABC", history)
    assert abs(result - 0.75) < 1e-9


def test_wallet_track_record_empirical_rate():
    """4 confirmed of 5 resolved => 0.80."""
    history = (
        [{"wallet": "0xW", "outcome": "confirmed"}] * 4 +
        [{"wallet": "0xW", "outcome": "refuted"}]   * 1
    )
    result = wallet_track_record("0xW", history)
    assert abs(result - 0.80) < 1e-9


def test_wallet_track_record_case_insensitive():
    history = [{"wallet": "0xabc", "outcome": "confirmed"}]
    assert wallet_track_record("0xABC", history) == 1.0


def test_wallet_track_record_filters_by_wallet():
    history = [
        {"wallet": "0xAAA", "outcome": "confirmed"},
        {"wallet": "0xBBB", "outcome": "refuted"},
    ]
    r = wallet_track_record("0xAAA", history)
    assert abs(r - 1.0) < 1e-9


# ---------------------------------------------------------------------------
# vault_outcome_stats
# ---------------------------------------------------------------------------

def _make_records(n_confirmed=0, n_refuted=0, n_ambiguous=0, n_expired=0, n_open=0):
    import uuid
    records = []
    for _ in range(n_confirmed + n_refuted + n_ambiguous + n_expired):
        pid = uuid.uuid4().hex
        records.append({"vault_record_id": pid, "claim_type": "prediction"})
    idx = 0
    for out, count in [("confirmed", n_confirmed), ("refuted", n_refuted),
                       ("ambiguous", n_ambiguous), ("expired_unresolved", n_expired)]:
        for _ in range(count):
            records.append({
                "vault_record_id":       uuid.uuid4().hex,
                "claim_type":            "resolution_event",
                "propagation_source_id": records[idx]["vault_record_id"],
                "outcome":               out,
            })
            idx += 1
    for _ in range(n_open):
        records.append({"vault_record_id": uuid.uuid4().hex, "claim_type": "prediction"})
    return records


def test_vault_stats_empty():
    stats = vault_outcome_stats([])
    assert stats["n_predictions"] == 0
    assert stats["n_resolved"] == 0
    assert stats["track_record"] == 0.0


def test_vault_stats_counts():
    records = _make_records(n_confirmed=3, n_refuted=1, n_ambiguous=2)
    stats = vault_outcome_stats(records)
    assert stats["n_predictions"] == 6
    assert stats["n_confirmed"] == 3
    assert stats["n_refuted"] == 1
    assert stats["n_ambiguous"] == 2


def test_vault_stats_track_record():
    records = _make_records(n_confirmed=7, n_refuted=3)
    stats = vault_outcome_stats(records)
    assert abs(stats["track_record"] - 0.7) < 1e-6


def test_vault_stats_beta_prior_uniform():
    """Zero resolved: Beta(1,1), mean=0.5."""
    stats = vault_outcome_stats([])
    assert stats["beta_alpha"] == 1.0
    assert stats["beta_beta_"] == 1.0
    assert abs(stats["beta_mean"] - 0.5) < 1e-6


def test_vault_stats_beta_excludes_ambiguous():
    """Ambiguous outcomes do not move the Beta posterior."""
    records_clean    = _make_records(n_confirmed=2, n_refuted=1)
    records_plus_amb = _make_records(n_confirmed=2, n_refuted=1, n_ambiguous=5)
    s1 = vault_outcome_stats(records_clean)
    s2 = vault_outcome_stats(records_plus_amb)
    assert s1["beta_alpha"] == s2["beta_alpha"]
    assert s1["beta_beta_"] == s2["beta_beta_"]


def test_vault_stats_beta_excludes_expired():
    records = _make_records(n_confirmed=1, n_refuted=1, n_expired=10)
    stats = vault_outcome_stats(records)
    assert stats["beta_alpha"] == 2.0
    assert stats["beta_beta_"] == 2.0


def test_vault_stats_open_predictions_not_counted_as_resolved():
    records = _make_records(n_confirmed=1, n_open=4)
    stats = vault_outcome_stats(records)
    assert stats["n_predictions"] == 5
    assert stats["n_resolved"] == 1


# ---------------------------------------------------------------------------
# score() — core V computation
# ---------------------------------------------------------------------------

def test_score_returns_v_field():
    result = score({"witness_type": "blockchain"})
    assert "V" in result
    assert 0.001 <= result["V"] <= 0.999


def test_score_blockchain_no_decay_high_v():
    """Blockchain witness, fresh, fully anchored => V near ceiling."""
    result = score({
        "witness_type":    "blockchain",
        "T_years":         0.0,
        "anchor_strength": 1.0,
        "claim_type":      "on_chain_commit",
    })
    assert result["V"] >= 0.99


def test_score_anonymous_internet_low_v():
    result = score({"witness_type": "anonymous_internet"})
    assert result["V"] < 0.05


def test_score_temporal_decay_reduces_v():
    v_fresh = score({"witness_type": "blockchain", "T_years": 0.0})
    v_old   = score({"witness_type": "blockchain", "T_years": 5.0})
    assert v_old["V"] < v_fresh["V"]


def test_score_anchor_slows_decay():
    v_unanchored = score({"witness_type": "blockchain", "T_years": 2.0, "anchor_strength": 0.0})
    v_anchored   = score({"witness_type": "blockchain", "T_years": 2.0, "anchor_strength": 1.0})
    assert v_anchored["V"] > v_unanchored["V"]


def test_score_multiple_witnesses_raises_q():
    v_one  = score({"witness_type": "journalist_primary", "N": 1})
    v_many = score({"witness_type": "journalist_primary", "N": 10})
    assert v_many["Q"] > v_one["Q"]


def test_score_viral_social_triggers_asymmetry_discount():
    result = score({
        "witness_type": "institutional_statement",
        "claim_type":   "regulatory_status",
        "N_social":     50_000,
    })
    assert result["asymmetry_discount"] < 1.0


def test_score_viral_social_no_discount_below_threshold():
    result = score({
        "witness_type": "institutional_statement",
        "claim_type":   "regulatory_status",
        "N_social":     50,    # below 100 threshold
    })
    assert result["asymmetry_discount"] == 1.0


def test_score_verbal_hop_collapses_c():
    """verbal_trusted has physical_trace=0 => C=0 => V at floor."""
    result = score({
        "witness_type": "blockchain",
        "custody_hops": [{"type": "verbal_trusted"}],
    })
    assert result["C"] == 0.0
    assert result["V"] == 0.001


def test_score_helix_hop_uses_fidelity():
    commit = {"wallet": "0xW", "PT": 0.70, "committed_at": "2026-01-01T00:00:00"}
    history = [{"wallet": "0xW", "outcome": "confirmed"}]
    result = score({
        "witness_type": "blockchain",
        "custody_hops": [{"type": "helix", "commit": commit}],
        "helix_history": history,
    })
    assert result["C"] > 0.0
    assert result["C"] < 1.0


def test_score_unknown_witness_type_defaults_to_anonymous():
    result = score({"witness_type": "does_not_exist"})
    anon   = score({"witness_type": "anonymous_internet"})
    assert result["W_provenance"] == anon["W_provenance"]


def test_score_v_clamped_at_floor():
    result = score({"witness_type": "anonymous_internet", "T_years": 100.0})
    assert result["V"] >= 0.001


def test_score_v_clamped_at_ceiling():
    result = score({
        "witness_type":    "blockchain",
        "T_years":         0.0,
        "anchor_strength": 1.0,
        "N":               1000,
        "claim_type":      "on_chain_commit",
    })
    assert result["V"] <= 0.999


# ---------------------------------------------------------------------------
# score_commit()
# ---------------------------------------------------------------------------

def test_score_commit_returns_v():
    commit = {
        "wallet":       "0xABC",
        "PT":           0.62,
        "committed_at": "2026-01-01T00:00:00",
        "tx_hash":      "0x" + "a" * 64,
        "claim_type":   "on_chain_commit",
    }
    result = score_commit(commit, [commit])
    assert "V" in result
    assert result["V"] > 0.0


def test_score_commit_includes_tx_hash():
    commit = {"wallet": "0xW", "PT": 0.5, "tx_hash": "0xdeadbeef"}
    result = score_commit(commit, [commit])
    assert result["tx_hash"] == "0xdeadbeef"


def test_score_commit_high_pt_high_fidelity():
    """PT=1.0 means motivation_clean=1.0 in helix_hop_fidelity."""
    c_high = {"wallet": "0xW", "PT": 1.0, "outcome": "confirmed"}
    c_low  = {"wallet": "0xW", "PT": 0.01, "outcome": "confirmed"}
    r_high = score_commit(c_high, [c_high])
    r_low  = score_commit(c_low,  [c_low])
    assert r_high["fidelity"] > r_low["fidelity"]


# ---------------------------------------------------------------------------
# witness_mean / list_witness_types
# ---------------------------------------------------------------------------

def test_witness_mean_known_type():
    mean = witness_mean("blockchain")
    assert abs(mean - 490 / 500) < 1e-6


def test_witness_mean_unknown_returns_anonymous_value():
    mean = witness_mean("invented_type")
    anon = witness_mean("anonymous_internet")
    assert abs(mean - anon) < 1e-9


def test_list_witness_types_sorted_descending():
    types = list_witness_types()
    means = [t["mean"] for t in types]
    assert means == sorted(means, reverse=True)


def test_list_witness_types_length():
    assert len(list_witness_types()) == 12


# ---------------------------------------------------------------------------
# analysis — smoke tests
# ---------------------------------------------------------------------------

def test_score_report_returns_string():
    report = score_report({"witness_type": "blockchain"})
    assert isinstance(report, str)
    assert "V" in report


def test_calibration_table_returns_string():
    table = calibration_table()
    assert isinstance(table, str)
    assert "blockchain" in table


def test_compare_anchoring_returns_string():
    result = compare_anchoring()
    assert isinstance(result, str)
    assert "Lift" in result


def test_decay_curve_returns_string():
    curve = decay_curve(T_max_years=2.0, steps=4, claim_types=["prediction", "on_chain_commit"])
    assert isinstance(curve, str)
    assert "prediction" in curve


def test_track_record_report_empty():
    report = track_record_report([])
    assert isinstance(report, str)
    assert "0" in report


def test_track_record_report_with_outcomes():
    records = _make_records(n_confirmed=5, n_refuted=2)
    report = track_record_report(records)
    assert "5" in report
    assert "2" in report
