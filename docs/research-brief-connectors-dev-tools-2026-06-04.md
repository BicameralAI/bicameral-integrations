# Research Brief

**Date**: 2026-06-04
**Analyst**: The Qor-logic Analyst
**Target**: Evaluate and prepare two AI-coding-tool connectors — **Continue** (continue.dev) and **Aider** (aider.chat) — as provider-neutral parse surfaces capturing developer-AI decision/implementation evidence.
**Scope**: Verify each tool emits an official-or-stable, documented, normalizable artifact (read-only); map onto `adapter.core` `Observation`/`normalize()`. Live ingestion (file-watch / git-log walk / HTTP sink) DEFERRED per the parse-surface convention. Sources: official docs + source repos (cited inline below; full citations in the cycle research agent transcript).

---

## Executive Summary

Both candidates clear the §4 evaluation criteria as **read-only, file/git-import evidence sources** that fit the existing `Observation` → `normalize()` seam with zero contract change. **Neither exposes a public read API or webhook** — both are ingested from local artifacts, so both are **Trust Tier T0** (file/git import). **Continue** is the stronger fit (**P1**): a purpose-built, schema-*versioned* "development data" JSONL surface. **Aider** (**P1**) is best ingested via its deterministic **git-commit attribution** (the only stable, documented, code-free provenance surface); its rich transcript file is unversioned and deferred. The producer sensitive screen (`FX-SEC-001`) is the relevant guard — both surfaces can carry source code/prompts. No blocking gaps → `/qor-plan` at L2.

## Findings

### F1 — Continue development data (T0, passive file import; dev-AI decision evidence)
Continue writes "development data" as local **JSONL** to `.continue/dev_data/` (configurable via `config.yaml` `data` block: a `file://` dir or an HTTP sink). The `data` block carries a **versioned `schema`** (`0.1.0` / `0.2.0`) and a `level` of `all | noCode` (`noCode` strips file contents, prompts, completions). Documented event types: `autocomplete`, `chatInteraction`, `chatFeedback`, `editInteraction`, `editOutcome`, `nextEditOutcome`, `nextEditWithHistory`, `quickEdit`, `tokensGenerated`, `toolUsage` (per-event schemas in `packages/config-yaml/src/schemas/data`). Map **one Observation per event**: `source_id="continue"`, `kind=<eventName>`, excerpt from the event's human-meaningful text (prompt/completion/edit summary when present) with an event-name terminal fallback, `timestamp` from the event ts when present, `metadata={schema, eventName, model?}`. **No public read API** (docs route all dev-data to local files or a user-hosted HTTP sink); Continue Hub cloud read-API for dev-data is **unverified → open question**. Mode PASSIVE.

### F2 — Aider git-commit attribution (T0, passive git import; implementation-evidence provenance)
Aider auto-commits by default and, by default, appends **`(aider)`** to the git author *and* committer name; flags toggle `--attribute-commit-message-author` (`"aider: "` subject prefix), `--attribute-co-authored-by` (adds a `Co-authored-by:` trailer). This makes git-log the **most stable, documented, deterministic** Aider evidence surface, and it is code-free at the metadata level. Map **one Observation per attributed commit record** `{hash, message, author_name, committer_name, authored_at, trailers}`: `source_id="aider"`, `ref=<hash>`, `kind="commit"`, `excerpt=<commit subject>` with hash fallback, `author=<author_name>`, `timestamp=<authored_at>`, `metadata={attributed_by: author|committer|co-author, short_hash}`. Mode PASSIVE.

### F3 — Aider secondary surfaces (DEFERRED)
`--analytics-log <file.jsonl>` is documented and structured but **opt-in** and deliberately **code/prompt-free** (PostHog event shape); `.aider.chat.history.md` carries the rich transcript but has **no versioned/documented schema** (markdown prose) → scraping-prone. Both are deferred to a follow-up; the connector's `auth.md` records them as the planned secondary modes. Primary build is F2 (git attribution).

### F4 — Contract fit + safety
Both: read-only parse surfaces emitting `Observation` → `pipeline.normalize()`; no canonical writes (ADR-0008). Non-empty-excerpt **terminal-literal** fallback required per SG-2026-06-04-G (normalize rejects blank excerpt; use `"continue-event"` / `"aider-commit"` floors). Fixtures synthetic/PII-safe (`example.com`, no Luhn PAN, no secret-shaped tokens) so `FX-SEC-001` + TruffleHog stay green. Continue's `level: noCode` is the operator's native redaction lever; document it in `auth.md`.

### F5 — Catalog placement
Neither is in the current catalog. Both belong in a new/used category — **§6.1 Source Control & Code Review** (developer-AI tooling evidence) or §10 Related Tooling. Both **P1** (high value after foundation), default trust tier **T0**, integration role "evidence + provenance", readiness Scaffold → Prototype this cycle.

## Blueprint Alignment

| Claim | Finding | Status |
|---|---|---|
| Candidate must have official API OR stable documented ingestable artifact | Continue: versioned dev-data JSONL; Aider: documented git attribution | MATCH |
| Evidence adapters, not state authorities (ADR-0008) | both read-only → Observation; no writes | MATCH |
| Trust-tier model (T0–T5) | both T0 (file/git import) | MATCH |
| Observation/AdapterEmission contract unchanged | both shapes fit existing fields | MATCH |
| Excerpt terminal-literal floor (SG-2026-06-04-G) | `"continue-event"` / `"aider-commit"` floors planned | MATCH |

No DRIFT.

## Recommendations

1. **[P1] `/qor-plan` at L2.** One plan, two connectors: Continue `parse_event(event)->Observation` (dev-data JSONL event) + Aider `parse_commit(record)->Observation` (git attribution) + `<Provider>Connector.observations` + synthetic fixture + end-to-end `normalize()` conformance test each.
2. **[P1] Defer live paths**: Continue file-watch/HTTP-sink + Hub API; Aider git-log walk, analytics JSONL, and chat-history parse — record in each `auth.md`; parse surface only.
3. **[P2] Catalog update**: add Continue + Aider rows (P1, T0) and a SHADOW_GENOME note.

## Updated Knowledge

SHADOW_GENOME **SG-2026-06-04-H** (proposed): AI-coding tools (Continue, Aider) expose evidence as *local artifacts*, not APIs — Continue via a schema-versioned dev-data JSONL (`level: noCode` is a native redaction lever), Aider via deterministic `(aider)` git-commit attribution (its rich transcript file is unversioned → defer). Ingest the stable surface; defer the fragile one.

---

_Research complete. Findings are advisory — implementation decisions remain with the Governor._
