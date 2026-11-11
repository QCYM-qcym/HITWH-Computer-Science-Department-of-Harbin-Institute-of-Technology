# 保存 IF 预测的测试分钟标签审计

日期：2026-11-11。状态：源码与七阶段新安装运行通过，独立规格和质量后验复核后已由主控实际接受；当前批次发布仍待核。字段和错误边界见[设计](../design/release-if-evaluation-v1.md)，分工见[实施计划](../superpowers/plans/2026-11-11-release-if-evaluation.md)。

本入口读取一个保存结果包及其原始、准备输入包，核对声明绑定后，按 P_U、P_B、P_A 输出测试分钟的混淆计数、误报率和漏报率。三个报告使用同一份保存预测，只有现有标签口径不同；原拟合政策单独保留。它们不代表三次训练、重新校准或最终政策选择。

本命令只读保存包，不访问源 CSV，不生成数据、拟合预处理、重放历史、训练或评分，也不选择新阈值。保存分数的 Q99 一致性复核仍会执行。研究阶段保持 S2 / Data Gate `BLOCKED`；真实 C17 训练、评分、阈值校准及正式比较仍为 `NOT_RUN`。

## 显式提供三个保存包

使用已安装本入口及其锁定依赖的 Python 3.14 core 环境。此命令不需要估计器或 backend。结果由已有[结果命令](release-if-result-cli.md)生成；人工源链另见[复现指南](release-example.md)。本步骤仅消费那些已保存产物。

将占位符替换为自己的三个绝对本地路径。每个目录须是对应完整包，不能只提供其中一个 JSON 文件。相对路径、`..`、UNC、链接/reparse、Windows 保留名或 ADS 等不受支持的路径会被拒绝。

```powershell
$python = '<ABSOLUTE_LOCKED_PYTHON>'
$resultPackage = '<ABSOLUTE_SAVED_RESULT_DIRECTORY>'
$rawPackage = '<ABSOLUTE_ORIGINAL_RAW_PACKAGE_DIRECTORY>'
$preparedPackage = '<ABSOLUTE_ORIGINAL_PREPARED_PACKAGE_DIRECTORY>'
& $python -m traffic_anomaly.release_if_evaluation_cli evaluate --result-package $resultPackage --raw-package $rawPackage --prepared-package $preparedPackage
```

可分别对 current13 和 h30_26 的结果目录运行同一条命令。每次仅评价显式提供的一个视图，不能据两次输出自动推断哪个模型更好。

单独查看帮助：

```powershell
& $python -m traffic_anomaly.release_if_evaluation_cli --help
```

只有退出 0、stderr 为空且得到完整成功 JSON，才记录该次命令成功。先读取结果，再读取 raw、prepared，配对后核结果与输入绑定；任何一步失败就停止，不输出部分政策报告。

## 分母怎样计算

完整测试人口包含保存分段中所有 `role=test` 的分钟。可评价人口还必须满足保存结果的 `scored_mask`，并与输入的 `common_valid` 一致。训练、验证、校准的已评分分钟及报警都不进入测试指标。

| 人口 | 含义 |
| --- | --- |
| calendar_test_minutes | 完整注册测试分钟数 |
| scored_test_minutes | 测试且共同有效、已有保存预测的分钟数 |
| excluded_unscored_test_minutes | 测试中未评分的分钟数，含历史预热等情况 |
| calendar/scored/unscored_by_kind | 上述三类各自按 normal、attack、unknown 细分 |

unknown 即使报警，也不进入 TP、FP、TN 或 FN；未评分的空预测同样排除。unknown、未评分和未报警分别保留，不能合并成正常负例。每种标签的 scored 加 unscored 等于 calendar；FP+TN 等于已评分正常分母，TP+FN 等于已评分攻击分母。

