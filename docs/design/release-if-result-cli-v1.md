# Release IF 结果命令行 v1

日期：2026-11-11。状态：W0依据用户自主工程授权采用，builder check、实现、独立源码复核、完整 Python 回归及新安装人工验收均已完成并接受。实际范围与未执行项见[运行指南](../guides/release-if-result-cli.md)和[验证记录](../research/2026-11-11-release-if-result-cli-verification.json)。基线为已发布结果包/只读页版本 `bc276bb3ea4ba57f53a773b9bdc14ad72d753d72`，其[真实发布回执](../research/2026-11-11-release-if-results-publication.json)与原控制器失败/后验功能接受分别保留。本次仅补状态和链接，不改变下述接口；当前 CLI 批次发布为 PENDING_AT_SNAPSHOT，真实研究 Gate 不升级。

## 用途和选择

已安装 core 的使用者可以从自己持有的一对 raw/prepared 保存包生成单个 IF 结果包，之后可以单独检查该包，也可以重新提供两个输入包检查声明绑定。已有后台命令能同时打开 current13 和 h30_26。W0 选择每条 run 明确计算一个视图，两条命令分别拥有自己的目标目录和退出状态。双输出命令需要新增部分成功协议。纯离线评价还需要确定标签对齐、测试人口和分母，另行设计。

本提案使用已有 [IF 内存契约](release-iforest-engineering-v1.md)、[输入配对契约](release-model-input-pair-v1.md)、[结果包](release-if-result-package-v1.md) 及其预算。工程选择来自本轮自主迭代授权。S2/Data Gate BLOCKED，真实 C17 训练、评分、Q99 与正式实验 NOT_RUN。验收使用已知人工包。包不认证数据的人工或真实身份，CLI 不根据文件名、用户声明或开关推断来源。研究端点、标签政策、candidate、生产 134/268、后台和 UI 均不在此次变更范围。

## 公共接口

新增 `traffic_anomaly.release_if_result_cli.main(argv: Sequence[str] | None = None) -> int`。模块命令为 `python -m traffic_anomaly.release_if_result_cli`。无新 console script、依赖、环境变量或配置文件。argv 为 None 时取 sys.argv[1:]。help、inspect、verify 无须 sklearn 模型依赖，run 沿既有固定 IF 实现按需导入 sklearn。

| 命令 | 必须且仅允许的选项 | 成功 status |
| --- | --- | --- |
| run | --raw-package ABS、--prepared-package ABS、--view current13 或 h30_26、--output NEW_ABS | SAVED |
| inspect | --result-package ABS | INTERNAL_CONSISTENCY_CHECKED |
| verify | --result-package ABS、--raw-package ABS、--prepared-package ABS | INPUT_BINDING_MATCHED |

命令名位于首位，选项任意排序。接受 `--name value` 和 `--name=value`，值非空。独占 `-h` 或 `--help` 时写固定 UTF-8 帮助文本并以一个 LF 结尾、退出 0，包含以上三条用法及 run 会拟合、inspect/verify 只核验的提示。子命令混合 help、重复选项（含两种形式混用）、未知长短选项、缩写、额外位置参数、`--`、缺项、空 argv、传入 str/bytes 代替参数序列、非 str 元素、以 @ 开头的 token/选项值、非法 view 均为 INVALID_ARGUMENTS。分离写法不把以 - 开头的下一个 token 吞为值。无需读取文件、加载包、导入 sklearn 或执行业务来处理 help/语法错误。

## 路径与执行顺序

通过语法后才做路径预检。全部路径先按原始值检查，顺序为 run 的 raw/prepared/output、inspect 的 result、verify 的 result/raw/prepared。复用既有包 lexical 约束和当前平台 Path 语义，拒绝相对路径、含 ..、NUL、UNC、Windows 非本地盘绝对路径/保留名/ADS，错误为 INVALID_PACKAGE_PATH。Windows 只带根斜杠的 /package 不算盘符绝对路径。检查路径关系采用完整组件及平台大小写规则。

