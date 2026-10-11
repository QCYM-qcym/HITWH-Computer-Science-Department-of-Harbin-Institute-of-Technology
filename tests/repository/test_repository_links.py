"""当前导航链接边界；历史Wiki与外部来源不由此工具核验。"""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("repository_check", ROOT / "tools/repository/check_repository.py")
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


class LinkTests(unittest.TestCase):
    def test_authorized_repository_link_is_not_private_account_text(self):
        url = "https://github.com/QCYM-qcym/HITWH-Computer-Science-Department-of-Harbin-Institute-of-Technology"
        term = url.split("/")[-2].split("-")[0]
        self.assertEqual(checker.inspect("README.md", (url + "/actions/workflows/check.yml/badge.svg").encode(), [term]), [])
        self.assertIn("本地禁止项", checker.inspect("README.md", term.encode(), [term]))
        self.assertIn("本地禁止项", checker.inspect("README.md", (url + "-copy").encode(), [term]))

    def inspect_links(self, name, text, files):
        self.assertTrue(hasattr(checker, "check_links"), "缺少当前入口链接检查")
        return checker.check_links(name, text, set(files))

    def test_valid_relative_and_encoded_links(self):
        self.assertEqual(self.inspect_links("docs/README.md", "[报告](<reports/报告.md>) [首页](../README.md#进度)",
                                            ["docs/reports/报告.md", "README.md"]), [])

    def test_broken_link_and_escape_are_rejected(self):
        self.assertTrue(self.inspect_links("docs/README.md", "[缺失](missing.md)", ["docs/README.md"]))
        self.assertTrue(self.inspect_links("README.md", "[越界](../outside.md)", ["README.md"]))

    def test_external_anchor_and_code_are_not_local_files(self):
        self.assertEqual(self.inspect_links("README.md", "[来源](https://example.org/paper) [段落](#进度)\n```md\n[示例](missing.md)\n```", []), [])


if __name__ == "__main__":
    unittest.main()
