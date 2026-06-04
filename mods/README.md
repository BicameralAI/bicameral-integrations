# EM-Safe Mods

Mods are advisory post-processors over adapter emissions. They can annotate
evidence and suggest review routing, but cannot write canonical decisions,
approve signoff, resolve compliance, or create direct blocking results — the mod
safety contract enforced by the [project root](../README.md#mod-safety-contract).

## Mods

| Mod | Purpose | Status |
|---|---|---|
| [dependency_risk](dependency_risk/) | Dependency upgrade, pin, SDK-drift, and compatibility-risk signals | Placeholder |
| [noisy_source_gate](noisy_source_gate/) | Manual-gate high-noise sources (Slack, email, meetings) unless trust is configured higher | Placeholder |
| [security_mentions](security_mentions/) | Auth, token, secret, PII, webhook-verification, and transport-exposure signals | Placeholder |