run 先检查 output 与两个输入分别相同或任一方位于对方之下，有重叠报 INVALID_PATH_LAYOUT，优先于 OUTPUT_EXISTS。输入之间的身份及包格式匹配交给两个 loader/pair。再以 lstat 校验全部输出祖先为普通目录、父目录存在。祖先为链接/reparse/非目录报 INVALID_PACKAGE_PATH，父目录缺失、权限或其他访问错误报 OUTPUT_ERROR。lstat 观察到目标已存在（含文件、目录、悬空链接）报 OUTPUT_EXISTS。输入加载仍使用既有逐级目录及成员身份/预算检查。在路径存在别名的平台，对输出父级路径链与已核实的输入根目录也比较可观测的设备/文件身份，避免通过另一种拼写在输入包内建目录。有此重叠报 INVALID_PATH_LAYOUT。含歧义的多个无效条件按上述阶段首先观察的错误返回。预检只观察，无目录创建、写探针或提前保留目标。

1. run：完成预检，依次各一次 load_release_minute_package、load_release_input_package、pair_release_model_inputs。通过上述包含输入根身份的预检后调用一次 fit_release_iforest(pair, view=view)，一次 make_release_if_result_package(pair, result)，一次 save_release_if_result_package(package, output)。save 返回的四字段结果身份必须精确匹配 package.identity，才输出 SAVED。类型或返回身份异常为 INVALID_RESULT。成功写入顺序与读回核对归 save；CLI 无额外重读或重试。save 自身 exclusive mkdir/xb 最终裁定竞争，出现竞争可以已完成计算，永不覆盖赢家。
2. inspect：一次 load_release_if_result_package，投影包及 load_report。本命令不要求原输入、模型执行或显式配对。
3. verify：依次各一次 load_release_if_result_package、load_release_minute_package、load_release_input_package、pair_release_model_inputs、verify_release_if_result_pair(package,pair)，成功后投影。检查读入包的完整性与声明绑定，不重放预处理、不重新运算 IF 分数。

inspect/verify 的产品调用不得 prepare、fit、score 或估计预处理参数。load/verify/make/save 中由既有 codec 对**保存的校准分数**做 Q99 一致性检查，和模型 fit/score 时的阈值计算分别记账。显式绑定可能进行有限的纯输入数值验证。产生包的 run 行为与一份已存包的模型执行认证是两个不同字段。

## 成功回执

正常业务成功仅输出一个 UTF-8 JSON object，ensure_ascii=False、allow_nan=False、sort_keys=True、紧凑分隔符、末尾单 LF，含 LF 总长 ≤65,536 字节。stderr 为空。只投影以下键，无路径、标签、模型权重、segment ID 或逐分钟数组。

| 顶层键 | 精确内容 |
| --- | --- |
| version、command、status | 整数 1，所执行的命令和上表对应 status |
| result_identity | 恰 profile_id、context_sha256、manifest_sha256、manifest_byte_count，取经接纳包的精确结果 identity。run 同时核对 save 的返回值 |
| view、threshold、configuration_sha256 | 对应 context.view、result.threshold、context.configuration_sha256。阈值为原有限 float，配置摘要指准备配置 |
| input_references | 恰 raw、prepared，分别为 context.raw_identity、context.prepared_identity 的完整四字段投影 |
| counts | 恰 total、scored、training、calibration、preprocessing_fit，分别为总轴长度、scored_mask 真值数和三个保存索引 train/calibration/preprocessing_fit 的长度，均为整数 |
| checks | 恰 internal_consistency=MATCHED、saved_score_q99=MATCHED、input_pair_binding、source_authentication=NOT_AUTHENTICATED、model_execution=NOT_AUTHENTICATED。input_pair_binding 在 run/verify 为 MATCHED，在 inspect 为 NOT_PERFORMED |
| operations | 恰 model_fit_score，在 run 为 PERFORMED，在 inspect/verify 为 NOT_PERFORMED，仅表示本次调用 |

