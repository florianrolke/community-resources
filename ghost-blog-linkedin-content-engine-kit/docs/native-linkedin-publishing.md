# Native LinkedIn Publishing

The native LinkedIn publisher is the official-API path for sending approved Ghost Content Engine drafts to a LinkedIn member profile.

For the complete reusable setup, use:

- `linkedin-setup/README.md`
- `linkedin-setup/coolify.md`
- `linkedin-setup/docker.md`
- `linkedin-setup/cli-workflow.md`

The short version:

1. Create a LinkedIn Developer app.
2. Add `Share on LinkedIn`.
3. Add `Sign In with LinkedIn using OpenID Connect`.
4. Deploy `deploy/linkedin-native.Dockerfile`.
5. Set the variables from `linkedin-setup/env.example`.
6. Mount persistent storage at `/data`.
7. Open `/auth/start` on your deployed service.
8. Publish from a Ghost slug:

```bash
python scripts/ghost_to_linkedin.py --slug your-ghost-post-slug --review-only
python scripts/ghost_to_linkedin.py --slug your-ghost-post-slug --dry-run
python scripts/ghost_to_linkedin.py --slug your-ghost-post-slug --publish-now
```

This path uses LinkedIn OAuth and LinkedIn's REST post/image endpoints. It does not use browser automation, cookies, or unofficial APIs.
