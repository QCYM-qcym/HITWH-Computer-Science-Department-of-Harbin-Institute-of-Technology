# 发布记录准备输入包 v1

日期：2026-11-07，Asia/Shanghai。状态：`LOCAL_ENGINEERING_ACCEPTED_PUBLICATION_PENDING_DESKTOP`。本版本描述已实现并经人工数据验收的独立 13/26 维输入准备与保存格式。发布为 `PENDING_DESKTOP`，本批远端 CI 为 `NOT_RUN`；不据此判定 Data Gate 通过。

实现：[数值准备与编解码](../../src/core/traffic_anomaly/release_inputs.py)、[固定文件存取](../../src/core/traffic_anomaly/release_input_package.py)。上游见[原始分钟包](release-minute-package-v1.md)，使用说明及实际结果见[运行指南](../guides/release-input-package.md)与[验证记录](../research/2026-11-07-release-input-package-verification.json)。

## 1. 适用范围与身份

本格式接收显式的 `ReleaseMinutePackage`，输出当前 13 维、严格过去 H15/H30 历史残差，以及各窗口独立的 26 维拼接。它不读取 CSV、不加载模型、不生成分数、阈值或指标，不隐式兼容旧 candidate 或生产 134/268 维契约。

| 项目 | 固定值 |
| --- | --- |
| 输入包 profile | `c17-release-prepared-input-package-v1` |
| 数值规则 | `c17-release-log1p-mad-input-rules-v1` |
| 重放报告 profile | `c17-release-input-replay-v1` |
| 上游包 profile | `c17-release-minute-package-v1` |
| 源 schema | `c17-release-91-v1` |
| 来源认证 | `NOT_AUTHENTICATED` |
| 时间基准 | `SOURCE_WALL_CLOCK_COMPLETION_PROXY` |
| 政策身份 | `AUDIT_ONLY` |

源时间没有已认证时区或 UTC 偏移。完成时刻仍是离线可用时间代理，不证明真实导出时刻、实时可用性或完整网络采集。包中不放 `SYNTHETIC_ONLY`、`REAL` 或 `APPROVED` 授信字段；本次人工性质由包外配方和收据记录。摘要用于绑定内容，不是作者校验和、签名或研究许可。

## 2. 特征、标签与维度

固定列序如下；直接沿用上游合法原始值及语义，不补零凑 134 维。

| 序号 | 字段 |
| ---: | --- |
| 1 | `completed_source_record_count` |
| 2 | `fwd_packet_sum` |
| 3 | `bwd_packet_sum` |
| 4 | `fwd_source_length_sum` |
| 5 | `bwd_source_length_sum` |
| 6 | `tcp_source_record_count` |
| 7 | `udp_source_record_count` |
| 8 | `known_other_source_protocol_record_count` |
| 9 | `unresolved_source_protocol_record_count` |
| 10 | `duration_max_s` |
| 11 | `duration_median_s` |
| 12 | `duration_p95_s` |
| 13 | `no_backward_packet_source_record_count` |

Protocol0 仅计入源协议未解析通道，不认证为合法物理协议，也不改变 known-other 通道。其他非法码沿上游规则拒绝。标签与矩阵分开，P_U/P_B/P_A 三种审计解释始终各自保存，不沿用 UGR 八标签语义。

`joined(15)` 或 `joined(30)` 返回当前 13 项与相应残差 13 项，形状为 N×26，不同时拼两个 H；该 H 无效时整行 26 项为 None。当前 13 项有效而历史预热不足是合法状态。joined 检查保存内容的结构后拼接，不重新计算中位数/MAD。

## 3. 公共接口

```text
# traffic_anomaly.release_inputs：纯数值与字节编解码
prepare_release_inputs(
    upstream: ReleaseMinutePackage,
    config: ReleasePreparationConfig,
) -> ReleasePreparedInputs

verify_release_input_derivation(
    upstream: ReleaseMinutePackage,
    saved: ReleasePreparedInputs,
) -> ReleaseInputReplayReport

encode_release_input_package(
    saved: ReleasePreparedInputs,
) -> tuple[tuple[str, bytes], ...]

decode_release_input_package(
    members: dict[str, bytes],
) -> ReleasePreparedInputs

# traffic_anomaly.release_input_package：固定文件 I/O
save_release_input_package(
    saved: ReleasePreparedInputs,
    output_directory: Path,
) -> ReleaseInputIdentity

load_release_input_package(directory: Path) -> ReleasePreparedInputs
```

