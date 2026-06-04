# Aider Connector

Provider-facing Aider (aider.chat) adapter. **Status: Prototype** (catalog
source-control/developer-AI tooling, priority P1, default trust tier T0). A
candidate from the
[Integration Candidate Catalog](../../docs/INTEGRATION_CANDIDATE_CATALOG.md).

## Modes

- **Passive** — Aider auto-commits its edits and attributes them (`(aider)` in
  the git author/committer name, or a `Co-authored-by:` trailer). Each
  attributed commit record maps to one neutral `Observation` (`parse_commit`).
  Git attribution is Aider's most stable, documented, code-free provenance
  surface. No canonical-state writes — evidence adapter, not state authority
  (ADR-0008).

The live git-log walk, the opt-in `--analytics-log` JSONL, and the unversioned
`.aider.chat.history.md` transcript are deferred this cycle (see
[`auth.md`](auth.md)); this connector is the parse surface only.

## Surface

- `parse_commit(record)` — Aider git-commit record → `Observation` (commit
  subject → excerpt/title, with `hash` then an `aider-commit` terminal fallback;
  `hash` → ref; `author_name` → author; `authored_at` → timestamp;
  `attributed_by` (author/committer/co-author) + `short_hash` → metadata).
- `AiderConnector` — connector identity and capabilities (`PASSIVE`).

## References

- Canonical documentation: [references.md](references.md)
- Auth model (deferred): [auth.md](auth.md)
