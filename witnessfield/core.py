"""
witnessfield.core
=================
Witness Field Protocol v2.1 — computable evidence scoring.

Formula:
  V = W_provenance × Q × D × C × Anchor_boost × Asymmetry_discount
  V clamped to [0.001, 0.999]

Axiom: not all witnesses are equal.
       Kirandeep Kaur, 2026

The Witness Field Protocol assigns a verifiability score V to any claim
based on five computable factors: who witnessed it, how many, how long ago,
through what custody chain, and whether an on-chain anchor exists.

References
----------
- Eigenstate Research, Kirandeep Kaur (2026)
- Landauer (1961): minimum action per bit = k_B T ln(2)
- Bernstein & Smith (1994): Beta distribution as Bayesian credibility prior
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# CONSTANTS
# ---------------------------------------------------------------------------

# Beta distribution parameters per witness type.
# W_base = alpha / (alpha + beta)
# Uniform prior (1,1) updated by field observations of each witness class.
WITNESS_TYPES: Dict[str, Dict[str, float]] = {
    "blockchain":              {"alpha": 490, "beta": 10},    # mean = 0.980
    "federal_court":           {"alpha": 190, "beta": 10},    # mean = 0.950
    "licensed_professional":   {"alpha": 85,  "beta": 15},    # mean = 0.850
    "journalist_primary":      {"alpha": 75,  "beta": 25},    # mean = 0.750
    "institutional_statement": {"alpha": 70,  "beta": 30},    # mean = 0.700
    "journalist_secondary":    {"alpha": 55,  "beta": 45},    # mean = 0.550
    "llm_unanchored":          {"alpha": 44,  "beta": 56},    # mean = 0.440
    "llm_helix_anchored":      {"alpha": 68,  "beta": 32},    # mean = 0.680
    "social_primary_gps":      {"alpha": 35,  "beta": 65},    # mean = 0.350
    "social_secondary":        {"alpha": 10,  "beta": 90},    # mean = 0.100
    "friend_memory":           {"alpha": 5,   "beta": 95},    # mean = 0.050
    "anonymous_internet":      {"alpha": 1,   "beta": 99},    # mean = 0.010
}

# Temporal decay lambda per claim type (per year).
# Higher lambda = faster decay. Anchor reduces effective lambda by up to 90%.
CLAIM_TYPE_LAMBDAS: Dict[str, float] = {
    "on_chain_commit":     0.001,   # near-permanent
    "regulatory_filing":   0.04,    # decades relevant
    "court_record":        0.06,    # durable but fades
    "regulatory_status":   0.10,    # updates quarterly
    "financial_data":      0.30,    # stales quickly
    "social_content":      0.50,    # rapid decay
    "prediction":          0.70,    # ages fastest
    "person_memory":       0.20,    # human recall fades
    "default":             0.15,
}

# The seven dimensions of custody chain fidelity.
# Geometric mean: any dimension at 0.0 collapses the entire hop to 0.
FIDELITY_DIMS = [
    "reversibility",        # can the record be altered without detection?
    "accountability",       # is the witness identifiable and answerable?
    "physical_trace",       # does a tamper-evident physical record exist?
    "independence",         # is the witness free from the claim's beneficiary?
    "specificity",          # does the witness address this claim specifically?
    "motivation_clean",     # does the witness have clean motive (no conflict)?
    "cross_referenceable",  # can the claim be confirmed from an independent source?
]

# Pre-computed seven-dimension vectors for standard hop types.
# 'helix' is always computed from chain history via helix_hop_fidelity().
DEFAULT_HOP_VECTORS: Dict[str, Optional[Dict[str, float]]] = {
    "helix": None,  # computed dynamically from chain history
    "official_document": {
        "reversibility": 0.95, "accountability": 0.90, "physical_trace": 1.00,
        "independence": 0.85, "specificity": 0.95, "motivation_clean": 0.90,
        "cross_referenceable": 1.00,
    },  # geometric mean ~0.93
    "notarized": {
        "reversibility": 0.90, "accountability": 0.92, "physical_trace": 1.00,
        "independence": 0.80, "specificity": 0.90, "motivation_clean": 0.88,
        "cross_referenceable": 0.95,
    },  # ~0.90
    "verbal_trusted": {
        "reversibility": 0.20, "accountability": 0.70, "physical_trace": 0.00,
        "independence": 0.60, "specificity": 0.55, "motivation_clean": 0.85,
        "cross_referenceable": 0.20,
    },  # collapses to 0.0 — physical_trace=0 dominates via geometric mean
    "verbal_trusted_with_notes": {
        "reversibility": 0.40, "accountability": 0.70, "physical_trace": 0.50,
        "independence": 0.60, "specificity": 0.65, "motivation_clean": 0.85,
        "cross_referenceable": 0.50,
    },  # ~0.59
    "social_reshare": {
        "reversibility": 0.10, "accountability": 0.05, "physical_trace": 0.20,
        "independence": 0.30, "specificity": 0.40, "motivation_clean": 0.70,
        "cross_referenceable": 0.50,
    },  # ~0.23
    "llm_unanchored": {
        "reversibility": 0.40, "accountability": 0.70, "physical_trace": 0.20,
        "independence": 0.50, "specificity": 0.75, "motivation_clean": 0.65,
        "cross_referenceable": 0.30,
    },  # ~0.44
    "llm_helix_anchored": {
        "reversibility": 0.40, "accountability": 0.70, "physical_trace": 1.00,
        "independence": 0.50, "specificity": 0.75, "motivation_clean": 0.65,
        "cross_referenceable": 1.00,
    },  # ~0.68
}


# ---------------------------------------------------------------------------
# FIDELITY — seven-dimension geometric mean
# ---------------------------------------------------------------------------

def geometric_mean_7(vector: Dict[str, float]) -> float:
    """
    Compute the geometric mean of the seven fidelity dimensions.

    If any dimension is 0.0, returns 0.0.
    A motivated deceiver (motivation_clean=0) or absent physical trace
    (physical_trace=0) collapses the entire hop, regardless of how well
    the other six score. Missing dimensions default to 0.5.
    """
    product = 1.0
    for dim in FIDELITY_DIMS:
        val = float(vector.get(dim, 0.5))
        if val <= 0.0:
            return 0.0
        product *= val
    return product ** (1.0 / 7.0)


# ---------------------------------------------------------------------------
# WALLET ACCOUNTABILITY
# ---------------------------------------------------------------------------

def wallet_track_record(wallet_address: str, helix_history: List[Dict]) -> float:
    """
    Compute accountability score for a wallet from its on-chain commit history.

    Before any resolved outcomes:
        prior = min(0.75, 0.50 + 0.01 × N_commits)
        A wallet that has committed 32 times → prior = min(0.75, 0.82) = 0.75.

    After resolved outcomes exist:
        empirical = n_confirmed / n_resolved
        A wallet with 40 confirmed of 57 resolved → 40/57 = 0.70.

    Parameters
    ----------
    wallet_address : str
        EVM wallet address (case-insensitive).
    helix_history : list of dict
        Contents of helix_commits.json. Each dict should have keys:
        'wallet', 'outcome' (None if unresolved, else 'confirmed'/'refuted').
    """
    wallet_commits = [
        c for c in helix_history
        if c.get("wallet", "").lower() == wallet_address.lower()
    ]
    confirmed = sum(1 for c in wallet_commits if c.get("outcome") == "confirmed")
    total_resolved = sum(1 for c in wallet_commits if c.get("outcome") is not None)
    if total_resolved == 0:
        return min(0.75, 0.50 + 0.01 * len(wallet_commits))
    return confirmed / total_resolved


# ---------------------------------------------------------------------------
# PREDICTION TRACK RECORD
# ---------------------------------------------------------------------------

def vault_outcome_stats(vault_records: List[Dict]) -> Dict[str, Any]:
    """
    Join resolution_event records to their predictions.

    Computes accuracy statistics from a list of vault records that contain
    both prediction records and resolution_event records.

    Linking schema:
        resolution_event.propagation_source_id == prediction.vault_record_id

    Parameters
    ----------
    vault_records : list of dict
        All vault records (predictions + resolution_events + anything else).
        Records without claim_type are ignored.

    Returns
    -------
    dict with:
        n_predictions  : total prediction records
        n_resolved     : predictions with a matching resolution_event
        n_confirmed    : resolutions with outcome == "confirmed"
        n_refuted      : resolutions with outcome == "refuted"
        n_ambiguous    : resolutions with outcome == "ambiguous"
        n_expired      : resolutions with outcome == "expired_unresolved"
        track_record   : n_confirmed / n_resolved, or 0.0 if none resolved
        beta_alpha     : posterior alpha = 1 + n_confirmed
        beta_beta_     : posterior beta  = 1 + n_refuted
        beta_mean      : beta_alpha / (beta_alpha + beta_beta_)

    Beta prior starts at (1, 1) — uniform. Each confirmed adds to alpha;
    each refuted adds to beta. Ambiguous and expired carry no directional
    signal and are excluded from the Beta update.
    """
    prediction_ids = {
        r["vault_record_id"]
        for r in vault_records
        if r.get("claim_type") == "prediction" and r.get("vault_record_id")
    }
    n_predictions = len(prediction_ids)

    resolutions = [
        r for r in vault_records
        if r.get("claim_type") == "resolution_event"
        and r.get("propagation_source_id") in prediction_ids
    ]

    n_resolved   = len(resolutions)
    n_confirmed  = sum(1 for r in resolutions if r.get("outcome") == "confirmed")
    n_refuted    = sum(1 for r in resolutions if r.get("outcome") == "refuted")
    n_ambiguous  = sum(1 for r in resolutions if r.get("outcome") == "ambiguous")
    n_expired    = sum(1 for r in resolutions if r.get("outcome") == "expired_unresolved")

    track_record = n_confirmed / n_resolved if n_resolved > 0 else 0.0
    beta_alpha   = 1.0 + n_confirmed
    beta_beta_   = 1.0 + n_refuted
    beta_mean    = beta_alpha / (beta_alpha + beta_beta_)

    return {
        "n_predictions": n_predictions,
        "n_resolved":    n_resolved,
        "n_confirmed":   n_confirmed,
        "n_refuted":     n_refuted,
        "n_ambiguous":   n_ambiguous,
        "n_expired":     n_expired,
        "track_record":  round(track_record, 6),
        "beta_alpha":    beta_alpha,
        "beta_beta_":    beta_beta_,
        "beta_mean":     round(beta_mean, 6),
    }


# ---------------------------------------------------------------------------
# HELIX HOP FIDELITY
# ---------------------------------------------------------------------------

def helix_hop_fidelity(commit: Dict[str, Any], helix_history: List[Dict]) -> float:
    """
    Compute fidelity for a HelixHash custody hop from on-chain commit data.

    Five of the seven fidelity dimensions are automatically 1.0 for any
    on-chain HelixHash commit (blockchain guarantees):
        reversibility, physical_trace, independence,
        specificity, cross_referenceable

    Two are computed from chain history:
        accountability  = wallet_track_record(wallet, helix_history)
        motivation_clean = PT at time of commit (accumulated coherence)

    Parameters
    ----------
    commit : dict
        A single helix commit record. Must have 'wallet' and 'PT' keys.
    helix_history : list of dict
        Full helix_commits.json contents for track-record computation.
    """
    wallet = str(commit.get("wallet", ""))
    a = wallet_track_record(wallet, helix_history)
    m = float(commit.get("PT") or 0.5)
    m = max(0.001, min(1.0, m))
    return geometric_mean_7({
        "reversibility":       1.0,
        "accountability":      a,
        "physical_trace":      1.0,
        "independence":        1.0,
        "specificity":         1.0,
        "motivation_clean":    m,
        "cross_referenceable": 1.0,
    })


# ---------------------------------------------------------------------------
# CORE SCORING
# ---------------------------------------------------------------------------

def score(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compute the full Witness Field Protocol score V for a single claim.

    V = W_provenance × Q × D × C × Anchor_boost × Asymmetry_discount
    V clamped to [0.001, 0.999]

    Parameters
    ----------
    params : dict with these keys:

        witness_type (str, required)
            One of the 12 types in WITNESS_TYPES.
            Default: 'anonymous_internet'.

        N (int, default 1)
            Number of independent witnesses.

        sybil_resist (float, default 1.0)
            Corroboration discount — reduces effective N when witnesses
            may be coordinated (e.g., 0.3 for social reshares).

        virality (float, default 0.0)
            Correlation amplifier: how much network spread inflates
            apparent witness count. Higher = more discounted.

        T_years (float, default 0.0)
            Years elapsed since the original observation.

        claim_type (str, default 'default')
            Selects the temporal decay rate (lambda) from CLAIM_TYPE_LAMBDAS.

        anchor_strength (float, default 0.0)
            HelixHash anchor strength (0.0 to 1.0).
            1.0 = fully anchored on-chain, reduces temporal decay by 90%
            and adds a 15% credibility boost.

        R_institution (float, default 1.0)
            Jurisdiction reliability multiplier. Values > 1 for high-trust
            jurisdictions, < 1 for compromised legal systems.

        N_social (int, default 0)
            Social reshare count. Triggers asymmetry discount when
            viral social spread accompanies an institutional claim.

        custody_hops (list of dict, default [])
            Ordered list of custody chain hops. Each hop is a dict:
              {'type': 'helix', 'commit': commit_dict}
              {'type': 'social_reshare'}
              {'type': 'official_document'}
              {'type': 'custom', 'vector': {7 dim dict}}
            Fidelity of all hops is multiplied together to form C.
            Empty list: C = 1.0.

        helix_history (list of dict, default [])
            Contents of helix_commits.json. Required for 'helix' hop type
            to compute wallet track records.

    Returns
    -------
    dict with:
        V                  : final verifiability score [0.001, 0.999]
        W_provenance       : witness credibility (Beta mean × R_institution)
        Q                  : quantity corroboration factor
        D                  : temporal decay factor
        C                  : custody chain fidelity
        anchor_boost       : boost from HelixHash anchoring
        asymmetry_discount : discount for viral social spread on inst. claims
        N_effective        : effective witness count after sybil and virality
        W_content_note     : reminder that V scores structure, not content truth
    """
    # W_provenance
    wtype = str(params.get("witness_type", "anonymous_internet"))
    if wtype not in WITNESS_TYPES:
        wtype = "anonymous_internet"
    wt = WITNESS_TYPES[wtype]
    W_base = wt["alpha"] / (wt["alpha"] + wt["beta"])
    R_institution = float(params.get("R_institution", 1.0))
    W_provenance = min(1.0, W_base * R_institution)

    # Q — quantity corroboration
    N = max(1, int(params.get("N", 1)))
    sybil_resist = float(params.get("sybil_resist", 1.0))
    virality     = float(params.get("virality", 0.0))
    N_effective  = max(1.0, N * sybil_resist / max(1.0, 1.0 + virality))
    Q = 1.0 + math.log10(N_effective) * W_base if N_effective > 1.0 else 1.0

    # D — temporal decay
    T_years       = float(params.get("T_years", 0.0))
    claim_type    = str(params.get("claim_type", "default"))
    lam_base      = CLAIM_TYPE_LAMBDAS.get(claim_type, CLAIM_TYPE_LAMBDAS["default"])
    anchor_strength = float(params.get("anchor_strength", 0.0))
    lam_eff       = lam_base * (1.0 - anchor_strength * 0.90)
    D = math.exp(-lam_eff * max(0.0, T_years))

    # C — custody chain fidelity
    custody_hops  = list(params.get("custody_hops", []))
    helix_history = list(params.get("helix_history", []))
    fidelities: List[float] = []
    for hop in custody_hops:
        hop_type = str(hop.get("type", ""))
        if hop_type == "helix":
            commit_dict = hop.get("commit", {})
            if not isinstance(commit_dict, dict):
                commit_dict = {}
            f = helix_hop_fidelity(commit_dict, helix_history)
        elif hop_type == "custom":
            f = geometric_mean_7(hop.get("vector", {}))
        else:
            dv = DEFAULT_HOP_VECTORS.get(hop_type)
            f = geometric_mean_7(dv) if dv is not None else 0.5
        if hop.get("is_aggregation") and int(hop.get("N_sources", 0)) > 1:
            f = min(1.0, f * (1.0 + 0.1 * math.log(int(hop["N_sources"]))))
        fidelities.append(f)
    C = 1.0
    for f in fidelities:
        C *= f

    # Anchor boost
    anchor_boost = 1.0 + 0.15 * anchor_strength

    # Asymmetry discount
    N_social = int(params.get("N_social", 0))
    _institutional = {"on_chain_commit", "regulatory_filing", "court_record", "regulatory_status"}
    if N_social > 100 and claim_type in _institutional:
        asymmetry_discount = max(0.30, 1.0 - math.log10(max(1, N_social)) / 10.0)
    else:
        asymmetry_discount = 1.0

    V_raw = W_provenance * Q * D * C * anchor_boost * asymmetry_discount
    V = max(0.001, min(0.999, V_raw))

    return {
        "V":                  round(V, 6),
        "W_provenance":       round(W_provenance, 6),
        "Q":                  round(Q, 6),
        "D":                  round(D, 6),
        "C":                  round(C, 6),
        "anchor_boost":       round(anchor_boost, 6),
        "asymmetry_discount": round(asymmetry_discount, 6),
        "N_effective":        round(N_effective, 2),
        "W_content_note": (
            "W_provenance scores witnessing structure, not content truth. "
            "Content truth evaluated separately."
        ),
    }


