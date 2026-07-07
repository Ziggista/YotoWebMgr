# 0002: Authentication Scaffold

## Status

Accepted

## Decision

Introduce a simple initial auth model with three modes:

- Home-page household user selection for Krystin and Dale.
- Local username/password support scaffolded with Argon2 hashing.
- OAuth 2.0 reserved in the API contract but left disabled until a provider is chosen.

## Rationale

This keeps the first release simple for household use while avoiding a dead-end auth shape.

## Notes

- Current users are in-memory placeholders.
- Passwords are not yet persisted or exposed in UI setup flows.
- Session issuance is scaffold-only and should later be replaced with signed cookies or tokens.
