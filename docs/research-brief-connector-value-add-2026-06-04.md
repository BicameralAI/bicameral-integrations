# Research Brief

**Date**: 2026-06-04
**Analyst**: The Qor-logic Analyst
**Target**: Net-new connector value-add pass — discover high-value candidate connectors NOT yet catalogued (or under-prioritized), assess each against the §4 evaluation criteria, and extend/re-rank the catalog.
**Scope**: Three clusters — (A) AI coding tools, (B) vulnerability/advisory data, (C) model/agent platforms. Bar (SG-2026-06-04-H): an official API/webhook OR a stable, documented, normalizable read-only artifact; no brittle scraping. Sources: official docs (cited in the cycle research transcript), grounded and tagged verified/uncertain.

---

## Executive Summary

The highest-value net-new connectors split cleanly by evidence class. **Supply-chain risk: build the aggregator, not the per-ecosystem feeds** — **OSV.dev** is a free, no-auth, versioned, read-only API that already aggregates GHSA-global, PyPA, and RustSec, so npm/RustSec/PyPA standalone connectors are redundant (the catalog's OSV row should move **P2 → P0**). **Developer-AI evidence is two distinct surfaces**: (1) local **transcripts/commits** (T0 file import — rich but secret-laden and unversioned: Claude Code, plus the already-built Continue/Aider), and (2) vendor **admin/usage-metrics APIs** (T1 read-only governance/leverage evidence, org-admin-key gated, no code: GitHub Copilot, Cursor, OpenAI, Anthropic). **Model/agent provenance** (Hugging Face model cards, LangSmith traces) rounds out §6.9. No code this pass — candidate evaluation + catalog update only.

## Findings

### F1 — OSV.dev is the supply-chain aggregator (re-prioritize P2 → P0)
Free, **no-auth**, no current rate limits; versioned REST (`/v1/query`, `/v1/querybatch`, `/v1/vulns/{id}`) with a published OpenAPI spec and a separately-maintained OSV schema [verified]. Aggregates GHSA, PyPA (PYSEC), RustSec, GSD — so it **subsumes** standalone npm / RustSec / PyPA advisory connectors (those drop to **P3**). Public vuln data only: no PII/code/secrets. **Mode**: active API (query by SBOM/lockfile entries). **Trust tier T1.** Risk: only the 32 MiB HTTP/1.1 response cap (use `querybatch` + HTTP/2). **The single clearest P0 in this pass.**

### F2 — Per-repo exposure: GHSA Dependabot alerts (the unique GitHub signal)
GHSA global data is already in OSV; the unique value is **per-repo Dependabot alerts** (your actually-exposed vulns) via GitHub GraphQL/REST + the full DB published as an OSV-format git repo (CC-BY-4.0, versioned) [verified]. Already represented by the catalog's **Dependabot (P1)** / **GitHub Code Scanning (P0)** rows — keep; note the OSV-mirror passive-file option.

### F3 — Developer-AI evidence surface 1: local transcripts/commits (T0 file)
**Claude Code** writes complete machine-readable JSONL session transcripts to `~/.claude/projects/<project>/<session>.jsonl` (messages, tool uses, tool results, file-mod tracking) + a slash-command history, and appends `Co-Authored-By: Claude` attribution to commits by default [verified]. Richest first-party implementation/decision/provenance evidence, **no API dependency** — same parse-surface class as the built Continue/Aider. **P0**, passive file import, **T0**. Risk: transcripts carry file contents/secrets/PII (mandatory redaction via `FX-SEC-001`) and the JSONL schema is documented but **not formally versioned** (tolerant parser, per SG-2026-06-04-I).

### F4 — Developer-AI evidence surface 2: vendor admin/usage-metrics APIs (T1)
Distinct from transcripts — read-only governance + AI-leverage evidence, **no source code**, but org/enterprise-admin-key gated and per-user (PII):
- **GitHub Copilot** — official usage-metrics REST (enterprise/org/team, signed download links; the post-2026-04 supported set) [verified]. **P1**, active API, T1.
- **Cursor** — official Admin API read endpoints (`daily-usage-data`, `filtered-usage-events`, `spend`, `audit-logs`, `members`) [verified]; use read endpoints only. **P1**, T1. Open question: Privacy Mode's effect on the usage surface [uncertain].
- **Windsurf** — UI dashboards only; **no official API endpoint confirmed** (post-acquisition docs redirect Windsurf→Devin) [uncertain]. **P2 / Deferred** pending a verifiable API.

### F5 — Model/agent platforms (provenance & access governance, §6.9)
- **OpenAI Admin API** — immutable `audit_logs` (key/user/project lifecycle) + groupable `usage` [verified]; no prompts/outputs exposed. **P1**, active API, T1; org-owner admin key.
- **Anthropic Admin API** — usage + cost reports (group_by model/workspace/key) [verified]; Enterprise Compliance activity feed [uncertain schema]. Pairs with F3 Claude Code for org-side provenance. **P1**, T1.
- **Hugging Face Hub** — model/dataset card metadata (license, eval results) via documented Cards API [verified]. **P2**, active API, T1. Risk: author-supplied metadata is inconsistently populated.
- **LangSmith** — runs/traces + eval scores via REST + Bulk Data Export [verified]. **P2**, T1. Risk: traces carry prompts/secrets/PII (same redaction class as F3).

### F6 — Contract fit
All clusters reduce to the existing read-only `parse_*(payload) -> Observation -> normalize()` seam (zero contract change). API-mode candidates (OSV, Copilot, Cursor, OpenAI/Anthropic/HF/LangSmith) are T1 (live fetch + auth deferred per the parse-surface convention); transcript candidates (Claude Code) are T0 file import. Every excerpt path needs the SG-2026-06-04-G terminal-literal floor; every external schema needs the SG-2026-06-04-I type/whitespace defense.

## Blueprint Alignment

| Claim | Finding | Status |
|---|---|---|
| Candidate must have official API OR stable documented artifact (SG-H) | OSV/Copilot/Cursor/OpenAI/Anthropic/HF/LangSmith APIs verified; Claude Code JSONL verified; Windsurf NOT | MATCH (Windsurf deferred) |
| Evidence adapters, not state authorities (ADR-0008) | all read-only (admin APIs use read endpoints only; transcripts are file reads) | MATCH |
| Build aggregators over redundant feeds | OSV subsumes npm/RustSec/PyPA → those P3 | MATCH |
| Trust-tier model | OSV/Copilot/Cursor/OpenAI/Anthropic/HF/LangSmith T1; Claude Code T0 | MATCH |

No DRIFT.

## Recommendations (ranked shortlist — top net-new value-add)

1. **[P0] OSV.dev** — free/no-auth/versioned aggregator; re-prioritize catalog OSV P2 → P0; mark npm/RustSec/PyPA P3 (subsumed).
2. **[P0] Claude Code** transcripts + commit attribution — passive JSONL (T0), richest first-party evidence; same surface as Continue/Aider.
3. **[P1] GitHub Copilot** usage metrics — official org/enterprise/team API (T1).
4. **[P1] Cursor** Admin API (read endpoints) — usage/spend/audit (T1); verify Privacy-Mode impact.
5. **[P1] OpenAI Admin/Audit API** — immutable audit log + usage (T1); Anthropic Admin API (T1) is the near-tie for Anthropic-API shops.

Secondary: GHSA Dependabot per-repo alerts (P1, covered by existing rows), Hugging Face Hub (P2), LangSmith (P2). Deferred: Windsurf (no verifiable API). All API/auth/live-fetch deferred per the parse-surface convention when built.

## Updated Knowledge

SHADOW_GENOME **SG-2026-06-04-J** (proposed): for advisory data, build the **aggregator** (OSV.dev — free/no-auth/versioned, subsumes GHSA-global/PyPA/RustSec) not the per-ecosystem feeds; and developer-AI evidence is **two surfaces** — local transcripts/commits (T0 file, rich + secret-laden + unversioned) vs vendor admin/usage-metrics APIs (T1 read-only, no code, org-admin-key gated). Choose the surface to the evidence class you want.

---

_Research complete. Findings are advisory — implementation decisions remain with the Governor._