# ---------------------------------------------------------------------------
# HELIX COMMIT SCORING
# ---------------------------------------------------------------------------

def score_commit(
    commit: Dict[str, Any],
    helix_history: List[Dict],
) -> Dict[str, Any]:
    """
    Score a single HelixHash on-chain commit as a WFP claim.

    Automatically sets witness_type='blockchain', claim_type='on_chain_commit',
    anchor_strength=1.0, and computes T_years from the commit's timestamp.
    """
    wallet = str(commit.get("wallet", ""))
    T_years = 0.0
    try:
        t = datetime.fromisoformat(str(commit.get("committed_at", "")))
        if t.tzinfo is None:
            t = t.replace(tzinfo=timezone.utc)
        T_years = max(0.0, (datetime.now(timezone.utc) - t).total_seconds() / (365.25 * 86400))
    except Exception:
        pass

    result = score({
        "witness_type":    "blockchain",
        "N":               1,
        "T_years":         T_years,
        "claim_type":      commit.get("claim_type", "on_chain_commit"),
        "anchor_strength": 1.0,
        "custody_hops":    [{"type": "helix", "commit": commit}],
        "helix_history":   helix_history,
    })
    result["fidelity"]           = round(helix_hop_fidelity(commit, helix_history), 6)
    result["wallet_track_record"] = round(wallet_track_record(wallet, helix_history), 6)
    result["PT_at_commit"]       = float(commit.get("PT") or 0.5)
    result["T_years"]            = round(T_years, 4)
    result["tx_hash"]            = commit.get("tx_hash", "")
    result["block_number"]       = commit.get("block_number")
    result["committed_at"]       = commit.get("committed_at", "")
    return result


