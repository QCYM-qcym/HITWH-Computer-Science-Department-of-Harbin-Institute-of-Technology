# 工具

- `repository/check_repository.py`：检查公开分区或Git索引，不输出敏感匹配值。
- `documentation/export_office_text.py`：用Python标准库从Office原稿抽取脱敏Markdown文本。它不处理图像，也不声称原Office文件已脱敏。

示例：

```bash
python tools/documentation/export_office_text.py 本地原稿.docx docs/reports/公开报告.md --redactions privacy.local.json
python tools/repository/check_repository.py --worktree
```

本地配置包含 `deny_terms` 数组或 `replacements` 字典，可填写需要去除的姓名、标识及文本。该配置必须保留在本地。导出后人工审阅并运行仓库检查，再使用GitHub Desktop提交。

