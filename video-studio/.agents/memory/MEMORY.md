# Memory Index

- [Video pipeline product decisions](video-pipeline-decisions.md) — voice provider is Fish Audio (user choice over ElevenLabs); finished renders FTP to user's Hostinger site; user has an existing editing pipeline on Hostinger to integrate, not duplicate.
- [API codegen zod quirk](api-codegen-quirks.md) — orval emits zod-v4 syntax; the codegen script rewrites imports to 'zod/v4'; generated hooks need `{ mutation: {...} }` wrappers and exact param names.
