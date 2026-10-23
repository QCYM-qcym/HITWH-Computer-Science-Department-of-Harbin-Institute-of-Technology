# 工具

- `repository/update_progress.py --write`：从docs/project/status.json生成README标记内的进度，保留外部正文。
- `repository/update_progress.py --check`：验证状态、验收分母、仓库证据、阶段图/表一致；`--staged`读取Git索引并要求本次提交更新进度区。

使用`python -X utf8`在Windows显式设置UTF-8；Python3.10+标准库即可。测试命令见[tests](../tests/README.md)。阶段完成条件的证据内容仍需维护者审阅，工具仅验证结构/路径和状态一致性，不自动认定研究结论。

- `repository/check_repository.py`：检查公开分区或Git索引，不输出敏感匹配值。
- `data_audit/c18_prefix.py`：仅离线核查获准C18-S前缀，拒绝大于4MiB的单文件，复核获取清单及片段SHA256，输出字段、时间钟面和标签汇总；没有下载或模型入口。用法与实际结果见[结构样本记录](../docs/research/2026-10-23-c18-structure-sample.md)。
- `documentation/export_office_text.py`：用Python标准库从Office原稿抽取脱敏Markdown文本。它不处理图像，也不声称原Office文件已脱敏。

示例：

```bash
python tools/documentation/export_office_text.py 本地原稿.docx docs/reports/公开报告.md --redactions privacy.local.json
python tools/repository/check_repository.py --worktree
```

本地配置包含 `deny_terms` 数组或 `replacements` 字典，可填写需要去除的姓名、标识及文本。该配置必须保留在本地。导出后人工审阅并运行仓库检查，再使用GitHub Desktop提交。

