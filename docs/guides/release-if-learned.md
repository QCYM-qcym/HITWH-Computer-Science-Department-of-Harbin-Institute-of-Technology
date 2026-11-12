# 学习状态包的命令与只读页面

更新：2026-11-13。学习状态接口、只读摘要与 CLI 已实现；CLI 源码和一次独立安装命令链已在人工工程范围内接受。[本轮工作流验证](../research/2026-11-13-release-if-learned-workflow-verification.json)记录完整源码回归5624通过/26跳过/1项既有警告/56子测试，318.04秒。此前5375通过/26跳过/1项警告/56子测试、314.42秒保留为新增 CLI 之前的历史结果。首次安装失败与后续独立 R2 的记录保留。只读后端和前端的源码、手工验证已接受；后继安装态 HTTP 与浏览器观测也已在原始人工 A 的只读范围内接受。真实研究实验为 `NOT_RUN`，Data Gate 为 `BLOCKED`。

## CLI 安装态验收范围

[CLI 验证记录](../research/2026-11-13-release-if-learned-cli-verification.json)对应一次独立离线构建、安装及八阶段观测，沿用原始人工 A：176分钟、公共56、训练18、独立校准10、预处理拟合18。`current13` 与 `h30_26` 各执行一次 `fit-save`、一次移动后冷 `inspect` 和一次独立进程 `replay`；两次新拟合共112项原始、112项拟合侧 P1 及112项独立复算值逐项精确一致，严格预测、Q99 和每视图120个非公共空值也一致。六份 CLI 成功回执均为规范 UTF-8 JSON 加 LF，stderr 为空；冷 inspect 未尝试导入 NumPy、模型或 pickle，也未执行拟合、预处理或 P1。

外层、控制器和八个阶段均实际退出0，无强制停止，回收、排空和句柄关闭完成。八阶段原生计数为8/4/2/2/2/2/2/2，内部合计24、外层26，差额2保持未归因。安装链核对了87个 wheel 成员、90个安装成员和83个冻结 Python 源码成员。最终335文件、2,968,143字节、18份原生 stdout/stderr 满足冻结上限，11组共1073个明确保护文件在该窗口内保持。独立规格和质量后验审查均为 C0/I0/M0，主控接受该人工 CLI 契约。

这次命令链与 R2 分别记账，不修复首次安装失败或历史 G 的父进程原生输出缺口。单独的安装态输出 flush 失败观测仍为 `NOT_RUN`。已有回归中的失败输出检查与本次成功安装命令链也分别记账。结果不认证源数据和模型历史，不证明全机无其他写入，不提供连续资源峰值或真实检测效果结论。

## CLI 命令

在已安装 `traffic-anomaly-core` 的 Python3.14 环境运行以下入口。`<ABS_...>` 是中性占位符，使用前替换为本机完整绝对目录，保留引号；`<NEW_ABS_...>` 指尚不存在的输出目录，其父目录必须已存在。输入包应已按既有格式保存；命令不会下载数据、生成输入或重新预处理。

```text
python -m traffic_anomaly.release_if_learned_cli --help
python -m traffic_anomaly.release_if_learned_cli inspect --learned-package "<ABS_LEARNED_PACKAGE>"
python -m traffic_anomaly.release_if_learned_cli replay --learned-package "<ABS_LEARNED_PACKAGE>" --result-package "<ABS_RESULT_PACKAGE>" --raw-package "<ABS_RAW_PACKAGE>" --prepared-package "<ABS_PREPARED_PACKAGE>"
python -m traffic_anomaly.release_if_learned_cli fit-save --raw-package "<ABS_RAW_PACKAGE>" --prepared-package "<ABS_PREPARED_PACKAGE>" --view current13 --result-output "<NEW_ABS_RESULT_OUTPUT>" --learned-output "<NEW_ABS_LEARNED_OUTPUT>"
```

`--view` 仅接受 `current13` 或 `h30_26`。各业务命令列出的选项均必填且只能出现一次，也可使用 `--option=value`。命令不接受缩写、额外位置参数或 `@` 参数文件；`-h`、`--help` 只可作为完整的单独参数。路径须符合包接口的本地绝对路径规则，不能含 `..`，不能使用 UNC 路径或链接/重解析点。不要把占位符原样传给命令。

