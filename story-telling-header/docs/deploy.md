# Deploy

`dist/` is a plain static folder — host it anywhere (Netlify, GitHub Pages, S3, nginx,
Cloudflare Pages). One requirement: the server must send the `.mp4` with **HTTP range
support** so the video is seekable. Most static hosts do this by default; see
[gotchas.md](gotchas.md) #2 if scrubbing snaps to frame 0 (the blob-fetch in this repo already
works around it).

## Cloudflare Pages (one command)

```bash
npx wrangler pages deploy dist --project-name my-hero --commit-dirty=true
```

You'll need a Cloudflare account and an API token with **Pages: Edit** permission (a DNS-only
token will fail). Set them for the command:

```bash
export CLOUDFLARE_API_TOKEN=<your Pages-scoped token>
export CLOUDFLARE_ACCOUNT_ID=<your account id>
npx wrangler pages deploy dist --project-name my-hero --commit-dirty=true
```

First run creates the project; it goes live at `https://my-hero.pages.dev`.

> Windows note: run wrangler from a normal working directory (it writes a `.wrangler/tmp`
> folder in the current dir). Set the env vars in the same shell invocation as the deploy.

## GitHub Pages

```bash
# commit dist/ to a gh-pages branch, or point Pages at /dist on main
```

## Keep the upload lean

Only `dist/` needs to ship. The repo's `.gitignore` already keeps the raw per-scene
`clip*.mp4` and the checkpoint out of git — only the stitched `ascent.mp4` is used.
