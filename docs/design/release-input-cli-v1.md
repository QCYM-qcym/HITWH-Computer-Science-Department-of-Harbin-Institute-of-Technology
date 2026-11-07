# 发布记录准备输入 CLI v1

日期：2026-11-07，Asia/Shanghai。状态：LOCAL_ENGINEERING_ACCEPTED，发布PENDING_DESKTOP，新CI NOT_RUN。本文按实际源码、独立运行复核和主控接受记录描述行为；不是新的研究协议或真实运行批准。

实现：[release_input_cli.py](../../src/core/traffic_anomaly/release_input_cli.py)。依赖[准备包规范](release-input-package-v1.md)与[原始分钟包规范](release-minute-package-v1.md)；使用及结果见[指南](../guides/release-input-cli.md)、[验证记录](../research/2026-11-07-release-input-cli-verification.json)、[实施记录](../superpowers/plans/2026-11-07-release-input-cli.md)。

## 1. 范围与入口

本入口只包装既有raw包加载、准备、prepared保存/加载及保存参数重放，不改六个包接口、数值公式、依赖或生产134/268契约。CSV→raw CLI和只读view属于后续接缝，本批没有完成它们。

可调用入口为 `main(argv: Sequence[str] | None = None) -> int`；模块入口为 `python -m traffic_anomaly.release_input_cli`。三个命令：

```text
prepare --raw-package ABS_DIR --output NEW_ABS_DIR --epsilon POSITIVE_FINITE_FLOAT --audit-fit-policy {P_U,P_B,P_A}
inspect --prepared-package ABS_DIR
verify --raw-package ABS_DIR --prepared-package ABS_DIR
```

只接受对应参数及-h/--help，拒未知/重复选项、缩写、额外位置参数、跨命令选项及@文件参数。支持正常--name=value；含“=@”的合法目录值不因该子串被误拒。epsilon和政策无默认：epsilon先转float，拒非有限、非正值、下溢零和非法文本；政策精确为三者之一。语法错误在包I/O前拒绝。路径不resolve、不自动改写，绝对本机路径安全由原load/save执行。help输出固定文本，不读包。

## 2. 调用次序

| 命令 | 有序动作 | 成功status |
| --- | --- | --- |
| prepare | raw load→显式固定config→prepare→完整摘要编码/限额→save→确认返回身份与快照一致→stdout | SAVED |
| inspect | prepared load一次→保存字段投影及bool计数→stdout | INTERNAL_CONSISTENCY_CHECKED |
| verify | prepared load一次→raw load一次→显式verify一次→投影实际报告→stdout | MATCHED |

prepare使用上游已校验的13项列序、规则c17-release-log1p-mad-input-rules-v1、H15/H30、fit_window30、显式epsilon/政策、AUDIT_ONLY。它确实拟合预处理并计算历史；不额外verify或重开输出。没有窗口/切分/特征/容差选项，也没有real/approve开关。

inspect不调用raw loader、prepare、上游重绑定或数值变换/MAD；原load允许内部结构/资格核对，不称零计算。verify使用保存mean/scale重放，不重新估计参数，不保存、修包或失败回退。来源保持NOT_AUTHENTICATED，时间保持SOURCE_WALL_CLOCK_COMPLETION_PROXY，不认证UTC或实时可用性。

## 3. 固定成功输出

stdout一条紧凑JSON加LF，顶层精确为version=1、command、status、summary、replay。prepare/inspect的replay为null，verify只投影实际返回的报告。完整输出成功并flush才返回0；status不是任务、研究或Data Gate状态。

summary精确字段：

| 字段 | 固定结构及来源 |
| --- | --- |
| identity、upstream_identity | 各profile_id、context_sha256、manifest_sha256、manifest_byte_count，取saved及context |
| source_authentication、time_basis | 原context字符串 |
| configuration | schema_version、numeric_rules_id、windows、fit_window、epsilon、audit_fit_policy、policy_status、feature_count |
| configuration_sha256 | 保存值，不由CLI重算 |
| minute_counts | total、raw_valid、prepared_valid、common_valid、history_h15_valid、history_h30_valid；人数来自保存轴/布尔sum |
| fit | count、mask_sha256、rows_sha256；与common人数分列 |
| qualification_counts | P_U/P_B/P_A各八项保存mask的sum |
| package_checks | status、scope、byte_integrity、structure、upstream_replay、transform_history_replay、fit_parameters |

