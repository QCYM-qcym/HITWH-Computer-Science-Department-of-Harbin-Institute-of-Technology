# 候选合成产物：只读完整性与重放复查

日期：2026-10-30。状态：**SYNTHETIC_ONLY**。用途：复查[记录适配CLI](candidate-records.md)与[候选数值CLI](candidate-inputs.md)的两个完整输出目录。依据[本批计划](../superpowers/plans/2026-10-30-candidate-artifact-verifier.md)和[开题报告V0.40](../reports/开题报告-V0.40-公开文本.md)的可复现要求。研究准入、最终标签和真实模型授权不改变。

## 运行

沿用[开发环境](development.md)，无新增依赖。先按上述两个指南生成同一政策的记录适配和数值输出，再执行：

```powershell
python -X utf8 -m traffic_anomaly.candidate_verify_cli --records .runtime/P_U-adapt --inputs .runtime/P_U-inputs
python -X utf8 -m traffic_anomaly.candidate_verify_cli --records .runtime/P_U-adapt --inputs .runtime/P_U-inputs --source-fixture tests/fixtures/g13u-records-v1.json
```

成功exit0，stdout为JSON报告；失败exit2，stderr为`{"error":"安全错误码"}`。命令本身只读，不创建目录、修补文件、重新拟合或写入报告。需要留存stdout时写到两个产物目录外；包内额外sidecar会被拒绝。Python接口见[candidate_artifacts.py](../../src/core/traffic_anomaly/candidate_artifacts.py)，CLI见[candidate_verify_cli.py](../../src/core/traffic_anomaly/candidate_verify_cli.py)。

## 检查关系

| 检查 | 规则与可证明范围 |
|---|---|
| 完成与白名单 | 记录目录恰为manifest.json、minute-fixture.json、label-audit.json；数值目录恰为manifest.json、candidate-inputs.json、preprocess.json；manifest须COMPLETE |
| 字节完整性 | 实际大小/SHA256匹配manifest；数值manifest.fixture须精确等于记录目录实际minute-fixture字节摘要 |
| 兼容 | schema/profile、13项特征顺序、13/26维、H15/H30、变换、时间基准和AUDIT_ONLY政策固定；configuration及epsilon精确比较，配置不使用数值容差 |
| 标签独立 | 三政策的normal/attack/unknown及normal布尔掩码一致，选中政策与分钟fixture一致；原标签、类别和协议计数守恒；coverage、攻击存在标志与已有计数不能自相矛盾 |
| 保存参数重放 | 用已保存mean/scale做transform，复查全部current值、null和有效性；n_samples_seen核对原始分钟H30全历史正常训练资格数 |
| 因果历史 | 以相同保存参数和完整分钟轴重放H15/H30，核对current/residual/joined、理由、common交集、训练/校准/测试资格及四段摘要 |
| 可选源重放 | 提供原始人工fixture时先核其实际字节身份，再重放记录适配、13项与完整标签审计；未提供时source_replay=NOT_PROVIDED，不声称已核源记录 |

有效分钟的计数通道须为整数且四协议通道之和等于记录数；无后向包数不超过总数，duration满足median≤P95≤max≤86400秒。observed空桶、missing或confirmed_empty冲突不能被重新封装为有效分钟。无源时这些只是内部一致性检查，不能重建不可得的原始记录。

数值重放固定rtol=atol=1e-12；数组结构、bool/int、枚举、时间、特征顺序和配置精确校验。预热期间history.current仍保留有效当前13项；只有residual/joined因历史不足整行null。H15/H30各自可能因非有限历史重置，common为交集，不假定两个有效掩码总是包含关系。原始拟合资格与最终有限历史训练资格不必相同。

## 只读边界与资源

文件在解析前检查大小并最多读取上限+1字节；拒绝重复JSON键、非标准NaN/Infinity及无法重放的非有限值。目录、文件与各层未解析父路径均检查符号链接/Windows重解析点，不先resolve隐藏链接；白名单不允许任意manifest路径。工具不递归搜索、不加载pickle或模型、不联网。

| 对象 | 单项读取上限 |
|---|---:|
| 原始人工fixture、minute-fixture | 各1MiB |
| 两个manifest | 各64KiB |
| preprocess | 16KiB |
| label-audit | 16MiB |
| candidate-inputs | 64MiB |

固定七个输入文件的最大响应数据总量为82MiB+144KiB；未提供源时减少1MiB。资源上限是本工具工程决定，不是实际数据筛选协议。检查会比较读取前后文件身份与大小，但不承诺抵抗具有本机写入权限的并发恶意替换。

错误码：INVALID_ARGUMENTS（参数）、INPUT_UNAVAILABLE（不可读取）、INVALID_PACKAGE（格式或内部矛盾）、INCOMPATIBLE_PACKAGE（版本/配置）、INTEGRITY_MISMATCH（摘要或血缘断链）、REPLAY_MISMATCH（重放不符）、RESOURCE_LIMIT（超限）。公共错误不包含私人路径、输入内容或堆栈。

## 报告解释与搬迁

报告status=VERIFIED只表示本版本人工产物内部一致。checks.fit_parameters始终为NOT_REESTIMATED：复查没有调用fit/prepare，也没有证明mean/scale确实只来自训练正常样本。参数拟合来源仍须依赖生产器代码、运行证据与未来真实准入；即使攻击者重写全部一致文件并重算SHA，也不能由本工具认证来源。

哈希是本次字节身份，不是作者签名或官方一致性证明。文件换行也参与SHA，LF与CRLF不同；搬迁已有产物须保留字节，可选源必须是当时原字节。另一平台可重新生成整链并取得自己的摘要，不能混用旧manifest。使用同一实现重放只证明与当前实现一致，不是独立数学正确性证明；上批手算验证仍单独保留。

本批实际复查上一批三个政策，有/无源各一次，6次exit0；18文件SHA快照不变。共同有效24、拟合/校准正常各6、测试当前正常P_U4/P_B5/P_A4保持。测试、发现及未运行阶段见[验证记录](../research/2026-10-30-candidate-artifacts-verification.json)。本机无特权实际symlink测试明确skip，重解析点及祖先检查由可控测试验证，远端Linux实际结果由CI记录。

新下载、真实CSV读取0；真实预处理拟合、训练、评分、阈值校准、正式实验NOT_RUN，主数据采用与134/268生产迁移仍待批准，S2/Data Gate BLOCKED。
