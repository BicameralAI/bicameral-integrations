# SPDX-License-Identifier: MIT

# AI Authorship Review Mod

Status: Built — `AiAuthorshipReviewMod` in [`connector.py`](connector.py), run via
`mods.contract.run_mod`.

Advisory mod for routing AI-authored evidence to human/QA review when it carries low-confidence
or unfinished-work markers — so a reviewer weighs an AI-generated change before it lands. Advisory
only: it annotates and routes; it never blocks or approves (see the
[mod safety contract](../README.md)).

## How it works

Pure, read-only function over `list[AdapterEmission]`, stdlib-only and deterministic:

- **Source gate** — fires only when `safe_id(source_id)` is one of the AI coding tools
  (`aider`, `cursor`, `copilot`, `claude_code`, `continue_dev`, `devin`). A non-AI source
  produces no output.
- **Uncertainty markers** — over an AI source, scans `title` + `body` + evidence excerpts
  (lowercased) for low-confidence / unfinished-work markers (`TODO`, `FIXME`, `untested`,
  `placeholder`, `unverified`, `stub`, `wip`, `not sure`, `i think`, `might be`, `best guess`,
  `needs review`, `double check`, `double-check`, `not tested`, `hallucination`, `hallucinated`).
  Alphanumeric terms word-boundary match; space/hyphen phrases substring match
  (via `mods._signals.matched_terms`). Markers are sorted + de-duplicated.

On an AI source with at least one marker it emits an `advisory_governance_result` naming the
markers, a `routing_hint` to `qa`, and a `suggested_review_question`. Source ids are passed
through `safe_id` so no generic name/email is echoed into a message or metadata.

## Outputs (mirror [`manifest.yaml`](manifest.yaml))

- `advisory_governance_result`
- `routing_hint`
- `suggested_review_question`

## References

See [references.md](references.md).
