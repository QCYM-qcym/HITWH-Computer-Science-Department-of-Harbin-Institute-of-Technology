# 保存输入的自编码器内存接口

更新：2026-11-13。源码审查、175项最终手工用例和一次原始人工 A 双视图数值观察已接受；本页快照时，本批发布与新提交 CI 待核对。依据：[验证记录](../research/2026-11-13-release-autoencoder-verification.json)。研究仍为S2，Data Gate `BLOCKED`，真实研究 `NOT_RUN`。

该接口消费既有原始包与预处理包配成的 `ReleaseModelInputPair`，一次调用拟合一个固定CPU自编码器，返回不可变数值结果。它不生成输入、不重新拟合预处理，也不认证输入来源或重放输入推导。

## 最小调用

在项目源码环境中用于人工工程运行时，调用方提供既有包的绝对目录：

```python
from traffic_anomaly.release_minute_package import load_release_minute_package
from traffic_anomaly.release_input_package import load_release_input_package
from traffic_anomaly.release_model_inputs import pair_release_model_inputs
from traffic_anomaly.release_autoencoder import fit_release_autoencoder

# raw_directory、prepared_directory 由调用方提供。
raw = load_release_minute_package(raw_directory)
prepared = load_release_input_package(prepared_directory)
pair = pair_release_model_inputs(raw, prepared)
result = fit_release_autoencoder(pair, view="current13")

scores = result.scores
threshold = result.threshold
predictions = result.predictions
```

`fit_release_autoencoder(pair, *, view)` 必须显式传入 `current13` 或 `h30_26`。每次到达数值阶段都会新建并训练模型；换成另一个视图是另一次拟合。查看已有结果时直接读取 `result` 字段，再次调用会重新训练。接口串行使用，不接受调用方模型、优化器、回调或可调训练参数。

运行契约为Python3.14、NumPy2.5.4、Torch2.14.1+cpu，使用已有CPU环境；不自动安装依赖或下载模型。线程与互操作线程数须各在1—64内，接口不修改全局线程设置。输入最多10000分钟、7个段，仍须通过既有身份、时间轴、资格与有限数值检查；输入行数相同不代表两个包匹配。

## 固定数值语义

| 项目 | 契约 |
| --- | --- |
| 视图 | current13为13维当前值；h30_26为当前13维与H30残差13维 |
| 网络 | 宽度→8→3→8→宽度，隐藏层ReLU、输出线性；参数分别288、509 |
| 训练 | 既有工程profile；CPU float32，种子42，5轮全批、不打乱；Adam学习率0.001，每轮一次更新 |
| 资格 | 仅共同有效人口中的训练正常行参与拟合；训练与独立正常校准不交叠，训练索引须属于已有预处理拟合人口 |
| 分数 | float64重建MSE；current13为当前通道，h30_26为当前与历史残差通道各占一半 |
| 阈值 | 仅所属模型的独立正常校准分数，线性Q99；严格 `score > threshold` 才报警 |

current13也沿用保存输入的共同有效资格，不扩大成所有当前值有效行。合法训练或校准人口为空会拒绝；不会补零、扩大资格或重新估计预处理。固定profile是人工工程设置，不代表真实数据的窗口、结构或超参数选择。

## 返回值与错误

`ReleaseAEResult` 及嵌套配置、校准、运行信息为冻结记录；向量和索引使用元组。主要字段如下：

| 字段 | 含义 |
| --- | --- |
| `scores`、`predictions`、`scored_mask` | 与原始分钟轴等长；未评分位置为 `None`、`None`、`False`，不能计作正常负例 |
| `current_reconstruction_mse` | 共同分钟的当前通道MSE，其余为 `None` |
| `history_deviation_reconstruction_mse` | h30_26共同分钟的历史残差MSE；current13全轴为 `None` |
| `threshold`、`calibration` | 阈值、校准样本数、等于阈值数及严格超过数 |
| `training_losses` | 五次已有训练损失标量；它们不是检测效果指标，也不保证单调下降 |
| `train_indices`、`calibration_indices`、`preprocessing_fit_indices` | 保存轴上的资格索引 |
| `raw_identity`、`prepared_identity`、`configuration_sha256` | 既有输入及预处理配置的身份引用 |
| `configuration`、`runtime` | 固定模型设置、运行版本和CPU线程信息 |

结果profile为 `c17-release-ae-engineering-v1`，scope为 `IN_MEMORY_ENGINEERING_NUMERICAL_RESULT_ONLY`。返回值不暴露网络、权重或优化器，不能据此恢复模型、续训或重新推理。当前没有AE结果包、保存/重载、inspect、CLI或HTTP/页面入口；[既有IF保存命令与页面](release-if-learned.md)不接收这个结果。

接口错误使用 `ReleaseAEError.code`，不提供外部异常详情。有限代码为 `INVALID_AE_ARGUMENTS`、`INVALID_AE_INPUT`、`RESOURCE_LIMIT`、`NO_TRAINING_NORMAL`、`NO_CALIBRATION_NORMAL`、`INVALID_INPUT_NUMERIC`、`INCOMPATIBLE_RUNTIME`、`MODEL_UNAVAILABLE`、`MODEL_ERROR`、`INVALID_MODEL_STATE`、`NONFINITE_TRAINING`、`INVALID_MODEL_SCORES`、`RNG_RESTORATION_FAILED`、`AE_ERROR`。包加载/配对步骤仍使用各自异常。真实 `KeyboardInterrupt`、`SystemExit` 继续传播；内存不足转换为资源错误。失败不返回部分结果，也不自动重试；异常不表示此前没有模型操作。数值上下文恢复调用前的Python、NumPy和Torch RNG状态，本次双视图已逐项核对保存的完整状态。

## 已接受的工程范围

最终手工组175项通过，含60项准入与115项数值/错误交互用例；模型部分使用闭合替身。最终一轮另有24次既有真实校准算术、每次4项，共96个选值断言，以及2次坏阈值拦截。七次手工pytest观察包含五次有效RED/GREEN/最终观察和两次保留的围栏/环境配置失败；各轮重叠用例不累加，也不把七次当作全部准备或原生调用数。

随后一次独立原始人工 A 观察使用176分钟、56个共同分钟、训练18、独立校准10和预处理拟合18。两视图共2个模型、10次更新、12次前向与2次模型Q99。112个分数来自同一56分钟的两个视图；20个模型校准分数选择仍对应同一10个分钟索引。完整捕获输入/输出、五个已有损失标量、分数/通道位值、严格预测、每视图120个空值及三类RNG恢复均匹配。两视图实际运行版本一致：Python3.14.0、NumPy2.5.4、Torch2.14.1+cpu，CPU线程1、互操作线程6。独立规格与质量后验审查均为C0/I0/M0，主控已接受该人工数值范围。

模型的2次Q99、子观察器的2次独立Q99和主控的2次标准库保存值Q99分别记账，各选择20项；两名后验审查者未新增Q99或MSE。观察器另有2次独立float64 MSE核对，没有额外模型前向或训练损失归约。完整原生输出为8份、210字节；最终26文件、619636字节满足冻结资源上限，采样不提供连续峰值或全机写入范围证明。

专门的冷导入验证、安装态、持久化、CLI、页面和本批完整本地回归为 `NOT_RUN`；新提交CI与发布待核对。此前IF的安装、页面、全套测试和CI属于独立批次。生产134/268、既定492固定源门禁及真实研究准入不变；本接口不提供检测效果或正式IF/AE比较结论。