| 命令 | 成功 `status` | 实际操作与边界 |
|---|---|---|
| `inspect` | `INTERNAL_CONSISTENCY_CHECKED` | 只读一个学习状态包并生成结构摘要；仅需标准库，不加载输入或结果，不做数值复算 |
| `replay` | `NUMERICAL_REPLAY_MATCHED` | 显式读取学习状态、结果、原始、预处理四个包，检查绑定并复算；需要 NumPy，不拟合、不保存 |
| `fit-save` | `SAVED` | 一次新拟合，先保存结果包，再保存学习状态包；两个输出都成功后才尝试写成功回执 |

`fit-save` 当前只在另行批准的人工工程验证范围内使用；该入口和示例不授权真实数据训练。调用到达拟合步骤后启动一次新的拟合；参数或输入检查失败可能在拟合前返回。它不提供历史估计器恢复、续训或自动重试。使用 `replay` 检查已有状态，不要重复 `fit-save` 来规避分数不一致。

## CLI 回执、错误与残留

`--help` 成功时退出0并输出固定帮助文本。三个业务命令成功时退出0、stderr 为空，stdout 为一行规范 UTF-8 JSON，排序键、紧凑分隔符、末尾一个 LF，最多32768字节。回执包含 `version=1`、`profile_id=c17-release-iforest-learned-cli-v1`、`command`、`status`、`summary`、`replay` 和 `operations`。`inspect`、`fit-save` 的 `replay` 为 `null`；成功 `replay` 的三个复算字段为 `MATCHED`，scope 为 `EXPLICIT_INPUT_NUMERICAL_REPLAY_ONLY`。

`operations` 的字段为 `fresh_fit_calls`、`numerical_replay_calls`、`result_save_calls`、`learned_save_calls`：成功 inspect 全为0，replay 仅第二项为1，fit-save 为1/0/1/1。这些是成功命令中的适配器操作声明，不能代替失败尝试计数、底层校验调用统计或运行观测。

可分类错误退出2；stderr 尝试输出一行 `{"error":"CODE"}` 加 LF，不暴露路径、堆栈或外部异常详情。有限代码来自 CLI 和所属包接口，按实际执行阶段返回。

| 分类 | 代码 |
|---|---|
| 命令、路径布局与返回对象 | `INVALID_ARGUMENTS`、`INVALID_PATH_LAYOUT`、`INVALID_RESULT` |
| 文件访问与完整性 | `INVALID_PACKAGE_PATH`、`INPUT_UNAVAILABLE`、`OUTPUT_EXISTS`、`PACKAGE_CHANGED`、`OUTPUT_ERROR`、`INTEGRITY_MISMATCH` |
| 包格式 | `INVALID_LEARNED_ARGUMENTS`、`INVALID_LEARNED_PACKAGE`、`INCOMPATIBLE_LEARNED_PACKAGE`、`INVALID_PACKAGE_ARGUMENTS`、`INVALID_PACKAGE`、`INCOMPATIBLE_PACKAGE`、`INCONSISTENT_PACKAGE` |
| 输入配对与预处理声明 | `INVALID_PAIR_ARGUMENTS`、`INVALID_PAIR_STRUCTURE`、`INCOMPATIBLE_PAIR`、`PAIR_ALIGNMENT_MISMATCH`、`UPSTREAM_IDENTITY_MISMATCH`、`INPUT_BINDING_MISMATCH`、`INVALID_PREPARATION_CONFIG`、`NO_TRAINING_NORMAL_MINUTES`、`NONFINITE_FIT_STATE`、`DERIVATION_MISMATCH` |
| 拟合与数值比较 | `NO_TRAINING_NORMAL`、`NO_CALIBRATION_NORMAL`、`INVALID_INPUT_NUMERIC`、`MODEL_UNAVAILABLE`、`MODEL_ERROR`、`INVALID_MODEL_STATE`、`INVALID_MODEL_SCORES`、`SCORE_MISMATCH`、`CALIBRATION_MISMATCH`、`PREDICTION_MISMATCH` |
| 运行与兜底 | `RESOURCE_LIMIT`、`INCOMPATIBLE_RUNTIME`、`INTERRUPTED`、`LEARNED_ERROR`、`INTERNAL_ERROR` |

