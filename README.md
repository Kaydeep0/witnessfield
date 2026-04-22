# witnessfield

A computable evidence scoring library. Assigns a verifiability score V to any claim based on five measurable factors: who witnessed it, how many, how long ago, through what custody chain, and whether an on-chain anchor exists.

## Install

```bash
pip install witnessfield
```

## Quickstart

```python
from witnessfield import score

# An LLM-generated prediction with no external anchor
result = score({
    "witness_type":    "llm_unanchored",
    "N":               1,
    "T_years":         0.5,
    "claim_type":      "prediction",
    "anchor_strength": 0.0,
})
print(result["V"])   # 0.2441 — below the midline

# Same prediction committed on-chain via HelixHash
result = score({
    "witness_type":    "llm_helix_anchored",
    "N":               1,
    "T_years":         0.5,
    "claim_type":      "prediction",
    "anchor_strength": 1.0,
})
print(result["V"])   # 0.7823 — materially more credible
```

## The formula

```
V = W_provenance x Q x D x C x Anchor_boost x Asymmetry_discount
V clamped to [0.001, 0.999]
```

| Factor | What it measures |
|--------|-----------------|
| W_provenance | Witness credibility — Beta mean of the witness class, scaled by jurisdiction reliability |
| Q | Quantity of independent witnesses — logarithmic corroboration with sybil discount |
| D | Temporal decay — exponential with lambda per claim type |
| C | Custody chain fidelity — geometric mean of 7 dimensions per hop, multiplied across all hops |
| Anchor_boost | HelixHash on-chain anchor — 1.15x boost, lambda reduced by 90% |
| Asymmetry_discount | Viral social spread penalty — discounts institutional claims with >100 reshares |

## Witness types

Twelve witness classes calibrated as Beta distributions:

| Witness type | W_base (mean) | Notes |
|---|---|---|
| blockchain | 0.980 | Tamper-proof by protocol |
| federal_court | 0.950 | Durable legal record |
| licensed_professional | 0.850 | Credentialed, accountable |
| journalist_primary | 0.750 | Named, verified, primary source |
| institutional_statement | 0.700 | Official corporate/government release |
| journalist_secondary | 0.550 | Secondary report |
| llm_unanchored | 0.440 | Below midline — unreliable solo |
| llm_helix_anchored | 0.680 | Anchored LLM gains +24 points |
| social_primary_gps | 0.350 | Geotagged primary social post |
| social_secondary | 0.100 | Reshare or repost |
| friend_memory | 0.050 | Human recollection, high decay |
| anonymous_internet | 0.010 | Near-zero prior |

The central finding: `llm_unanchored` starts at 0.440 — below the credibility midline. A single HelixHash commit lifts this to 0.680, adds 90% decay resistance, and applies a 15% V boost.

## Seven fidelity dimensions

Every custody chain hop is scored on seven dimensions. The geometric mean is taken: any dimension at 0.0 collapses the entire hop to zero.

```python
FIDELITY_DIMS = [
    "reversibility",        # can the record be altered without detection?
    "accountability",       # is the witness identifiable and answerable?
    "physical_trace",       # does a tamper-evident physical record exist?
    "independence",         # is the witness free from the claim's beneficiary?
    "specificity",          # does the witness address this claim specifically?
    "motivation_clean",     # does the witness have clean motive (no conflict)?
    "cross_referenceable",  # can the claim be confirmed from an independent source?
]
```

A verbal statement with no notes collapses C to 0 because `physical_trace = 0`. This is intentional.

## Prediction track record

The library includes a Bayesian track record system for prediction scoring:

```python
from witnessfield import vault_outcome_stats

stats = vault_outcome_stats(vault_records)

print(stats["n_predictions"])  # 12
print(stats["track_record"])   # 0.75 (9 confirmed / 12 resolved)
print(stats["beta_mean"])      # 0.769 — Beta(10, 4) posterior mean
```

Beta prior starts at (1, 1) — uniform. Each `confirmed` adds to alpha; each `refuted` adds to beta. Ambiguous and expired outcomes carry no directional signal and are excluded from the update.

## HelixHash anchor scoring

```python
from witnessfield import score_commit, score_commits_file

commit = {
    "wallet":       "0xABCDEF...",
    "PT":           0.62,
    "committed_at": "2026-04-20T02:00:00",
    "tx_hash":      "0x...",
    "claim_type":   "on_chain_commit",
}
helix_history = [commit]

result = score_commit(commit, helix_history)
print(result["V"])                   # 0.999
print(result["fidelity"])            # geometric mean of 7 dims
print(result["wallet_track_record"]) # empirical or prior rate

# Score a full helix_commits.json file
results = score_commits_file("path/to/helix_commits.json")
```

## Use cases

**1. LLM calibration**: Score whether AI-generated claims meet the threshold for publication without additional sourcing.

**2. On-chain evidence anchoring**: Any commit to a public blockchain moves a claim from `llm_unanchored` (W=0.44) to `blockchain` (W=0.98).

**3. Prediction track records**: Build a Bayesian credibility posterior over time. The posterior feeds directly into wallet accountability scoring.

**4. Custody chain verification**: Score complex evidence chains (document -> notarization -> court filing) as a product of hop fidelities.

**5. Asymmetry detection**: Detect when viral social spread of an institutional claim should reduce its credibility weight.

## Reference implementation

Eigenstate Research uses Witness Field Protocol to score all information signals entering the GeniusFlow topology engine — 197 entities in tokenized settlement infrastructure.

- Research site: https://kaydeep0.github.io/eigenstate-research/
- On-chain commits: https://kaydeep0.github.io/eigenstate-research/onchain/
- Publications: https://paragraph.com/@eigenstate

## Demos

```bash
# LLM calibration: unanchored vs anchored V comparison
python examples/llm_calibration.py

# Prediction track record: Beta posterior walkthrough
python examples/track_record.py
```

## Tests

```bash
pytest tests/test_core.py -v
```

## Honest limitations

- W_base priors are calibrated by field observation, not formal experiment. The values encode the author's epistemic judgements about source reliability.
- The geometric mean fidelity formula means a single zero dimension collapses a hop entirely. This is intentional but aggressive.
- Anchor boost (1.15x) and lambda reduction (90%) are design parameters, not empirically derived constants.
- V scores the witnessing structure, not the content truth of the underlying claim. A well-witnessed false claim can have V = 0.99.

## License

MIT — Kirandeep Kaur, 2026
