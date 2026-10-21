# W1 首轮交付与运行说明

日期：2026-10-21。分支 `codex/core-pipeline`，准确基点 `74f163bf69559f02ad70ae1d5bb730e1f10d15bf`。公共契约及统一 fixture 未修改。真实 Data Gate 未通过；程序交付身份为 **SYNTHETIC_ONLY**。

## 可运行内容

- W1-01：规范CSV读取、重复/冲突/缺口审计、独立标签、四段切分；真实MAT/四份CSV比对及失败报告。
- W1-02：训练拟合预处理、连续中位数/MAD历史、正常窗口资格和共同分钟交集。
- W1-03：IF、当前AE和增强AE共用流水线；CLI训练/评分、模型保存重载、独立校准与原子产物。
- W1-04：逐点评价、覆盖、完全漏报片段及共同时间交集内核。正式比较、参数选择和高负载分组未执行。

环境沿用[公共锁](../src/core/requirements-cpu-lock.txt)，本work使用独立.venv、pip缓存、.runtime/w1/raw、私有输出目录，无数据库或页面服务。安装见[开发环境](../docs/guides/development.md)，安装后实际 `pip check` 无冲突。

```powershell
.venv\Scripts\python -m pytest tests/core -q
.venv\Scripts\python -m pytest -q
.venv\Scripts\python -m pip check
.venv\Scripts\python -m traffic_anomaly.cli demo --workspace .runtime/w1/outputs/w1-smoke
.venv\Scripts\python -m traffic_anomaly.cli run --config configs/core/smoke.example.json --workspace .runtime/w1/outputs/w1-smoke
```

demo 显式生成160分钟手工规则数据和可信本地 registry.json，四段各40分钟，H=3仅供边界检查；不覆盖已有数据或登记表。输出JSON中的路径均相对workspace，run_id动态生成。对输出的完整运行目录继续执行：

```powershell
.venv\Scripts\python -m traffic_anomaly.cli verify --run <完整运行目录>
.venv\Scripts\python -m traffic_anomaly.cli score --model <完整运行目录>/model --config configs/core/smoke.example.json --workspace .runtime/w1/outputs/w1-smoke
```

API执行入口仍为 `execute_run(config, workspace) -> RunResult`。W2可使用合成工作区测试适配；**W2-02真实接入验收未放行**。registry为本地受信配置，网页不传路径。真实注册项会在训练前明确失败；当前版本不提供真实Gate解锁开关。

产物按公共契约保存 summary/config/metrics、完整测试轴 scores/channels、完整独立标签轴、模型与预处理、manifest摘要；另存 audit/splits/runtime诊断。必需文件完成并校验后，临时目录才原子更名为成功目录。中途失败保留.tmp供本地诊断，消费者不得将其作为成功结果。模型统一通过 `artifacts.load_model`：先验清单、摘要和跨文件关系，再调用公共兼容检查，最后反序列化实际载荷。底层Detector.load是已验证包内部的执行接口，不能替代统一加载入口。

UTC时间表读取使用 `artifacts.read_table`，避免Windows缺少IANA时区库时直接Arrow转Python datetime失败；存储类型仍为timestamp[ns,UTC]，没有改公共Schema。载荷、原始评分、权重、虚拟环境与绝对私人路径不提交。

## 验证与限制

新增测试先在缺少模块时失败；补充Row首列识别、零正常分母、非整分纳秒时间回归均观察到失败后修复。实际验证：核心60项通过；完整pytest为73项通过、7个subtests通过；仓库unittest为13项通过。独立审查发现两处跨文件一致性问题，三项回归先失败，修复后通过。合成测试包含未来值不影响过去、缺口重置、标签重叠、校准空集、阈值相等不报警、AE通道等权、三方法重载、改动测试标签不影响评分，以及损坏模型拒载。

[真实审计结果](../data/AUDIT_REPORT.md)记录2,874训练正常候选和0测试正常候选及未知时区，须由W0汇总处理；不通过改变背景身份、测试范围或模型特征绕过问题。真实IF/AE、正式效果比较与效率测量继续NOT_RUN。Desktop提交/远端/CI状态以最终实际记录为准，不预写成功。

实际CLI：IF运行及score重载成功，40个测试分钟中37个有效；当前AE与历史AE均运行成功，均为合成数据。真实audit-provider返回码2。README生成检查、公共OpenAPI不变检查、依赖检查、隐私与作者检查均通过；正式研究不据此升级。
