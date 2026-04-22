# witnessfield

Describes the external witness structure around a claim. Scoring is a swappable policy — not the protocol.

v1.0 is a clean rewrite. In v0.x, scoring and priors were baked
into the protocol, which created circular dependencies between the
two libraries (HelixHash was a high-trust witness class inside
witnessfield, and witnessfield-style credibility values leaked into
HelixHash entries). v1.0 separates the protocol (what the library
guarantees) from policy (opinions about how to weight things).
HelixHash now only guarantees order and non-tampering. witnessfield
now only describes witness structure. Scoring is a separate,
swappable policy layer.

## Install

```bash
pip install witnessfield
```

## What it guarantees

**witnessfield describes the external witness structure around a claim.
The structure is the protocol. Scores are policy — one plausible
policy ships as DefaultPolicy, but the priors, weights, and thresholds
it uses are opinion, not measurement. Swap it for your own.**

## Quickstart

```python
from witnessfield import Claim, Witness, CustodyHop, WitnessStructure
from witnessfield.policy import DefaultPolicy

# Describe the structure — no scoring needed
claim = Claim(
    id="claim-001",
    content="The Federal Reserve will issue tokenized-asset guidance by 2026-12-31.",
    observed_at=1745000000.0,
)
journalist = Witness(
    id="w1",
    witness_class="journalist_primary",  # caller-assigned — library makes no assumption
    attested_content="WSJ reports Fed circulating draft guidance on tokenized settlement.",
    observed_at=1745000000.0,
)
structure = WitnessStructure(claim=claim, witnesses=[journalist], hops=[])

# Structural summary — no policy required
desc = structure.describe()
print(desc["n_witnesses"])    # 1
print(desc["n_independent"])  # 1
print(desc["hop_count"])      # 0

# Score with any Policy implementation
policy = DefaultPolicy.from_legacy_priors()  # loads v0.x calibration as a starting point
score  = structure.score(policy)
print(f"V = {score:.4f}")    # ~0.64 for a 1-year-old claim from a primary journalist
```

## Protocol structure

The protocol defines four dataclasses and one constant.

```python
FIDELITY_DIMS: tuple[str, ...] = (
    "reversibility",        # can the record be altered without detection?
    "accountability",       # is the witness identifiable and answerable?
    "physical_trace",       # does a tamper-evident physical record exist?
    "independence",         # is the witness free from the claim's beneficiary?
    "specificity",          # does the witness address this claim specifically?
    "motivation_clean",     # does the witness have clean motive (no conflict)?
    "cross_referenceable",  # can the claim be confirmed from an independent source?
)

@dataclass(frozen=True)
class Claim:
    id:          str
    content:     str
    observed_at: float

@dataclass(frozen=True)
class Witness:
    id:               str
    witness_class:    str           # free-form; policy decides meaning
    attested_content: str
    observed_at:      float
    signature:        Optional[bytes] = None

@dataclass(frozen=True)
class CustodyHop:
    source:      str               # witness id or "origin"
    destination: str               # witness id or "engine"
    fidelity:    dict[str, float]  # subset of FIDELITY_DIMS; values in [0, 1]

@dataclass
class WitnessStructure:
    claim:     Claim
    witnesses: list[Witness]
    hops:      list[CustodyHop]

    def describe(self) -> dict: ...     # structural summary, no scoring
    def score(self, policy) -> float:   # delegates to policy.score(self)
```

`CustodyHop` raises `ValueError` at construction if any fidelity key is not in
`FIDELITY_DIMS`, or if any value is outside `[0.0, 1.0]`.

`WitnessStructure` raises `ValueError` at construction if the hop graph contains
a cycle (cycles are meaningless in a custody chain).

## describe() — structural summary

```python
desc = structure.describe()
# {
#   "n_witnesses": 2,
#   "n_independent": 1,          # witnesses not receiving info from another witness
#   "hop_count": 1,
#   "age_seconds": 31557600.0,   # time.time() - claim.observed_at
#   "witness_class_counts": {"journalist_primary": 1, "licensed_professional": 1},
#   "fidelity_profile": {        # per FIDELITY_DIM across all hops
#       "reversibility": {"min": 0.7, "mean": 0.7, "max": 0.7},
#       ...
#   }
# }
```

`describe()` is deterministic and policy-free. Calling it with no policy,
or calling it before any policy is loaded, always works.

## Scoring is policy

```python
from witnessfield.policy import Policy, DefaultPolicy

class Policy(Protocol):
    def score(self, structure: WitnessStructure) -> float: ...
```

Implement the one-method Protocol with any callable to plug in your own scoring.

`DefaultPolicy` ships as a reference implementation. It uses:
- `w_base`: prior credibility per witness class
- `decay_lambda`: temporal decay rate per claim type
- `fidelity_aggregator`: how to aggregate hop fidelity dimensions (default: geometric mean)
- `quantity_fn`: how to aggregate witness count (default: log corroboration)

```python
policy = DefaultPolicy(
    w_base={"primary_source": 0.80, "secondary_report": 0.45},
    decay_lambda={"prediction": 0.70, "default": 0.15},
)
score = structure.score(policy)
```

## Migration from v0.x

```python
# Load the old priors exactly — use as a starting point, not production calibration
policy = DefaultPolicy.from_legacy_priors()
```

The v0.x priors are stored in `witnessfield/_legacy/legacy_priors.json` as a
data file. They are opinion, not measurement. `from_legacy_priors()` is a
migration bridge; replace it with your own calibrated priors.

The archived v0.x tag is `v0.1.0-archive`.

## Custody chain example

```python
hop1 = CustodyHop(
    source="origin",
    destination="w1",
    fidelity={
        "reversibility": 0.95,
        "accountability": 0.90,
        "physical_trace": 1.00,
        "independence":   0.85,
        "specificity":    0.95,
        "motivation_clean": 0.90,
        "cross_referenceable": 1.00,
    },
)
hop2 = CustodyHop(
    source="w1",
    destination="engine",
    fidelity={"reversibility": 0.80, "physical_trace": 0.60},
)

structure = WitnessStructure(claim=claim, witnesses=[w1], hops=[hop1, hop2])
desc = structure.describe()
# fidelity_profile["reversibility"]["mean"] == 0.875
# fidelity_profile["physical_trace"]["mean"] == 0.80
```

## Tests

```bash
pytest tests/test_witnessfield.py -v
```

Includes a grep test verifying that no blessed witness class names
(`"blockchain"`, `"helix_anchored"`, `"helixhash"`) appear in `core.py`
or `policy.py`. The library does not privilege any witness class.

## Honest limitations

- `DefaultPolicy` uses `"default"` lambda for all claims. Subclass it and
  override `score()` if you need per-claim-type decay.
- `describe()` uses `time.time()` for `age_seconds`. Mock it in tests for
  deterministic age values.
- No cryptographic signature verification in the protocol layer. If a
  `Witness.signature` is present, a policy may verify it; the library does not.

## License

MIT — Kirandeep Kaur, 2026
