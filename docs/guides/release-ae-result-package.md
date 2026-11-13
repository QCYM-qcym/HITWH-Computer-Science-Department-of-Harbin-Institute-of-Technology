# AE 结果包：保存、移动与只读检查

更新：2026-11-13。三模块源码、原396项手工专项用例、已有人工结果的保存产物，以及独立v2冷源检查与真实断管观察均已接受；首次v1整轮失败保留。依据：[原验证记录](../research/2026-11-13-release-ae-result-verification.json)。该批已发布，完整CI暴露了测试导入隔离问题；本轮复现、测试修复与相关396项已通过，新提交的准确CI待核，见[CI隔离修复记录](../research/2026-11-13-release-ae-result-ci-repair.json)。

已有 `ReleaseAEResult` 可保存为三文件目录，移动后在另一进程加载或用 `inspect` 查看摘要。读取只消费保存值，不训练或评分。S2 / Data Gate 仍为 `BLOCKED`，真实研究及正式 IF/AE 比较保持 `NOT_RUN`。

## 保存已有结果

调用方沿用[内存接口](release-autoencoder.md)的已有结果和对应保存输入。`ReleaseAEResultDeclarations` 含十个明确字段；配置 SHA 指预处理配置。下面从调用方已有的 `pair` 读取声明，沿用已有 `result`，不再次调用拟合接口。构包核对声明内部关系，不重开上游包。

```python
from traffic_anomaly import release_ae_result_contract as contract
from traffic_anomaly import release_ae_result_package as disk

# pair、result 是调用方已有的同一输入配对与结果。
declarations = contract.ReleaseAEResultDeclarations(
    raw_identity=pair.raw_identity,
    prepared_identity=pair.prepared_identity,
    configuration_sha256=pair.configuration_sha256,
    source_schema_id=pair.source_schema_id,
    source_authentication=pair.source_authentication,
    time_basis=pair.time_basis,
    policy_status=pair.configuration.policy_status,
    audit_fit_policy=pair.configuration.audit_fit_policy,
    segments=pair.segments,
    minute_count=len(pair.roles),
)

# new_directory 是尚不存在的绝对目录，父目录已存在。
package = contract.make_release_ae_result_package(result, declarations)
saved_identity = disk.save_release_ae_result_package(package, new_directory)
loaded = disk.load_release_ae_result_package(new_directory)
```

每包只保存一个 `current13` 或 `h30_26` 视图，两个新目录独立保存，不构成原子提交。库不知道上游路径；调用方须保证输出与输入及证据目录互不重叠。

| 成员 | 内容 | 含末尾 LF 的上限 |
| --- | --- | ---: |
| `result.json` | 完整 AE 结果；含全轴向量、阈值、索引与固定配置 | 2,097,152 B |
| `manifest.json` | 输入声明、源钟面分段及结果字节引用 | 65,536 B |
| `COMPLETE.json` | 清单引用，最后写入 | 4,096 B |

包 profile 为 `c17-release-ae-result-package-v1`，总上限 2,166,784 B，轴长 1—10,000 分钟、最多 7 段。规范 UTF-8 JSON 与 SHA256 引用均须核对，`COMPLETE.json` 存在不单独表示有效。

仅接受普通绝对本地路径，拒绝 `..`、UNC、链接/reparse 等形式；排他保存不覆盖既有目录。签名检查只检测采样步骤间的变化，不提供原子快照、回滚或掉电持久性保证。

## 移动后读取

移动完整目录后传新绝对路径给 load，无需上游路径或权重。返回 `identity/context/result/load_report` 冻结记录，向量和索引为元组。

`scores/predictions/scored_mask` 保留全轴，未评分行是 `None/None/False`；零分数、未报警与未评分分别保留。`train_indices/calibration_indices/preprocessing_fit_indices` 记录三类人口，预处理可含未评分 train 预热分钟。分段 gap 不补行，源钟面不变成认证 UTC。

结果沿用 `c17-release-ae-engineering-v1` 默认配置：current13 为 13 维、288 参数，h30_26 为 26 维、509 参数，固定五轮全批，无调参项。current13 分数等于当前 MSE，历史全为 `None`；H30 按 binary64 的 `0.5*当前+0.5*历史` 核保存总分，不重算 MSE。

报警严格采用 `score > threshold`，相等不报警。加载按本包校准索引的保存分数复核 linear Q99 与校准计数。保存 loss/运行版本只是声明，不证明训练效果或历史执行；返回值没有网络、权重或优化器。

`load_report` 的字节/结构/保存 Q99/声明内部绑定为 `MATCHED`；输入配对与推导重放为 `NOT_PERFORMED`，来源/模型执行为 `NOT_AUTHENTICATED`。自洽改写仍可形成另一合法包；报警不能直接判作误报或漏报，未报警也不等于正常标签。

## inspect 命令

使用具备当前源码的 Python 3.14 core 与已有 NumPy 2.5.4；inspect 需保存 Q99，单独 help 只用标准库。不导入 Torch/sklearn 等模型，不下载依赖。占位符替换为绝对包目录：

```text
python -m traffic_anomaly.release_ae_result_cli --help
python -m traffic_anomaly.release_ae_result_cli inspect --result-package ABS_SAVED_AE_RESULT_DIR
```

inspect 每次只读一个包，无 raw/prepared 参数；没有 fit/pack/verify/replay/网页命令。IF 命令不接纳 AE 包。

成功退出 0、stderr 空，stdout 为规范 UTF-8 JSON 加 LF，最多 65,536 B；profile 为 `c17-release-ae-result-cli-v1`，状态为 `INTERNAL_CONSISTENCY_CHECKED`。摘要含身份、分段人口与配置，保留运行声明和阈值/loss/校准/三类分数范围，无全轴数组、路径或权重。current13 历史范围是 count 0、min/max null；全轴从 `loaded.result` 或 `result.json` 读取。