两个输出目录须互不相同、互不嵌套，也不能与任一输入目录相同或互为祖先。命令先检查输出布局、既有父目录和目标占用，再加载输入；拟合和保存前会复查可观测目录变化。两个独立输出目录不会使两次保存成为原子事务：结果保存成功后，学习状态保存仍可能失败。已有结果、部分目录及其他残留全部保留，不覆盖、不删除、不回滚。

stdout 写入或 flush 失败可能发生在两个包都保存成功之后，也可能留下部分甚至完整的成功 JSON 字节；此时仍退出2，错误输出本身也可能写入失败。调用方必须同时检查实际退出码、原生 stdout/stderr 和输出包，不能仅凭看似完整的 stdout 判定成功，也不能根据退出2推断未拟合或未保存。停止并保留该次证据，查明原因后使用新的输出目录；重跑 `fit-save` 会再次拟合。

## 安装后的只读页面

在安装了 `traffic-anomaly-core` 和 `traffic-anomaly-api` 的 Python3.14 环境运行专用模块入口。六个参数分别指向既有原始包、预处理包，以及 `current13`、`h30_26` 各自的结果包和学习状态包。`<ABS_...>` 均须替换为本机完整绝对目录，不能原样传入；路径规则沿用所属包接口。页面入口不会生成输入或保存新模型。

```text
python -m traffic_api.release_if_learned_serve_cli --help
python -m traffic_api.release_if_learned_serve_cli --raw-package "<ABS_RAW_PACKAGE>" --prepared-package "<ABS_PREPARED_PACKAGE>" --current-result "<ABS_CURRENT13_RESULT_PACKAGE>" --current-learned "<ABS_CURRENT13_LEARNED_PACKAGE>" --h30-result "<ABS_H30_RESULT_PACKAGE>" --h30-learned "<ABS_H30_LEARNED_PACKAGE>" --port 8769 --serve-seconds 180
```

六个包选项必填且各出现一次，可使用 `--option=value`。`--port` 接受1..65535的整数，默认8769；绑定地址固定为 `127.0.0.1`，没有对外监听的 host 选项。`--serve-seconds` 接受1..300的整数，默认300，示例使用180。该计时在 `SERVER_READY` 成功写入并 flush 后开始，到期请求协作停止；启动与排空另需时间，参数值不构成进程物理退出的硬期限。端口占用或包检查失败会停止，不自动更换端口或重试。

