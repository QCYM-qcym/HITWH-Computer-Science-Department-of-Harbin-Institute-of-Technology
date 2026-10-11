"""维护工具契约测试；不下载数据或执行检测实验。"""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

TOOL = Path(__file__).resolve().parents[2] / "tools/repository/update_progress.py"


class ProgressTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "docs/project").mkdir(parents=True)
        (self.root / "docs/project/ROADMAP.md").write_text("规划", encoding="utf-8")
        self.source = {
            "schema_version": 1, "updated": "2026-10-11", "current_stage": "S0",
            "theme": "维护进度", "counting_scope": "阶段验收清单v1",
            "recent_changes": ["核对文档", "更新进度", "研究状态保持不变"], "blockers": ["实验未运行"],
            "next_tasks": [{"id": f"TASK-0{i}", "text": "登记评审", "path": "docs/project/ROADMAP.md"} for i in range(1, 4)],
            "entrypoints": [{"label": "规划", "path": "docs/project/ROADMAP.md"}],
            "stages": [{"id": "S0", "name": "需求", "status": "IN_PROGRESS",
                        "next": "评审", "entry": "docs/project/ROADMAP.md",
                        "criteria": [{"id": "S0-C1", "text": "文档", "met": True,
                                      "evidence": ["docs/project/ROADMAP.md"]},
                                     {"id": "S0-C2", "text": "评审", "met": False, "evidence": []}]}],
        }
        self.save()
        (self.root / "README.md").write_text(
            "项目介绍\n\n<!-- PROJECT-PROGRESS:START -->\n旧状态\n<!-- PROJECT-PROGRESS:END -->\n\n末尾说明\n", encoding="utf-8")

    def save(self):
        (self.root / "docs/project/status.json").write_text(
            json.dumps(self.source, ensure_ascii=False), encoding="utf-8")

    def run_tool(self, *args):
        self.assertTrue(TOOL.exists(), "缺少 README 进度生成与核对工具")
        return subprocess.run([sys.executable, "-X", "utf8", str(TOOL), "--root", str(self.root), *args],
                              capture_output=True, text=True, encoding="utf-8")

    def test_write_preserves_surrounding_content_and_counts_evidence(self):
        result = self.run_tool("--write")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        readme = (self.root / "README.md").read_text(encoding="utf-8")
        self.assertTrue(readme.startswith("项目介绍\n\n"))
        self.assertTrue(readme.endswith("\n\n末尾说明\n"))
        self.assertIn("1/2", readme)
        self.assertIn("进行中", readme)
        self.assertIn("```mermaid", readme)
        self.assertEqual(self.run_tool("--check").returncode, 0)

    def test_check_rejects_stale_readme(self):
        self.assertNotEqual(self.run_tool("--check").returncode, 0)

    def test_recent_changes_requires_three_to_five_items(self):
        for count in (0, 1, 2, 6):
            with self.subTest(count=count):
                self.source["recent_changes"] = ["修订"] * count
                self.save()
                self.assertNotEqual(self.run_tool("--write").returncode, 0)

    def test_write_is_idempotent(self):
        self.assertEqual(self.run_tool("--write").returncode, 0)
        before = (self.root / "README.md").read_bytes()
        self.assertEqual(self.run_tool("--write").returncode, 0)
        self.assertEqual(before, (self.root / "README.md").read_bytes())

    def test_staged_check_reads_index_instead_of_unstaged_worktree(self):
        self.assertEqual(self.run_tool("--write").returncode, 0)
        subprocess.run(["git", "init", "-q"], cwd=self.root, check=True, capture_output=True)
        subprocess.run(["git", "add", "README.md", "docs"], cwd=self.root, check=True, capture_output=True)
        self.source["theme"] = "尚未暂存的新主题"
        self.save()
        self.assertEqual(self.run_tool("--check", "--staged").returncode, 0)
        self.assertNotEqual(self.run_tool("--check").returncode, 0)
        subprocess.run(["git", "add", "docs/project/status.json"], cwd=self.root, check=True, capture_output=True)
        self.assertNotEqual(self.run_tool("--check", "--staged").returncode, 0)

    def test_completed_requires_all_criteria(self):
        self.source["stages"][0]["status"] = "COMPLETED"
        self.save()
        self.assertNotEqual(self.run_tool("--write").returncode, 0)

    def test_not_run_cannot_contain_completed_criteria(self):
        self.source["stages"][0]["status"] = "NOT_RUN"
        self.save()
        self.assertNotEqual(self.run_tool("--write").returncode, 0)

    def test_met_criterion_requires_existing_repository_evidence(self):
        for evidence in ([], ["docs/missing.md"], ["../outside.md"]):
            with self.subTest(evidence=evidence):
                self.source["stages"][0]["criteria"][0]["evidence"] = evidence
                self.save()
                self.assertNotEqual(self.run_tool("--write").returncode, 0)

    def test_invalid_status_and_duplicate_criteria_fail_without_writing(self):
        original = (self.root / "README.md").read_bytes()
        good = copy.deepcopy(self.source)
        self.source["stages"][0]["status"] = "PASS"
        self.save()
        self.assertNotEqual(self.run_tool("--write").returncode, 0)
        self.source = good
        self.source["stages"][0]["criteria"].append(copy.deepcopy(self.source["stages"][0]["criteria"][0]))
        self.save()
        self.assertNotEqual(self.run_tool("--write").returncode, 0)
        self.assertEqual(original, (self.root / "README.md").read_bytes())


if __name__ == "__main__":
    unittest.main()
