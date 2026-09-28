"""
skool_messaging_sandbox_v2.py — Safe DM testing with allowlist guard

Generates and optionally sends Skool DMs with strict safety controls:
  1. ALLOWLIST-ONLY — will not send to anyone not on the list
  2. Full audit trail — every attempt logged to messaging_log.jsonl
  3. 3 modes: draft-only, dry-run (shows what would happen), live (sends)

Usage:
  # Generate draft only (no send):
  python execution/skool_messaging_sandbox_v2.py --recipient john-connor-3508 --auto-draft --tenant aiautomationsbyjack

  # Dry-run (generates + shows send preview):
  python execution/skool_messaging_sandbox_v2.py --recipient john-connor-3508 --auto-draft --tenant aiautomationsbyjack --dry-run

  # Send a specific message:
  python execution/skool_messaging_sandbox_v2.py --recipient john-connor-3508 --message "Hey John, saw you in Jack's community..." --tenant aiautomationsbyjack --live

  # Manage allowlist:
  python execution/skool_messaging_sandbox_v2.py --add-to-allowlist john-connor-3508
  python execution/skool_messaging_sandbox_v2.py --show-allowlist
"""

import asyncio
import argparse
import json
import os
import sys
from pathlib import Path
from datetime import datetime, timezone

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BASE_DIR = Path(__file__).parent.parent
EXECUTION_DIR = Path(__file__).parent
STATE_DIR = BASE_DIR / ".tmp" / "intelligence_v2"

sys.path.insert(0, str(EXECUTION_DIR))

from dotenv import load_dotenv
load_dotenv(BASE_DIR / ".env")

# ============================================================================
# Allowlist Management
# ============================================================================

ALLOWLIST_PATH = STATE_DIR / "messaging_allowlist.json"

# Default allowlist — add handles here for testing
DEFAULT_ALLOWLIST = [
    "john-connor-3508",
]


def load_allowlist() -> list:
    """Load the messaging allowlist. Creates with defaults if missing."""
    if ALLOWLIST_PATH.exists():
        with open(ALLOWLIST_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("allowed_handles", [])

    # Create default allowlist
    ALLOWLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    save_allowlist(DEFAULT_ALLOWLIST)
    return DEFAULT_ALLOWLIST


def save_allowlist(handles: list):
    """Save the allowlist to disk."""
    ALLOWLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(ALLOWLIST_PATH, "w", encoding="utf-8") as f:
        json.dump({
            "allowed_handles": handles,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }, f, indent=2)


def is_allowed(handle: str) -> bool:
    """Check if a handle is on the allowlist."""
    handle = handle.strip().lstrip("@").lower()
    return handle in [h.lower() for h in load_allowlist()]


# ============================================================================
# Audit Logging
# ============================================================================

LOG_PATH = STATE_DIR / "messaging_log.jsonl"


def log_action(action: str, recipient: str, message: str = "", result: str = "",
               mode: str = "", extra: dict = None):
    """Append an action to the audit log."""
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action": action,
        "recipient": recipient,
        "message_preview": message[:200] if message else "",
        "result": result,
        "mode": mode,
    }
    if extra:
        entry.update(extra)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


# ============================================================================
# Member Lookup
# ============================================================================

def lookup_member_from_state(handle: str, tenant: str) -> dict:
    """Try to find member info from orchestrator state."""
    state_path = STATE_DIR / tenant / "member_delta_state.json"
    if not state_path.exists():
        return {"handle": handle, "name": handle}

    with open(state_path, "r", encoding="utf-8") as f:
        state = json.load(f)

    member_info = state.get("handles", {}).get(handle, {})
    if member_info:
        return {
            "handle": handle,
            "name": member_info.get("name", handle),
            "bio": member_info.get("bio", ""),
            "profileUrl": f"https://www.skool.com/@{handle}",
        }
    return {"handle": handle, "name": handle, "profileUrl": f"https://www.skool.com/@{handle}"}


# ============================================================================
# Draft Generation
# ============================================================================

def generate_auto_draft(member: dict, tenant: str) -> str:
    """Generate a personalized DM draft using the message drafter."""
    config_path = EXECUTION_DIR / "tenants" / tenant / "config.json"
    if not config_path.exists():
        print(f"  [WARN] No tenant config at {config_path} — using default tone")
        config = {
            "messaging": {
                "mode": "draft",
                "model": "anthropic/claude-haiku-4.5",
                "tone_template": "Direct, warm, curious. 3-4 sentences. No emojis.",
                "include_post_matches": False,
            },
            "tenant_id": tenant,
        }
    else:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)

    from skool_message_drafter_v2 import draft_message
    draft = draft_message(
        member=member,
        signal_type="new_qualified_member",
        relevant_posts=[],
        config=config,
    )
    return draft


# ============================================================================
# DM Sending via Playwright
# ============================================================================

