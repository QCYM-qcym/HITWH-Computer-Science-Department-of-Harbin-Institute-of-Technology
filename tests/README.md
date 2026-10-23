# 测试

修订2026-10-23。当前已有核心/后端/集成及前端合成测试，运行入口见[联调记录](../docs/project/W0-SYNTHETIC-INTEGRATION-2026-10-21.md)。真实工程和正式模型实验仍NOT_RUN，工程测试通过不升级研究验收。

本轮新增`data_audit/test_c18_prefix.py`，只使用人工CSV验证前缀截断、字段重复、非有限值、标签缺失、Benign拼写及时间/协议歧义，不联网、不拟合模型；真实前缀只在本地离线核查。与既有维护测试分别运行：

```powershell
python -X utf8 -m unittest discover -s tests/data_audit -p 'test_*.py'
python -X utf8 -m unittest discover -s tests/repository -p 'test_*.py'
```

CI的Python检查包含`tests/core tests/backend tests/integration tests/data_audit`；真实数据载荷不进入CI。

