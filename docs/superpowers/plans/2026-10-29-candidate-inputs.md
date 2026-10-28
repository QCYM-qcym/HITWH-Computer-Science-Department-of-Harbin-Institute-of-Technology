# 候选输入计算开发计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans or superpowers:subagent-driven-development task-by-task. 提交与推送仅用GitHub Desktop。

**Goal:** 将已审计G13U候选表示实现为可运行、可人工复核的13维变换与26维因果历史输入。

**Architecture:** 独立候选模块，不更改134/268生产契约或运行入口。标签掩码只筛训练/校准资格；完整时间轴先变换，再构造历史。独立CLI仅接受显式SYNTHETIC_ONLY小样例，保存可重载变换与输入产物。

**Tech Stack:** 现有Python 3.14、NumPy和标准库；不新增依赖。

**Spec:** [报告V0.40 §4.1.1/4.1.2/4.1.7](../../reports/开题报告-V0.40-公开文本.md)、[G13U审计结果](../../research/2026-10-24-c17-g13u-audit.md)。日期：2026-10-29。依据用户“自己指定计划、自己进行开发”的授权，由主控确定工程方案并直接执行；不将其写成最终标签、主数据采用或真实实验批准。

## 方案与实施决定

直接放宽生产维度会牵动已冻结API、模型格式与UGR语义；只再整理审计计数无法填补数值计算缺口。本轮选择独立候选模块：完成输入计算及保存/重载，后续正式迁移另有明确接缝。变换沿用训练正常拟合log1p/StandardScaler（ddof=0），零方差scale=1；原始13项名称/顺序不变。所有对象固定SYNTHETIC_ONLY，不消费真实CSV或模型。

## Global Constraints

- 分钟输入13维，标签分离；当前13与历史偏离13拼成26。缺口、分段、分区和无效输入重置，不把缺分钟补零。
- H15/H30共同资格，训练与校准当前及过去全正常；测试历史不消费标签，测试当前正常资格另列。
- 历史只取当前之前H分钟，公式为(current-median)/(MAD+epsilon)，epsilon显式且正有限；无历史/非有限值用无效掩码与null导出。
- 变换参数只拟合训练段共同正常资格；验证/校准/测试值不得影响参数。不运行真实拟合、模型、评分、Q99或正式比较。
- 保留G12/G13U已有真实证据和生产契约；Data Gate/S2 BLOCKED，验收项分母不升级。

## Review Focus

1. 测试极值不能改变训练mean/scale，修改未来不能改变过去历史。
2. 原始与已变换空间不能混用；非有限、错误维度/顺序、标签列和长度错误拒绝。
3. 同segment但换partition仍重置；间隔和当前无效行不能被正常掩码跨越。
4. 变换保存/重载必须校验候选profile/特征顺序/数值；不能加载成原生产模型。
5. CLI显式合成身份、输入大小限制、JSON null及目录独占；失败不生成貌似完整产物，不覆盖既有输出。

## Task 1：独立候选数值模块（主控）

文件：新建`src/core/traffic_anomaly/candidate_inputs.py`、`tests/core/test_candidate_inputs.py`。

接口：`G13U_FEATURE_NAMES`、`CandidateMinuteBatch(timestamps, values, row_valid, segment_ids, partitions, feature_names=G13U_FEATURE_NAMES, value_space='raw', evidence_kind='SYNTHETIC_ONLY')`；严格递增整分钟datetime64[us]、(n,13) float64、bool(n)、字符串(n)，最大10000行。分区枚举train/validation/calibration/test按序，原始有效值非负有限，prepared有效值有符号有限；数组防御复制。

`CandidatePreprocessor().fit(batch, normal_candidates, window=30)`：筛训练且当前/此前连续window全normal；空集失败。`transform(batch)`保留原时间轴，返回prepared批次；`save(path)`独占写与`load(path)`验证版本/顺序和13维mean/scale。

`build_candidate_history(batch, *, window, epsilon)`只接prepared，返回current/residual/joined/valid/invalid_reason。`prepare_candidate_inputs(batch, normal_candidates, *, epsilon=1e-6)`固定H15/H30，返回`preprocessor`, `prepared`, `histories`（int键）, `common_valid`, `training_normal`, `calibration_normal`, `test_normal`；后3掩码均与common相交，训练/校准要求全H30正常，测试仅当前normal。不产出模型分数。

- [x] 先写手算、隔离、重置、错误输入及重载测试并实际RED。
- [x] 最小实现，跑相关测试GREEN；参数与边界不按效果更改。

## Task 2：有界合成CLI及产物（独立实现者）

文件：新建`src/core/traffic_anomaly/candidate_cli.py`、`tests/core/test_candidate_cli.py`、`tests/fixtures/g13u-inputs-v1.json`。

命令：`python -m traffic_anomaly.candidate_cli --fixture <json> --output <new-dir>`。fixture顶层恰含`schema_version:1`、`evidence_kind:SYNTHETIC_ONLY`、`time_basis:synthetic_source_clock`、`feature_names`、`minutes`、`normal_candidates`、`epsilon`。每分钟恰含`timestamp`（无时区整分钟ISO钟面）、`features`、`valid`、`segment_id`、`partition`；标签掩码是独立bool数组。fixture<=1MiB，<=10000行，不接CSV/联网/模型；禁止未知字段/冒充REAL。

产物：`candidate-inputs.json`（13/26值、掩码/原因及分区汇总）、`preprocess.json`、最后写`manifest.json`（合成身份、配置/fixture SHA、产物SHA/大小、完成状态）。所有非有限转null；不写scores/metrics，也不含私人路径。验证输入和数值后独占创建目录；目录存在拒绝覆盖。错误exit2、安全错误码，不回显路径/堆栈。

- [x] fixture包含四段各至少36分钟、测试标签变化；先CLI缺失/拒绝/独占测试RED。
- [x] 调用Task1共享实现，保存重载核对，CLI实际产物与模块输出一致；GREEN。

## Task 3：验收与交接（主控）

- [x] 新CLI实际运行，复核H15/H30、train/cal/test掩码、JSON合法及重载一致；状态仅SYNTHETIC_ONLY。
- [x] 独立审查实现与研究边界，有缺陷先失败复现再修；运行核心及契约/相关审计回归，仓库要求检查。
- [x] 更新开发说明、status/README、路线图/决定/Gate补记与Vault日志；保护历史证据，记录NOT_RUN。
- [ ] GitHub Desktop提交推送，核远端准确SHA/README和三项实际CI，不合并main。

本地完成证据：[验证与实际运行](../../guides/candidate-inputs.md)。提交/推送及本次CI按最终交付回复登记，不预填SHA。
