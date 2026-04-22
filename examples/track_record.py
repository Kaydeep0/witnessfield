"""
examples/track_record.py
=========================
Demonstrates the prediction track record system:
- Emit synthetic predictions with vault records
- Resolve them to different outcomes
- Compute Beta posterior credibility from the record
- Show how the posterior updates with each resolution

Run: python examples/track_record.py
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import uuid
from witnessfield import vault_outcome_stats, track_record_report


def make_prediction(entity: str, claim: str) -> dict:
    return {
        "vault_record_id": uuid.uuid4().hex,
        "claim_type":      "prediction",
        "entity":          entity,
        "claim_text":      claim,
    }


def make_resolution(prediction_id: str, outcome: str) -> dict:
    return {
        "vault_record_id":       uuid.uuid4().hex,
        "claim_type":            "resolution_event",
        "propagation_source_id": prediction_id,
        "outcome":               outcome,
    }


def build_scenario(n_confirmed: int, n_refuted: int,
                   n_ambiguous: int = 0, n_expired: int = 0,
                   n_open: int = 0) -> list:
    """Build a synthetic vault with given outcome mix."""
    records = []

    def add(outcome):
        p = make_prediction("TEST", f"Test prediction ({outcome})")
        r = make_resolution(p["vault_record_id"], outcome)
        records.extend([p, r])

    for _ in range(n_confirmed):  add("confirmed")
    for _ in range(n_refuted):    add("refuted")
    for _ in range(n_ambiguous):  add("ambiguous")
    for _ in range(n_expired):    add("expired_unresolved")

    # Open predictions (no resolution yet)
    for i in range(n_open):
        records.append(make_prediction("TEST", f"Open prediction {i+1}"))

    return records


def main():
    sep  = "-" * 64
    sep2 = "=" * 64

    print("\n" + sep2)
    print("  Prediction Track Record Demo")
    print("  Witness Field Protocol v2.1 — vault_outcome_stats")
    print(sep2)

    # --- Scenario 1: No outcomes yet ---
    print("\n\n[Scenario 1] Fresh system — no resolved predictions")
    print(sep)
    records = build_scenario(0, 0, n_open=4)
    print(track_record_report(records))

    # --- Scenario 2: First few outcomes ---
    print("\n[Scenario 2] Early outcomes — 3 confirmed, 1 refuted")
    print(sep)
    records = build_scenario(3, 1, n_open=2)
    print(track_record_report(records))

    # --- Scenario 3: Mature track record ---
    print("\n[Scenario 3] Mature record — 7 confirmed, 3 refuted")
    print(sep)
    records = build_scenario(7, 3)
    print(track_record_report(records))

    # --- Scenario 4: With ambiguous and expired ---
    print("\n[Scenario 4] Mixed outcomes — 4 confirmed, 2 refuted, 3 ambiguous, 2 expired")
    print(sep)
    records = build_scenario(4, 2, n_ambiguous=3, n_expired=2)
    print(track_record_report(records))

    # --- Show step-by-step Beta update ---
    print("\n" + sep2)
    print("  Beta Posterior — step-by-step update")
    print("  Prior: Beta(1,1) = uniform mean = 0.500")
    print(sep2)
    print(f"\n  {'After N resolutions':<24}  {'confirmed':>10}  {'refuted':>8}  {'beta_mean':>10}")
    print(f"  {'-'*24}  {'-'*10}  {'-'*8}  {'-'*10}")

    cumulative = []
    outcomes = ["confirmed", "confirmed", "refuted", "confirmed",
                "confirmed", "refuted", "confirmed", "confirmed"]
    for i, outcome in enumerate(outcomes):
        p = make_prediction("DEMO", "Demo prediction")
        r = make_resolution(p["vault_record_id"], outcome)
        cumulative.extend([p, r])
        stats = vault_outcome_stats(cumulative)
        print(
            f"  {i+1} ({outcome:<9})           "
            f"  {stats['n_confirmed']:>10}  {stats['n_refuted']:>8}  "
            f"{stats['beta_mean']:>10.4f}"
        )

    final_stats = vault_outcome_stats(cumulative)
    print(f"\n  Final: Beta({final_stats['beta_alpha']:.1f}, {final_stats['beta_beta_']:.1f})")
    print(f"  Posterior mean = {final_stats['beta_mean']:.4f}")
    print(f"  Raw track record = {final_stats['track_record']:.4f}")
    print(f"\n  Ambiguous and expired outcomes carry no directional signal")
    print(f"  and are excluded from the Beta update.")
    print(f"\n  This is the same posterior used to score wallet accountability")
    print(f"  in helix_hop_fidelity() — your track record affects your fidelity score.\n")


if __name__ == "__main__":
    main()
