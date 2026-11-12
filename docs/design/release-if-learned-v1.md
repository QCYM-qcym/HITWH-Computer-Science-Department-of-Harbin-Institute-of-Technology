# Isolation Forest 学习状态包

学习状态接口已实现，通过独立源码审查及完整回归。安装态首次观测为 `FAILED_OBSERVER_CONTRACT`；部分数值已观察，完整安装态未接受。真实研究实验仍为 `NOT_RUN`，Data Gate 为 `BLOCKED`。

## 操作范围

一次显式新拟合保留同一估计器，完成唯一一次原始评分，导出只含数值的森林状态，再逐项比较全部公共分钟分数。成功后返回既有结果包和新的学习状态包。两类包分别保存；跨目录保存不构成事务。

独立进程显式提供输入对、结果包和学习状态包，复算全部公共分数、Q99及严格预测。复算只证明这些声明与数值一致。不认证来源、历史模型起源或预处理派生。

仅新增三模块，既有输入/结果/P1接口保持；CLI/UI均 `NOT_IMPLEMENTED`。

| 模块 | 职责 |
|---|---|
| `release_if_learned_contract.py` | 不可变声明、编码解码、与 P1 状态组合、总体索引摘要 |
| `release_if_learned.py` | 同一估计器的一次新拟合与导出；显式独立数值复算 |
| `release_if_learned_package.py` | 固定三成员目录保存和读取 |

## 公共值与接口

新增数据类均为 `frozen=True, slots=True`，无默认字段；字段按声明顺序列出。

| 数据类 | 字段 |
|---|---|
| `ReleaseIFLearnedReference` | profile_id, context_sha256, manifest_sha256, manifest_byte_count |
| `ReleaseIFLearnedConfiguration` | input_width, n_estimators, max_samples, max_features, bootstrap, contamination, random_state, n_jobs |
| `ReleaseIFLearnedContext` | profile_id, view, raw_identity, prepared_identity, result_identity, configuration_sha256, minute_count, train_count, calibration_count, preprocessing_fit_count, population_sha256, input_rules_id, feature_columns, model_configuration, fit_runtime_id |
| `ReleaseIFLearnedLoadReport` | profile_id, scope, byte_integrity, structure, numerical_replay, source_authentication, model_origin |
| `ReleaseIFLearnedPackage` | identity, context, state, load_report |
| `ReleaseIFLearnedRun` | result_package, learned_package |
| `ReleaseIFLearnedReplayReport` | profile_id, scope, learned_identity, result_identity, scored_count, calibration_count, score_replay, calibration_replay, prediction_replay, source_authentication, derivation_replay |

```python
fit_release_iforest_learned(pair, *, view) -> ReleaseIFLearnedRun
replay_release_iforest_learned(package, pair, result_package) -> ReleaseIFLearnedReplayReport
encode_release_if_learned_package(package) -> tuple[tuple[str, bytes], ...]
decode_release_if_learned_package(members: dict[str, bytes]) -> ReleaseIFLearnedPackage
save_release_if_learned_package(package, output_directory) -> ReleaseIFLearnedReference
load_release_if_learned_package(directory) -> ReleaseIFLearnedPackage
```

`pair` 为既有 `ReleaseModelInputPair`，结果包沿用 `ReleaseIFResultPackage`。参数及嵌套声明要求精确类型；`bool` 不代替整数，冻结对象仍重验。路径只接受精确 `str` 或原生 `Path`，须为合法绝对路径。

## 数值与绑定

只支持 `current13` 和 `h30_26`。森林固定16棵，`max_samples=min(32,训练数)`，`max_features=1.0`、`bootstrap=False`、`contamination='auto'`、`random_state=42`、`n_jobs=1`。训练超过32行时仍将全部训练行传入拟合。训练和评分只接收数值，不传标签。

拟合环境为 Python3.14、NumPy2.5.4、scikit-learn1.9.1 和 joblib1.6.0；使用 threading 后端、单任务和 working_memory1024。原始返回必须为有限原生 float64 数组。取反得到异常分数后，P1 对全部公共行评分一次，逐项比较 `float.hex()`；任何差异均停止，不进行容差比较、重拟合或重试。

结果包保存原始评分及独立校准行的 Q99-linear。公共分钟采用 `score > threshold`；其他位置的分数和预测均为 `None`。学习状态绑定原始、预处理与结果的完整引用，以及配置摘要、特征顺序、计数和总体索引摘要。总体摘要覆盖完整掩码及训练、校准和预处理拟合索引；复算仍显式检查这些索引，摘要不能替代逐项绑定。

