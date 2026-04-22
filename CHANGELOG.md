# Changelog

## v1.0.0 — 2026-04-22

### BREAKING CHANGES

v1.0 is a clean rewrite. In v0.x, scoring and priors were baked
into the protocol, which created circular dependencies between the
two libraries (HelixHash was a high-trust witness class inside
witnessfield, and witnessfield-style credibility values leaked into
HelixHash entries). v1.0 separates the protocol (what the library
guarantees) from policy (opinions about how to weight things).
HelixHash now only guarantees order and non-tampering. witnessfield
now only describes witness structure. Scoring is a separate,
swappable policy layer.

### Removed

Everything hardcoded and scoring-related has been deleted:

- `WITNESS_TYPES` dict (12 hardcoded Beta priors) — removed from the protocol
- `CLAIM_TYPE_LAMBDAS` — removed from the protocol
- `DEFAULT_HOP_VECTORS` — removed
- `score()` as a top-level function — removed
- `compute_wfp()` — removed
- `helix_hop_fidelity()` — removed (HelixHash is no longer a privileged witness class)
- `wallet_track_record()` — removed
- `vault_outcome_stats()` — removed
- `score_commit()`, `score_commits_file()` — removed
- `witness_mean()`, `list_witness_types()` — removed
- `analysis.py` module — removed
- `examples/` directory — removed
- Hardcoded `Anchor_boost` (1.15x) — removed
- Hardcoded lambda-reduction (90%) — removed
- Hardcoded 100-reshare asymmetry threshold — removed
- `V = W * Q * D * C * Anchor * Asymmetry` formula from the core — removed

### Added / Rebuilt

**Protocol layer (`witnessfield/core.py`):**
- `FIDELITY_DIMS` — tuple of 7 dimension names
- `Claim` dataclass: `id`, `content`, `observed_at`
- `Witness` dataclass: `id`, `witness_class`, `attested_content`, `observed_at`, `signature`
- `CustodyHop` dataclass with validation: rejects unknown fidelity keys and out-of-range values
- `WitnessStructure` dataclass with `describe()` and `score(policy)`
- Cycle detection at construction time: circular witness graphs raise `ValueError`

**Policy layer (`witnessfield/policy.py`):**
- `Policy` Protocol: `score(structure) -> float`
- `geometric_mean(values)` utility
- `log_corroboration(n, w_base)` utility
- `DefaultPolicy(w_base, decay_lambda, fidelity_aggregator, quantity_fn)`
- `DefaultPolicy.from_legacy_priors()` — loads v0.x calibration values from data file

**Migration bridge:**
- `witnessfield/_legacy/legacy_priors.json` — v0.x priors as a data file
- `DefaultPolicy.from_legacy_priors()` — reproduces v0.x numbers for the
  canonical migration fixture (see `tests/test_witnessfield.py::test_legacy_priors_migration_fixture`)

### Invariants enforced by tests

- `WitnessStructure.describe()` is policy-free and produces identical structural
  output regardless of which policy is used
- No string `"blockchain"`, `"helix_anchored"`, or `"helixhash"` appears in
  `core.py` or `policy.py` (grep test)
- Circular hop graphs raise `ValueError` at construction

### Migration

`DefaultPolicy.from_legacy_priors()` gives you the old numbers as a starting
point. Migrate by:

1. Construct `Claim`, `Witness`, `CustodyHop`, `WitnessStructure` from your data
2. Call `structure.score(DefaultPolicy.from_legacy_priors())`
3. Verify output matches expectations using the migration fixture test
4. Replace `DefaultPolicy.from_legacy_priors()` with your own calibrated policy

The archived tag is `v0.1.0-archive`.

---

## v0.1.0 (archived at `v0.1.0-archive`)

Initial release. WFP formula `V = W * Q * D * C * Anchor * Asymmetry` with
hardcoded priors, 12 witness types, HelixHash as a privileged witness class,
and scoring baked into the core.
