# 候选单分钟详情

日期：2026-10-31。状态：SYNTHETIC_ONLY。用途：将已验证的候选运行分数与对应输入快照按同一分钟读取，为后续回放准备。依据[实施计划](../superpowers/plans/2026-10-31-candidate-minute-detail.md)、[运行快照](candidate-run-snapshots.md)和[输入快照](candidate-snapshots.md)。生产 HTTP、网页和 134/268 维契约未迁移。

```python
from traffic_anomaly.candidate_artifacts import load_verified_candidate_artifacts
from traffic_anomaly.candidate_run_artifacts import load_verified_candidate_if_run
from traffic_anomaly.candidate_details import candidate_minute_detail

inputs = load_verified_candidate_artifacts(
    ".runtime/P_U-adapt", ".runtime/P_U-inputs",
    source_fixture="tests/fixtures/g13u-records-v1.json",
)
run = load_verified_candidate_if_run(
    ".runtime/if-run", ".runtime/P_U-adapt", ".runtime/P_U-inputs",
    source_fixture="tests/fixtures/g13u-records-v1.json",
)
detail = candidate_minute_detail(run, inputs, "2026-01-01T00:30")
```

路径和时间是调用示例，不保证相应运行目录已存在。AE 使用对应的 `load_verified_candidate_ae_run` 加载入口。加载器照常验算保存的变换、历史与阈值关系；单分钟查询本身只读取内存，不打开文件、运行模型或重新计算历史、阈值、评价指标。

查询先检查运行与输入的五组产物摘要及大小、政策、特征顺序、预处理状态、H15/H30 窗口，以及完整时间、采集段、分区和有效性轴。五组身份为记录 manifest、输入 manifest、源 fixture、分钟 fixture 和预处理文档；标签审计文件由记录 manifest 间接绑定。检查完整轴后才选择分钟，不能只凭相同 run_id 或单个时间戳拼接不同输入。

时间只接受 `YYYY-MM-DDTHH:MM`、末尾 `:00` 或 `:00.000000` 三种整分钟形式。输出沿用保存文档的规范形式，`time_basis` 保持 `synthetic_source_clock`。带 Z、时区偏移、非零秒或小数以及非法日期均拒绝；不调用机器本地时区，不把未知源钟面认证为 UTC。

返回普通字典，修改它不会改变两个快照。字段分组如下：

| 分组 | 含义 |
| --- | --- |
| run_id、selected_policy、feature_names | 运行身份、审计对照政策及 13 个特征的固定顺序 |
| source_replay | 分别保存运行与输入的来源重放状态；只有二者都 VERIFIED，combined 才 VERIFIED |
| point | 分钟、采集段、分区、评分有效性、原分数、报警和阈值 |
| inputs.raw / inputs.prepared | 原始聚合值与预处理值各 13 维，分别保留自己的 valid |
| histories.15 / histories.30 | 已保存的历史偏离、有效性和无效原因；不在查询时补造历史 |
| labels | P_U/P_B/P_A 分钟分类和源攻击标签存在标记，独立于特征；不是原始逐流标签明细 |
| reconstruction | AE 已保存的当前/历史偏离组标量 MSE；IF 标 NOT_APPLICABLE；逐特征误差标 NOT_STORED |

评分无效时 score/alarm 维持 null。当前输入可用并不保证历史预热完成：原始值、预处理值、H15、H30 与评分各用自己的有效性；H15 可用而 H30 未就绪时，H15 偏离仍可读取。两种历史作为输入通道同时提供，不表示该模型使用了两个窗口；具体方法和所选窗口仍读取原运行报告。无效向量是 13 个 null，不能以零值伪装成正常。AE 的 APPLICABLE 通道在评分无效时也可以为 null；当前 AE 没有历史重构通道，不补造 0。

接口抛出 `CandidateDetailError`，公开消息与 code 均为安全枚举：`INVALID_QUERY`（格式错误）、`MINUTE_NOT_FOUND`（轴上没有该分钟）、`INCOMPATIBLE_SNAPSHOTS`（类型或配对不符）。错误不带文件路径、载荷或内部堆栈。快照对象与这些一致性检查均不是来源认证；调用者应使用既有加载器，不能把自行构造的对象当作已验收产物。

此接口没有范围分页、页面抽样、模型比较或指标重算。完整分钟评价仍来自原运行报告。原人工无报警负例照常保留。新增58项测试、相关110项通过。57项先失败，首次实现的24:00归次日问题已修复；测试夹具准备训练人工toy模型。主控实际复用四个旧人工包完成12详情、24时间别名、12副本隔离、4弱来源状态和8错误查询，39旧文件SHA/大小/mtime保持；该实际验收没有模型库导入或执行，查询无文件IO/历史阈值评价复算。[验证记录](../research/2026-10-31-candidate-minute-detail-verification.json)。真实 CSV、下载、真实模型训练评分校准和正式实验未执行，Data Gate 保持 BLOCKED。
