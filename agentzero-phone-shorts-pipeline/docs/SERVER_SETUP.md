# Server Setup Notes

## Recommended Architecture

Use two routes/domains:

- AgentZero UI: port used by your normal AgentZero app.
- Phone upload page: port `8080`.

Both write to the same mounted assets volume:

```text
/app/work_dir/assets/
  agentzero_uploads/shorts_test/
  agentzero_outputs/
  agentzero_pipeline/
```

## No-Redeploy Editing Loop

The key design choice is `AGENTZERO_PIPELINE_DIR`.

At startup, the Docker image can seed defaults into:

```text
/app/work_dir/assets/agentzero_pipeline/defaults/
```

The live scripts and config live at:

```text
/app/work_dir/assets/agentzero_pipeline/
```

Set:

```bash
AGENTZERO_PIPELINE_SYNC_CODE=false
```

Then you can edit these live files over SSH:

```text
phone_render_worker.py
phone_upload_server.py
pipeline_config.json
audio/
logo/
```

Use redeploys for code you want baked into the image. Use live config/assets for daily tuning.

## Validating A Render

Every job writes a folder under:

```text
/app/work_dir/assets/agentzero_outputs/{job_id}/
```

Useful files:

- `final.mp4`
- `thumbnail.jpg`
- `transcript.json`
- `metadata.json`
- `editing_preset.json`
- `asset_manifest.json`
- `sfx_events.json`
- `resource_usage.json`
- `render.log`

If a render sounds wrong, inspect `asset_manifest.json` and `sfx_events.json` first.

## Common Failures

`moov atom not found`

The upload is incomplete or damaged. Re-upload the file.

`YouTube token missing`

Rendering succeeded, but publishing was skipped. Add OAuth token files or keep upload disabled.

No logo appears

Make sure this exists:

```text
/app/work_dir/assets/agentzero_pipeline/logo/logo.png
```

No SFX

Make sure the audio paths in `pipeline_config.json` exist, or put files in `audio/brand/`.
