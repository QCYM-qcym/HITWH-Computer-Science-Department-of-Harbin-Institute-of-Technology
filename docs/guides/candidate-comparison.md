# 候选已存 IF/AE 结果核对

日期2026-10-30；独立候选工程入口，当前实现与验证记录见[实施记录](../superpowers/plans/2026-10-30-candidate-comparison.md)。只接收 `SYNTHETIC_ONLY/AUDIT_ONLY` 已保存结果。研究依据为 V0.40 的共同有效分钟、独立校准及容量对照约束；不改变生产134/268维接口和真实数据协议。

```powershell
python -m traffic_anomaly.candidate_compare_cli --records <adapter-directory> --inputs <input-directory> --source-fixture <synthetic-json> --if-run <if-directory> --ae-run <current-ae-directory> --ae-run <history15-directory> --ae-run <history30-directory>
```

固定支持IF当前13维、当前AE13维、历史AE26维H15和H30四个槽位。一次2—4项，IF至多一个、AE至多三个；ID、槽位和规范化目录均不能重复。可省略部分槽位，报告明确列出缺项，不补跑。source可省略，但所有行保留 `NOT_PROVIDED`。成功stdout单JSON/exit0，失败stderr安全JSON/exit2。没有输出目录、训练、评分、修复或挑选优胜者选项。

比较层额外读取每个固定manifest，调用对应[IF](candidate-run-verification.md)或[AE](candidate-ae-run-verification.md)验算器后，要求额外读取的SHA和大小与验算报告中的实际摘要完全一致，再使用其上下文。上游五摘要、预处理状态、13特征顺序、政策、共同H15/H30资格规则和训练/校准/测试人口必须相同；相同路径或相同计数不能替代字节身份。各验算器已核完整时间轴、有效掩码和拟合/校准索引，比较层据此建立共同资格证据链，不再读取并重建一遍大轴。

通过只称 `DATA_QUALIFICATION_ALIGNED`，按固定槽位顺序显示各自阈值、校准信息和三政策原指标，NULL及原因原样保留。只要求共同评价人口相同，允许报警、混淆矩阵、precision分母和校准并列数不同。IF分数与AE误差尺度不同，不比较阈值高低、不归一化、不输出排名、显著性或自动选择窗口。

当前AE288参数、历史AE509参数，尚未容量匹配；IF不解析不透明权重，参数量为NULL并附原因。容量比较和历史因果归因均 `NOT_COMPARABLE`。不同版本/CPU线程仅列保存声明，声明相同也不认证执行环境相同。模型得分重放、训练及来源未认证的边界随每行保存；多个存储验算通过不能升级为模型有效性证据。

每包继承32MiB总量上限，IF权重8MiB、AE权重1MiB、其余单JSON16MiB。比较层每包额外manifest≤16MiB；最多4包顺序处理，最多128MiB运行包加64MiB额外manifest读取，另有至多四次既有上游验算。不是全局单次读取，也不是内存占用承诺。路径先检查词法祖先、链接和Windows重解析；JSON重复键/非有限数/无效结构拒绝，任何失败中止整份比较，错误不暴露路径或堆栈。

本入口不导入模型库、不反序列化IF权重、不重建AE、不执行fit/score。验算器只复算已存分数的Q99/报警/评价关系。真实主数据、最终Attempted政策、真实模型和正式对比均未获此入口放行，Data Gate保持BLOCKED。


实际验证：新增核心37/CLI30项共67项通过，独立审查通过。[已存四包复查](../research/2026-10-30-candidate-comparison-verification.json)中，有/无源两次调用均保持20结果、18上游和源SHA/mtime不变；共48/52次内容读取，manifest每包2次。各行144分钟轴、共同有效24、训练/校准各6，P_U正常/攻击/未知为4/1/1，P_B为5/1/0，P_A为4/2/0。所有原运行均无报警、FNR=1、precision=NULL；只保留工程负例，不据此比较模型效果或选择政策。测试准备阶段生成合成包，与实际只读复查分开。
