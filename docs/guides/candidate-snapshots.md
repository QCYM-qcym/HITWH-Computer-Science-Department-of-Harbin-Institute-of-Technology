# 已验证候选产物的只读快照

## 后续候选消费者

[候选13维IF合成入口](candidate-if-synthetic.md)现已消费本快照；必需原人工source重放通过，再独占输出和执行工程toy模型。它不改变本加载API、原写入格式或真实准入。

日期：2026-10-30。身份：**SYNTHETIC_ONLY**。用途：让后续候选消费者取得同一次有界读取、完整验证后的值，避免先校验再自行重开JSON。依据[只读产物复查](candidate-artifacts.md)和[本批计划](../superpowers/plans/2026-10-30-candidate-verified-snapshot.md)。本批不实现或运行候选IF，不做评分、校准或研究决策。

## Python入口

```python
from traffic_anomaly.candidate_artifacts import load_verified_candidate_artifacts

snapshot = load_verified_candidate_artifacts(
    ".runtime/P_U-adapt", ".runtime/P_U-inputs",
    source_fixture="tests/fixtures/g13u-records-v1.json",
)
assert snapshot.value_space == "prepared"
print(snapshot.current_values.shape)  # 已有人工样例为(144, 13)
print(snapshot.report_dict())
```

[核心实现](../../src/core/traffic_anomaly/candidate_artifacts.py)新增VerifiedCandidateArtifacts及VerifiedCandidateHistory。旧verify_candidate_artifacts和[命令行](../../src/core/traffic_anomaly/candidate_verify_cli.py)继续返回原JSON报告；不新增命令行参数或产物写入格式。新旧入口共享同一次验证过程，每个manifest/产物只读一次，可选源也只读一次；没有第二次文件内容读取或懒加载路径。

## 快照字段

| 字段 | 值及用途 |
|---|---|
| report | 原验证报告的递归只读映射；source_replay和fit_parameters范围保持 |
| provenance | record_manifest、input_manifest、source_fixture、minute_fixture、preprocess五组SHA256/byte_count，不含私人路径 |
| preprocessing_state | 原保存状态的递归只读副本；不暴露可变预处理器、不重新拟合 |
| feature_names / value_space | 固定13项顺序/`prepared`；与134/268生产契约隔离 |
| timestamps / segment_ids / partitions | 完整无偏移源钟面轴、采集段和四段身份 |
| raw_values / raw_valid | 分钟fixture原始13项；无效位置为NaN，不能当作0 |
| current_values / row_valid | 已验证数值产物中的13项prepared值及当前有效性 |
| histories[15/30] | current/residual/joined/valid数组和invalid_reason元组，保持预热、缺口与分段重置 |
| common_valid / training_normal / calibration_normal / test_normal | 原产物对齐资格；不会根据消费方式删行或重算标签 |
| labels / normal_candidates | 三政策独立三态标签元组和normal布尔掩码 |
| source_attack_label_present | 逐分钟原明确攻击存在标志，unknown不自动变成正常或攻击 |

缺源时provenance.source_fixture仍是记录manifest声明的摘要；report.checks.source_replay为NOT_PROVIDED。不能把“有摘要”解释成“已核对原源”。提供原人工源并通过重放才为VERIFIED。fit_parameters始终NOT_REESTIMATED，快照不认证参数拟合来源。

## 不可变与数值身份

映射递归只读，原JSON列表转为元组；冻结对象使用slots，普通属性、内部字典及嵌套映射不能改写快照。所有数组存储在不可写bytes中，赋值和setflags(write=True)都会失败。

每次访问数组属性或normal掩码都会返回独立NumPy view。调用者可以改变自己取得的view的shape/dtype/strides元数据，这不会改变快照内部元数据或下次获取的数组。调用`.copy()`可得到自己的可写副本。对Python反射或本机任意代码的刻意绕过不提供安全隔离承诺。

快照返回已验证的**实际产物值**。只读复查的1e-12浮点容差只用于验算；产物中容差内的细微数值差异仍保留，避免摘要绑定原字节、载荷却被无声替换成重算值。原null转换为NaN只用于已经验证的无效数值位置。report_dict()返回可修改的深副本，修改它不会影响快照。

加载完成后，即使原文件被改写或搬走，现有快照仍保持本次值与摘要；再次加载将重新检查当前文件。它不是文件锁、作者签名或研究批准凭证，消费者也不能据快照类型跳过真实准入。

## 实际验证与限制

独立新增22项测试，覆盖三政策有/无源、五摘要、23个数组存储及元数据隔离、单次读取/no-fit、原文件后改、实际产物微差和拒绝兼容。初次缺接口实际观察17失败/2通过；完整原始trace未保存，保留工具观察摘录并标明限制。审查发现冻结对象仍能通过__dict__改写，新增完整失败测试后为四类添加slots，最终通过。详见[验证记录](../research/2026-10-30-candidate-snapshots-verification.json)。

实际复用上一批三政策已有目录，有/无源6次加载通过；144分钟、24共同、训练/校准正常各6、测试当前normal4/5/4保持，18个产物文件字节未变。独立进程未导入torch/sklearn，未调用fit/prepare；人工修改局部view验证隔离时出现1项NumPy元数据setter弃用提示，保留记录。相关测试对该主动触发的接口只做局部精确过滤，不屏蔽其他警告。

读取白名单、字节上限、安全错误及link/reparse父路径检查沿用[既有规则](candidate-artifacts.md)。本批没有新增数据下载/真实CSV读取，没有训练、评分或阈值校准；最终Attempted/主数据采用/134-268迁移仍未批准，Data Gate/S2 BLOCKED，真实模型与正式实验NOT_RUN。