冻结 dataclass 构造本身不认证内容。prepare/verify 先重新编码上游的已有分钟对象，核其声明 profile、context SHA、manifest SHA 与长度；不重读 CSV 或再次聚合。encode/save/verify 也重新核下游完整内容和派生身份，不相信调用者手工构造的 identity/load_report。身份不放进自身哈希载荷，报告不作为第六个包成员。

## 4. 配置和绑定规则

配置恰有八字段：`schema_version=1`、固定规则 ID、上述特征有序 tuple、`windows=(15,30)`、`fit_window=30`、`epsilon`、`audit_fit_policy`、`policy_status=AUDIT_ONLY`。所有字段显式传入；epsilon 和政策没有默认值。epsilon 必须为有限正 float，拒 int/bool，不因溢出自动增大。人工验收的 1e-6 只是该次配置，不是已验证真实参数。

上游四字段身份、完整配置及配置 SHA、段定义、分钟数、时间和来源范围都进入 context；context SHA 绑定三个数据文件。政策不同会改变配置与包身份，不允许静默替换。纯结构加载不能证明完整自洽改写的来源，原始标签文本、私人路径和机器信息不复制进准备包。

## 5. 拟合人口与数值变换

对显式政策 q，raw fit_mask 为 train 段中当前及此前连续 30 分钟均 raw 有效且 q-normal 的当前行。段/角色必须相同，相邻时间差必须 60 秒；每个合格当前行只计一次，不能把滑动窗口重复堆叠，也不能先删除攻击/未知再拼时间。

只在这些行的 raw13 上计算 float64 的 log1p，逐列拟合 mean 和总体标准差（ddof=0）。完全相同列用首个 log 值作为 mean、scale=1；其他算得零的 scale 也置 1。非有限拟合状态整次失败。空人口报 `NO_TRAINING_NORMAL_MINUTES`，不切换政策/窗口或借其他分段补样本。

保存 mean13、scale13、人数、拟合窗口/政策、fit_mask 和 fit_rows 摘要。全轴统一变换为 `(log1p(raw)-mean)/scale`。raw 无效时当前行全 None、原因 source_invalid；变换非有限时全 None、原因 nonfinite_transform。允许有限负数和正负零，不截断、不补零，不用留出段更新参数。

raw 拟合人口与最终 prepared/common/训练资格分列。历史失败可能减少最终资格，不能按事后 common 重新拟合。校准零资格允许保存准备结果，但不产生阈值或正常误报率。训练拟合使用整个已选训练人口，因此“严格过去”的历史声明以保存拟合状态为条件；修改较晚训练拟合行可能影响较早训练变换，不能把这项离线拟合性质误记为测试泄漏。

## 6. 历史、重置与共同资格

在 prepared 空间，H 窗口只取目标前 `[t-H,t)`：
`residual = (current - median(history)) / (median(abs(history-median(history))) + epsilon)`。
没有 1.4826 系数、clip 或残差再次缩放。中位数、MAD、分子、分母、结果都检查有限性。

两窗口独立维护状态。先处理段/角色边界，再防御性检查分钟缺口；prepared 无效时清空历史，从下一分钟重新预热。达到窗口资格却出现非有限历史时，该目标不进入新历史，下一次可能恢复是 i+H+1。预热期间沿用 nonfinite_history 原因不表示再次重置。合法上游段内轴完整，跨段缺口先记 boundary；单独 gap 是防御枚举，不以非法上游制造成功例。

`common_valid = prepared_valid & H15.valid & H30.valid`。不能假定 H30 有效就必然 H15 有效。测试标签不删除攻击或未知历史，不参与数值历史重置。

每政策独立保留训练/校准全历史正常资格、验证/测试当前 normal/attack/unknown，共 24 个 N 长 bool mask。准确公式见附录 A4。验证/测试三分类在对应 role∩common 内互斥并覆盖全体；未知不变正常，prepared 数值失败不覆盖原上游有效标签。这里的 common 尚不包含未来模型评分有效性，不是正式比较的最终分母。

## 7. 五文件保存与硬上限