async def send_dm_playwright(handle: str, message: str, headless: bool = True) -> dict:
    """
    Send a DM to a Skool member via Playwright.

    Returns dict with success status and details.
    """
    auth_token = os.getenv("SKOOL_AUTH_TOKEN")
    if not auth_token:
        return {"success": False, "error": "SKOOL_AUTH_TOKEN not set in .env"}

    profile_url = f"https://www.skool.com/@{handle}"

    from playwright.async_api import async_playwright

    p = await async_playwright().start()
    try:
        browser = await p.chromium.launch(headless=headless)
        context = await browser.new_context()

        # Set auth cookie
        await context.add_cookies([{
            "name": "auth_token",
            "value": auth_token,
            "domain": ".skool.com",
            "path": "/",
            "httpOnly": True,
            "secure": True,
            "sameSite": "Lax",
        }])

        page = await context.new_page()

        # Navigate to member profile
        print(f"  Navigating to {profile_url}...")
        await page.goto(profile_url, wait_until="domcontentloaded")
        await page.wait_for_timeout(3000)

        # Find and click Message button
        print(f"  Looking for Message button...")
        msg_btn_found = await page.evaluate("""() => {
            const buttons = document.querySelectorAll('button, a');
            for (const btn of buttons) {
                const text = btn.textContent.toLowerCase().trim();
                if (text === 'message' || text === 'send message' || text === 'dm') {
                    btn.click();
                    return true;
                }
            }
            const icons = document.querySelectorAll('[data-icon="envelope"], [aria-label*="message"], [aria-label*="Message"]');
            if (icons.length > 0) {
                icons[0].click();
                return true;
            }
            return false;
        }""")

        if not msg_btn_found:
            return {"success": False, "error": "Could not find Message button on profile"}

        await page.wait_for_timeout(3000)

        # Type message into editor
        print(f"  Typing message...")
        editor_type = await page.evaluate("""(messageText) => {
            // Try contenteditable (ProseMirror/TipTap)
            const editors = document.querySelectorAll(
                '[contenteditable="true"], .ProseMirror, [role="textbox"]'
            );
            if (editors.length > 0) {
                const editor = editors[editors.length - 1];
                editor.focus();
                editor.innerHTML = '<p>' + messageText.replace(/\\n/g, '</p><p>') + '</p>';
                editor.dispatchEvent(new Event('input', { bubbles: true }));
                return 'editor';
            }
            // Try textarea
            const textareas = document.querySelectorAll('textarea');
            if (textareas.length > 0) {
                const ta = textareas[textareas.length - 1];
                ta.focus();
                ta.value = messageText;
                ta.dispatchEvent(new Event('input', { bubbles: true }));
                return 'textarea';
            }
            return null;
        }""", message)

        if not editor_type:
            # Fallback: keyboard type
            print(f"  Fallback: keyboard typing...")
            await page.keyboard.type(message, delay=10)

        await page.wait_for_timeout(1000)

        # Click Send button
        print(f"  Clicking Send...")
        send_clicked = await page.evaluate("""() => {
            const buttons = document.querySelectorAll('button');
            for (const btn of buttons) {
                const text = btn.textContent.toLowerCase().trim();
                if (text === 'send' || text === 'send message') {
                    btn.click();
                    return true;
                }
            }
            return false;
        }""")

        if not send_clicked:
            # Try Enter key
            await page.keyboard.press("Enter")

        await page.wait_for_timeout(2000)

        # Take screenshot for proof
        screenshot_dir = STATE_DIR / "screenshots"
        screenshot_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        screenshot_path = screenshot_dir / f"dm_{handle}_{ts}.png"
        await page.screenshot(path=str(screenshot_path))
        print(f"  Screenshot saved: {screenshot_path.name}")

        await browser.close()
        return {"success": True, "screenshot": str(screenshot_path)}

    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        await p.stop()


# ============================================================================
# Main
# ============================================================================

