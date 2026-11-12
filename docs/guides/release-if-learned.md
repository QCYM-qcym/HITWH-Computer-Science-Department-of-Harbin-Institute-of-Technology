# 学习状态包的保存与显式复算

学习状态接口已实现，源码定向验证与独立源码审查已完成。全量回归已接受，5375通过/26跳过/1项既有警告/56子测试，314.42秒；安装态首次观测为 `FAILED_OBSERVER_CONTRACT`，部分数值已观察，完整安装态未接受。真实研究实验为 `NOT_RUN`，Data Gate 为 `BLOCKED`。本功能没有 CLI 或 UI，二者均为 `NOT_IMPLEMENTED`。

## 环境与输入

新拟合使用 Python3.14、NumPy2.5.4、scikit-learn1.9.1 和 joblib1.6.0。只支持 `current13` 与 `h30_26`。调用方必须显式传入既有格式的原始包和预处理包；学习状态接口不会生成输入或重新预处理。

```python
from traffic_anomaly.release_minute_package import load_release_minute_package
from traffic_anomaly.release_input_package import load_release_input_package
from traffic_anomaly.release_model_inputs import pair_release_model_inputs

raw = load_release_minute_package(raw_directory)
prepared = load_release_input_package(prepared_directory)
pair = pair_release_model_inputs(raw, prepared)
```

示例中的目录变量由调用方提供，均应为符合路径规则的绝对目录。不要根据两个包的长度相同推断它们匹配；配对操作会检查引用、时间轴及保存声明。

## 新拟合并分别保存两类包

```python
from traffic_anomaly.release_if_learned import fit_release_iforest_learned
from traffic_anomaly.release_if_result_package import save_release_if_result_package
from traffic_anomaly.release_if_learned_package import save_release_if_learned_package

run = fit_release_iforest_learned(pair, view="current13")
result_identity = save_release_if_result_package(run.result_package, result_directory)
learned_identity = save_release_if_learned_package(run.learned_package, learned_directory)
```

每次调用会进行一次新的拟合。函数保留同一估计器，唯一一次原始评分之后导出数值树，并用 P1 对全部公共分钟逐项比较 `float.hex()`。完整比较成功才返回结果包和学习状态包。不要用重复调用规避 `SCORE_MISMATCH`，也不要将新的拟合解释为历史模型恢复。

结果包保存分数、独立校准 Q99 和严格 `>` 预测，仍为权威结果。学习状态包保存只含数值的森林及绑定声明，不保存估计器对象或训练矩阵。

两个输出目录必须分别不存在。保存先独占创建目录，COMPLETE 最后写入；出错后保留全部残留，不覆盖、不删除，也不自动恢复。两次保存是独立操作，第一次成功不保证第二次成功。修复原因后应使用新的输出目录并重新判断已完成的阶段。

## 不加载 NumPy 的学习状态读取

```python
from traffic_anomaly.release_if_learned_package import load_release_if_learned_package
from traffic_anomaly.release_if_learned_contract import (
    encode_release_if_learned_package,
    decode_release_if_learned_package,
)

learned = load_release_if_learned_package(learned_directory)
members = encode_release_if_learned_package(learned)
decoded = decode_release_if_learned_package(dict(members))
```

学习状态模块导入、编解码和磁盘保存/读取可仅用标准库完成。目录固定包含 `numeric-state.json`、`manifest.json` 和 `COMPLETE.json`，分别最多262144、8192和4096字节，总计最多274432字节。读取先检查全体成员预算，再验证摘要及结构。加载成功代表包内一致性检查通过，尚未执行数值复算或认证模型来源。

## 独立进程显式复算

在另一个进程重新加载所需包，并显式建立原始输入对。传入原始输入和结果是复算契约的一部分，不能只凭学习状态包推断它们。

```python
from traffic_anomaly.release_if_result_package import load_release_if_result_package
from traffic_anomaly.release_if_learned_package import load_release_if_learned_package
from traffic_anomaly.release_if_learned import replay_release_iforest_learned

result = load_release_if_result_package(result_directory)
learned = load_release_if_learned_package(learned_directory)
report = replay_release_iforest_learned(learned, pair, result)
```

复算使用 Python3.14和 NumPy2.5.4，不需要安装 sklearn 或 joblib。冷启动 NumPy 自身可能导入标准库 pickle；该依赖初始化必须与产品复算的 pickle 操作检查分开。学习状态磁盘读取和编解码仍可在 NumPy/pickle 导入禁用条件下完成。

复算会先验证学习状态和结果引用，再绑定输入配置、特征顺序及各总体索引。随后仅用 P1 复算全部公共分数，独立计算校准 Q99，并比较严格预测及非公共位置的 `None`。成功报告的三个复算字段均为 `MATCHED`，scope 为 `EXPLICIT_INPUT_NUMERICAL_REPLAY_ONLY`。`source_authentication=NOT_AUTHENTICATED`、`derivation_replay=NOT_PERFORMED` 保留不变。

已保存的包可移动到新目录，复算仍依赖显式提供的输入对与结果。字节完整性和声明一致性不证明数据来源或历史拟合过程；一致改写的整组输入与状态可能通过内部检查。

## 失败处理与验证范围

捕获 `ReleaseIFLearnedError` 并记录其有限 `code`。输入或引用不匹配应修正传入对象；`SCORE_MISMATCH`、`CALIBRATION_MISMATCH`、`PREDICTION_MISMATCH` 应停止并保留证据。资源超限为 `RESOURCE_LIMIT`；目录存在为 `OUTPUT_EXISTS`；可观测变化为 `PACKAGE_CHANGED`。不将外部异常详情写入公开错误信息。

源码人工输入集成已执行两个视图的两次新拟合；手工输入公共55/训练17/校准4，原始和拟合侧 P1 各110值，独立进程复算110值，均为精确比较。定向回归分别记录347通过、250通过和254通过/10跳过，这些测试范围重叠。两项独立源码审查与根审查已接受源码范围；另有验证执行器独立审查。

安装态人工观测要求使用原先接受的 A：176分钟、公共56、训练18、校准10、预处理拟合18，分段公共数为18/10/10/18。A 不可用同计数的后续生成例子或源码手工输入替换。首次安装态实际观测已结束：两次人工输入新拟合，112项拟合侧及112项独立复算精确匹配，校准行20+20；冷加载和六个绑定/声明负例已观察。五个内部阶段均退出0、未强制且已回收；外层退出1，原生总数20与“内层合计18加一”的假设不符，caller完成收据未生成。构建还写入任务目录外的持久pip wheel缓存。因此状态为 `FAILED_OBSERVER_CONTRACT`，部分数值仅 `OBSERVED_NOT_FULL_ACCEPTED`。原冻结脚本及运行残留保留，没有重跑；任务外缓存足迹未知，不能称完整时间/资源及写入范围通过。

后续先修订原生进程计数政策，直接记录有界实际计数，取消固定一控制器假设；pip使用 `--no-cache-dir` 和任务内临时目录。先完成不含拟合的观察器回归与独立复核，再另行放行一次新运行。本轮未修改业务源码，也未执行这些后续步骤。历史 G 控制器父进程原生输出字节缺口仍未关闭；本功能不改变真实数据或研究阶段的状态。

后验规格和质量复审均确认完整安装观测为FAIL（C0/I2/M0）。主控仅接受112个分数与文件复算的一致性范围；原生计数条件失败和任务外缓存写入均保留，未重跑覆盖。