成功调用的保存 Q99 账本如下，各项不能误称模型执行：

| 入口 | 保存分数 Q99 次数 |
| --- | ---: |
| `decode_release_ae_result_projection(payload: bytes)` | 1；重建数据，仅核结果局部关系 |
| `make_release_ae_result_package(result, declarations)` | 1 |
| `encode_release_ae_result_package(package)` | 1；返回三份 `(name, bytes)` |
| `decode_release_ae_result_package(members: dict[str, bytes])` | 1；从三份成员字节重建包 |
| save | 2：编码与单次保留读回解码各 1 |
| load / inspect | 各 1；inspect 的摘要投影不另做 Q99 |

示例 make→save→load 共 4 次复核；重复选择不增加独立校准分钟。CLI operations 为 fit 0、forward 0、保存 Q99 1、上游 load 0。

## 错误与残留

库异常为 `ReleaseAEResultPackageError.code`：路径/参数无效、`OUTPUT_EXISTS`、`INPUT_UNAVAILABLE`、`PACKAGE_CHANGED`、字节或语义不一致、`RESOURCE_LIMIT`、依赖/版本不符和 `OUTPUT_ERROR`；未知错误为 `PACKAGE_ERROR`，不回显原异常/路径。

CLI 一般错误及Ctrl+C返回 2，stderr 尽力输出 `{"code":"CODE","status":"ERROR"}` 加 LF，最多 1,024 B；非法参数为 `INVALID_ARGUMENTS`，未知外部异常为 `CLI_ERROR`，Ctrl+C 为 `INTERRUPTED`。CLI收到的真实 `SystemExit` 继续传播；库层真实 `KeyboardInterrupt`、`SystemExit` 也继续传播。stdout 短写或 flush 失败可能已留下部分甚至完整摘要，须结合实际退出与 stderr 判定成功。

保存失败保留残留，不自动删除、改名重试或续写；也可能留下完整可加载包。先独立检查，再保留残留并选择新输出目录，不能重跑覆盖。读取不改写包。

## 分项验证

源码三模块及三份测试已接受。最终同组396项通过：契约231、磁盘55、CLI110。首次契约 GREEN 的229通过/2失败与各阶段缺模块 RED 保留；已修正空分数字段的错误分类与异常子类属性读取问题。CLI 另修正跨调用缓存，8项既有成功用例同时核对模块状态保持。

手工测试共8个具名调用，各轮用例不累加；既有真实校准函数执行手工保存分数算术130次、466个重复选值，含失败阶段，最终396项一轮为47次/164项。这些是手工数据的检查次数，不是新模型训练或独立分钟。源码及两次提取函数的闭合状态控制也经独立复核；闭合替身的范围与真实命令运行分开。

已发布提交`6b1650ab`的完整synthetic CI为6086通过、45失败、90跳过、1警告、56subtests；docs13、contracts21、frontend375通过。失败保留，不能以局部通过代替完整CI。原手工组按契约→磁盘→CLI运行，未覆盖CLI先载入磁盘别名后再重载契约模块的顺序。该测试重载会重建异常类，已有消费者仍绑定旧类；修复仅改导入测试，用临时新导入核对标准库边界，并恢复原模块、父包绑定及消费者身份，三份生产模块未改。

本轮另有3次普通源码pytest观察：原顺序代表用例复现为2通过/1失败，修复后同组3通过，CLI→契约→磁盘的相关396项全部通过。前两轮保存Q99均0，相关组为47次/164个重复选值；模型导入尝试0、无模型模块、源码来源核对通过。它们不并入原8次手工观察，也不新增独立用例；这是源码测试证据，不是原生进程树或业务原始流验收。完整新CI仍待核。

实际保存桥接消费已有人工A的两份结果与原始/准备输入，完成两次保存和移动；176分钟、共同56、训练与预处理18、独立校准10保持。两个三成员包的完整结果、空位、float64位值、分段、人口与输入身份经标准库被动复查匹配。此次完成8次保存分数Q99/80重复选值，模型与前向均0。

首次四阶段验收在观察器进程身份核对处失败：Windows虚拟环境启动器与实际Python进程身份不同。整轮保持失败，不计作冷加载或断管通过；当时后两类实际操作均未运行，原25文件/52227字节失败证据完整保留。

独立v2随后只消费这两份已移动包，三个子进程依次退出0、0、2，外层与原生调用者均退出0；没有重复保存桥接。两个成功inspect各复核一次保存Q99/10个选值，真实缓冲断管另一次/10个选值；新3次/30项与v1的8次/80项分开。断管stderr为有限OUTPUT_ERROR，stdout不可捕获，未将其伪作空流。七份实际原生流共8743字节，最终22文件/57601字节、最大成员9373字节；正常回收、句柄关闭与冻结保护均经复核。

两份完整结果的浮点位值与null、输入声明和三类人口，以及三个19字段摘要均与保存原件匹配，独立被动复核不另做Q99/MSE。实际命令是在全新源码进程中受守卫的runpy真实module-main，包含模块入口与物理退出观察；不是wheel安装或未包装的字面python-m运行证明。安装态、AE HTTP/页面、本批完整本地回归仍为 `NOT_RUN`；本轮修复的新提交发布/CI保持快照待核。此前内存接口的175项和双模型观察各保留原范围。

真实研究、134/268 与既定492门禁不变；本轮不形成正常误报率、漏报或正式IF/AE比较结论。
