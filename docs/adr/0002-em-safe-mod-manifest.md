# ADR-0002: EM-Safe Mod Manifest

**Date:** 2026-05-27  
**Status:** proposed  
**Level:** L1

## Problem

EMs should be able to create small domain-specific extensions without compromising Bicameral authority boundaries.

## Decision

Mods use a declarative manifest plus fixtures. The manifest declares source type, output object types, owner lens, review roles, confidence surfaces, storage behavior, and audit preservation. Validation rejects direct canonical writes, single-score confidence, silent signoff approval, compliance resolution, and direct blocking.

## Consequences

EM customization remains fast and local while governance invariants stay centralized in the bot.
