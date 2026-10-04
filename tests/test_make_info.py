"""scripts/make_info.pyのテスト。リポジトリのルートで python3 -m unittest discover -s tests -v"""

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures"
SCRIPT = ROOT / "scripts" / "make_info.py"
sys.path.insert(0, str(ROOT / "scripts"))

import make_info  # noqa: E402

PACKAGE = "https://raw.githubusercontent.com/ejointjp/wordpress-plugin-updates/main/sample-plugin/sample-plugin-1.2.3.zip"
LAST_UPDATED = "2026-10-04 12:00:00"


def read(path):
    return (FIXTURES / path).read_text(encoding="utf-8")


class ReadHeaderTest(unittest.TestCase):
    def test_reads_value_from_docblock(self):
        self.assertEqual("Sample Plugin", make_info.read_header(read("sample-plugin/sample-plugin.php"), "Plugin Name"))
        self.assertEqual("6.4", make_info.read_header(read("sample-plugin/sample-plugin.php"), "Requires at least"))

    def test_reads_value_from_plain_comment(self):
        self.assertEqual("0.1.0", make_info.read_header(read("no-readme/no-readme.php"), "Version"))

    def test_missing_field_is_empty(self):
        self.assertEqual("", make_info.read_header(read("no-readme/no-readme.php"), "Requires PHP"))

    def test_does_not_match_a_longer_field_name(self):
        # 「Version」が「Requires PHP」などの行や、本文中の文字列に当たらないこと
        self.assertEqual("1.2.3", make_info.read_header(read("sample-plugin/sample-plugin.php"), "Version"))


class InlineTest(unittest.TestCase):
    def test_escapes_html(self):
        self.assertEqual("&lt;script&gt;alert(1)&lt;/script&gt;", make_info.inline("<script>alert(1)</script>"))

    def test_code_bold_and_link(self):
        self.assertEqual(
            '<strong>Bold</strong> and <code>a &lt; b</code> and <a href="https://example.com/">site</a>',
            make_info.inline("**Bold** and `a < b` and [site](https://example.com/)"),
        )

    def test_code_is_not_formatted(self):
        self.assertEqual("<code>**not bold**</code>", make_info.inline("`**not bold**`"))

    def test_only_http_links_become_anchors(self):
        self.assertEqual("[x](javascript:alert(1))", make_info.inline("[x](javascript:alert(1))"))


class ToHtmlTest(unittest.TestCase):
    def test_headings_lists_and_paragraphs(self):
        body = "Intro line one\nline two\n\n= Title =\n* A\n* B\n\nOutro"
        self.assertEqual(
            "<p>Intro line one\nline two</p>\n<h4>Title</h4>\n<ul><li>A</li><li>B</li></ul>\n<p>Outro</p>",
            make_info.to_html(body),
        )

    def test_list_item_continues_on_next_line(self):
        self.assertEqual("<ul><li>First part second part</li></ul>", make_info.to_html("* First part\n  second part"))

    def test_list_right_after_paragraph(self):
        self.assertEqual("<p>Lead:</p>\n<ul><li>A</li></ul>", make_info.to_html("Lead:\n* A"))


class BuildInfoTest(unittest.TestCase):
    def test_with_readme(self):
        info = make_info.build_info(
            read("sample-plugin/sample-plugin.php"),
            read("sample-plugin/readme.txt"),
            "sample-plugin",
            "1.2.3",
            PACKAGE,
            LAST_UPDATED,
        )
        self.assertEqual(json.loads(read("sample-plugin/expected.json")), info)

    def test_without_readme(self):
        info = make_info.build_info(
            read("no-readme/no-readme.php"), None, "no-readme", "0.1.0", "https://example.com/x.zip", LAST_UPDATED
        )
        self.assertEqual(
            {
                "name": "No Readme",
                "slug": "no-readme",
                "version": "0.1.0",
                "author": "Takashi Fujisaki",
                "last_updated": LAST_UPDATED,
                "package": "https://example.com/x.zip",
                "sections": {"description": "<p>Has &quot;quotes&quot; &amp; no readme.</p>"},
            },
            info,
        )

    def test_header_version_mismatch_stops(self):
        with self.assertRaises(SystemExit) as raised:
            make_info.build_info(read("sample-plugin/sample-plugin.php"), None, "sample-plugin", "1.2.4", PACKAGE, LAST_UPDATED)
        self.assertIn("Version", str(raised.exception))

    def test_stable_tag_mismatch_stops(self):
        readme = read("sample-plugin/readme.txt").replace("Stable tag: 1.2.3", "Stable tag: 1.2.2")
        with self.assertRaises(SystemExit) as raised:
            make_info.build_info(read("sample-plugin/sample-plugin.php"), readme, "sample-plugin", "1.2.3", PACKAGE, LAST_UPDATED)
        self.assertIn("Stable tag", str(raised.exception))

    def test_missing_plugin_name_stops(self):
        with self.assertRaises(SystemExit):
            make_info.build_info("<?php\n// Version: 1.0.0\n", None, "x", "1.0.0", PACKAGE, LAST_UPDATED)


class CliTest(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True, check=False)

    def test_prints_expected_json(self):
        result = self.run_cli(
            "--main", str(FIXTURES / "sample-plugin" / "sample-plugin.php"),
            "--readme", str(FIXTURES / "sample-plugin" / "readme.txt"),
            "--slug", "sample-plugin",
            "--version", "1.2.3",
            "--package", PACKAGE,
            "--last-updated", LAST_UPDATED,
        )
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(read("sample-plugin/expected.json"), result.stdout)

    def test_version_mismatch_prints_nothing_and_fails(self):
        result = self.run_cli(
            "--main", str(FIXTURES / "sample-plugin" / "sample-plugin.php"),
            "--slug", "sample-plugin",
            "--version", "9.9.9",
            "--package", PACKAGE,
        )
        self.assertNotEqual(0, result.returncode)
        self.assertEqual("", result.stdout)

    def test_default_last_updated_is_utc_now(self):
        result = self.run_cli(
            "--main", str(FIXTURES / "no-readme" / "no-readme.php"),
            "--slug", "no-readme",
            "--version", "0.1.0",
            "--package", "https://example.com/x.zip",
        )
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertRegex(json.loads(result.stdout)["last_updated"], r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$")


if __name__ == "__main__":
    unittest.main()