程序在前台运行。看到 `SERVER_READY` 后可打开[学习状态页](http://127.0.0.1:8769/release/learned)，查看两个视图的保存声明和共同人口，再沿页面链接进入[保存结果页](http://127.0.0.1:8769/release/results)。结果页按100分钟分页；原始人工 A 的两页分别为100和76行。正常结束输出 `SERVER_STOPPED`，实际退出0且 stderr 为空；有限错误通常退出2，收到键盘中断时退出130。事件行不能代替实际退出码和错误流。

| 路由 | 用途 |
|---|---|
| `/release/learned` | 学习状态页面，展示两个视图及注册检查 |
| `/release-if-learned/v1/summary` | 学习状态元数据，含人口、两份摘要与保存引用 |
| `/release/learned/learned.mjs`、`/release/learned/learned.css` | 学习状态页的固定资源 |
| `/release/results` | 既有保存结果页面 |
| `/release-if/v1/summary` | 保留既有协议的结果元数据 |
| `/release-if/v1/series?page=0`、`/release-if/v1/series?page=1` | 原始人工 A 的完整176分钟序列 |
| `/release/results/results.mjs`、`/release/results/results.css` | 结果页的固定资源 |

上述路由只接受 GET。仅序列接口接受单个有效 `page` 参数；其他路由拒绝查询串。无效查询返回422，未知路径返回404，不支持的方法返回405，HEAD 错误响应体为空。页面没有上传、拟合或复算操作。

## 页面声明与显式复算的边界

启动时读取六个保存包，核对输入对、结果引用和学习声明，随后在绑定端口前冻结响应数据。后续 GET 和翻页使用这些冻结字节，不重新读取输入包，不执行新拟合、模型评分或 P1 复算。启动注册需要 NumPy 做保存内容的数值一致性检查；这与仅使用标准库的 CLI `inspect` 范围不同。

新元数据的 `registration_checks` 可为 `MATCHED`，表示这组保存声明与输入、结果绑定相符。两份学习状态摘要仍保留 `numerical_replay=NOT_RUN`、`input_pair_binding/result_binding=NOT_PERFORMED`，以及 `source_authentication/model_origin=NOT_AUTHENTICATED`；页面的 `replay` 为 `null`。数值复算仍须显式调用前文 `replay` 命令。已保存报警与真实标签也分别展示，页面不认证数据来源或历史训练过程。

## 只读页面的安装态观测

后继只读页面 v2 观测已完成，独立规格和质量后验复审均为 C0/I0/M0，主控接受该人工只读范围。沿用 CLI 命令链保存并移动的原始人工 A 包和既有90成员核心安装，没有重建核心或新增模型操作。原始 A 为176分钟、共同56、非公共120；测试段48分钟，其中共同18，训练18、独立校准10、预处理拟合18。

55次实际 HTTP 请求完成了首轮、重复和分页核对，并覆盖有限查询、方法与未知路径错误。两个序列页的全部176行与保存轴一致；两视图合计112个已保存分数的 binary64 位模式、严格 `>` 预测及每视图120个空值均逐项相同。注册阶段共6次保存分数 Q99 检查，每次选择所属视图的10个已保存校准值，合计60项选择；另有2次只读矩阵验证，形状为176×13和176×26，各有56个共同分钟行。这些核对没有新增拟合、P1 评分、输入准备或显式 replay。

后端构建、安装和只读服务三阶段，以及控制器均实际退出0；外部观测另行记录 caller 退出0。原生阶段计数为8/4/2，合计14，外层16，差额2保持未归因。未强制停止，回收、排空及进程/作业句柄关闭完成，正常服务记录了 READY 后协作停止和 STOPPED。最终265文件、2,855,111字节及8份控制器/阶段原生 stdout/stderr 均在冻结上限内；388个冻结身份、14组共1597个保护文件和两个已知旧缓存对象在该窗口内保持一致。这些检查提供采样及最终资源记录，不提供连续峰值或全机写入范围证明。

浏览器在1280像素和320像素视口完成观察，未见水平溢出；结果页第二页显示76行，未观察到控制台问题。该次浏览器观察使用同一有限服务窗口，没有延长或重启服务，也没有新增模型调用。

此前只读页面 v1 在后端安装校验阶段失败。准备阶段从基础 distlib 模板推导了错误预期，安装校验据此返回 `EXACT_CONSOLE_SCRIPT_BODY`，尚未启动服务。失败目录和原始证据保留；v2 在独立新目录中使用经源码核对的准确预期，严格入口检查保持。该历史与下节 R2、前述 CLI 命令链、最初学习状态安装失败分别记账，历史 G 的父进程原生输出缺口仍未关闭。页面观测不改变研究 S2/Data Gate `BLOCKED`、真实研究实验 `NOT_RUN`。

## 独立 R2 安装验收

[R2 验证记录](../research/2026-11-12-release-if-learned-installed-r2.json)使用同一份原始人工 A：176分钟、公共56、训练18、独立校准10、预处理拟合18。新的离线安装后，两种视图各拟合一次；112项原始、拟合侧 P1、保存结果及独立进程复算值逐项精确一致，Q99、严格 `>` 预测和120个非公共空值也一致。移动后的包可读取和复算，冷加载损坏副本及六个绑定负例按预期拒绝。

本次外层、控制器及五个内部阶段均退出0，无强制停止，回收、句柄关闭和计数排空完成。事先冻结的计数政策记录实际外层20、内部合计18及未归因差额2，不再假设差额必为一。构建明确禁用持久缓存，实际日志仅报告任务内临时缓存；两个已知旧缓存对象保持。最终320文件、2,751,446字节及12份原生流均满足已定上限，730个保护文件在本次窗口内保持。两项独立后验审查均为 C0/I0/M0，主控接受该人工契约范围。

R2 是一次独立的新调用，未改写首次失败，也未补齐历史 G 的父进程输出缺口。这些检查不认证源数据或模型历史，不证明机器上不存在其他写入，也不提供连续资源峰值或研究效果结论。后续新增 CLI 源码属于 R2 窗口结束后的独立开发。

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
from traffic_anomaly.release_if_learned_summary import summarize_release_if_learned

learned = load_release_if_learned_package(learned_directory)
members = encode_release_if_learned_package(learned)
decoded = decode_release_if_learned_package(dict(members))
summary = summarize_release_if_learned(learned)
```

学习状态模块导入、编解码和磁盘保存/读取可仅用标准库完成。目录固定包含 `numeric-state.json`、`manifest.json` 和 `COMPLETE.json`，分别最多262144、8192和4096字节，总计最多274432字节。读取先检查全体成员预算，再验证摘要及结构。加载成功代表包内一致性检查通过，尚未执行数值复算或认证模型来源。

`summarize_release_if_learned` 验证已加载对象后返回新的摘要字典，profile 为 `c17-release-iforest-learned-summary-v1`，规范编码预算为16384字节。摘要包含学习状态标识、视图、输入/结果引用、配置及总体声明、分钟/树/节点计数和检查状态，不包含数值树、分数或路径。其 scope 为 `SAVED_LEARNED_INTERNAL_CONSISTENCY_ONLY`；`byte_integrity`、`structure` 为 `MATCHED`，`numerical_replay` 为 `NOT_RUN`，`input_pair_binding`、`result_binding` 为 `NOT_PERFORMED`，`source_authentication`、`model_origin` 为 `NOT_AUTHENTICATED`。CLI 的成功 replay 将实际复算结果另放在 `replay`，保留这些结构摘要状态，不把声明展示改写成绑定或来源认证证明。

## 独立进程显式复算

在新进程中先运行“环境与输入”一节的加载和配对代码，建立本进程的 `pair`，再运行下段加载结果和学习状态包。四个包目录均由调用方显式提供；不能只凭学习状态包推断输入或结果。

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

新增 CLI 之前的学习状态源码人工输入集成已执行两个视图的两次新拟合；手工输入公共55/训练17/校准4，原始和拟合侧 P1 各110值，独立进程复算110值，均为精确比较。该阶段定向回归分别记录347通过、250通过和254通过/10跳过，这些测试范围重叠。两项独立源码审查与根审查已接受该阶段源码范围；另有验证执行器独立审查。

安装态人工观测要求使用原先接受的 A：176分钟、公共56、训练18、校准10、预处理拟合18，分段公共数为18/10/10/18。A 不可用同计数的后续生成例子或源码手工输入替换。首次安装态实际观测已结束：两次人工输入新拟合，112项拟合侧及112项独立复算精确匹配，校准行20+20；冷加载和六个绑定/声明负例已观察。五个内部阶段均退出0、未强制且已回收；外层退出1，原生总数20与“内层合计18加一”的假设不符，caller完成收据未生成。构建还写入任务目录外的持久pip wheel缓存。因此状态为 `FAILED_OBSERVER_CONTRACT`，部分数值仅 `OBSERVED_NOT_FULL_ACCEPTED`。原冻结脚本及运行残留保留，没有重跑；任务外缓存足迹未知，不能称完整时间/资源及写入范围通过。

首次失败后要求修订原生进程计数政策，直接记录有界实际计数，取消固定一控制器假设；pip使用 `--no-cache-dir` 和任务内临时目录。其不含拟合的控制流检查及独立复核随后完成，再冻结并执行了上节 R2；首次运行的冻结脚本与残留未修改。历史 G 控制器父进程原生输出字节缺口仍未关闭；本功能不改变真实数据或研究阶段的状态。

首次安装观测的后验规格和质量复审均确认其完整契约为FAIL（C0/I2/M0）。当时主控仅接受112个分数与文件复算的一致性范围；原生计数条件失败和任务外缓存写入均保留，未重跑覆盖。
