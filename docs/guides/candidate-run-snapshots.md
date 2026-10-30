# 候选运行结果的只读快照

日期：2026-10-31。范围：SYNTHETIC_ONLY 候选 IF/AE 已保存结果的程序读取。依据[实施计划](../superpowers/plans/2026-10-31-candidate-run-snapshot.md)。该接口为分钟回放准备，不表示生产网页或真实数据联调已完成。

```python
from traffic_anomaly.candidate_run_artifacts import load_verified_candidate_if_run
from traffic_anomaly.candidate_ae_run_artifacts import load_verified_candidate_ae_run

snapshot = load_verified_candidate_if_run(
    ".runtime/if-run", ".runtime/P_U-adapt", ".runtime/P_U-inputs",
    source_fixture="tests/fixtures/g13u-records-v1.json",
)
print(snapshot.report["run_id"])
print(snapshot.scores_document["timestamps"])
print(snapshot.scores_document["scores"])
```

AE 接口接收相同参数，读取当前 13 维或历史 26 维的既有人工结果包。路径为调用者指定的本地目录，示例名称不保证已生成；本接口不创建运行、训练模型或保存产物。

VerifiedCandidateRun 只保留递归只读的 report 与 scores_document。后者是本次验证使用的实际保存文档，包含完整分钟轴、分区、采集段、当前/共同/评分有效性、原 null 分数及报警、H15/H30 历史无效原因、阈值和校准说明。AE 的当前重构误差与历史偏离重构误差保持原字段；IF 不补造这两个通道。输入特征及独立标签仍使用[输入快照](candidate-snapshots.md)，不能混入模型分数。

快照在既有验证成功点构造，不先返回报告再重开 scores.json，不用期望值替换实际保存值。两个旧 verify 函数、命令行和[运行比较](candidate-comparison.md)仍返回原报告与错误码。缺少人工源时 source_replay 仍为 NOT_PROVIDED；传入源才执行原来的源重放检查。原 IF/AE 运行文档的一致性检查未增加数值容差。

对象使用 frozen 与 slots，字典和列表转为只读映射与元组。report_dict()/scores_dict()返回独立可修改深副本；修改副本不影响原快照。此约束防止普通调用者误改共享结果，不防御 Python 反射，也不让对象类型成为来源认证或研究批准凭证。

原始目录之后变化不会改变已返回快照，下一次加载仍重新验证当前文件。快照保留解析后的分数文档和报告，延长它们的内存生命周期；转换深副本会另占内存。不保留原包字节、权重、可执行模型或上游大数组，不承诺精确 RSS 上限或目录级原子快照。

各文件读取上限、链接/重解析检查、安全错误以及 Q99、严格报警、三政策评价关系验算沿用 [IF](candidate-run-verification.md)与 [AE](candidate-ae-run-verification.md)说明。验算保存关系不等于重新训练或评分；IF 权重不反序列化，AE 网络不重建。模型输出与训练来源仍未认证。

新增30项测试，相关344项通过、1项跳过。主控实际有/无源8次加载与8次旧报告对照通过，39个历史文件身份保持，每包144分钟/24有效/120null，原无报警负例保留。单次API读取11/12文件各一次；另有旧报告对照及78次前后身份读取，不能把整次验收称为全局单次读取。自动测试准备训练人工toy模型；实际只读验收不导入模型库、不拟合、不训练评分。[验证记录](../research/2026-10-31-candidate-run-snapshot-verification.json)。真实主数据、最终 Attempted 政策、生产 134/268 维迁移及真实模型未因此获准；Data Gate 保持 BLOCKED。