def score_commits_file(path: str) -> List[Dict[str, Any]]:
    """
    Read a helix_commits.json file and score each commit.
    Returns results sorted by V descending.
    """
    p = Path(path)
    if not p.is_file():
        return []
    try:
        commits = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return []
    if not isinstance(commits, list):
        return []
    results = [score_commit(c, commits) for c in commits]
    results.sort(key=lambda x: x.get("V", 0), reverse=True)
    return results


# ---------------------------------------------------------------------------
# WITNESS TYPE LOOKUP
# ---------------------------------------------------------------------------

def witness_mean(witness_type: str) -> float:
    """Return the Beta mean for a witness type. Returns 0.01 for unknown types."""
    wt = WITNESS_TYPES.get(witness_type, WITNESS_TYPES["anonymous_internet"])
    return wt["alpha"] / (wt["alpha"] + wt["beta"])


def list_witness_types() -> List[Dict[str, Any]]:
    """Return all witness types sorted by mean credibility descending."""
    result = []
    for name, params in WITNESS_TYPES.items():
        mean = params["alpha"] / (params["alpha"] + params["beta"])
        result.append({
            "type":   name,
            "alpha":  params["alpha"],
            "beta":   params["beta"],
            "mean":   round(mean, 3),
        })
    return sorted(result, key=lambda x: x["mean"], reverse=True)
