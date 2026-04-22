"""
examples/llm_calibration.py
============================
Demonstrates the difference between an unanchored LLM claim
and one backed by a HelixHash on-chain commit.

The central finding: LLM-generated content starts below the credibility
midline (V = 0.44). A single HelixHash commit lifts V to 0.68+, with
full decay resistance and a 15% anchor boost on top.

Run: python examples/llm_calibration.py
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from witnessfield import (
    score,
    score_report,
    compare_anchoring,
    calibration_table,
    witness_mean,
)


def scenario_bare_llm():
    """An LLM-generated claim with no external anchor."""
    return score({
        "witness_type":   "llm_unanchored",
        "N":              1,
        "T_years":        0.5,
        "claim_type":     "prediction",
        "anchor_strength": 0.0,
    })


def scenario_llm_anchored():
    """
    Same LLM claim, but committed on-chain via HelixHash.

    The commit provides:
    - witness_type upgrades to 'llm_helix_anchored' (W: 0.44 -> 0.68)
    - physical_trace = 1.0 (blockchain guarantee)
    - cross_referenceable = 1.0 (transaction hash verifiable by anyone)
    - temporal decay lambda reduced 90% (anchor_strength=1.0)
    - 15% anchor boost on V
    """
    commit = {
        "wallet":       "0xABCDEF1234567890abcdef1234567890abcdef12",
        "PT":           0.62,
        "committed_at": "2026-04-20T00:00:00",
        "tx_hash":      "0x" + "a1b2c3" * 10,
        "claim_type":   "prediction",
    }
    helix_history = [commit]

    return score({
        "witness_type":   "llm_helix_anchored",
        "N":              1,
        "T_years":        0.5,
        "claim_type":     "prediction",
        "anchor_strength": 1.0,
        "custody_hops":   [{"type": "helix", "commit": commit}],
        "helix_history":  helix_history,
    })


def scenario_multi_witness():
    """
    Regulatory filing confirmed by 3 independent licensed professionals.
    High credibility, structured custody chain, moderate time elapsed.
    """
    return score({
        "witness_type":    "licensed_professional",
        "N":               3,
        "sybil_resist":    0.85,   # professionals not coordinated
        "T_years":         1.5,
        "claim_type":      "regulatory_filing",
        "anchor_strength": 0.0,
        "R_institution":   1.0,
        "custody_hops": [
            {"type": "official_document"},
            {"type": "notarized"},
        ],
    })


def scenario_viral_social():
    """
    Claim backed by an institutional filing but retweeted 50,000 times.
    Social virality triggers asymmetry discount.
    """
    return score({
        "witness_type":    "institutional_statement",
        "N":               1,
        "T_years":         0.1,
        "claim_type":      "regulatory_status",
        "anchor_strength": 0.0,
        "N_social":        50_000,  # 50k reshares
    })


def main():
    print("\n" + "=" * 64)
    print("  LLM Calibration Demo — Witness Field Protocol v2.1")
    print("=" * 64)

    # --- Witness type table ---
    print("\n" + calibration_table())

    # --- Scenario comparisons ---
    scenarios = [
        ("Bare LLM prediction",          scenario_bare_llm()),
        ("LLM + HelixHash anchor",        scenario_llm_anchored()),
        ("3 licensed professionals",      scenario_multi_witness()),
        ("Institutional + 50k reshares",  scenario_viral_social()),
    ]

    print("\n" + "=" * 64)
    print("  Scenario Comparison")
    print("=" * 64)
    print(f"  {'Scenario':<36}  {'V':>6}  {'W_prov':>6}  {'D':>6}  {'C':>6}")
    print(f"  {'-'*36}  {'-'*6}  {'-'*6}  {'-'*6}  {'-'*6}")
    for name, r in scenarios:
        print(
            f"  {name:<36}  {r['V']:>6.4f}  {r['W_provenance']:>6.4f}  "
            f"{r['D']:>6.4f}  {r['C']:>6.4f}"
        )

    # --- Full report on the anchored LLM ---
    print("\n\nFull breakdown for 'LLM + HelixHash anchor':")
    anchored_params = {
        "witness_type":   "llm_helix_anchored",
        "N":              1,
        "T_years":        0.5,
        "claim_type":     "prediction",
        "anchor_strength": 1.0,
        "custody_hops":   [{"type": "helix", "commit": {
            "wallet": "0xABCDEF1234567890abcdef1234567890abcdef12",
            "PT": 0.62,
        }}],
        "helix_history":  [{
            "wallet": "0xABCDEF1234567890abcdef1234567890abcdef12",
            "PT": 0.62,
            "outcome": None,
        }],
    }
    print(score_report(anchored_params, title="LLM + HelixHash Anchor"))

    # --- Anchoring lift summary ---
    print(compare_anchoring(
        witness_type="llm_unanchored",
        claim_type="prediction",
        T_years=0.5,
    ))

    print("\nKey takeaways:")
    bare_mean   = witness_mean("llm_unanchored")
    anchor_mean = witness_mean("llm_helix_anchored")
    print(f"  llm_unanchored   W_base = {bare_mean:.3f}")
    print(f"  llm_helix_anchor W_base = {anchor_mean:.3f}")
    print(f"  Lift from anchoring:     +{anchor_mean - bare_mean:.3f}")
    print("  Plus: decay resistance +90%, V boost +15%")
    print("  A single HelixHash commit makes an LLM claim materially more credible.\n")


if __name__ == "__main__":
    main()