| 成员（写入顺序） | 字节硬上限，含末尾 LF |
| --- | ---: |
| preprocess.json | 16384 |
| inputs.json | 16777216 |
| labels.json | 2097152 |
| manifest.json | 65536 |
| COMPLETE.json | 4096 |
| 合计 | 20971520 |

N≤10000、段数≤7，来源与上游其他限额不变。inputs 只保存当前13与两份残差13，不冗余保存 joined。inputs 绑定 preprocess，manifest 绑定 context 和三个数据成员，COMPLETE 最后绑定 manifest。没有分数、指标、权重或原 CSV。精确字段及中间摘要预算见附录 A3/A5。

存取接受绝对本机路径，拒路径上跳、UNC/设备路径、ADS、链接/reparse 和多硬链接。加载按 COMPLETE、manifest、三个数据成员有界读取，以同句柄和前后目录/文件签名检查可观察变化。加载不是跨文件原子快照。

保存先完成编码与验证，再独占新目录，以 xb 写成员、检查短写、关闭与回读，并在最后写 COMPLETE；不覆盖已有目录，不自动重试、回滚或清理。异常可能留下未完成目录，也可能发生在包已完整可加载后。完成标记不等于本次调用成功，不承诺 fsync 断电耐久、跨文件原子性或恶意并发隔离。

A9 三个人工最大形状已在明确修订的 360 秒监督预算下编码/解码通过；这是内存字节尺寸验证，不是磁盘包或原 120 秒性能保证。原三次超时与预算修订单列在验证记录。

## 8. 加载、重放和结论边界

普通 decode/load 检查字节、形状、内部关系、资格状态机及 mask；不重新变换或计算 median/MAD，但不是“零计算”。返回 `SAVED_INPUT_INTERNAL_CONSISTENCY_ONLY`，上游和变换历史重放为 NOT_PERFORMED，拟合参数为 NOT_REESTIMATED。

显式 verify 对给定上游、保存 mean/scale、变换/历史/标签/资格逐项重放，返回 `SAVED_PARAMETER_DERIVATION_REPLAY`。它不重新估计 mean/scale，不能证明参数最初确由训练人口拟合。有限数值按附录 A7 的固定方向容差比较；身份、配置、标签、mask、人数、原因与 None 位置精确比较。完全自洽改写可能通过且身份不同，不宣称防伪。

本批已接受的结论限于人工 raw 包的 13/26 维准备、保存、独立重开和保存参数推导核验。最终 Attempted 政策、主数据采用、真实试点、真实预处理拟合/模型运行和生产迁移仍待明确决定；S2/Data Gate 为 BLOCKED，真实训练、评分、Q99 校准、正式实验为 NOT_RUN。包接口验收不等同于 CLI、HTTP、页面或真实闭环验收。

## 附录 A：规范性字段与检查

以下字段、类型和数组次序与本地接受版本一致。缺失/未知键均拒绝；不提供任意 metadata 扩展。固定值域不等于构造默认参数。

### A1. 常量、标量与数组顺序

- P=`c17-release-prepared-input-package-v1`；R=`c17-release-log1p-mad-input-rules-v1`；V=`c17-release-input-replay-v1`。
- raw profile固定`c17-release-minute-package-v1`，源schema固定`c17-release-91-v1`。
- F为上游已冻结的13项特征名完整有序tuple，按本文第2节逐项相同，禁止重排/标签列。POLS=(P_U,P_B,P_A)，KINDS=(normal,attack,unknown)，ROLES=(train,validation,calibration,test)，WINS=(15,30)。JSON对象键排序不替代这些数组列顺序。
- N精确int，1≤N≤10000；S精确int，1≤S≤7；K为fit人数，1≤K≤N。index为0≤i<N；segment ordinal为0≤j<S。bool不算int，所有公开值对象的容器必须为精确tuple，拒可变列表与自定义容器；JSON文档的数组只在decode后转tuple。
- SHA精确64位小写hex；MemberRef恰为`{byte_count:int,sha256:SHA}`。计数为正，且≤对应成员/中间对象硬限。两个身份类型恰有profile_id、context_sha256、manifest_sha256、manifest_byte_count，前三者按对应固定profile及SHA约束，后者1..65536。
- epsilon、scale各项为精确内置float、有限且>0，拒int/bool/负零；mean为精确有限float。本版不以结构检查认证mean来自log1p，因此不增加未经重估支持的取值域推断。prepared/residual为精确有限float，可负、可±0；无效行只能全13个None。fitrows的raw13遵上游非负、拒负零与语义规则，不接收JSON整数冒充float。
- 时间为合法公历、无tzinfo、second=microsecond=0的精确datetime；JSON恰`YYYY-MM-DDTHH:MM:00`，无Z、offset或缩写，往返不丢信息。段id为1..128 Unicode字符，禁止NUL、C0、DEL及孤立代理；段id唯一，段start<end，不重叠且时间非降、role非降。轴只展开各登记段[start,end)，段间不补齐，N为长度和。
- PreparedReason=`None | source_invalid | nonfinite_transform`；HistoryReason=`None | warmup | boundary | gap | invalid_input | nonfinite_history`。None在JSON为null，不能写字符串"null"。