复算先验证学习状态包，再验证结果包及其引用，随后分配输入矩阵并绑定。声明一致后才进行一次完整 P1 评分，依次比较分数、独立 Q99 和预测。报告范围固定为 `EXPLICIT_INPUT_NUMERICAL_REPLAY_ONLY`，来源为 `NOT_AUTHENTICATED`，派生复算为 `NOT_PERFORMED`。

## 导入与磁盘边界

三个新模块的导入、学习状态编解码及学习状态磁盘保存/读取仅依赖标准库与 P1 的标准库编解码。它们可在禁止 NumPy、模型库和 pickle 导入的独立进程中使用。

数值复算显式需要 NumPy2.5.4。冷启动时 NumPy 自身会导入标准库 pickle；此依赖初始化与产品操作分别记录。初始化期间持续禁止 sklearn、joblib、torch 和 cloudpickle；之后禁止 pickle 导入及 load/loads/dump/dumps，才检查产品复算。该描述不宣称冷复算从未导入 pickle，也不构成系统调用级隔离。

| 固定成员 | 含末尾 LF 的上限 |
|---|---:|
| `numeric-state.json` | 262144字节 |
| `manifest.json` | 8192字节 |
| `COMPLETE.json` | 4096字节 |
| 合计 | 274432字节 |

数值状态原样使用 P1 编码。上下文4096字节；总体摘要文档262144字节。摘要链绑定成员，读取前检查全部预算。固定三成员，拒绝链接、重解析点及可观测变化。

先验证，再独占创建目录；依次数值状态、manifest、COMPLETE，各一次有界读回。失败保留残留，输出不可复用；晚期失败可能留下可加载的完整包，不提供回滚或持久化保证。

## 有限错误

`ReleaseIFLearnedError` 只公开代码，不复制外部异常内容。未知代码归一为 `LEARNED_ERROR`；`MemoryError` 优先映射为 `RESOURCE_LIMIT`。其余顺序按实际校验阶段确定。

```text
INVALID_LEARNED_ARGUMENTS INVALID_LEARNED_PACKAGE INCOMPATIBLE_LEARNED_PACKAGE
RESOURCE_LIMIT INTEGRITY_MISMATCH INPUT_BINDING_MISMATCH
NO_TRAINING_NORMAL NO_CALIBRATION_NORMAL INVALID_INPUT_NUMERIC
MODEL_UNAVAILABLE MODEL_ERROR INVALID_MODEL_STATE INVALID_MODEL_SCORES
SCORE_MISMATCH CALIBRATION_MISMATCH PREDICTION_MISMATCH INCOMPATIBLE_RUNTIME
INVALID_PACKAGE_PATH INPUT_UNAVAILABLE OUTPUT_EXISTS PACKAGE_CHANGED OUTPUT_ERROR
LEARNED_ERROR
```

新增学习状态对象缺失字段为 `INVALID_LEARNED_PACKAGE`。既有输入对象仍委托既有验证器：精确输入对缺失字段在新拟合中映射为 `INPUT_BINDING_MISMATCH`，在复算输入阶段映射为 `INVALID_LEARNED_PACKAGE`；更早的学习状态、结果或引用检查可先行拒绝。

## 验证状态

源码规格与质量两项独立审查均为 C0/I0/M0，已有根审查接受。定向347/250/254通过及10跳过，范围重叠不相加。

源码人工输入集成测试已完成两次新拟合。手工声明输入为176分钟、公共55、训练17、校准4、预处理拟合18；原始/P1拟合侧各110值，独立进程复算110值，均按完整十六进制比较。测试父进程与复算子进程的原生输出分别保存。此输入与安装态原始人工 A 的公共56/训练18/校准10不同。

全量回归5375通过/26跳过/1项既有警告/56子测试，314.42秒，父进程原始流已捕获，源码保持。安装态两次新拟合的112项原始/P1分数与112项独立复算匹配，校准行20+20；冷加载和六个绑定/声明负例已观察。五阶段均退出0并自然回收，但外层退出1：原生总数20与内层合计18加一的假设不符；构建还写入任务外持久pip缓存。状态为 `FAILED_OBSERVER_CONTRACT`，数值仅 `OBSERVED_NOT_FULL_ACCEPTED`，无重跑。任务外缓存足迹未知，不能宣称完整时间/资源或写入范围通过。历史 G 的父控制器原生输出字节缺口仍为 `UNVERIFIED`，本次材料不追溯修补该结论。

后验规格和质量复审均确认完整安装观测为FAIL（C0/I2/M0）。主控仅接受112个分数与文件复算的一致性范围；原生计数条件失败和任务外缓存写入均保留，未重跑覆盖。