P_U 将合法 Attempted 作为 unknown，P_B 作为 normal，P_A 作为 attack。这里报告的是现有三种标签审计映射，`audit_fit_policy` 始终保留当初保存的拟合政策，`policy_status` 为 `AUDIT_ONLY`。对象按规范键序列化时显示 P_A、P_B、P_U；标签列的逻辑对应关系仍为 P_U、P_B、P_A。

## 指标与空值

| 指标 | 算式 | 分母为零时的原因 |
| --- | --- | --- |
| precision | TP/(TP+FP) | NO_POSITIVE_LABELED_TEST_PREDICTIONS |
| recall | TP/(TP+FN) | NO_SCORED_TEST_ATTACK |
| FPR | FP/(FP+TN) | NO_SCORED_TEST_NORMAL |
| FNR | FN/(FN+TP) | NO_SCORED_TEST_ATTACK |
| F1 | 2TP/(2TP+FP+FN) | NO_ATTACK_OR_POSITIVE_LABELED_TEST_PREDICTIONS |

零分母返回 `null`，`undefined_reasons` 恰包含这些空指标的原因；有定义的零保持 `0.0`。例如已有正常测试分母、且没有误报时 FPR 为 0.0；正常分母为零时 FPR 为 null。攻击分母存在且没有漏报时 FNR 才能为 0.0。

指标逐项判断。没有正预测但存在攻击时，precision 可为空而 recall、FNR、F1 仍有定义。合法输入没有测试段时，仍返回完整报告，三政策测试计数全零、五指标全为 null；已有训练和独立校准资格仍须合法。

## 成功输出

stdout 是一份规范 UTF-8 JSON，末尾一个 LF，含换行不超过 16,384 字节；无 BOM、逐分钟数组或本机路径。产品不另建报告文件。

顶层恰有以下 16 个字段：

| 字段 | 内容 |
| --- | --- |
| version、profile_id | 版本 1 与固定标签审计 profile |
| status | SAVED_PREDICTION_LABEL_AUDIT |
| scope、unit | 保存结果标签敏感性内部一致性范围，单位 minute |
| result_identity | 本次结果包的完整四字段身份 |
| input_references | raw、prepared 的完整四字段身份 |
| configuration_sha256 | 已绑定准备配置摘要，不是模型权重认证 |
| view | 保存的 current13 或 h30_26 |
| audit_fit_policy、policy_status | 原拟合政策与 AUDIT_ONLY |
| source_authentication、time_basis | NOT_AUTHENTICATED 与 SOURCE_WALL_CLOCK_COMPLETION_PROXY |
| model_execution | NOT_AUTHENTICATED，指保存结果的历史执行认证范围 |
| prediction_basis | FIXED_SAVED_PREDICTIONS_NO_REFIT |
| policies | P_U、P_B、P_A 三键对象 |

每个政策对象恰有 9 个字段：三个分钟人口、三个标签细分对象，以及 `confusion_counts`、`metrics`、`undefined_reasons`。混淆计数保留 tp/fp/tn/fn；指标保留 precision/recall/f1/fpr/fnr。无定义时只给空值和固定原因，不能用省略字段或零代替。

## 错误与保存原件

失败或中断退出 2，stderr 尽力输出 `{"error":"CODE"}` 加一个 LF，不回显路径、原异常或堆栈。常见情况包括：

| 错误 | 含义 |
| --- | --- |
| INVALID_ARGUMENTS / INVALID_PACKAGE_PATH | 参数或原路径拼写不符合约定 |
| INPUT_UNAVAILABLE / PACKAGE_CHANGED | 保存包不可读或读取期间观察到身份、成员变化 |
| INTEGRITY_MISMATCH | 包成员字节与保存摘要不符 |
| UPSTREAM_IDENTITY_MISMATCH / PAIR_ALIGNMENT_MISMATCH | raw 与 prepared 无法作为一对输入 |
| INPUT_BINDING_MISMATCH | 结果与另一对合法输入的声明身份或人口不匹配 |
| INVALID_EVALUATION_INPUT | pure 校验未接受所提供保存声明 |
| OUTPUT_ERROR | stdout 获取、写入、短写或 flush 失败 |