JSON数字解析：整数token仅允许无符号1..8位ASCII数字，随后执行上述逐字段范围；负整数token（包括-0）拒绝，不能先转float。固定窗口/版本也按精确int检查。8位可容纳20MiB/16MiB字节数，**本格式不复制raw source_byte_count或duration_max_us**。浮点token最多32 ASCII字符，解析后须finite；最终canonical回编码精确相等，因此额外小数位、1e0代替1.0等非canonical字节仍拒绝。严禁NaN/Infinity、重复键、BOM、多文档、非法UTF-8、未知键；解码/递归/数值异常投影固定错误码，不改全局JSON/整数限制。

### A2. 精确内存值类型

以下均为`@dataclass(frozen=True, slots=True)`的精确类型；注解的tuple长度在公共操作与codec时严格检查，dataclass构造本身不执行这些检查。表中等号表示固定值域，不表示Python构造默认值：所有字段显式传入，尤其epsilon与audit_fit_policy没有默认。公开构造器不认证内容，encode/save/verify仍做完整复核。JSON字段映射以A3为唯一依据。

| 类型 | 全部字段（顺序固定） |
|---|---|
| ReleasePreparationConfig | schema_version:int=1, numeric_rules_id:str=R, feature_names:tuple[str,...]=F, windows:tuple[int,...]=(15,30), fit_window:int=30, epsilon:float, audit_fit_policy:str∈POLS, policy_status:str=AUDIT_ONLY |
| ReleaseInputIdentity | profile_id:str=P, context_sha256:SHA, manifest_sha256:SHA, manifest_byte_count:int |
| ReleaseInputContext | profile_id:str=P, source_schema_id:str=c17-release-91-v1, source_authentication:str=NOT_AUTHENTICATED, time_basis:str=SOURCE_WALL_CLOCK_COMPLETION_PROXY, upstream:ReleaseMinutePackageIdentity, configuration:ReleasePreparationConfig, configuration_sha256:SHA, segments:tuple[ReleaseSegment,...]长度S, minute_count:int=N |
| ReleasePreprocessState | mean:tuple[float,...]长度13, scale:tuple[float,...]长度13, n_samples_seen:int=K, fit_window:int=30, audit_fit_policy:str, fit_mask_sha256:SHA, fit_rows_sha256:SHA |
| ReleasePreparedHistory | window:int∈WINS, residual:tuple[tuple[float或None,...],...]为N×13, valid:tuple[bool,...]长度N, invalid_reason:tuple[HistoryReason,...]长度N |
| ReleasePreparedMinutes | timestamps:tuple[datetime,...]长度N, segment_ordinals:tuple[int,...]长度N, raw_valid:tuple[bool,...]长度N, current_values:N×13的tuple, prepared_valid:tuple[bool,...]长度N, prepared_reason:tuple[PreparedReason,...]长度N, histories:tuple[ReleasePreparedHistory,ReleasePreparedHistory]依15/30, common_valid:tuple[bool,...]长度N |
| ReleasePolicyQualification | policy:str∈POLS，随后为A4列出的8个tuple[bool,...]字段，每个长度N |
| ReleaseInputLabels | policies:tuple[str,...]=POLS, label_kinds:tuple[tuple[str,str,str],...]为N×3，fit_mask:tuple[bool,...]长度N, fit_indices:tuple[int,...]长度K, qualification_masks:tuple[ReleasePolicyQualification,...]长度3依POLS |
| ReleaseInputLoadReport | profile_id:str=P, status:str=INTERNAL_CONSISTENCY_CHECKED, scope:str=SAVED_INPUT_INTERNAL_CONSISTENCY_ONLY, identity:ReleaseInputIdentity, byte_integrity:str=CHECKED, structure:str=CHECKED, upstream_replay:str=NOT_PERFORMED, transform_history_replay:str=NOT_PERFORMED, fit_parameters:str=NOT_REESTIMATED, source_authentication:str=NOT_AUTHENTICATED |
| ReleasePreparedInputs | identity:ReleaseInputIdentity, context:ReleaseInputContext, preprocessing:ReleasePreprocessState, minutes:ReleasePreparedMinutes, labels:ReleaseInputLabels, load_report:ReleaseInputLoadReport |

