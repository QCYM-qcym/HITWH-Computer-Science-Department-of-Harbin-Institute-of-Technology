# 测试

## 2026-11-13 AE内存接口验证

[AE验证记录](../docs/research/2026-11-13-release-autoencoder-verification.json)分开登记175项手工用例与一次真实人工双视图观察。手工组为60项准入和115项数值/错误交互，模型使用闭合替身；最终一轮另有24次真实校准算术、96个选值断言。七次手工pytest观察含两次保留的围栏/环境配置失败，重叠用例不累加。实际双视图为2模型/10更新/12前向，独立后验规格和质量审查均C0/I0/M0。

本批未重复完整本地回归，新提交CI待核对；下文5624项完整回归属于AE新增前的独立批次。专门冷导入、安装、持久化、CLI和页面仍NOT_RUN，研究S2/Data Gate BLOCKED保持。API用法见[AE指南](../docs/guides/release-autoencoder.md)。

## 2026-11-13 学习状态工作流验证

新增测试分别覆盖标准库摘要、三类命令的路径与输出失败、六包注册、前台服务生命周期，以及独立页面的请求清理和规范字节。源码、人工安装命令链、真实服务及浏览器证据分别登记，入口见[学习状态指南](../docs/guides/release-if-learned.md)和[CLI 验证](../docs/research/2026-11-13-release-if-learned-cli-verification.json)。

前端联合测试使用实际后端工厂返回的字节；前端 CI 先按现有锁准备 Python 环境，再运行该测试。它不需要真实数据，也不执行模型拟合。当前完整 Python 回归5624项通过、26项跳过、1项既有警告及56个子测试通过，318.04秒；该完整合成套件包含已有人工模型测试，不声称全套零模型调用。另一次页面安装v2已接受55项HTTP、全部176分钟保存值及实际浏览器核对；首次安装模板校验失败保留，未重跑模型。分项结果以[工作流记录](../docs/research/2026-11-13-release-if-learned-workflow-verification.json)及[项目状态](../docs/project/status.json)为准。

修订2026-10-23。当前已有核心/后端/集成及前端合成测试，运行入口见[联调记录](../docs/project/W0-SYNTHETIC-INTEGRATION-2026-10-21.md)。真实工程和正式模型实验仍NOT_RUN，工程测试通过不升级研究验收。

本轮新增`data_audit/test_c18_prefix.py`，只使用人工CSV验证前缀截断、字段重复、非有限值、标签缺失、Benign拼写及时间/协议歧义，不联网、不拟合模型；真实前缀只在本地离线核查。与既有维护测试分别运行：

```powershell
python -X utf8 -m unittest discover -s tests/data_audit -p 'test_*.py'
python -X utf8 -m unittest discover -s tests/repository -p 'test_*.py'
```

CI的Python检查包含`tests/core tests/backend tests/integration tests/data_audit`；真实数据载荷不进入CI。

