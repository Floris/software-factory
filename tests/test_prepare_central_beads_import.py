import json
from pathlib import Path
import sys
import tempfile
import unittest


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from prepare_central_beads_import import prepare  # noqa: E402


class PrepareCentralBeadsImportTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)

    def source(self, name, rows):
        path = self.root / name
        path.write_text("".join(json.dumps(row) + "\n" for row in rows))
        path.chmod(0o600)
        return path

    def test_preserves_issue_and_adds_validated_routing(self):
        first = self.source("factory.jsonl", [{"_type": "issue", "id": "sf-1", "title": "Factory", "dependencies": [{"issue_id": "sf-1", "depends_on_id": "et-1", "type": "blocks"}]}])
        second = self.source("product.jsonl", [{"_type": "issue", "id": "et-1", "title": "Product", "comments": [{"text": "kept"}]}])
        output = self.root / "combined.jsonl"

        summary = prepare([("software-factory", first), ("expense-tracker", second)], output)

        rows = [json.loads(line) for line in output.read_text().splitlines()]
        self.assertEqual(summary["issue_count"], 2)
        self.assertEqual(summary["dependency_count"], 1)
        self.assertEqual(output.stat().st_mode & 0o777, 0o600)
        self.assertEqual(rows[0]["metadata"]["repository_id"], "software-factory")
        self.assertEqual(rows[1]["metadata"]["repository_id"], "expense-tracker")
        self.assertEqual(rows[1]["comments"], [{"text": "kept"}])

    def test_duplicate_id_fails_without_output(self):
        issue = {"_type": "issue", "id": "et-1", "title": "Task"}
        first = self.source("a.jsonl", [issue])
        second = self.source("b.jsonl", [issue])
        output = self.root / "combined.jsonl"

        with self.assertRaisesRegex(ValueError, "duplicate issue ID"):
            prepare([("factory", first), ("product", second)], output)
        self.assertFalse(output.exists())

    def test_conflicting_repository_fails_without_output(self):
        source = self.source("a.jsonl", [{"_type": "issue", "id": "sf-1", "title": "Task", "metadata": {"repository_id": "other"}}])
        output = self.root / "combined.jsonl"

        with self.assertRaisesRegex(ValueError, "conflicting repository_id"):
            prepare([("factory", source)], output)
        self.assertFalse(output.exists())

    def test_dangling_dependency_fails_without_output(self):
        source = self.source("a.jsonl", [{"_type": "issue", "id": "sf-1", "title": "Task", "dependencies": [{"issue_id": "sf-1", "depends_on_id": "missing", "type": "blocks"}]}])
        output = self.root / "combined.jsonl"

        with self.assertRaisesRegex(ValueError, "dangling dependency"):
            prepare([("factory", source)], output)
        self.assertFalse(output.exists())

    def test_world_readable_export_is_rejected(self):
        source = self.source("a.jsonl", [{"_type": "issue", "id": "sf-1", "title": "Task"}])
        source.chmod(0o644)

        with self.assertRaisesRegex(ValueError, "private"):
            prepare([("factory", source)], self.root / "combined.jsonl")


if __name__ == "__main__":
    unittest.main()
