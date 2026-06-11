# Purple-Team Go-Live Assessment — Linear, Google Drive, Devin

**Date**: 2026-06-11
**Method**: multi-agent purple team — 8 red-team attack classes (read real source) x blue-team adversarial verification (default-skeptic, must trace the exploit past every existing defense) -> per-connector readiness synthesis. 35 agents, 24 findings, 17 confirmed real gaps.
**Boundary**: machine-side go-live readiness (parse -> screen -> live fetch -> GatewaySink -> gateway; + config descriptor -> mcp UI). Actual Live remains operator-gated (real secrets + live network; ADR-0012).

---

## Verdict (pre-fix): all three BLOCKED

The connector cores held (HMAC-before-parse, fail-closed PollError, FX-SEC-001 emit screen, token-free errors). Every confirmed gap was an edge / defense-in-depth in the SG-2026-06-05 family, one layer deeper.

| # | Issue | Severity | Connectors | Verdict |
|---|---|---|---|---|
| SSRF-1 | Transport follows provider 3xx, re-sends auth cross-host (token exfil + SSRF) | **HIGH (blocker)** | shared (all 3) | needs-fix |
| PII-1..4 / GATEWAY-1 | `_screen_sensitive` joins core wire fields -> cross-field PAN suppression; un-redacted url/ref email/phone | medium | shared + all 3 | needs-fix |
| PARSE-1 | Deeply-nested JSON -> uncaught RecursionError bypasses fail-closed parse | medium | shared (3 paths) | needs-fix |
| PARSE-2 | Devin `parse_session` `.strip()` on non-string scalar -> crash | medium | devin | needs-fix |
| PARSE-3 | Google Drive body walk type-confusion crash | low | google_drive | needs-fix |
| SSRF-4 | servicenow instance/fields raw-spliced into URL -> host/path/query injection | medium | shared | needs-fix |
| SECRET-LEAK-1 | GatewaySink reflects untrusted gateway body -> token disclosure | low | shared | needs-fix |
| CONFIG | runtime-key widening + unpinned credentialed endpoint | low | shared | accepted-risk (fixed) |
| DOS-1 | per-page cap but no aggregate cap (~800MB transient) | low | shared | accepted-risk (deferred) |

## Remediation (this cycle)

Fixed (issues #94-#100 + the cheap #101 items): no-follow redirect opener on `UrllibTransport` + `GatewaySink`; per-leaf `_screen_sensitive` (+ author/timestamp); `RecursionError` caught on all 3 parse paths; `gateway_mapping._source` redacts url/ref; servicenow host validation + urlencoded query + shared `_require_bare_host`/`_require_https_endpoint`; GatewaySink fixed-discriminator error (no body reflection); devin `_text` guard; google_drive body-walk isinstance guards + documentId fullmatch; runtime_config key allowlist; Linear endpoint host-pin + Devin https requirement. NO connector parse contract changed in a behavior-visible way for legitimate payloads (measured: full suite green).

Deferred as accepted-risk (issue #101): aggregate memory cap (DOS-1, bounded transient in a single-process run-once runner); within-field `order_id: <PAN>` suppression (deliberate catalog policy).

## Regression barriers

Every fix ships with a behavioral gate in `tests/redteam/test_redteam_gates.py` (28 tests) run by the new blocking `.github/workflows/red-team.yml` and the main `ci.yml` pytest set. Already-defended classes carry characterization tests.

## Post-fix readiness

All three connectors clear the blocker + every needs-fix gap; only documented accepted-risk items remain. **Machine-side go-live readiness: APPROVED (purple-team).** The operator live flip (real secrets + live network test + review per ADR-0012) is the sole remaining step; see each connector's `SETUP.md` go-live section + `wire_gates`.

---

_Assessment advisory; the fixes were implemented under the governed cycle sealed at META_LEDGER #133._