错误回执与部分 stdout 可能同时存在；即使已经发送完整 JSON，也要以实际退出和 stderr 判定该次调用。失败不会修改或删除保存包，也不自动重试。嵌入程序调用 `main` 时，宿主流仍由调用方管理；普通模块入口另有退出期描述符保护，不能把单测的 main 返回值冒称物理进程退出证明。

报告只能核保存字节、配对关系与标签算术。来源、标签真值、源钟面的绝对时区、预处理数值派生和历史模型执行保持各自认证边界；内部通过不能解除 Data Gate，也不能据人工示例宣称真实网络检测效果或跨网络泛化。

## 本阶段验证范围

六项真实保存包磁盘集成通过，2.05 秒，无警告。范围包括两个视图的完整手算报告、合法无测试段报告、另一合法输入对的绑定失败、损坏成员完整性错误，以及 stdout flush 失败后原包可独立加载。各例原件的成员、字节与 mtime 前后保持；成功报告逐字节匹配规范 JSON 和手算计数。

测试 setup 实际执行了 7 次人工预处理统计拟合，用于封印合法输入，单独记录在测试收据；操作期禁止 producer、save、prepare、replay、文件写入与源 CSV 读取，估计器入口及模型库导入全程禁止。手写分数只构造内部一致性测试值，不计作模型结果。混淆数校验使用测试图样的手算值，不由产品函数生成自己的期望。

以上为源码验收时点的 pytest 进程内真实文件 I/O 与 `main` 调用。该时点安装后普通模块退出与已接受结果只读评价仍为 `NOT_RUN`；后续新安装实际运行单独记录于下节。物理断管、API 和浏览器本E仍为 `NOT_RUN`。测试中的流故障不能替代物理进程退出证明，文档命令也不计为已运行。


## 新安装实际运行快照

一个新core wheel含80成员，安装到新target共83文件，依赖复用既有锁定环境。一次7个直接子进程按预期退出0/0/0/0/0/2/2并自然回收，父进程实际退出0。控制器记录7.4620446秒到最终收据组装，不含外层退出总时长，也不作为模型延迟或研究成本比较。完整记录见[本阶段验证](../research/2026-11-11-release-if-evaluation-verification.json)。

普通help是未插桩模块。其余四个业务阶段使用透明观察器运行实际公开module，物理退出另记；两项评价的完整stdout分别为2616、2613字节，均与两份独立stdlib报告预期逐字节一致。325个保护项和29个原输入成员的完整名称、字节、摘要及已落盘初始mtime保持。新安装仅复用前批人工结果，不重新生成源、prepare或运行模型。

这四个受控业务进程中，模型fit、score和模型Q99均为0，另记录6次保存分数Q99复核；其人口10和返回阈值指向原保存校准声明，本E没有再次独立重算Q99数学。标签报告按test48、共同有效test18和未评分30分列，不能把全角色共同56当测试分母。P_U/P_B/P_A的实际TP/FP/TN/FN分别为0/1/14/1、0/2/14/1、1/1/14/1；这是既有人工预测的标签算术，不是检测效果结论。

安装后另一个合法输入对与C结果的绑定反例实际退出2/INPUT_BINDING_MISMATCH；原B当时未执行该反例的历史不改。物理断管、API、HTTP及浏览器本E未安排；两项源码环境退出证据与本轮新安装分别记账。完整回归仍可能执行旧人工模型fixture，不能以这四个业务进程的0次模型概括整个开发批。

前批固定人工源链的准确19文件Desktop提交及三项CI见[前阶段发布回执](../research/2026-11-11-release-example-publication.json)。本E新提交及准确CI保持PENDING，不以C成功代替；当前实际运行快照已经独立规格和质量后验复核，主控已实际接受。
