#!/usr/bin/env python3
"""
Widget Injector — injects a chat widget into any HTML file.

Supports two widget types:
  - ghl: GoHighLevel chat widget (reads from widget-demo/ghl-config-{slug}.json)
  - retell: Retell AI voice widget (reads from widget-demo/retell-config-{slug}.json)

Usage:
    python execution/inject_widget.py --slug example --widget-type ghl
    python execution/inject_widget.py --slug example --widget-type ghl --html-file .tmp/redesigns/example-redesign.html
    python execution/inject_widget.py --slug example --widget-type retell
"""

import os
import sys
import json
import argparse
from pathlib import Path
from dotenv import load_dotenv

# Windows Unicode fix
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

load_dotenv()


def inject_css(html: str, css: str) -> str:
    """Inject CSS into <head> or prepend to <style> block."""
    style_tag = f"<style>\n{css}\n</style>"
    if "</head>" in html:
        return html.replace("</head>", f"{style_tag}\n</head>", 1)
    elif "<head>" in html:
        return html.replace("<head>", f"<head>\n{style_tag}", 1)
    else:
        # No head tag — prepend to HTML
        return style_tag + "\n" + html


def inject_script(html: str, script: str) -> str:
    """Inject script just before </body>."""
    if "</body>" in html:
        return html.replace("</body>", f"\n{script}\n</body>", 1)
    else:
        # No body close — append to end
        return html + f"\n{script}"


def load_ghl_config(slug: str) -> dict:
    """Load GHL widget config from widget-demo/ghl-config-{slug}.json."""
    config_path = Path(f"widget-demo/ghl-config-{slug}.json")
    if not config_path.exists():
        print(f"  Error: GHL config not found at {config_path}")
        print(f"  Run first: python execution/setup_ghl_widget.py --slug {slug}")
        return {}
    with open(config_path, encoding="utf-8") as f:
        return json.load(f)


def load_retell_config(slug: str) -> dict:
    """Load Retell widget config from widget-demo/retell-config-{slug}.json."""
    config_path = Path(f"widget-demo/retell-config-{slug}.json")
    if not config_path.exists():
        print(f"  Error: Retell config not found at {config_path}")
        print(f"  Run first: python widget-demo/setup_retell_agent.py --slug {slug}")
        return {}
    with open(config_path, encoding="utf-8") as f:
        return json.load(f)


def build_retell_embed(config: dict) -> tuple[str, str]:
    """Build Retell voice widget CSS + script embed."""
    agent_id = config.get("agent_id", "")
    public_key = os.getenv("RETELL_PUBLIC_KEY", "")
    accent_color = config.get("accent_color", "#111827")

    css = f"""
/* Retell Voice Widget */
retell-client-widget {{
  --primary-color: {accent_color};
  position: fixed;
  bottom: 20px;
  right: 20px;
  z-index: 99999;
}}
""".strip()

    if not public_key:
        script = f"""
<!-- Retell Voice Widget — RETELL_PUBLIC_KEY not set yet -->
<!-- Get it from: Retell Dashboard → Keys → Public Key → add to .env -->
<script>console.warn('RETELL_PUBLIC_KEY missing — widget will not load');</script>
""".strip()
    else:
        script = f"""
<!-- Retell Voice Widget -->
<script src="https://retellai.com/embed/retell-client-bundle.min.js"></script>
<retell-client-widget
  data-agent-id="{agent_id}"
  data-api-key="{public_key}">
</retell-client-widget>
""".strip()

    return css, script


def main():
    parser = argparse.ArgumentParser(
        description="Inject a chat widget into any HTML file"
    )
    parser.add_argument("--slug", required=True, help="Prospect slug")
    parser.add_argument(
        "--widget-type", choices=["ghl", "retell"], default="ghl",
        help="Widget type (default: ghl)"
    )
    parser.add_argument(
        "--html-file", default="",
        help="Path to HTML file to inject into. Defaults to .tmp/redesigns/{slug}-redesign.html"
    )
    parser.add_argument(
        "--output-file", default="",
        help="Output path. Defaults to overwriting the input file."
    )
    args = parser.parse_args()

    slug = args.slug

    # Resolve HTML file path
    html_file = args.html_file or f".tmp/redesigns/{slug}-redesign.html"
    output_file = args.output_file or html_file

    html_path = Path(html_file)
    if not html_path.exists():
        print(f"Error: HTML file not found: {html_file}")
        print(f"Run UC1 first: python execution/generate_redesign.py --slug {slug}")
        sys.exit(1)

    print(f"\n=== Injecting {args.widget_type.upper()} widget into: {html_file} ===\n")

    # Load widget config
    if args.widget_type == "ghl":
        config = load_ghl_config(slug)
        if not config:
            sys.exit(1)
        css = config.get("css", "")
        html_trigger = config.get("html_trigger", "")
        script = config.get("script", "")
        widget_name = config.get("display_name", "GHL Chat")
        # For custom widget, script contains the JS logic; html_trigger has the DOM elements
        # Combine html_trigger + script as the body injection
        script = html_trigger + "\n\n" + script if html_trigger else script
        print(f"  Widget: {widget_name}")
        print(f"  Color: {config.get('color', 'default')}")

    elif args.widget_type == "retell":
        config = load_retell_config(slug)
        if not config:
            sys.exit(1)
        css, script = build_retell_embed(config)
        widget_name = "Retell Voice Widget"
        print(f"  Widget: {widget_name}")
        print(f"  Agent ID: {config.get('agent_id', 'unknown')}")

    # Read HTML
    with open(html_path, encoding="utf-8", errors="replace") as f:
        html = f.read()

    original_size = len(html)

    # Inject CSS into head
    if css:
        html = inject_css(html, css)

    # Inject script before </body>
    if script:
        html = inject_script(html, script)

    new_size = len(html)
    delta = new_size - original_size

    # Write output
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"  Injected: {delta:+d} chars ({original_size} → {new_size})")
    print(f"  Saved: {output_path}")
    print(f"\n=== Done! ===")
    print(f"  Widget appears bottom-right when page loads")
    print(f"  Deploy with:")
    print(f"    python execution/deploy_redesign.py --slug {slug} --html-file {output_file} --deploy-type redesign")


if __name__ == "__main__":
    main()
