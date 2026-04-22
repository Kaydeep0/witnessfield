"""
witnessfield.analysis
=====================
Reporting and calibration tools for the Witness Field Protocol.

Includes:
- score_report()        : human-readable breakdown of a single V computation
- calibration_table()   : witness type credibility table
- compare_anchoring()   : show V lift from HelixHash anchoring
- decay_curve()         : show how V decays over time for each claim type
- track_record_report() : print Beta posterior summary from vault records
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

from .core import (
    WITNESS_TYPES,
    CLAIM_TYPE_LAMBDAS,
    score,
    vault_outcome_stats,
    witness_mean,
    list_witness_types,
)


# ---------------------------------------------------------------------------
# SCORE REPORT
# ---------------------------------------------------------------------------

def score_report(params: Dict[str, Any], title: str = "WFP Score") -> str:
    """
    Generate a readable plain-text breakdown of a single V computation.

    Parameters
    ----------
    params : dict
        Same dict you would pass to score(). All keys optional.
    title : str
        Header label for the report.

    Returns
    -------
    str
        Formatted report ready for print().
    """
    result = score(params)
    sep  = "-" * 64
    sep2 = "=" * 64
    lines = [
        sep2,
        f"  {title}",
        f"  V = W x Q x D x C x Anchor x Asymmetry",
        sep2,
        "",
        f"  V (final verifiability score)  : {result['V']:.4f}",
        "",
        sep,
        "  Factor breakdown:",
        f"    W_provenance       : {result['W_provenance']:.4f}  (witness credibility)",
        f"    Q                  : {result['Q']:.4f}  (quantity / corroboration)",
        f"    D                  : {result['D']:.4f}  (temporal decay)",
        f"    C                  : {result['C']:.4f}  (custody chain fidelity)",
        f"    Anchor boost       : {result['anchor_boost']:.4f}  (HelixHash anchoring)",
        f"    Asymmetry discount : {result['asymmetry_discount']:.4f}  (viral spread penalty)",
        "",
        "  Inputs used:",
        f"    witness_type       : {params.get('witness_type', 'anonymous_internet')}",
        f"    N witnesses        : {params.get('N', 1)}",
        f"    sybil_resist       : {params.get('sybil_resist', 1.0)}",
        f"    virality           : {params.get('virality', 0.0)}",
        f"    N_effective        : {result['N_effective']}",
        f"    T_years elapsed    : {params.get('T_years', 0.0)}",
        f"    claim_type         : {params.get('claim_type', 'default')}",
        f"    anchor_strength    : {params.get('anchor_strength', 0.0)}",
        f"    R_institution      : {params.get('R_institution', 1.0)}",
        f"    N_social           : {params.get('N_social', 0)}",
        f"    custody_hops       : {len(params.get('custody_hops', []))} hop(s)",
        "",
        sep,
        f"  Note: {result['W_content_note']}",
        sep2,
        "  Kirandeep Kaur | 2026 | witnessfield",
        sep2,
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# WITNESS TYPE CALIBRATION TABLE
# ---------------------------------------------------------------------------

def calibration_table() -> str:
    """
    Return a formatted table of all 12 witness types and their Beta parameters.

    Useful for understanding the prior credibility assigned to each
    witness class before any domain-specific adjustment.
    """
    types = list_witness_types()
    sep  = "-" * 64
    sep2 = "=" * 64
    lines = [
        sep2,
        "  Witness Type Calibration Table",
        "  W_base = alpha / (alpha + beta)",
        sep2,
        f"  {'Type':<28}  {'alpha':>6}  {'beta':>6}  {'W_base':>8}",
        f"  {'-'*28}  {'-'*6}  {'-'*6}  {'-'*8}",
    ]
    for wt in types:
        bar_len = int(wt["mean"] * 20)
        bar = "#" * bar_len + "." * (20 - bar_len)
        lines.append(
            f"  {wt['type']:<28}  {wt['alpha']:>6}  {wt['beta']:>6}  "
            f"{wt['mean']:>8.3f}  [{bar}]"
        )
    lines += [
        sep,
        "  Interpretation:",
        "    blockchain (0.980): on-chain commit, tamper-proof by protocol",
        "    llm_unanchored (0.440): below the midline — unreliable solo",
        "    llm_helix_anchored (0.680): anchored LLM gains +24 points",
        "    anonymous_internet (0.010): near-zero prior — treat as noise",
        sep2,
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# ANCHORING COMPARISON
# ---------------------------------------------------------------------------

def compare_anchoring(
    witness_type: str = "llm_unanchored",
    claim_type: str = "prediction",
    T_years: float = 0.5,
    N: int = 1,
) -> str:
    """
    Show the V lift that comes from HelixHash anchoring.

    Compares three scenarios:
    1. Unanchored (anchor_strength=0.0)
    2. Fully anchored (anchor_strength=1.0, witness_type='blockchain')
    3. Anchored LLM (anchor_strength=1.0, witness_type='llm_helix_anchored')

    Parameters
    ----------
    witness_type : str
        Starting witness type (default: 'llm_unanchored').
    claim_type : str
        Claim type for temporal decay (default: 'prediction').
    T_years : float
        Time elapsed in years (default: 0.5).
    N : int
        Witness count (default: 1).
    """
    base_params = {
        "witness_type": witness_type,
        "claim_type":   claim_type,
        "T_years":      T_years,
        "N":            N,
    }

    v_bare   = score({**base_params, "anchor_strength": 0.0})
    v_anchor = score({**base_params, "anchor_strength": 1.0,
                      "witness_type": "blockchain"})
    v_llm    = score({**base_params, "anchor_strength": 1.0,
                      "witness_type": "llm_helix_anchored"})

    sep  = "-" * 64
    sep2 = "=" * 64
    lift_anchor = v_anchor["V"] - v_bare["V"]
    lift_llm    = v_llm["V"]   - v_bare["V"]
    lines = [
        sep2,
        "  HelixHash Anchoring Lift",
        f"  claim_type={claim_type}  T={T_years:.2f}yr  N={N}",
        sep2,
        f"  Scenario                      V       W_prov    D         C",
        f"  {'-'*28}  {'-'*6}  {'-'*8}  {'-'*8}  {'-'*8}",
        f"  Unanchored ({witness_type:<17})  {v_bare['V']:.4f}  "
        f"{v_bare['W_provenance']:.4f}    {v_bare['D']:.4f}    {v_bare['C']:.4f}",
        f"  Blockchain anchor              {v_anchor['V']:.4f}  "
        f"{v_anchor['W_provenance']:.4f}    {v_anchor['D']:.4f}    {v_anchor['C']:.4f}",
        f"  LLM + helix anchor             {v_llm['V']:.4f}  "
        f"{v_llm['W_provenance']:.4f}    {v_llm['D']:.4f}    {v_llm['C']:.4f}",
        sep,
        f"  V lift: unanchored -> blockchain   : +{lift_anchor:.4f}",
        f"  V lift: unanchored -> llm_anchored : +{lift_llm:.4f}",
        "",
        "  Why anchoring matters:",
        "    1. Temporal decay lambda reduced by 90% (anchor_strength=1.0)",
        "    2. Anchor boost multiplier adds 15% to V",
        "    3. Witness type upgrades from 0.44 (llm) to 0.98 (blockchain)",
        "    4. physical_trace and cross_referenceable dimensions become 1.0",
        sep2,
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# DECAY CURVE
# ---------------------------------------------------------------------------

def decay_curve(
    T_max_years: float = 5.0,
    steps: int = 10,
    claim_types: Optional[List[str]] = None,
) -> str:
    """
    Show how V decays over time for each claim type (unanchored).

    Parameters
    ----------
    T_max_years : float
        Maximum time horizon to show (default: 5 years).
    steps : int
        Number of time steps to display (default: 10).
    claim_types : list of str, optional
        Subset of claim types to show. Default: all.
    """
    if claim_types is None:
        claim_types = list(CLAIM_TYPE_LAMBDAS.keys())

    times = [T_max_years * i / steps for i in range(steps + 1)]
    sep  = "-" * 72
    sep2 = "=" * 72

    lines = [
        sep2,
        f"  Temporal Decay Curve (unanchored, witness='blockchain', T=0..{T_max_years:.0f}yr)",
        sep2,
    ]

    # Header
    header = f"  {'claim_type':<22}"
    for t in times[::2]:  # every other step to fit
        header += f"  T={t:.1f}"
    lines.append(header)
    lines.append(sep)

    for ct in claim_types:
        row = f"  {ct:<22}"
        for t in times[::2]:
            v = score({
                "witness_type":   "blockchain",
                "claim_type":     ct,
                "T_years":        t,
                "anchor_strength": 0.0,
            })
            row += f"  {v['V']:.3f}"
        lines.append(row)

    lines += [
        sep,
        "  Anchoring (anchor_strength=1.0) reduces lambda by 90% for all types.",
        "  Use compare_anchoring() to see the per-scenario lift.",
        sep2,
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# TRACK RECORD REPORT
# ---------------------------------------------------------------------------

def track_record_report(vault_records: List[Dict[str, Any]]) -> str:
    """
    Print a Beta posterior summary from prediction vault records.

    Parameters
    ----------
    vault_records : list of dict
        All vault records (predictions + resolution_events).
        Mirrors the schema in witnessfield.core.vault_outcome_stats().

    Returns
    -------
    str
        Formatted report with track record, Beta posterior, and interpretation.
    """
    stats = vault_outcome_stats(vault_records)
    sep  = "-" * 64
    sep2 = "=" * 64
    pct  = f"{stats['track_record']:.1%}" if stats["n_resolved"] > 0 else "N/A"

    beta_str = (
        f"Beta({stats['beta_alpha']:.1f}, {stats['beta_beta_']:.1f})  "
        f"mean = {stats['beta_mean']:.3f}"
    )

    lines = [
        sep2,
        "  Prediction Track Record",
        "  Witness Field Protocol — vault_outcome_stats",
        sep2,
        "",
        f"  Total predictions    : {stats['n_predictions']}",
        f"  Resolved             : {stats['n_resolved']}",
        f"  Unresolved (open)    : {stats['n_predictions'] - stats['n_resolved']}",
        "",
        sep,
        "  Outcome breakdown:",
        f"    Confirmed            : {stats['n_confirmed']}",
        f"    Refuted              : {stats['n_refuted']}",
        f"    Ambiguous            : {stats['n_ambiguous']}  (excluded from Beta)",
        f"    Expired unresolved   : {stats['n_expired']}  (excluded from Beta)",
        "",
        sep,
        "  Track record (confirmed / resolved):",
        f"    Raw rate             : {pct}",
        "",
        "  Bayesian posterior:",
        f"    {beta_str}",
        f"    Prior: Beta(1,1) = uniform",
        f"    Each confirmed: +1 to alpha",
        f"    Each refuted:   +1 to beta",
        f"    Ambiguous/expired: excluded",
        "",
        sep,
        "  Interpretation:",
    ]

    mean = stats["beta_mean"]
    if stats["n_resolved"] == 0:
        lines.append("    No resolved predictions yet. Prior = uniform Beta(1,1).")
    elif mean >= 0.70:
        lines.append(f"    Strong track record ({mean:.1%}). Predictions carry high credibility.")
    elif mean >= 0.50:
        lines.append(f"    Moderate track record ({mean:.1%}). More resolution data needed.")
    else:
        lines.append(f"    Weak track record ({mean:.1%}). Model calibration needs review.")

    lines += [
        sep2,
        "  Kirandeep Kaur | 2026 | witnessfield",
        sep2,
    ]
    return "\n".join(lines)
