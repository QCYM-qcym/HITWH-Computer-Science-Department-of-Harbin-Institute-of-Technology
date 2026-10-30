# 候选AE结果的只读验算

用途：检查已保存的[候选AE人工运行](candidate-ae-synthetic.md)是否在文件、身份和数值关系上保持一致。日期2026-10-30；SYNTHETIC_ONLY / STORED_ARTIFACT_CONSISTENCY_ONLY。依据[本批计划](../superpowers/plans/2026-10-30-candidate-ae-run-verifier.md)，与[IF只读验算](candidate-run-verification.md)分别维护。

## 入口和范围

```text
python -X utf8 -m traffic_anomaly.candidate_ae_verify_cli --run .runtime/toy-current-ae-v1 --records .runtime/toy-records --inputs .runtime/toy-inputs --source-fixture tests/fixtures/g13u-records-v1.json
```

核心入口为`verify_candidate_ae_run(run_directory, record_directory, input_directory, *, source_fixture=None)`。命令只读，不修复产物或创建输出目录；成功stdout返回JSON、exit0，失败stderr只返回安全错误码、exit2。没有模型、设备、调参或任意文件导出参数。

原人工source可省略，此时`source_replay=NOT_PROVIDED`；提供源且通过记录适配复查时为VERIFIED。缺源不能依靠摘要声明获得已核源身份。

## 检查内容

| 对象 | 检查规则 |
|---|---|
| 五文件 | 恰为weights.json、model-state.json、scores.json、evaluation.json、manifest.json；摘要与实际字节相符 |
| 共同身份 | 用已核快照的字段/资格/预处理/上游摘要和固定AE配置重建binding；权重声明不能自证 |
| 权重结构 | 固定八tensor、13或26维对应shape、float32精确可表示的有限值，无额外层或buffer |
| 时间与资格 | 完整轴、分区、segment、共同有效分钟、H15/H30原因与上游一致 |
| 误差与分数 | 有效处有限非负；当前score等于当前误差，历史score精确等于0.5×当前误差+0.5×历史误差 |
| 不适用状态 | 无效分钟的分数/报警/误差必须null；当前模式历史通道全null且NOT_APPLICABLE |
| 阈值与报警 | 从独立校准正常共同分钟的保存分数重算linear Q99，严格大于才报警 |
| 评价 | 同一保存预测重算三政策分母、指标及未定义原因；未知不并入正常 |
| 训练声明 | fit/cal索引与上游一致；五个有限非负loss跨文件一致，不复现训练 |

配置、掩码、索引及元数据类型精确检查，bool不能冒充数字。分数/误差接受有限JSON整数或小数，不以容差放过归约、阈值和报警变化。拒绝重复键、NaN/Infinity、超大指数和无效编码，错误不暴露私人路径或堆栈。

版本只核python/numpy/torch三个有界声明，CPU线程只核正整数和跨文件一致；不查询当前Torch、GPU或线程。不同于本机的合法版本声明可以通过，报告仍为DECLARATION_CONSISTENT_ONLY，不代表加载兼容。

## 资源与证明边界

权重单文件1MiB、其他单JSON16MiB、五文件总32MiB；先核所有物理大小，再按剩余预算读取。词法祖先链接及Windows重解析点在规范化前拒绝；读前后身份/大小/mtime一致，每份内容只读一次。上游快照沿用原有大小限制，报告不含本机路径。

导入和验算不导入torch/sklearn/joblib，不训练、重建网络、评分或加载可执行模型。权重仅作JSON结构检查，最多分配固定509个数值，不执行其中的类名或层图。

成功仅认证保存关系，报告明确：network_reconstruction和model_deserialization为NOT_PERFORMED；model_score_replay、training_execution和training_loss_replay为NOT_CHECKED；model_origin为NOT_AUTHENTICATED。

合法改权重后重封全部摘要，或将分数、通道、阈值、报警及指标一起改成内部自洽的另一组数值，都可能通过。本批正例测试明确保留这种边界，避免把存储一致性写成模型真实性。证明网络产生这些得分需要另外执行模型重放，本入口未执行。

## 实际验证

[实际记录](../research/2026-10-30-candidate-ae-run-verification.json)中，本批新增95项测试通过，独立Spec/Quality PASS；实际六次复查覆盖当前/H15/H30以及有/无原人工源。15份运行文件、18份上游文件及源的SHA/mtime未变，各次11/12份内容均只读一次；模型库导入、训练、网络重建、pickle及预处理拟合被主动禁止仍成功。

测试准备使用既有生成器创建人工包；被测验算和实际既有包复查禁止模型执行，两者分开记录。不接原API/网页、不改生产134/268。真实CSV/下载/训练评分/Q99及正式实验未因此获准，Data Gate/S2保持BLOCKED。