`ReleaseSegment`复用上游冻结类型的id/role/start/end四字段。context与labels的JSON顺序用ordinal/固定策略顺序显式恢复，不按字典插入顺序解释。labels类型的`policy`只映射为JSON对象键，不重复写入其8字段对象。

prepare、decode和load返回相同快照形状；load_report.identity必须等于顶层identity，其状态只描述canonical内容与内部一致性，不是实际磁盘写入完成或来源证明。load_report不属于五文件载荷，不能借重写report字串升级认证。joined(H)只接受精确int15/30，返回新tuple的N×26；该H.valid为false时整26为None，否则为current13接residual13。

### A3. 五文件精确键与映射

公共envelope为`schema_version:int=1, profile_id:str=P, context_sha256:SHA`，以下所说“加”指与这三键的精确并集，不允许其他键。

1. **preprocess.json**：envelope加`configuration_sha256:SHA`、`state:StateObject`。StateObject恰A2 ReleasePreprocessState的7键；mean/scale是13个float的数组，其他按A1。fit_window和audit_fit_policy必须分别等于context.configuration相应值，n_samples_seen=labels.fit_indices长度=fit_mask真值数；fit_mask_sha依A5重算。
2. **inputs.json**：envelope加`preprocess:MemberRef`、`timestamps`、`segment_ordinals`、`raw_valid`、`current_values`、`prepared_valid`、`prepared_reason`、`histories`、`common_valid`。数组按A2映射；histories对象恰字符串键"15"和"30"，每个值恰`window,residual,valid,invalid_reason`四键，window必须与所属字符串键相等。无joined字段、无raw_values、无labels/fit mask。
3. **labels.json**：envelope加`policies`、`label_kinds`、`fit_mask`、`fit_indices`、`qualification_masks`。policies数组精确POLS，label_kinds的列按POLS；qualification_masks对象恰POLS三个键，各值恰A4的8键，数组长度N。没有任意全轴current三分类的冗余mask，也没有原始标签文本或diagnostics副本。
4. **manifest.json**：恰`schema_version:int=1,profile_id:str=P,context_sha256:SHA,context:ContextObject,members:MembersObject`。ContextObject恰A2 context的9键；configuration按Config精确8键；segments JSON项恰`ordinal,id,role,start,end`（ordinal0开始连续），其余按A1/A2。members恰preprocess.json、inputs.json、labels.json三个键，每项MemberRef。其引用的大小/SHA必须为实际字节。context.configuration_sha256必须等于A5配置摘要。
5. **COMPLETE.json**：恰`schema_version:int=1,profile_id:str=P,status:str=COMPLETE,manifest:MemberRef`；该引用必须等于实际manifest字节。

五文件写序preprocess→inputs→labels→manifest→COMPLETE，读序COMPLETE→manifest→preprocess→inputs→labels。三数据envelope.context_sha256与manifest.context_sha256必须同为SHA256(C(ContextObject))；inputs.preprocess必须等于实际preprocess字节的MemberRef；preprocess.configuration_sha256与context值相等。配置里的R/F/WINS/fit_window/policy_status精确固定，不额外嵌入raw的91列完整协议。

身份构造不递归：私有逻辑内容encoder先验证context/state/minutes/labels并生成三成员、manifest、COMPLETE，返回五成员及派生identity；这些载荷不包含ReleasePreparedInputs.identity或load_report。prepare最后附上identity/report；公开encode/save/verify将调用者声明的identity/report与派生值核对，拒placeholder身份。

