# 候选IF五产物：不加载模型的只读验算

日期2026-10-30；身份**SYNTHETIC_ONLY**。用途：复查[候选IF人工运行](candidate-if-synthetic.md)的五个文件、上游身份和存储预测的一致性。范围见[本批计划](../superpowers/plans/2026-10-30-candidate-run-verifier.md)。本入口不训练、评分或反序列化模型，不改变生产134/268契约或研究准入。

## 运行

先按候选IF指南生成独立的record、input和run目录，再执行：

```powershell
python -X utf8 -m traffic_anomaly.candidate_run_verify_cli --run .runtime/toy-if-run --records .runtime/toy-if-records --inputs .runtime/toy-if-inputs
python -X utf8 -m traffic_anomaly.candidate_run_verify_cli --run .runtime/toy-if-run --records .runtime/toy-if-records --inputs .runtime/toy-if-inputs --source-fixture tests/fixtures/g13u-records-v1.json
```

命令只读，exit0打印JSON报告，exit2仅打印安全错误JSON。没有output/model/resume参数，不创建或修补任何文件。需要保存stdout时写到三个包目录外；包内额外文件会被拒绝。源码为[candidate_run_artifacts.py](../../src/core/traffic_anomaly/candidate_run_artifacts.py)和[薄CLI](../../src/core/traffic_anomaly/candidate_run_verify_cli.py)。

## 检查内容

| 对象 | 验算规则 |
|---|---|
| 物理包 | 恰为manifest/model-state/scores/evaluation四JSON及weights.bin；非空普通文件，无目录额外项 |
| 身份 | 四JSON的run_id、schema/model profile、13项顺序、prepared空间、源钟面、toy范围及AUDIT_ONLY政策一致 |
| 绑定 | 配置SHA、上游五摘要/保存参数与同次验证快照一致；manifest核四文件实际SHA/字节，state核weights，evaluation核scores字节 |
| 声明版本 | python/numpy/scikit_learn/joblib四项跨JSON一致；不检查本机模型库版本，不据此认证模型兼容 |
| 轴与资格 | 时间/segment/partition/当前valid、H15/H30理由、common/score_valid完整轴严格对应；score_valid必须精确等于common |
| 缺失 | 无效分数与报警必须null；有效分数必须有限number，报警必须bool；不允许以0/false替代未计算 |
| 拟合/校准索引 | 与快照train/cal全历史正常共同资格精确对应；索引不能乱序、重复、互换或用bool冒充整数 |
| Q99与报警 | 仅用存储calibration分数重算linear Q99；阈值、分位元数据和strict>报警精确匹配，无阈值容差 |
| 评价 | 在同一存储预测上重算三政策test分母、unknown、混淆、五指标及零分母原因，不做point-adjust |

极端但有限的分数仍可能使分位插值溢出；局部数值警告不回显路径，有限结果检查继续拒绝该包。重算只验算存储分数与当前固定算法一致，不是独立数学正确性或模型输出证明；既有手算和原模型当次重载记录分开保留。

原人工source可选。未提供时source_replay=NOT_PROVIDED，上游source摘要仅为声明；提供并核过才VERIFIED。原预处理来源仍不由本工具重新拟合或认证。

## 报告的证明范围

报告status=VERIFIED，scope=STORED_ARTIFACT_CONSISTENCY_ONLY，verifier_profile_id=c17-i1-g13u-iforest-run-verifier-v1。必须同时读取：

```json
{
  "model_deserialization": "NOT_PERFORMED",
  "model_score_replay": "NOT_CHECKED",
  "library_versions": "DECLARATION_CONSISTENT_ONLY",
  "model_type": "DECLARED_ONLY"
}
```

上述为checks内字段。weights只作为有界bytes核摘要；即使替换为不可加载的任意非空bytes并同步更新全部内部摘要，也可能通过字节一致性验算。成功不能解释为“权重可执行”“分数来自IF”“作者已认证”或“真实研究通过”。这里没有外部pickle加载入口，也不导入joblib/sklearn/torch；NumPy等基础依赖可能导入标准pickle模块，但验证不调用其反序列化函数。

版本不同但四JSON声明一致不会被当作加载兼容失败，因为本工具没有加载模型。数值规则若与未来实现不同可能导致精确验算失败，应保留失败并明确版本，不自动放宽阈值或重写产物。

## 读取预算与验证证据

单weights8MiB、单JSON16MiB、五文件总32MiB；先核全体物理大小，再按各文件及剩余总预算读取。每份运行文件只读一次，读取前后身份/大小核对；先检查原词法父路径的链接/Windows重解析点，再规范化目标。manifest只允许固定四项，不打开任意声明路径。上游快照沿用其独立预算；这些是文件载荷上限，不是解析对象内存峰值保证。

拒绝重复JSON键、NaN/Infinity、溢出数值、字段/类型/维度错误、缺文件、多文件、摘要断链和重封摘要后的语义冲突。安全错误不含私人路径、内容或堆栈。面对有本机写权限的恶意并发替换不提供文件系统事务保证。

实际复查既有toy-if-20261030-v1的两种source模式；原五运行文件、18上游文件及人工源保持字节不变，没有重跑模型。模型库导入与pickle.load/loads被主动禁止的独立进程仍可完成验证。测试、警告泄露修复与实际结果见[验证记录](../research/2026-10-30-candidate-run-verification.json)。

人工无报警/FNR1/precision null的负例保持。新下载/真实CSV读取0；真实拟合、IF/AE评分、真实Q99和正式实验NOT_RUN，最终标签/主数据采用/生产迁移待决，Data Gate/S2 BLOCKED。
