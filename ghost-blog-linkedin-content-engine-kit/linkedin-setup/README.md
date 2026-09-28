# LinkedIn Setup

This folder packages the native LinkedIn publishing layer for the Ghost Content Engine Kit.

It uses LinkedIn's official OAuth flow and Share on LinkedIn API. It does not use browser automation, cookies, or unofficial endpoints.

## What You Get

- A tiny OAuth + publishing service for LinkedIn.
- A Coolify setup path for self-hosting.
- A plain Docker Compose setup path for any VPS.
- A CLI flow that turns an existing Ghost post into a LinkedIn draft or live post.
- A persistence pattern so the LinkedIn OAuth token survives redeploys.

## Files

- `env.example` - safe environment variable template.
- `coolify.md` - exact Coolify deployment steps.
- `docker.md` - non-Coolify Docker Compose deployment.
- `cli-workflow.md` - Ghost blog to LinkedIn commands.
- `docker-compose.yml` - ready-to-edit compose file for a VPS.
- `../deploy/linkedin-native.Dockerfile` - Dockerfile used by Coolify and Docker Compose.
- `../scripts/linkedin_native_client.py` - OAuth, token storage, image upload, and posting.
- `../scripts/linkedin_post_pipeline.py` - converts Ghost posts or source files into LinkedIn drafts.
- `../scripts/ghost_to_linkedin.py` - one-command Ghost slug to LinkedIn wrapper.

## Setup Summary

1. Create a LinkedIn Developer app.
2. Request/add these products:
   - Share on LinkedIn
   - Sign In with LinkedIn using OpenID Connect
3. Add this redirect URL in the LinkedIn app:

```text
https://YOUR-LINKEDIN-SERVICE-DOMAIN/linkedin/callback
```

4. Deploy the native LinkedIn service with Coolify or Docker Compose.
5. Open:

```text
https://YOUR-LINKEDIN-SERVICE-DOMAIN/auth/start
```

6. After LinkedIn says the app is connected, create and publish from a Ghost slug:

```bash
python scripts/ghost_to_linkedin.py --slug your-ghost-post-slug --review-only
python scripts/ghost_to_linkedin.py --slug your-ghost-post-slug --dry-run
python scripts/ghost_to_linkedin.py --slug your-ghost-post-slug --publish-now
```

## Important Safety Defaults

- Live native LinkedIn posting requires `--publish-now`.
- Hosted publishing only supports public image URLs. Ghost feature images work well.
- Local files can be used when publishing with `--provider native` from the same machine that has the file.
- Keep `LINKEDIN_NATIVE_API_KEY`, `LINKEDIN_CLIENT_SECRET`, and token files out of git.
- Mount `/data` as persistent storage in production or you will need to reconnect LinkedIn after redeploys.