### A4. fit与全部标签资格mask

定义`E_H(valid,normal)[i]`：当前及前H行都位于同一段/角色、相邻时差60秒，全部valid且全部normal；否则false。它是完整轴的滑动资格，不因非正常标签清空数值历史，也不因历史nonfinite事件重置；后者由common另外约束。

fit_mask精确等于`role==train AND E_30(raw_valid,label[q]==normal)`，q=context.configuration.audit_fit_policy。fit_indices为按轴严格递增的所有真值索引，不能自行排序/去重修正输入；K须≥1。

每政策p恰8键，内存字段及JSON语义顺序如下：

1. train_full_history_normal = `train AND common AND E_30(prepared_valid,label[p]==normal)`。
2. calibration_full_history_normal = `calibration AND common AND E_30(prepared_valid,label[p]==normal)`。
3. validation_current_normal = `validation AND common AND label[p]==normal`。
4. validation_current_attack = `validation AND common AND label[p]==attack`。
5. validation_current_unknown = `validation AND common AND label[p]==unknown`。
6. test_current_normal = `test AND common AND label[p]==normal`。
7. test_current_attack = `test AND common AND label[p]==attack`。
8. test_current_unknown = `test AND common AND label[p]==unknown`。

合计24个N长bool数组。validation/test的三分类在各自role∩common上互斥且并集全覆盖；train/calibration只存正常资格，不虚构模型选参或评价分母。raw_valid=false的原三政策label_kinds必须全unknown；prepared数值失败不得覆盖raw仍有效的原标签。P_U/P_B/P_A的分钟标签先作为上游描述，纯load不从缺少的逐记录边际数据推导额外政策关系；显式verify逐项与上游比较。

### A5. canonical摘要输入及中间限额

C(x)固定为严格UTF-8、ensure_ascii=False、sort_keys=True、separators=(逗号,冒号)、allow_nan=False、末尾恰一LF；文件解析后必须C(parsed)逐字节等于原payload。严格float类型意味着0.0不能编码成整数0；保留负零。独立编码流逐chunk计预算，禁止先构造无界文本后才检查。中间JSON也遵同样规则。

| 摘要 | 唯一字节对象 | 含LF硬上限 |
|---|---|---:|
| configuration_sha256 | C(ConfigObject)，恰A2 Config的8键 | 16384 |
| context_sha256 | C(ContextObject)，恰A3 context的9键 | 65536 |
| fit_mask_sha256 | C({schema_version:1,minute_count:N,mask:[N个精确bool]})，恰3键 | 131072 |
| fit_rows_sha256 | C({schema_version:1,rows:[Row...]})，恰2键；Row恰index:int、timestamp:规范分钟串、values:13个raw精确float，按fit_indices顺序 | 8388608 |

fitmask与fitrows**不包含整个上游身份、配置/context SHA、全部labels或held-out行**。其归属通过持有摘要的preprocess及context绑定。因此固定轴、仅扰动held-out值/标签时，两训练摘要可保持不变，而context/上游/整个包身份仍会变化。fitrows虽不单独存feature_names，其13列含义由固定P/R/F与state所在context约束，不能从外部传另一列序解释。

fit_rows_sha只有prepare或显式verify拿到已重新绑定的上游raw13时才能计算；纯load只核64hex形状，不称已核这些raw行内容。fitmask在labels可用，load重算其摘要与fit人数。两中间对象都是哈希输入，不额外落地为第六成员；每个先独立预算，超限RESOURCE_LIMIT，不更改全局整数设置。

### A6. 纯load必要关系与历史可达性

每个文档精确字段、类型和数域首先通过，再验同一payload摘要绑定；所有数组N对齐。timestamps与segment_ordinals必须精确等于context.segments展开结果，角色/段名由ordinal唯一派生，不允许局部缺失/乱序/补缺口。prepared_valid⇒raw_valid。prepared_valid=true时13项均finite且prepared_reason=null；false时全null，reason在raw_valid=false时恰source_invalid、raw_valid=true时恰nonfinite_transform。

