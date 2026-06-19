<!-- GENERATED from config.json — do not edit; run scripts/build_mod_setup.py -->
# AI Authorship Review — mod setup

Advisory mod that routes AI-authored evidence (aider/cursor/copilot/claude_code/continue_dev/devin) carrying low-confidence/unfinished markers (TODO/FIXME/untested/not sure/hallucination/...) to human/QA review.

- **id** `ai_authorship_review` · **manifest** `ai-authorship-review` · **family** ai-safety · **version** 0.1.0 · **channel** beta
- **advisory only** (non-authoritative; ADR-0008) · **default enabled** True · **trust-gated** False

See [mods/README.md](README.md) for the general mod model + the mod safety contract.

## Advises on

AI-authored evidence (from an AI coding tool) that carries low-confidence or unfinished-work markers in title + body + evidence excerpts.

## Reads (evidence consumed)

- source_id (AI-coding source gate)
- title + body
- evidence excerpts

## Emits (advisory artifacts only)

- `advisory_governance_result`
- `routing_hint`
- `suggested_review_question`

## Can NEVER do (EM-safe boundary)

This mod is non-authoritative by construction — it may surface a concern, never act on it:
- `write_canonical_decision`
- `approve_signoff`
- `resolve_compliance`
- `create_blocking_ci_result`
- `bypass_governance_policy`
- `mutate_source_evidence`
- `collapse_confidence_score`

## Enable it (headless — no UI)

```bash
python -m runtime.cli run-mods <connector> --mods ai_authorship_review
```

Operator knobs:
_No operator knobs — enable/disable only._

## Requirements

- The neutral evidence stream (AdapterEmission) — no credentials, no live network.

## References

- scope: mods/ai_authorship_review/README.md
- mod-safety-contract: mods/README.md
- adr: docs/adr/0008-integrations-are-evidence-adapters-not-state-authorities.md