八个资格原名为train_full_history_normal、calibration_full_history_normal、validation_current_normal/attack/unknown、test_current_normal/attack/unknown。零是资格计数，不是正常误报率或攻击漏报率。摘要不包含路径、argv、段id、逐分钟标签/时间、矩阵、mean/scale或模型指标，不递归倾倒快照，不调用joined。

verify的replay精确字段为profile_id、status、scope、upstream_identity、input_identity、minute_count、fit_count、checks、numerical_tolerance。checks为byte_identity、upstream_fields、fit_selection、saved_transform、history、labels_and_masks、fit_parameters、source_authentication；tolerance为rtol、atol、reference。package_checks保持加载内部一致性语义；NOT_REESTIMATED不是prepare从未拟合的声明。verify的MATCHED也不证明参数最初由训练人口拟合。

## 4. 安全错误与完整输出

stdout/stderr单条输出各限65536个UTF-8字节，含最后LF；JSON使用ensure_ascii=False、allow_nan=False、sort_keys=True及紧凑分隔。编码与限额检查先于write；binary write须返回完整长度，随后flush。帮助为固定文本，不是JSON。

错误返回2，stderr尽力输出唯一 `{"error":"CODE"}` 加LF，不回显路径、参数或异常正文。两个release异常只透传精确str型且在[包规范](release-input-package-v1.md)A8所列16码内的code；缺失/其他类型/未知码及其他Exception均映射INTERNAL_ERROR。解析为INVALID_ARGUMENTS，摘要编码为INVALID_RESULT，超限为RESOURCE_LIMIT，输出为OUTPUT_ERROR，中断为INTERRUPTED。先检查code类型，再作集合判断；错误流本身失败不重复输出或重试。

### 模块退出期修复与限定

首轮实际断管时，main已处理输出失败，但Python退出期再次flush残留缓冲，最终OS退出120并附加错误。修复只加在模块入口：调用main后，若非零，将stdout/stderr可用文件描述符重定向至os.devnull，随后正常SystemExit。已成功flush的安全错误仍保留，不用os._exit跳过清理，也不改成功输出路径。

直接调用main不改宿主流或描述符；宿主自行负责生命周期，main返回2不是OS退出码证明。模块入口也只修复可用描述符的退出flush问题；fileno不可用或重定向失败会尽力跳过，不追加错误，不承诺任意嵌入式流、native I/O或第三方退出处理都可被控制。未全局禁用warnings。实际受测断管的退出2、唯一25字节错误流与原失败分列记录。

## 5. 文件失败与残留

prepare先编码摘要再save，但不预先抢占输出目录。已有空目录也拒绝覆盖，OUTPUT_EXISTS可能发生在人工预处理已经执行之后。保存返回身份不一致为INVALID_RESULT。保存晚期失败、输出失败或中断可留下部分包或完整可加载包；不回滚、不清理、不自动重试，不以COMPLETE存在替代本次命令成功。

物理write可能部分送达，不保证stdout或目录原子性。完整JSON与实际退出码共同判断命令结果；inspect仅核内部一致性，需数值推导检查时显式verify。重新prepare使用独立新目录，原失败证据保留。

## 6. 已验证范围

最终源码文件118项通过；独立修复4项与其重叠，不相加。首次实际运行N5退出120及109字节stderr保留；修复、复审、新冻结、新安装后的第二轮8次普通模块命令和2次受控main探针全部通过，父进程实际退出0。

普通8次未作动态动作profile；P1仅prepared_load=1，P2为prepared_load/raw_load/verify/upstream_bind/transform各1、history2，两个探针fit均0。普通prepare预期人工fit2次来自固定调用链说明，不能写成动态监测次数。新wheel64个产品文件与冻结源码一致，依赖复用既有锁定环境；未重做CSV聚合或独立数值参考。

本批仅人工工程，不改变最终Attempted、主数据采用、有限真实试点或生产迁移批准边界。S2/Data Gate BLOCKED，真实拟合、模型训练/评分/Q99和正式实验NOT_RUN。