两H逐行执行下列**仅资格状态机**，不计算median/MAD：初始start=0,pending=warmup；每行先boundary后gap重置。若prepared无效，h.valid=false、reason=invalid_input、residual全null，start=i+1,pending=invalid_input；若prepared有效但i-start<H，h.valid=false、reason=pending、residual全null，保持start不变；否则前缀已满足，允许两种结构结果：h.valid=true、reason=null、13项finite，或h.valid=false、reason=nonfinite_history、全null并置start=i+1,pending=nonfinite_history。

特别是预热阶段reason仍为nonfinite_history时，不再把该行当新数值失败重复重置，否则永远无法恢复。只有ready分支的nonfinite_history才触发新的start。合法段间缺口先命中boundary，完整raw轴不会产生单独gap；错误raw轴在准入/轴检查阶段拒绝，不拿非法包当gap成功例。

common逐项等于prepared_valid∩h15.valid∩h30.valid。A4所有mask从保存的轴/标签/valid重推并精确比较，fitmask非空且索引/计数/摘要完全一致。load可接受声称的ready阶段数值非有限失败，但它仅证明该诊断在状态机上可达，**不证明实际算出了溢出**；真实变换/历史原因由显式verify重算核对。

### A7. 返回报告与数值重放比较

load/prepare/decode的report按A2精确10字段；不写包、不中途把报告改为数值重放通过。verify成功才返回以下精确冻结值，任何失败抛安全错误，不返回半通过报告：

`ReleaseInputReplayReport(profile_id=V,status=MATCHED,scope=SAVED_PARAMETER_DERIVATION_REPLAY,upstream_identity:ReleaseMinutePackageIdentity,input_identity:ReleaseInputIdentity,minute_count:N,fit_count:K,checks:ReleaseReplayChecks,numerical_tolerance:ReleaseReplayTolerance)`。

ReleaseReplayChecks恰8字段：byte_identity=MATCHED、upstream_fields=MATCHED、fit_selection=MATCHED、saved_transform=MATCHED、history=MATCHED、labels_and_masks=MATCHED、fit_parameters=NOT_REESTIMATED、source_authentication=NOT_AUTHENTICATED。ReleaseReplayTolerance恰rtol:float=1e-12、atol:float=1e-12、reference:str=REPLAYED。上述报告类型是冻结dataclass，不是可变任意dict；如投影JSON也只能这组键，报告不属于五文件。

每个saved/replayed有限浮点对按固定方向检查：`abs(saved - replayed) <= 1e-12 + 1e-12 * abs(replayed)`。不使用对称math.isclose；极端差值相减溢出得到非有限差时直接视为不匹配，不靠Infinity<=Infinity放过。两边输入必须finite，None位置精确；±0可数值相等而canonical身份不同。mean/scale不重新估计；配置、epsilon、mask、reason、时间、fit索引/人数、SHA和身份均精确相等，不能套数值容差。

### A8. 固定错误类别

统一`ReleaseInputPreparationError(ValueError)`，精确code且str(error)==code。允许码恰：INVALID_PACKAGE_ARGUMENTS、INVALID_PACKAGE、INCOMPATIBLE_PACKAGE、RESOURCE_LIMIT、INTEGRITY_MISMATCH、INCONSISTENT_PACKAGE、INVALID_PACKAGE_PATH、INPUT_UNAVAILABLE、OUTPUT_EXISTS、PACKAGE_CHANGED、OUTPUT_ERROR、INVALID_PREPARATION_CONFIG、UPSTREAM_IDENTITY_MISMATCH、NO_TRAINING_NORMAL_MINUTES、NONFINITE_FIT_STATE、DERIVATION_MISMATCH。

调用参数类型错→INVALID_PACKAGE_ARGUMENTS；配置字段/域错→INVALID_PREPARATION_CONFIG；未知包/规则版本→INCOMPATIBLE_PACKAGE；JSON/字段/标量不合法→INVALID_PACKAGE；合法类型之间关系矛盾→INCONSISTENT_PACKAGE；文件摘要/下游声明identity不符→INTEGRITY_MISMATCH；上游声明identity或与saved所绑上游不符→UPSTREAM_IDENTITY_MISMATCH。预算先于解析，超限RESOURCE_LIMIT优先。fit空/非有限分别对应专有码；显式重放值/原因/mask不符→DERIVATION_MISMATCH。底层路径/读写失败按前述存取码投影，不包含路径、标签或内部异常消息，不吞KeyboardInterrupt等BaseException。
