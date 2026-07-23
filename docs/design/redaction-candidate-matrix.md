# Redaction backend candidate matrix

**Status:** Evaluation evidence for ADR-0020 (issues #277, #278)
**Owner:** Kevin Knapp
**Research date:** 2026-07-23
**Sources:** primary only (PyPI metadata, project repositories, official docs, Hugging Face model cards, OSV/GHSA advisories)

This matrix records every candidate investigated for the alpha redaction
boundary, including candidates rejected before implementation. Verdicts here
are eligibility calls, not the selection. Selection happens in issue #280
after the measured comparison.

Machine-readable form: `artifacts/redaction-evaluation/candidate-matrix.json`.

## Implemented configurations

### 1. bicameral-stdlib-v1 (baseline)

| Property | Value |
|---|---|
| Identity | `bicameral-stdlib-redaction` 1.0.0, ruleset `fx-sec-001-plus-pii-v1` (in-repo) |
| Maintenance | Owned by this repository; reviewed at PR #269 head `fd69ff27` |
| License | MIT (repo license) |
| Python / OS | Any supported repo target; stdlib `re` only |
| Offline | Fully offline, zero network paths |
| Dependencies | None beyond the Python standard library |
| Package / model size | 0 bytes beyond the repo; no model |
| Training data | None (pure rules) |
| Custom recognizers | The catalog itself (FX-SEC-001 secret/PHI/PAN + email/phone) |
| Determinism | Deterministic by construction (regex + Luhn) |
| Initialization | None; no cold start |
| Known limitations | No person-name, address, DOB, government-id, IP, or contextual detection; bare national phone numbers without a dialing prefix or keyword are a documented residual |
| Vulnerabilities | None (no third-party code) |
| Upgrade / rollback | Repo commit; trivially reversible |
| Verdict | **Implemented (baseline).** The engine the challenger must beat |

### 2. presidio-spacy-lg-v1

Presidio analyzer with a pinned conventional local NLP engine plus Bicameral
custom recognizers (the required "Presidio with custom recognizers"
configuration folded into one pinned config).

| Property | Value |
|---|---|
| Identity | presidio-analyzer 2.2.364 + presidio-anonymizer 2.2.364 (released 2026-07-22), spaCy 3.8.14, `en_core_web_lg` 3.8.0, plus Bicameral secret/PHI pattern recognizers |
| Maintenance | Active, roughly quarterly releases. Governance caveat: Presidio transferred from Microsoft to the community Data Privacy Stack org in June 2026 (release 2.2.363). Activity is currently high, but there is no longer a corporate owner behind releases or security response |
| License | MIT end to end (presidio, spaCy, and the `en_core_web_sm/lg` model wheels are all MIT) |
| Python / OS | Python >=3.10,<3.15 (3.13 in range); Windows, Linux, macOS first class |
| Offline | Fully offline once model wheels are installed, with one trap: the URL recognizer path uses `tldextract`, which fetches the Public Suffix List over HTTP on first use (presidio issue #1205). This evaluation excludes the URL recognizer and pins `suffix_list_urls=()` semantics; a production adoption must do the same |
| Dependencies | spacy, numpy, click, regex, tldextract, pyyaml, phonenumbers, pydantic (analyzer); cryptography only (anonymizer) |
| Package / model size | analyzer wheel ~266 KB; heavy weight is spaCy + numpy; `en_core_web_lg` 382 MB (`sm` is 12 MB at NER F 0.843 vs lg 0.855) |
| Training data | spaCy `en_core_web_*` models: OntoNotes 5 + word vectors (Explosion-published) |
| Custom recognizers | First class (`PatternRecognizer`, deny lists, context enhancement, YAML registry) |
| Determinism | spaCy inference is reproducible for a fixed model + input within one platform and environment; bit identity across OS/BLAS builds is not promised (Explosion discussion #11169). Evaluated per pinned environment |
| Initialization | Model load at engine construction; measured in the benchmark artifact |
| Known limitations | Project FAQ states no completeness guarantee; recognizer coverage is English/US biased; country-specific recognizers ship disabled by default since 2.2.359 as a precision posture; one NER model per language |
| Vulnerabilities | Zero OSV advisories for presidio packages and for base spaCy as of 2026-07-23. (`spacy-llm` SSTI advisory is not in this dependency set) |
| Upgrade / rollback | pip pins; spaCy model wheels pinned by direct release URL + hash; rollback is a pin revert |
| Verdict | **Implemented.** The required conventional Presidio configuration |

### 3. presidio-gliner-pii-v1

Presidio analyzer with the official `GLiNERRecognizer` (predefined since
presidio 2.2.360) and the pinned `urchade/gliner_multi_pii-v1` model, plus the
same Bicameral secret/PHI pattern recognizers.

| Property | Value |
|---|---|
| Identity | presidio-analyzer 2.2.364, gliner 0.2.27 (2026-06-15), model `urchade/gliner_multi_pii-v1` pinned at revision `1fcf13e85f4eef5394e1fcd406cf2ca9ea82351d`, torch 2.13.0 CPU, transformers 5.6.2, `en_core_web_sm` 3.8.0 for tokenization only |
| Maintenance | gliner is actively maintained (releases every 1 to 3 months) but pre-1.0 with no semver stability promise; presidio pins `gliner>=0.2.26,<1.0.0` |
| License | Apache-2.0 for gliner and for the whole candidate model set (`gliner_multi_pii-v1`, its `gliner_multi-v2.1` parent, knowledgator and gretel variants). No non-commercial restriction in this lane |
| Python / OS | Full stack installable on Python 3.13 Windows/Linux (torch cp313 Windows wheels since 2.6.0) |
| Offline | Offline after a one-time Hugging Face download; enforced via `HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`, `HF_HUB_DISABLE_TELEMETRY=1`, `local_files_only`, and a commit-pinned `revision` |
| Dependencies | torch >=2.0 (>=2.6 mandated here, see vulnerabilities), transformers, huggingface_hub, onnxruntime (core dep), sentencepiece, tqdm |
| Package / model size | model `pytorch_model.bin` 1.16 GB fp32 (~289M params, mdeberta-v3-base backbone); torch CPU adds several hundred MB installed |
| Training data | Synthetic LLM-generated PII data (`urchade/synthetic-pii-ner-mistral-v1`); model card publishes no benchmark for this model |
| Custom recognizers | Zero-shot labels at runtime; recall is sensitive to exact label wording, so the label list is frozen in the candidate configuration digest |
| Determinism | Pure forward pass + threshold decoding, no sampling; deterministic on one pinned platform/thread configuration; PyTorch explicitly does not promise cross-platform bit identity. Verified by repeated runs in this evaluation |
| Initialization | Full fp32 checkpoint deserialization; cold start and memory measured in the benchmark artifact |
| Known limitations | 384 word-token window forces chunking with offset remapping for long fields; ~50 label practical ceiling per prompt; published GLiNER PII numbers are on synthetic distributions; the flagship checkpoint ships only `pytorch_model.bin` (no safetensors) |
| Vulnerabilities | torch CVE-2025-32434 (`torch.load` RCE, fixed 2.6.0) is the controlling advisory because the model is a `.bin` checkpoint; mitigated here by torch 2.13.0 + commit-pinned revision. transformers pinned >=4.53 (CVE-2025-6921). gliner itself has no known CVEs |
| Upgrade / rollback | pip pins + HF revision pin; rollback is a pin revert plus cached snapshot retention |
| Verdict | **Implemented.** The required contextual configuration |

### 4. datafog-regex-v1

| Property | Value |
|---|---|
| Identity | datafog 4.8.0 (released 2026-07-06), regex engine only, no extras |
| Maintenance | Active (beta uploads as recent as 2026-07-23); small single-vendor community (DataFog Inc) |
| License | LICENSE file MIT; PyPI classifier says Apache-2.0. Both permissive; the inconsistency is recorded and should be pinned down before any production adoption |
| Python / OS | `>=3.10,<3.14`, Python 3.13 explicitly certified for the core profile; Windows/Linux |
| Offline | Fully offline; project states zero network calls in the regex core |
| Dependencies | pydantic + pydantic-settings only (regex core) |
| Package / model size | Small (no model) |
| Training data | None (rules) |
| Custom recognizers | Allowlist / allowlist-pattern suppression; German-locale patterns included |
| Determinism | Deterministic regex |
| Initialization | Negligible |
| Known limitations | No person-name or address detection in the regex core (that requires its spaCy/GLiNER extras, which would collapse it into the heavier lanes); secrets coverage far narrower than the Bicameral catalog |
| Vulnerabilities | None known for the core |
| Upgrade / rollback | pip pin revert |
| Verdict | **Implemented.** The credible lightweight local-first alternative |

## Candidates rejected before implementation

| Candidate | Version checked | Hard incompatibility |
|---|---|---|
| scrubadub (+ scrubadub_spacy) | 2.0.1 (2023-09-01) | Abandoned: no release or commit since 2023-09; Python classifiers stop at 3.9; pinned 2019-era `textblob==0.15.3`. Fails the maintenance screen |
| LLM-Guard (protectai) anonymize | 0.3.16 | Repository archived read-only 2026-07-09 with an explicit unmaintained notice; `requires_python <3.13` blocks the target interpreter; internally it is Presidio + torch anyway |
| piiranha (`iiiorg/piiranha-v1-detect-personal-information`) | v1 (mid-2024) | Model license CC-BY-NC-ND-4.0: non-commercial and no-derivatives. Incompatible with Bicameral distribution regardless of quality |
| pii-anonymizer (Thoughtworks) | 0.2.5 (2023-01-04) | Abandoned 3.5 years; requires pyspark + pandas<2; classifiers 3.10/3.11 only |
| commonregex | 1.5.4 (2014-08-29) | Dead for 12 years |

## Reference-only entries (not eligible or not detectors)

| Entry | Why reference only |
|---|---|
| detect-secrets 1.5.0 (Yelp, Apache-2.0, active) | Credible and 3.13-ready, but secrets-only: zero PII coverage, so it cannot fill the detector role alone. Documented as a possible future complement to whichever engine is selected |
| pii-codex 0.6.1 | Risk-scoring/categorization layer whose detection extras are Presidio itself; not a detector |
| anonipy 0.6.1 | Active and permissive but its core is spacy + gliner + transformers; evaluating it would re-measure the GLiNER lane through a thicker wrapper |
| Flair 0.15.1 / Stanza 1.14.0 | Maintained general NER engines, torch-weight, no PII typing (no emails, cards, SSNs); adopting one means rebuilding the whole recognizer layer that Presidio already provides |
| Hosted PII services (cloud de-identification APIs) | Documented comparison references only. Ineligible for the required alpha boundary: they add credential, availability, network, and privacy-boundary dependencies exactly where Bicameral requires local fail-closed processing |

## Eligibility screen summary

Four materially different configurations proceed to implementation and
measurement: the baseline, conventional Presidio, contextual Presidio+GLiNER,
and the lightweight datafog regex engine. Rejections above are recorded with
their hard incompatibility per the ADR-0020 requirement that rejected
candidates never be silently omitted.