每个 identity 中 profile_id 使用其既有原始/准备/结果 profile，两个 SHA 为 64 位小写十六进制，manifest_byte_count 为准确正整数。内部 load_report 的 structure 与 byte_integrity 均 MATCHED 才能投影 internal_consistency=MATCHED。使用已验证包限定字段后编码，不能将异形上游对象序列化进回执。构造/编码无效投影返回 INVALID_RESULT，合法编码超过预算返回 RESOURCE_LIMIT。

## 错误与中断

失败/KeyboardInterrupt 的退出值均 2，stderr 尽力写精确 `{"error":"CODE"}\n`，无原始异常、路径或 traceback。语义失败不输出成功信息。新命令自己的错误码为 INVALID_ARGUMENTS、INVALID_PATH_LAYOUT、INVALID_RESULT、INTERRUPTED、INTERNAL_ERROR，加上传输错误 OUTPUT_ERROR、字节预算 RESOURCE_LIMIT 和上文定义的路径错误。业务异常仅接受以下已知类型及其本类的允许码，其他 Exception、被篡改或类型不合法的 code 映射 INTERNAL_ERROR。KeyboardInterrupt 映射 INTERRUPTED。

| 异常 | 允许码 |
| --- | --- |
| ReleaseMinutePackageError，记其集合为 R | INVALID_PACKAGE_ARGUMENTS、INVALID_PACKAGE、INCOMPATIBLE_PACKAGE、RESOURCE_LIMIT、INTEGRITY_MISMATCH、INCONSISTENT_PACKAGE、INVALID_PACKAGE_PATH、INPUT_UNAVAILABLE、OUTPUT_EXISTS、PACKAGE_CHANGED、OUTPUT_ERROR |
| ReleaseInputPreparationError | R 加 INVALID_PREPARATION_CONFIG、UPSTREAM_IDENTITY_MISMATCH、NO_TRAINING_NORMAL_MINUTES、NONFINITE_FIT_STATE、DERIVATION_MISMATCH |
| ReleaseIFResultPackageError | R 加 INPUT_BINDING_MISMATCH |
| ReleaseModelInputPairError | INVALID_PAIR_ARGUMENTS、INVALID_PAIR_STRUCTURE、INCOMPATIBLE_PAIR、RESOURCE_LIMIT、UPSTREAM_IDENTITY_MISMATCH、PAIR_ALIGNMENT_MISMATCH |
| ReleaseIFError | INVALID_IF_ARGUMENTS、INVALID_IF_INPUT、RESOURCE_LIMIT、NO_TRAINING_NORMAL、NO_CALIBRATION_NORMAL、INVALID_INPUT_NUMERIC、INVALID_MODEL_SCORES、MODEL_UNAVAILABLE、MODEL_ERROR、INVALID_IF_RESULT |

stdout 单次写全部已编码 bytes 并 flush。写入数必须为精确 int 且等于字节长度，短写/写异常/flush 异常报 OUTPUT_ERROR，传输中的 KeyboardInterrupt 报 INTERRUPTED。stdout 故障时可能已写入部分甚至全部回执，stdout 不是提交标记。编码、回执或 stdout 在 save 成功后失败时，保留可独立核验的包。任何失败都保留 save 已创建的残留，无覆盖、清理、重试或恢复。stderr 本身失败仍返回 2，不追加其他诊断。main 保留宿主流所有权；模块入口复用现有 core CLI 对失败进程最终 flush 的保护习惯，最终以实际子进程退出验收。

## 验收范围

单测/集成覆盖调度、路径、回执、只读和竞争失败；真实运行证据来自 W0 冻结预算后的两个已知人工 view。W0 分别记录实际安装、有限调用、输出包、独立进程退出和保全。来源及历史执行认证、系统硬配额、真实模型效果都超出本接口证据范围。
