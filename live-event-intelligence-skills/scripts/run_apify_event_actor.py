from __future__ import annotations

import argparse
from scripts.api_clients import apify_actor_from_alias, apify_run_sync
from scripts.common import read_json, write_json


def main():
    parser = argparse.ArgumentParser(description="Run or dry-run an Apify event actor with a JSON payload.")
    parser.add_argument("--actor", required=True, help="Actor alias such as 10times/eventbrite/google-serp or full actor ID.")
    parser.add_argument("--payload-json", required=True)
    parser.add_argument("--output", default="")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    actor_id = apify_actor_from_alias(args.actor)
    result = apify_run_sync(actor_id, read_json(args.payload_json), dry_run=args.dry_run)
    if args.output:
        write_json(args.output, result)
    else:
        print(result)


if __name__ == "__main__":
    main()