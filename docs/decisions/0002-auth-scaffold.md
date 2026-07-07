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

- Current household users are stored in PostgreSQL and seeded by the initial user migration.
- Password hashes are nullable so click-based household auth works before passwords are configured.
- Argon2 embeds salt and parameters in the stored hash string, so there is no separate salt column.
- Password setup is not yet exposed in the UI.
- Session issuance is scaffold-only and should later be replaced with signed cookies or tokens.
