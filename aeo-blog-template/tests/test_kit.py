"""Offline checks for publication gates, output safety, and structured data."""

import contextlib
import importlib.util
import io
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class KitTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="aeo-kit-test-")
        self.addCleanup(self.temporary.cleanup)
        self.kit = Path(self.temporary.name) / "kit"
        shutil.copytree(ROOT, self.kit, ignore=shutil.ignore_patterns(
            ".env", ".tmp", ".venv", "__pycache__", "public", "preview"))
        self.builder = load_module("kit_builder", self.kit / "execution/build_site.py")

    def build(self, *args):
        result = subprocess.run(
            [sys.executable, "-X", "utf8", str(self.kit / "execution/build_site.py"), *args],
            cwd=self.kit, capture_output=True, text=True, encoding="utf-8", timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_production_excludes_drafts_and_future_pages_from_all_indexes(self):
        (self.kit / "content/guides/future.md").write_text(
            "---\ntitle: Future page\npublishDate: 9999-12-31\n---\n# Future page", encoding="utf-8")
        self.build()
        public = self.kit / "public"
        self.assertFalse((public / "queue/example-future-guide/index.html").exists())
        self.assertFalse((public / "guides/future/index.html").exists())
        self.assertEqual(len(list(public.rglob("*.html"))), 6)
        sitemap = (public / "sitemap.xml").read_text(encoding="utf-8")
        self.assertEqual(len(ET.fromstring(sitemap)), 6)
        for name in ("sitemap.xml", "llms.txt"):
            index = (public / name).read_text(encoding="utf-8")
            self.assertNotIn("/queue/", index)
            self.assertNotIn("/guides/future/", index)

    def test_preview_includes_drafts_and_preserves_production(self):
        self.build()
        production = (self.kit / "public/index.html").read_bytes()
        self.build("--include-drafts")
        self.assertTrue((self.kit / "preview/queue/example-future-guide/index.html").is_file())
        self.assertEqual((self.kit / "public/index.html").read_bytes(), production)

    def test_faq_text_matches_schema_and_html_does_not_break_out(self):
        page = next(p for p in self.builder.load_pages() if p["slug"] == "prepare-for-service")
        question = 'Can <script>alert("test")</script> & a quoted question appear?'
        answer = 'Yes, as text: </script><script>untrusted()</script>.'
        page["meta"]["faqs"] = [{"q": question, "a": answer}]
        markup = self.builder.schema_blocks(page)
        blocks = re.findall(r'<script type="application/ld\+json">(.*?)</script>', markup, re.S)
        parsed = [json.loads(block) for block in blocks]
        faq = next(item for item in parsed if item["@type"] == "FAQPage")
        self.assertEqual(faq["mainEntity"][0]["name"], question)
        self.assertEqual(faq["mainEntity"][0]["acceptedAnswer"]["text"], answer)
        from html import unescape
        visible = self.builder.faq_html(page)
        self.assertNotIn("<script>", visible)
        self.assertIn(question, unescape(visible))
        self.assertIn(answer, unescape(visible))

    def test_output_guard_leaves_unrelated_files_untouched(self):
        outside = Path(self.temporary.name) / "important-files"
        outside.mkdir()
        marker = outside / "keep.txt"
        marker.write_text("keep", encoding="utf-8")
        with patch.object(self.builder, "PUBLIC", outside), patch.object(sys, "argv", ["build_site.py"]):
            with self.assertRaises(SystemExit):
                self.builder.main()
        self.assertEqual(marker.read_text(encoding="utf-8"), "keep")

    def test_research_dry_runs_never_send_requests(self):
        for script, args in (("discover_topics.py", []), ("enrich_faqs.py", ["--all", "--dry-run"])):
            module = load_module(script.replace(".py", ""), self.kit / "execution" / script)
            with patch.object(module.requests, "post", side_effect=AssertionError("Network request")), \
                    patch.object(sys, "argv", [script, *args]), contextlib.redirect_stdout(io.StringIO()):
                module.main()

    def test_competitor_analysis_does_not_fall_back_to_paid_provider(self):
        module = load_module("kit_competitor", self.kit / "execution/analyze_competitor.py")
        with patch.object(module, "_get", return_value=None), \
                patch.object(module, "FIRECRAWL_KEY", "test-key"), \
                patch.object(module, "firecrawl_html", side_effect=AssertionError("Paid request")), \
                patch.object(module, "firecrawl_map", side_effect=AssertionError("Paid request")):
            self.assertIsNone(module.profile_page("https://example.org/test/"))
            module.analyze("example.org", 1)

    def test_invalid_weekdays_fail_instead_of_hanging(self):
        result = subprocess.run(
            [sys.executable, str(self.kit / "execution/schedule_drip.py"),
             "--start", "2026-11-03", "--days", "7"],
            capture_output=True, text=True, timeout=10)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("weekday numbers", result.stderr)


if __name__ == "__main__":
    unittest.main()