async def main():
    parser = argparse.ArgumentParser(
        description="Skool Messaging Sandbox v2 — Safe DM testing with allowlist"
    )
    parser.add_argument("--recipient", help="Skool handle (e.g. john-connor-3508)")
    parser.add_argument("--message", help="Custom message text to send")
    parser.add_argument("--auto-draft", action="store_true",
                        help="Auto-generate message using AI drafter")
    parser.add_argument("--tenant", default="aiautomationsbyjack",
                        help="Tenant slug for config (default: aiautomationsbyjack)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Generate everything but don't actually send")
    parser.add_argument("--live", action="store_true",
                        help="Actually send the DM (requires allowlist)")
    parser.add_argument("--visible", action="store_true",
                        help="Show browser window")
    parser.add_argument("--add-to-allowlist", metavar="HANDLE",
                        help="Add a handle to the allowlist")
    parser.add_argument("--remove-from-allowlist", metavar="HANDLE",
                        help="Remove a handle from the allowlist")
    parser.add_argument("--show-allowlist", action="store_true",
                        help="Show current allowlist")
    parser.add_argument("--show-log", action="store_true",
                        help="Show recent messaging log entries")
    args = parser.parse_args()

    # ── Allowlist management ──
    if args.show_allowlist:
        allowlist = load_allowlist()
        print(f"\nMessaging Allowlist ({len(allowlist)} handles):")
        for h in allowlist:
            print(f"  - {h}")
        return

    if args.add_to_allowlist:
        handle = args.add_to_allowlist.strip().lstrip("@").lower()
        allowlist = load_allowlist()
        if handle not in allowlist:
            allowlist.append(handle)
            save_allowlist(allowlist)
            print(f"Added '{handle}' to allowlist ({len(allowlist)} total)")
            log_action("allowlist_add", handle)
        else:
            print(f"'{handle}' already on allowlist")
        return

    if args.remove_from_allowlist:
        handle = args.remove_from_allowlist.strip().lstrip("@").lower()
        allowlist = load_allowlist()
        if handle in allowlist:
            allowlist.remove(handle)
            save_allowlist(allowlist)
            print(f"Removed '{handle}' from allowlist ({len(allowlist)} total)")
            log_action("allowlist_remove", handle)
        else:
            print(f"'{handle}' not on allowlist")
        return

    if args.show_log:
        if not LOG_PATH.exists():
            print("No messaging log found yet.")
            return
        print(f"\nRecent messaging log ({LOG_PATH}):\n")
        with open(LOG_PATH, "r", encoding="utf-8") as f:
            lines = f.readlines()
        for line in lines[-20:]:
            entry = json.loads(line)
            ts = entry["timestamp"][:19]
            print(f"  [{ts}] {entry['action']:20s} → {entry['recipient']:25s} | {entry['result']}")
            if entry.get("message_preview"):
                print(f"    Preview: {entry['message_preview'][:100]}...")
        return

    # ── Message generation / sending ──
    if not args.recipient:
        parser.error("--recipient is required for drafting or sending")

    handle = args.recipient.strip().lstrip("@").lower()
    # Strip full URL if given
    if "skool.com/@" in handle:
        handle = handle.split("@")[-1].rstrip("/")

    print(f"\n{'='*60}")
    print(f"MESSAGING SANDBOX v2")
    print(f"{'='*60}")
    print(f"  Recipient: {handle}")
    print(f"  Tenant:    {args.tenant}")
    print(f"  Mode:      {'LIVE' if args.live else ('DRY RUN' if args.dry_run else 'DRAFT ONLY')}")

    # Look up member info
    member = lookup_member_from_state(handle, args.tenant)
    print(f"  Name:      {member.get('name', '?')}")
    print(f"  Profile:   {member.get('profileUrl', '?')}")

    # Generate or use provided message
    if args.auto_draft:
        print(f"\n[Draft] Generating AI draft...")
        message = generate_auto_draft(member, args.tenant)
        print(f"\n  +--- AI-Generated Draft ----------------")
        for line in message.split("\n"):
            print(f"  | {line}")
        print(f"  +------------------------------------------\n")
    elif args.message:
        message = args.message
        print(f"\n  Message: {message[:200]}")
    else:
        parser.error("Either --message or --auto-draft is required")

    log_action("draft_generated", handle, message, mode="auto" if args.auto_draft else "manual")

    # Draft-only mode (default)
    if not args.live and not args.dry_run:
        print(f"[DRAFT ONLY] Message generated. Use --dry-run to preview send, or --live to send.")
        log_action("draft_only", handle, message, result="stored")
        return

    # Allowlist check
    if not is_allowed(handle):
        print(f"\n  BLOCKED: '{handle}' is NOT on the allowlist.")
        print(f"  Add with: python execution/skool_messaging_sandbox_v2.py --add-to-allowlist {handle}")
        log_action("blocked_not_allowlisted", handle, message, result="rejected")
        return

    print(f"  Allowlist: APPROVED")

    # Dry-run mode
    if args.dry_run:
        print(f"\n[DRY RUN] Would send DM to @{handle}:")
        print(f"  Message: {message[:300]}")
        print(f"  Via: Playwright → skool.com/@{handle} → Message → Type → Send")
        log_action("dry_run", handle, message, result="simulated")
        return

    # LIVE mode
    print(f"\n[LIVE] Sending DM to @{handle}...")
    log_action("send_attempt", handle, message, mode="live")

    result = await send_dm_playwright(
        handle=handle,
        message=message,
        headless=not args.visible,
    )

    if result["success"]:
        print(f"\n  DM SENT successfully to @{handle}")
        if result.get("screenshot"):
            print(f"  Screenshot: {result['screenshot']}")
        log_action("send_success", handle, message, result="sent", extra=result)
    else:
        print(f"\n  DM FAILED: {result.get('error', 'unknown')}")
        log_action("send_failed", handle, message, result=result.get("error", "unknown"))

    print(f"\n{'='*60}")


if __name__ == "__main__":
    asyncio.run(main())
