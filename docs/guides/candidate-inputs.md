# 候选分钟输入与因果历史计算

日期：2026-10-29。用途：本地开发与复现；身份：**SYNTHETIC_ONLY**。本轮由主控依据用户自行规划开发的要求选定并实施，对应[报告V0.40](../reports/开题报告-V0.40-公开文本.md)§4.1.1、§4.1.2及§4.1.7，执行任务见[开发计划](../superpowers/plans/2026-10-29-candidate-inputs.md)。当前状态与验证结果在下方登记。

## 已实现的计算入口

[candidate_inputs.py](../../src/core/traffic_anomaly/candidate_inputs.py)接收已聚合的人工13维分钟向量。特征顺序与[G13U定义](../research/2026-10-24-c17-g13u-audit.md)一致，标签掩码独立传入；它不读取真实CSV，不重新认证源流级守恒或物理协议。已有真实审计工具及结果保留。

`CandidateMinuteBatch`检查维度、完整字段顺序及时间轴，区分`raw`和`prepared`数值空间，最多10000分钟。有效raw值须非负有限，prepared值可以有符号；无效输入保持原位置并使用NaN内部表示，导出为null。时间使用明确的源钟面坐标，按分钟递增；代码不调用机器本地时区，不把候选时间认证为UTC。

`CandidatePreprocessor.fit`先在原始时间轴筛选训练分区中当前及过去30分钟全正常的资格，再拟合log1p后的均值与总体标准差（ddof=0）。零标准差置1；其余分区不参与拟合。`transform`变换完整轴，保留无效行；保存状态绑定候选profile、13字段顺序和变换版本，重载检查兼容性。测试正常掩码不影响参数或历史数值。

`build_candidate_history`只接受prepared输入。每个字段取当前之前连续H分钟的中位数和MAD，偏离为`(current-median)/(MAD+epsilon)`，当前行不参与自己的参考。H15/H30分别产生13维偏离及26维拼接，共同掩码取二者交集。epsilon默认1e-6，是本轮人工开发配置，未声称真实验证或最优。

分区变化即使segment_id相同也重置；时间缺口、segment变化与无效输入同样重新预热，不拼接筛选后的正常行。训练和校准资格要求当前与完整H30历史全正常；测试正常资格只要求共同输入有效且当前normal。测试过去的攻击或未知身份不用于清除历史。所有没有可用历史或数值溢出的行都保留原因，不生成0分。

## 独立命令行

[candidate_cli.py](../../src/core/traffic_anomaly/candidate_cli.py)只接受明确标记SYNTHETIC_ONLY、synthetic_source_clock的JSON，大小不超过1MiB；时间须为无偏移整分钟ISO钟面。错误维度、标签混入、重复JSON键及非标准非有限值会被拒绝。输入样例为[144分钟手工fixture](../../tests/fixtures/g13u-inputs-v1.json)，四段各36分钟、全轴连续，测试段前5分钟normal_candidates=False；False只表示人工非正常/未确认为正常掩码，不映射任何C17最终标签政策。

在已安装核心包的现有环境执行，输出父目录需存在，目标目录须不存在：

```powershell
.venv\Scripts\python -X utf8 -m traffic_anomaly.candidate_cli --fixture tests/fixtures/g13u-inputs-v1.json --output .runtime/candidate-inputs-demo-v1
```

输出白名单固定为`candidate-inputs.json`、`preprocess.json`和最后写入的`manifest.json`。第一份包含完整时间轴、13维变换值、两窗口偏离/拼接、有效性和正常资格；预热数值为null。manifest记录合成身份、配置和fixture摘要，以及文件SHA/大小；保存并重载变换一致后才标COMPLETE。目录已存在返回OUTPUT_EXISTS，验证失败不创建输出目录，其他失败返回安全错误码，不回显私人路径或内部堆栈。

这里的COMPLETE仅指人工输入产物计算完成；没有scores、模型或研究指标，不接后端worker和原网页任务。原134/268生产契约继续独立使用。

## 实际验证

数值模块22项先因实现缺失失败，再通过；CLI缺失入口37项失败、1项样例检查通过，实现后38项通过。后续加入产物写失败与数值反例，最终新增数值24项、CLI42项共66项通过。完整Python工作流`pytest tests/core tests/backend tests/integration tests/data_audit -q`实际305项及56个subtests通过；仅1项既有TestClient弃用警告。对应测试：[数值测试](../../tests/core/test_candidate_inputs.py)、[CLI测试](../../tests/core/test_candidate_cli.py)。

独立复核发现并修复两项数值问题：逐列完全相同的log值因浮点归约产生极小非零std，现精确识别常数列并使用首值mean/scale=1；MAD+epsilon溢出曾输出有效零偏离，现检查所有中间量并按nonfinite_history无效/重置。两项新增反例先2失败再通过。CLI写失败也先复现伪完成文件，再清理本次独占创建的失败文件；不删除其他已有文件。独立Spec/Quality复审均PASS，无遗留问题。

主控实际执行CLI：首轮v1合成产物保留上述常数缩放失败证据，修复后独立v2运行exit0。用标准库log1p、mean/pstdev及median按固定训练索引独立复算，1404项有效历史逐字段检查通过；四段资格、重载、文件SHA与严格JSON一致。脱敏汇总见[验证记录](../research/2026-10-29-candidate-inputs-verification.json)，本地大数组不公开提交。

仓库13项维护测试、进度生成/check和worktree隐私/作者397文件0问题通过；本轮252个Markdown链接与新Vault日志5个Wiki Links有效。候选导入不初始化torch；前端无改动，本地不重复其套件，远端CI按本次提交检查。

人工样例的预期资格：各段H15有效21、H30/共同有效6，四段共同24；训练拟合6、校准全历史正常6、测试当前正常6。前5分钟人工非正常仍保留于测试历史；改变测试当前末尾掩码只减少测试正常分母，不改变历史数值。这些数值仅为人工计算验收，不替代真实150/88/148和1831供应证据。

真实CSV数值构造、真实变换拟合、IF/AE训练与评分、Q99、真实API/网页接入及正式比较均NOT_RUN。主数据采用、最终Attempted政策和生产迁移未在本轮改动，Data Gate/S2仍BLOCKED。源协议0和时间/生成限制沿用真实审计结论。

## 后续开发顺序

1. 复用实际审计分母形成有限试点与标签端点决定包，给出推荐及排除代价，不依据模型效果选政策；本轮开发无需重新审批常规工程细节。
2. 取得明确研究决定后，建立有版本的数据profile和真实适配器，再把本模块计算接入共享核心；保留原UGR profile及兼容拒绝。
3. 相应Gate与运行授权具备后，先做受限IF最小链路，核真实输入、CLI/API/网页及导出一致，再安排两种AE和正式对照。未知参数继续配置化，不填造效果。


2026-10-30兼容补充：[源记录适配入口](candidate-records.md)可输出无效整13null；本CLI现在接受valid=false的整行null，仍拒绝有效行null或部分null。原有限占位输入继续可用，生产契约不变。
