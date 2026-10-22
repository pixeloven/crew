import json
import pathlib
import subprocess
import sys
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


def run(script: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts" / script), *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def write(root: pathlib.Path, rel: str, text: str) -> pathlib.Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


class LinkCheckTests(unittest.TestCase):
    def check(self, root: pathlib.Path) -> subprocess.CompletedProcess[str]:
        return run("check_links.py", str(root))

    def test_resolving_links_pass(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            write(root, "docs/guide.md", "# Guide\n")
            write(root, "skills/a/SKILL.md", "x\n")
            write(
                root,
                "README.md",
                "[guide](docs/guide.md) [frag](docs/guide.md#guide) "
                "[dir](skills/a/) [titled](docs/guide.md \"Title\") "
                "![img](<docs/guide.md>)\n\n[ref]: ./docs/guide.md\n",
            )
            write(root, "skills/a/notes.md", "[up](../../README.md) [self](SKILL.md)\n")
            completed = self.check(root)
            self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr)
            self.assertIn("relative links resolve", completed.stdout)

    def test_missing_target_fails_with_location(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            write(root, "docs/guide.md", "intro\n\nsee [gone](missing.md#x)\n")
            completed = self.check(root)
            self.assertNotEqual(0, completed.returncode)
            self.assertIn("docs/guide.md:3", completed.stdout)
            self.assertIn("missing.md", completed.stdout)
            self.assertIn("does not exist", completed.stdout)

    def test_link_escaping_repo_root_fails_even_if_target_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            outer = pathlib.Path(tmp)
            root = outer / "repo"
            write(outer, "outside.md", "sibling checkout\n")
            write(root, "skills/a/SKILL.md", "[sib](../../../outside.md)\n")
            write(root, "README.md", "[ref link][r]\n\n[r]: ../outside.md\n")
            completed = self.check(root)
            self.assertNotEqual(0, completed.returncode)
            self.assertIn("skills/a/SKILL.md:1", completed.stdout)
            self.assertIn("README.md:3", completed.stdout)
            self.assertEqual(2, completed.stdout.count("escapes the repo"))

    def test_external_anchor_and_code_links_are_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            write(
                root,
                "README.md",
                "[web](https://example.com/x.md) [plain](http://example.com) "
                "[mail](mailto:a@b.c) [anchor](#section)\n"
                "inline `[nope](missing.md)` and ``[nope](also-missing.md)``\n"
                "```md\n[fenced](missing.md)\n```\n"
                "~~~\n[tilde](../../outside.md)\n~~~\n",
            )
            completed = self.check(root)
            self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr)

    def test_excluded_and_unscanned_dirs_are_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            for rel in (
                "node_modules/pkg/README.md",
                ".remember/notes.md",
                "skills/a/node_modules/x.md",
                "tests/fixtures/consumer/AGENTS.md",
            ):
                write(root, rel, "[broken](missing.md)\n")
            completed = self.check(root)
            self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr)

    def test_repo_itself_passes(self) -> None:
        completed = run("check_links.py")
        self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr)


class VersionCheckTests(unittest.TestCase):
    def repo(self, tmp: str, **manifests: dict) -> pathlib.Path:
        root = pathlib.Path(tmp)
        for rel, data in manifests.items():
            write(root, rel.replace("__", "/"), json.dumps(data))
        return root

    def test_agreeing_sources_pass(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.repo(
                tmp,
                **{
                    "package.json": {"version": "1.2.3"},
                    ".claude-plugin__plugin.json": {"version": "1.2.3"},
                },
            )
            completed = run("check_versions.py", str(root))
            self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr)
            self.assertIn("1.2.3", completed.stdout)

    def test_disagreement_lists_every_source_and_value(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.repo(
                tmp,
                **{
                    "package.json": {"version": "1.2.3"},
                    ".claude-plugin__plugin.json": {"version": "1.2.3"},
                    ".codex-plugin__plugin.json": {"version": "1.1.0"},
                },
            )
            completed = run("check_versions.py", str(root))
            self.assertNotEqual(0, completed.returncode)
            for line in (
                "package.json: 1.2.3",
                ".claude-plugin/plugin.json: 1.2.3",
                ".codex-plugin/plugin.json: 1.1.0",
            ):
                self.assertIn(line, completed.stdout)

    def test_optional_manifest_without_version_is_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.repo(
                tmp,
                **{
                    "package.json": {"version": "2.0.0"},
                    ".claude-plugin__plugin.json": {"version": "2.0.0"},
                    ".codex-plugin__plugin.json": {"name": "x"},
                },
            )
            completed = run("check_versions.py", str(root))
            self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr)
            self.assertNotIn(".codex-plugin", completed.stdout)

    def test_required_source_missing_version_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.repo(
                tmp,
                **{
                    "package.json": {"version": "2.0.0"},
                    ".claude-plugin__plugin.json": {"name": "x"},
                },
            )
            completed = run("check_versions.py", str(root))
            self.assertNotEqual(0, completed.returncode)
            self.assertIn(".claude-plugin/plugin.json", completed.stdout)

    def test_tag_is_compared_with_or_without_v_prefix(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.repo(
                tmp,
                **{
                    "package.json": {"version": "1.2.3"},
                    ".claude-plugin__plugin.json": {"version": "1.2.3"},
                },
            )
            ok = run("check_versions.py", "--tag", "v1.2.3", str(root))
            self.assertEqual(0, ok.returncode, ok.stdout + ok.stderr)
            bad = run("check_versions.py", "--tag", "v1.2.4", str(root))
            self.assertNotEqual(0, bad.returncode)
            self.assertIn("git tag: 1.2.4", bad.stdout)

    def test_repo_itself_passes(self) -> None:
        completed = run("check_versions.py")
        self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr)


if __name__ == "__main__":
    unittest.main()
