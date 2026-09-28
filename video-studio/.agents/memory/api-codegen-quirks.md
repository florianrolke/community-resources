---
name: API codegen zod quirk
description: Why the OpenAPI codegen script rewrites zod imports to the zod/v4 subpath
---

The rule: after changing `lib/api-spec/openapi.yaml`, run the codegen script as-is; do not remove its `sed` step that rewrites `from 'zod'` to `from 'zod/v4'` in the generated `lib/api-zod` output.

**Why:** orval 8.x emits zod-v4 API syntax (`zod.iso.datetime()`, `zod.uuid()`, top-level `zod.email()` etc.), but the workspace pins zod 3.25.x whose root export is the v3 API. zod 3.25 ships the v4 API under the `zod/v4` subpath, so rewriting the import makes the generated code valid without upgrading zod (which the catalog pins for other consumers).

**How to apply:** if generated zod schemas suddenly fail typecheck with "property does not exist on zod", check whether the import rewrite step was lost before touching zod versions. Frontend hook usage gotchas from the same generator: mutation options must be wrapped as `{ mutation: { onSuccess } }`, query options as a second arg `{ query: { queryKey: get<Op>QueryKey(), ... } }` (queryKey required), and mutate variables use the operation's param names (`{ jobId }`, `{ projectId, data }`), never `{ id }`.
