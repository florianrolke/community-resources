"""Optional Modal deployment profile.

Deploy:
    modal deploy deploy/modal/modal_app.py
"""

from __future__ import annotations

import modal

app = modal.App("meeting-intelligence-community")

image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install_from_requirements("requirements.txt")
    .add_local_dir("apps", "/root/apps")
    .add_local_dir("packages", "/root/packages")
    .add_local_dir("scripts", "/root/scripts")
)

volume = modal.Volume.from_name("meeting-intelligence-data", create_if_missing=True)


@app.function(image=image, volumes={"/data": volume}, timeout=30)
@modal.fastapi_endpoint(method="GET")
def health():
    return {"status": "ok"}


@app.function(image=image, volumes={"/data": volume}, timeout=30)
@modal.fastapi_endpoint(method="POST")
async def fathom_webhook(request):
    import os
    import sys

    sys.path.insert(0, "/root/packages")
    os.environ["DATA_DIR"] = "/data"
    from apps.api.main import fathom_webhook as handler

    return await handler(request)


@app.function(
    image=image,
    volumes={"/data": volume},
    secrets=[
        modal.Secret.from_name("meeting-intelligence-secrets"),
    ],
    timeout=600,
)
def process_jobs():
    import os
    import sys

    sys.path.insert(0, "/root/packages")
    os.environ["DATA_DIR"] = "/data"
    from apps.worker.main import process_once

    return {"processed": process_once()}


@app.function(
    image=image,
    volumes={"/data": volume},
    secrets=[modal.Secret.from_name("meeting-intelligence-secrets")],
    schedule=modal.Cron("*/15 * * * *"),
    timeout=600,
)
def scheduled_poll():
    import os
    import sys

    sys.path.insert(0, "/root/packages")
    os.environ["DATA_DIR"] = "/data"
    from apps.scheduler.main import poll_fathom_once

    return {"enqueued": poll_fathom_once()}
