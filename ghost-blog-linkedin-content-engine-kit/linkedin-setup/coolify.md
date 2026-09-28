# Coolify Deployment

Use this when you want a self-hosted LinkedIn API bridge that your IDE or CLI can call after publishing a Ghost post.

## 1. Create The LinkedIn App

In the LinkedIn Developer Portal:

1. Create an app.
2. Add the product `Share on LinkedIn`.
3. Add the product `Sign In with LinkedIn using OpenID Connect`.
4. Copy the Client ID and Client Secret.
5. Add an authorized redirect URL:

```text
https://linkedin-api.example.com/linkedin/callback
```

Replace `linkedin-api.example.com` with your real subdomain.

## 2. Create The Coolify Application

In Coolify:

1. Create a new application from your GitHub repo or fork.
2. Repository: `https://github.com/Florian1995-ai/ghost-blog-linkedin-content-engine-kit`
3. Branch: `master` unless your fork uses `main`.
4. Build type: Dockerfile.
5. Dockerfile path:

```text
deploy/linkedin-native.Dockerfile
```

6. Port:

```text
8080
```

7. Domain:

```text
https://linkedin-api.example.com
```

Do not include `:8080` in the public domain unless your reverse proxy requires it.

## 3. Add Environment Variables

Add the variables from `linkedin-setup/env.example`.

Recommended Coolify settings for each variable:

- Available at Runtime: checked
- Available at Buildtime: optional, checked is fine
- Is Literal: checked
- Is Multiline: unchecked

Use these values:

```text
LINKEDIN_CLIENT_ID=your LinkedIn app Client ID
LINKEDIN_CLIENT_SECRET=your LinkedIn app Client Secret
LINKEDIN_REDIRECT_URI=https://linkedin-api.example.com/linkedin/callback
LINKEDIN_NATIVE_API_URL=https://linkedin-api.example.com
LINKEDIN_NATIVE_API_KEY=your own long random secret
LINKEDIN_NATIVE_TOKEN_PATH=/data/linkedin-native-token.json
LINKEDIN_API_VERSION=202506
LINKEDIN_SCOPES=openid profile w_member_social
```

## 4. Add Persistent Storage

Add persistent storage mounted at:

```text
/data
```

This matters. The OAuth token is stored at:

```text
/data/linkedin-native-token.json
```

Without persistent storage, LinkedIn will disconnect after redeploys.

## 5. Deploy And Connect

Deploy the application, then check:

```text
https://linkedin-api.example.com/health
```

Expected:

```json
{"status":"ok","service":"linkedin-native"}
```

Then open:

```text
https://linkedin-api.example.com/auth/start
```

Approve LinkedIn access. The callback should show:

```json
{
  "status": "connected",
  "message": "LinkedIn is connected. You can close this tab.",
  "person_urn_present": true
}
```

## 6. Local CLI Environment

In your local `.env`, add:

```text
LINKEDIN_NATIVE_API_URL=https://linkedin-api.example.com
LINKEDIN_NATIVE_API_KEY=the same long random secret from Coolify
```

Now the local Ghost pipeline can call the hosted LinkedIn bridge.
