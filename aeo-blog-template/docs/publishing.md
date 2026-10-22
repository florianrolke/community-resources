# Build, schedule, and publish

Edit `site.config.json`, replace the fictional examples, and run the production build:

```text
python execution/build_site.py
```

For a standalone copy, upload `public/` to any static host. On Cloudflare Pages, use a project of your own with build command `python execution/build_site.py` and output directory `public`. If your connected repository contains multiple resources, set its root directory to `aeo-blog-template`. Keep credentials in the hosting provider's secret settings.

This resource does not automatically deploy anything or create cloud resources. No client domain or account is configured. Use your normal reviewed publishing process.

## Schedule after review

```text
python execution/schedule_drip.py --start 2026-11-03 --days 1,4
```

This shows proposed dates. Add `--apply` to write them after reviewing the plan. Weekdays use Monday=0 through Sunday=6. The builder omits drafts and future `publishDate` pages. A host must rebuild when a date arrives; the Markdown date alone cannot trigger a deployment. Configure your own schedule in your hosting environment if required.

`--include-drafts` writes a separate `preview/` folder. Keep that output local or protect it from public access and indexing.
