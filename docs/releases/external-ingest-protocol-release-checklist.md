# External-Ingest Producer Release Checklist

Use this checklist for every Integrations release that changes the separately
distributed Integrations → Bot protocol. CI and terminal receipts are validation
witnesses only; they do not create Product state or deployment authority.

## Pin and compatibility

- [ ] Record the exact Bot commit, protocol version, generated schema digest,
  contract fingerprint, capability path, and delivery path in
  `runtime/schemas/ingest_schema_pin.json`.
- [ ] Vendor the Bot-owned schema, contract manifest, and manifest fingerprint
  byte-for-byte.
- [ ] Run `python scripts/validate_ingest_schema_pin.py` and focused runtime tests.
- [ ] Prove version, schema, fingerprint, endpoint, and receipt-requirement skew
  each stop before POST with a value-free diagnostic.
- [ ] Prove every mismatch resolves to quarantine/no cursor advancement.

## Delivery and rollout

- [ ] Validate a real provider capture through redaction, capability negotiation,
  v2 delivery, Bot acceptance, and cursor persistence using exact commits.
- [ ] Show the information-cycle bundle's ``unproven_downstream`` stages
  (durable evidence persistence, candidate/Decision lifecycle, recall or
  RecallPacket production, and authentic agent-session exposure) either proven
  through the exact bound execution session or explicitly declared out of this
  release's authority. A component-evidence bundle does not close them.
- [ ] Deploy the compatible Bot contract before switching Integrations.
- [ ] Validate old Integrations → new Bot and new Integrations → old Bot behavior;
  no automatic downgrade is allowed.
- [ ] Prove rollback to the prior producer pin without evidence loss or cursor
  advancement during incompatibility.
- [ ] Attach CI runs, terminal commands, schema/fingerprint receipts, and cleanup
  evidence to the linked release issue before named human acceptance.
