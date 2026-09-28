# Coolify Deployment

Recommended Coolify setup:

1. Create a new GitHub repository from this package.
2. In Coolify, create a new Docker Compose application.
3. Set the compose file path to `deploy/docker-compose.yml`.
4. Add environment variables from `.env.example`.
5. Set the public domain to the `api` service on port `8080`.
6. Configure Fathom webhook URL: `https://your-domain.com/webhook/fathom`.

For Google OAuth token JSON values, paste the full one-line JSON into the matching environment variable.
Never commit `.env`, token JSON files, or transcripts.
