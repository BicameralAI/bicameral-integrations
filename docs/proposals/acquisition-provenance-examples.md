# Acquisition provenance examples

**Status:** Proposal evidence only  
**Issue:** #296  
**ADR:** `docs/adr/0021-acquisition-provenance-classes.md`

These records illustrate the intended semantic difference between direct-provider and host-mediated acquisition. They are not production schemas.

## Direct GitHub webhook

```json
{
  "source_id": "github",
  "source_ref": "https://github.com/example/repo/pull/42",
  "observed_at": "2026-08-10T13:00:00Z",
  "acquisition": {
    "mode": "direct_provider",
    "mediator": null,
    "source_provider": "github",
    "provider_auth_verified_by_bicameral": true,
    "source_receipt": {
      "kind": "github_webhook",
      "delivery_id": "example-delivery-id",
      "signature_scheme": "X-Hub-Signature-256",
      "signature_verified": true,
      "dedup_result": "first_seen",
      "connector_id": "github",
      "connector_version": "0.1.0"
    }
  },
  "evidence": {
    "kind": "pull_request",
    "title": "Sanitized example title",
    "excerpt": "Sanitized example excerpt"
  }
}
```

The `provider_auth_verified_by_bicameral` state above must be produced by trusted acquisition/runtime code after verification. It must not be granted because an inbound caller sets that value.

## Host-mediated GitHub acquisition

```json
{
  "source_id": "github",
  "source_ref": "https://github.com/example/repo/pull/42",
  "observed_at": "2026-08-10T13:00:00Z",
  "acquisition": {
    "mode": "host_mediated",
    "mediator": "example-agent-host",
    "source_provider": "github",
    "provider_auth_verified_by_bicameral": false,
    "source_receipt": null,
    "mediator_observation": {
      "host_source_ref": "host-visible-item-id",
      "host_retrieved_at": "2026-08-10T13:00:01Z"
    }
  },
  "evidence": {
    "kind": "pull_request",
    "title": "Sanitized example title",
    "excerpt": "Sanitized example excerpt"
  }
}
```

The host may have authenticated its own GitHub integration. That fact is useful provenance, but it does not become a claim that Bicameral independently verified the provider webhook or direct API response for this evidence item.

## Required negative invariant

Caller-controlled host-mediated submission like this:

```json
{
  "acquisition": {
    "mode": "direct_provider",
    "provider_auth_verified_by_bicameral": true
  }
}
```

must **not** be sufficient to create a direct-provider receipt.

The implementation should derive trusted acquisition provenance from the entry boundary and verification result, or strip/reject caller-owned assurance fields.

## Shared downstream behavior

Both paths should still converge through the common safety and evidence boundaries:

```text
provider/host input
  -> field minimization where applicable
  -> neutral evidence
  -> redact-and-pass + secret/PHI/PAN hard screen
  -> transformation trace
  -> daemon admission
```

The paths converge on compatible evidence. They do not converge on identical provenance claims.
