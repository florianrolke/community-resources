# Docker Compose Deployment

Use this if you are not using Coolify.

## 1. Prepare The Environment

From the repo root:

```bash
cp linkedin-setup/env.example linkedin-setup/.env
```

Edit `linkedin-setup/.env`:

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

In LinkedIn Developer Portal, the authorized redirect URL must exactly match `LINKEDIN_REDIRECT_URI`.

## 2. Start The Service

```bash
docker compose -f linkedin-setup/docker-compose.yml up -d --build
```

The compose file maps local port `8080` to container port `8080`.

## 3. Put It Behind HTTPS

LinkedIn OAuth requires a public HTTPS redirect URL.

Use a reverse proxy such as Caddy, Nginx, Traefik, Cloudflare Tunnel, or your VPS panel to route:

```text
https://linkedin-api.example.com -> http://127.0.0.1:8080
```

## 4. Connect LinkedIn

Open:

```text
https://linkedin-api.example.com/auth/start
```

Approve access. The token will be saved in:

```text
linkedin-setup/data/linkedin-native-token.json
```

Do not commit that file.

## 5. Verify

```bash
curl https://linkedin-api.example.com/health
```

Expected:

```json
{"status":"ok","service":"linkedin-native"}
```

