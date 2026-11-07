# 完整91列发布记录的原始13维分钟包设计 v1

日期：2026-11-07，Asia/Shanghai。状态：ENGINEERING_DESIGN_ACCEPTED；本公开版本登记时，实现、测试、安装往返与真实运行均NOT_RUN。主控已接受本文接口和硬上限，仅启动工程实现，不改变研究批准状态。实施步骤见[原始13维分钟包计划](../superpowers/plans/2026-11-07-release-minute-package.md)。

后续执行记录（同日）：本地实现、705通过/10跳过联合检查及安装后四例人工往返已通过独立复核；Desktop发布待恢复。上方NOT_RUN为设计登记时状态，保留历史；当前结果见[运行指南](../guides/release-minute-package.md)与[验证记录](../research/2026-11-07-release-minute-package-verification.json)。

工程基点为`c3e4396032a2af46cd282690767ae1c998255400`。本文整理自已冻结并独立审阅的设计，保留全部产品规则；公开措辞和链接调整不冒称与私有原稿具有相同文件哈希。

依据：基点中的[发布记录解析](../../src/core/traffic_anomaly/_release_csv.py)、[有界文件读取](../../src/core/traffic_anomaly/_release_file_reader.py)、[分钟聚合](../../src/core/traffic_anomaly/_release_minutes.py)、[磁盘聚合](../../src/core/traffic_anomaly/_release_disk.py)和[审计入口](../../src/core/traffic_anomaly/release_audit_cli.py)，以及已完成的独立设计与存取边界审阅。设计阶段没有读取真实CSV/ZIP/流量、旧模型或产物载荷，没有新聚合、预处理或训练。

## 1. 推荐范围和两个方案

推荐新增两个专用小模块：`release_minute_contract.py`负责纯结构/内部关系与字节编码，`release_minute_package.py`负责固定五文件的保存/加载。W1与W2可按文件边界实现，先冻结W1精确接口和常量再完成W2联合验收；允许W2先写mock边界测试，不宣称联合通过。

另一方案是单模块混合纯函数和I/O，可少一个文件，但复杂守恒与文件替换边界会互相干扰，也不利于现有W1/W2分工。因此不推荐。不新建通用“安全文件框架”，不复制整份candidate或audit CLI，也不重构它们来服务本包。

本批只把**已经完成的ReleaseMinuteResult**和明确segments保存后重开。生成链为既有`_aggregate_release_files(...).minutes`→新save接口；小型内存参考结果也可进入同一纯契约。原聚合返回前已关闭源并清理scratch（`_release_disk.py:521`以后），聚合失败或清理失败就没有保存调用。新包本身不聚合、不读CSV、不设置源查找路径。

不提供新CLI、HTTP、网页、导出ZIP、源重放命令或恢复命令；不调用旧candidate模型/预处理入口、不产生26维、H15/H30资格、共同有效掩码、校准或指标。保持所有三种审计政策，没有selected_policy。不能将此包称作“已就绪的模型输入”。

## 2. 可信范围与命名

固定新格式profile：`c17-release-minute-package-v1`；内部原始来源schema仍为`c17-release-91-v1`。协议版本固定为`c17-release-raw13-rules-v1`。这些是本批已接受的新包标识，不改旧candidate profile或生产契约。

- `source_authentication = NOT_AUTHENTICATED`。
- `time_basis = SOURCE_WALL_CLOCK_COMPLETION_PROXY`。保存无时区源钟面，绝不加Z/UTC/本地时区。
- 加载检查范围固定`PACKAGE_INTERNAL_CONSISTENCY_ONLY`，源重放、解析执行证明、聚合执行证明、采集完整性均`NOT_PERFORMED/NOT_ESTABLISHED`。
- **不设置evidence_kind=SYNTHETIC_ONLY，也不设置REAL或APPROVED。** 本批实测是否人工由外部验收记录说明。任意形状合法的手工对象也可能通过纯契约，dataclass或冻结类型不是解析执行凭证。
- 本地SHA绑定“此次包内字节”，不能认证作者、发布来源、原始标签正确性或实际导出时间。全包自洽重写且重算全部SHA可形成另一个包，加载器不能据此辨识伪造。
- 文件含分钟时间及三政策描述，属于本地运行产物。仅设计和脱敏验收摘要公开，包、原源和设备截图不进Git。

## 3. 最小接口与冻结结果

以下为冻结接口；公开计划登记时尚未实现：

```text
# release_minute_contract.py；无文件I/O
encode_release_minute_package(
    minutes: ReleaseMinuteResult,
    segments: tuple[ReleaseSegment, ...],
) -> tuple[tuple[str, bytes], ...]

decode_release_minute_package(
    members: dict[str, bytes],
) -> ReleaseMinutePackage

# release_minute_package.py；只存取固定直属成员
save_release_minute_package(
    minutes: ReleaseMinuteResult,
    segments: tuple[ReleaseSegment, ...],
    output_directory: Path,
) -> ReleaseMinutePackageIdentity

load_release_minute_package(directory: Path) -> ReleaseMinutePackage
```

`encode`输出恰好五对固定文件名与bytes，顺序见第4节；结果无可变字典/列表别名。`decode`只接受精确内置dict（不接受自定义Mapping或dict子类）、精确五个str键及精确bytes值，先核键集合/字节预算再解析；校验后重建深度不可变的原始result和segments。不调用任意Mapping迭代器来探测成员，不返回可修改的原解析字典，不在属性读取时重新开文件。

`ReleaseMinutePackageIdentity`为冻结值，字段恰为`profile_id: str`、`context_sha256: str`、`manifest_sha256: str`、`manifest_byte_count: int`。两个sha256字段为精确64位小写hex；byte_count为实际manifest字节长度的精确int（含LF、拒绝bool），不是manifest原bytes。manifest的实际SHA就是可搬迁的包身份，没有随机run_id、时间戳、绝对路径或机器标识。

`ReleaseMinutePackage`为冻结值，字段恰为`identity`、`minutes`、`segments`、`scope`。scope固定上述内部一致性范围，不取名VerifiedCandidate、不加trusted标志。输入/解码过程中严格核所有tuple/dataclass/scalar，最后创建新tuple和固定字段对象；不保留调用者可变容器。

W1内部使用同一套关系校验服务encode/decode，不复制两套规则。W2不重新实现政策、数值或守恒判断。save先完成全部纯校验/编码/字节预算，再独占建目录；成功后返回其实际写入且回读核对的manifest身份。load只把一次读取所得bytes交给decode，不能“先验证一路字节，再重新开路径返回另一路内容”。

模块导入不下载、训练、加载权重或初始化GPU。复用已有ReleaseMinuteResult/Segment及常量会沿现有依赖导入NumPy，但不得新增Torch/sklearn/joblib或旧模型入口依赖；不为消除既有NumPy依赖而重构本批范围外模块。

## 4. 固定五文件与无循环摘要关系

固定写入顺序：`minutes.json`、`labels.json`、`diagnostics.json`、`manifest.json`、`COMPLETE.json`。只能是五个直属普通文件，没有子目录、外部路径引用、任意扩展成员或SQLite文件。manifest中的名字只能是协议常量，不能用于拼接任意路径。

统一canonical编码C(x)：UTF-8严格编码、`ensure_ascii=False`、`sort_keys=True`、紧凑分隔符、禁非有限数，末尾恰一个LF。各文件解码后必须与C(对象)字节相等；拒绝BOM、尾随多文档、额外空白/非canonical数字、重复键。大小与摘要均针对含LF的实际字节。

摘要关系：`context_sha256 = SHA256(C(manifest.context))`；三个数据文件都保存同一context_sha256。manifest绑定三个数据文件各自的实际SHA/字节；COMPLETE绑定manifest的实际SHA/字节。无自引用hash。每个文档都必须是精确键集合，所有嵌套对象也拒绝未知/缺失/重复键。

### manifest.json

精确顶层键：

```text
schema_version: int = 1
profile_id: str = c17-release-minute-package-v1
context_sha256: lowercase_hex64
context: Context
members: {
  minutes.json: {byte_count: int, sha256: lowercase_hex64},
  labels.json: {byte_count: int, sha256: lowercase_hex64},
  diagnostics.json: {byte_count: int, sha256: lowercase_hex64}
}
```

Context精确键：`source_schema_id`、`source_authentication`、`time_basis`、`sources`、`segments`、`minute_count`、`protocol`。

- sources：有顺序的1—5项，项恰为`ordinal`（0开始连续）、`byte_count`（正整数）、`sha256`。对应result.source_bytes/source_sha256同一位置；不排序、不去重。不同文件内容相同可有相同SHA，不能用内容相同推断同一物理文件，也不因相同SHA静默删一项。包不存原文件路径/名字；当前ReleaseMinuteResult不保留每源行数，所以本版不虚构per-source logical_rows。
- segments：有顺序的1—7项，项恰为`ordinal`、`id`、`role`、`start`、`end`。ordinal连续；id唯一、1—128 Unicode字符，禁止NUL、C0控制、DEL及孤立代理项；UTF-8可编码。id只是逻辑名，绝不能当路径。role仅train/validation/calibration/test，非降序；start<end、段不重叠，后段start≥前段end，允许缺口及同role多个段。时间精确为`YYYY-MM-DDTHH:MM:00`，无偏移/时区，合法公历。
- minute_count：1—10000，等于各`[start,end)`整分钟长度之和；不补未登记段之间缺口。
- protocol：第5节的固定完整对象，不接受调用方自由配置。

### minutes.json（不含标签）

精确键：`schema_version`、`profile_id`、`context_sha256`、`timestamps`、`segment_ordinals`、`source_valid`、`values`。

前三项固定；其余长度均N。timestamps为每段start起每60秒一项至end前的完整轴，精确到整分钟；segment_ordinals逐项对应登记段；source_valid为精确bool；values为N×13。有效行是13个有限非负float，无效行恰好13个null，不允许部分null、NaN、Infinity或0占位。

段id和role不在每行重复存储，加载时按已校验ordinal重建，与result.segment_ids/roles逐项相同。没有label/selected_policy/history/normalized/scored字段。

### labels.json（只存三政策描述，不是最终政策批准）

精确键：`schema_version`、`profile_id`、`context_sha256`、`label_kinds`、`bucket_label_kind_counts`、`bucket_label_anomaly_counts`、`definite_attack_present`、`attempted_present`、`global_label_kind_counts`、`global_label_anomaly_counts`。

- label_kinds：N×3，依P_U/P_B/P_A，每值normal/attack/unknown。
- bucket_label_kind_counts：N×3×3，政策顺序相同，最后维度normal/attack/unknown；统计桶内**全部分配记录，包括被排除的记录**，不是可评分分钟分母。
- bucket_label_anomaly_counts：N×3，依unknown_label/unknown_attempted_category/label_category_conflict，精确非负整数。
- definite_attack_present与attempted_present：N个精确bool，保留源描述标志，不能拿它们覆盖label_kinds。
- global_label_kind_counts：3×3，全源记录含区间外/无法落桶；global_label_anomaly_counts：3项同上固定顺序。

不保存任意原标签文字、IP、Flow ID或逐记录标签。本包是当前聚合结果的持久化，不宣称替代原CSV原标签审计证据；原文件与原审计仍独立保留。

### diagnostics.json

精确键：`schema_version`、`profile_id`、`context_sha256`、`global`、`buckets`。

global精确键：`raw_records`、`eligible_records`、`excluded_records`、`outside_records`、`unplaced_invalid_rows`、`duplicate_groups`、`reason_counts`、`raw_protocol_counts`、`eligible_protocol_counts`。

buckets：N项，每项精确键`raw_records`、`eligible_records`、`excluded_records`、`reason_counts`、`raw_protocol_counts`、`eligible_protocol_counts`、`unused_field_issue_records`。桶的标签统计/标志已放labels文件，重建ReleaseBucketCounts时按同一索引合并。

reason_counts为13个整数数组，raw_protocol_counts为5项、eligible_protocol_counts为4项；顺序由protocol声明并严格等于固定v1常量。所有记录计数为0—2500000的精确int，bool不算int。`empty_unconfirmed`计桶，原因可以重叠，不能把原因求和等同排除记录数。不得新增global unused计数，现有ReleaseMinuteResult没有该字段。

### COMPLETE.json

精确键和值：`schema_version=1`、`profile_id=c17-release-minute-package-v1`、`status=COMPLETE`、`manifest={byte_count:int,sha256:hex64}`。无时间戳、路径、源认证或调用成功布尔值。

## 5. 固定协议对象：绑定“如何解释”，不证明“执行过”

protocol精确键及v1值如下。W1固定为只读常量，以当前实现常量/明确语义为依据；测试另存小型期望协议fixture防止无意漂移。未来语义变化须新protocol版本，不能只放宽加载v1。

| 键 | 固定v1值 |
|---|---|
| profile_id | c17-release-raw13-rules-v1 |
| header | 当前`_release_csv.EXPECTED_HEADER`完整91列有序字符串数组，完全相等 |
| feature_names | 下列固定13项顺序，完全相等 |
| policies | [P_U,P_B,P_A] |
| label_kind_order | [normal,attack,unknown] |
| reason_order | 当前REASON_CODES的13项，见下 |
| raw_protocol_order | [tcp,udp,known_other,unresolved,excluded_protocol] |
| eligible_protocol_order | [tcp,udp,known_other,unresolved] |
| label_anomaly_order | [unknown_label,unknown_attempted_category,label_category_conflict] |
| minute_seconds | 60 |
| minute_interval | LEFT_CLOSED_RIGHT_OPEN |
| completion_rule | SOURCE_START_PLUS_DURATION_US |
| assignment_rule | FLOOR_COMPLETION_TO_SOURCE_MINUTE |
| source_timestamp_profile | STRPTIME_YMD_HMS_FRACTION_NAIVE_V1 |
| integer_parse_profile | RELEASE_DECIMAL_NONNEGATIVE_INTEGRAL_4096_DIGITS_V1 |
| duration_max_us | 86400000000 |
| duration_output_unit | SECONDS |
| quantile_rule | LINEAR_RATIONAL_MICROSECONDS_THEN_FLOAT64 |
| duplicate_rule | EXCLUDE_ALL_FULL91_LENGTH_PREFIXED_UTF8_LEXICAL_COPIES_GLOBAL |
| cross_segment_rule | EXCLUDE_IF_START_NOT_IN_COMPLETION_SEGMENT |
| unplaced_rule | INVALIDATE_ALL_REGISTERED_MINUTES |
| empty_rule | UNCONFIRMED_INVALID_NULL_NOT_ZERO |
| minute_label_rule | INVALID_UNKNOWN_ELSE_UNKNOWN_THEN_ATTACK_THEN_NORMAL |
| protocol_codes | {tcp:[6],udp:[17],known_other:[1,2,132],unresolved:[0]} |
| other_protocol_rule | EXCLUDE_INVALID_OR_UNSUPPORTED_CODE |
| label_rules | 固定对象，定义如下 |

label_rules精确键：`profile_id=c17-release-attempted-three-policy-v1`、`normal_labels`、`attack_labels`、`attempted_labels`、`empty_categories`、`attempted_categories`、`attempted_policy_kinds`。五份词汇表与当前`_release_csv`对应完整元组值/顺序完全相等，不接受动态词汇；attempted_policy_kinds固定[unknown,normal,attack]。未知标签/未知类别/冲突的优先次序与label_anomaly_order一致，均给三政策unknown；其他已知合法记录按BENIGN/确定攻击映射。label_rules只记录当前三政策审计语义，不是用户最终选择。

feature_names固定：completed_source_record_count、fwd_packet_sum、bwd_packet_sum、fwd_source_length_sum、bwd_source_length_sum、tcp_source_record_count、udp_source_record_count、known_other_source_protocol_record_count、unresolved_source_protocol_record_count、duration_max_s、duration_median_s、duration_p95_s、no_backward_packet_source_record_count。

reason_order固定：invalid_duration、invalid_protocol、invalid_fwd_packets、invalid_bwd_packets、invalid_fwd_length、invalid_bwd_length、invalid_unsupported_protocol、invalid_timestamp、duplicate_record、cross_partition、outside_registered_minutes、unplaced_invalid_row、empty_unconfirmed。

协议字符串只选择固定解释，不执行解析或数值重放。没有独立作者版本认证、时区认证或真实导出可用性认证；不在包中放不可信“已执行聚合”标志。当前特征求和仍只保存float64物化后的数值，**不能从包恢复大于2^53前的精确整数和全部duration样本**。

## 6. 纯内部一致性检查

先验证精确字段/类型/长度/固定协议，再做下面可由已存字段成立的关系。全部检查失败整包拒绝，不丢行、不纠正数值、不自动补零。源重放不在这里发生。

### 轴、数值和有效性

1. 所有N维数组与context.minute_count一致；timestamps/segment_ordinals恰好由segments展开而来，无重复/乱序/段间补齐。解码恢复的result来源数组、feature_names、segment_ids和roles必须与context一致。
2. 有效行全部float（不接收bool或JSON整数冒充float）；有限、非负、拒绝负零；无效行全null。Python浮点→canonical JSON→浮点精确往返；不做容差改值或decimal量化。
3. `source_valid[i]`当且仅当桶13个reason计数均为0。有效桶raw=eligible>0、excluded=0。**无效桶仍可eligible>0**：全域unplaced污染和其他分配记录的排除会使整分钟无效，不能把eligible清零凑守恒。
4. 有效行value[0]=float(eligible_records)；value[5:9]分别等于四个eligible协议计数且总和等于value[0]。value[1:5]为非负整数值的有限float；不把rounding前整数重新构造为“原始精确和”。value[12]为0—eligible的整数值float，表示无反向包记录数。
5. 有效行duration三项满足0≤median≤p95≤max≤86400秒。没有duration样本时不能验证其真实分位是否正确；不能由这种边界检查写成重算分位。
6. 桶无效时三政策label_kinds均unknown；桶有效时按raw label_kind_counts的unknown优先、attack其次、normal最后推导每政策分钟标签。有效桶无排除，因此此处使用raw标签计数与现有合格集合相同；不对无效桶重新挑选“干净行”。

### 记录、原因及协议守恒

设R/E/X/O/U为全局raw/eligible/excluded/outside/unplaced，桶r/e/x为对应计数：

- R=E+X；每桶r=e+x；Σr+O+U=R；Σe=E；Σx+O+U=X。
- 每级raw_protocol_counts和为该级raw，eligible_protocol_counts和为eligible；每个eligible通道≤对应raw通道；全局eligible各通道=桶对应通道之和。全局raw各通道≥桶和，差值和=O+U。
- 全局reason[outside_registered_minutes]=O、reason[unplaced_invalid_row]=U、reason[empty_unconfirmed]=0。桶outside原因恒0；桶unplaced原因恰为U（全域传播，不受该桶r上限约束）；桶empty原因恰为int(r==0)。不要将U在各桶重复的计数加成全局被排除记录数。
- 桶invalid_timestamp和invalid_duration恒0：这两者使completion无法计算，记录进入全局U而不分配给桶。全局max(invalid_timestamp,invalid_duration)≤U≤两者之和。
- 将上面已单独处理的invalid_timestamp、invalid_duration、outside_registered_minutes、unplaced_invalid_row、empty_unconfirmed从原因集合剔除，余下八项定义为分配记录原因。桶内这八项各≤x；x>0当且仅当至少一项非零；它们可重叠，不要求和=x。全局这八项各≤X；其中cross_partition全局=桶和，另七项全局≥桶和且各自差值≤O+U。此规则不用于全域传播的U或empty标记。
- invalid_protocol与invalid_unsupported_protocol在记录级互斥；每级这两个计数之和=raw_protocol_counts[excluded_protocol]。
- duplicate_record表示全部重复副本数；0组当且仅当0重复副本，否则2×duplicate_groups≤global duplicate_record≤R，duplicate_groups≤R//2。无法由包推回每组指纹或证明全91列判重执行。
- unused_field_issue_records每桶≤r；它只是未用字段异常描述，不自动造成source_valid=false，不把它等同解析失败。

### 标签描述守恒

- 每桶每政策normal+attack+unknown=r；全局每政策同和=R。全局每项≥桶和，逐政策差值合计O+U。每级三个异常互斥计数之和≤该级raw；全局各异常≥桶和，差值总和≤O+U。
- 按当前三政策记录映射，每级满足PU.normal=PA.normal，PU.attack=PB.attack，PB.unknown=PA.unknown=sum(label_anomaly_counts)。差值T=PB.normal−PU.normal=PA.attack−PU.attack=PU.unknown−PA.unknown≥0。T是已知合法Attempted记录数，不是所有attempted_present记录数。
- r=0时两present标志false；PU.attack>0则definite_attack_present必true；T>0或unknown_attempted_category/label_category_conflict计数>0则attempted_present必true。反向不强求相等：未知/冲突记录也可能保留原definite/attempted标志，单靠已存边际计数无法完全恢复这些联合关系。
- 包不包含逐记录原标签，因此只验证这些必要内部关系，不宣称完全重建来源标签或将所有未知情况归为正常。

## 7. 固定资源上限与编码范围

本版无可放宽的调用方limits。source字节和记录数采用既有大文件聚合的硬域上界，仅约束能表达的已完成结果，**不是授权读取这些大小的数据**：源总字节≤2^31；每源>0且≤2^31；R≤2500000；N≤10000；1—5源、1—7段。

| 文件 | 实际UTF-8字节硬上限，含LF |
|---|---:|
| manifest.json | 65536 |
| minutes.json | 8388608 |
| labels.json | 8388608 |
| diagnostics.json | 8388608 |
| COMPLETE.json | 4096 |
| 五文件总和 | 20971520（20MiB） |

依据：分钟轴最长10000，timestamp固定19字符、segment ordinal单数位；数值每行13项，有限float canonical表示至多约24ASCII字节，分钟内容约数MiB。诊断每桶26个不超过7位的整数加固定键，标签每桶固定3×3/3计数及有限枚举/布尔；无原始行、任意字符串列表或无限整数。段id至多7×128字符，固定91列/13特征/标签词汇只存一次，manifest64KiB留出足够空间。W1须在纯测试中实际编码最大轴和最长字符串/数值的人工对象，给出实测字节，不能仅凭此估算声称最大配置可保存。

结构上限与字节上限同时适用；超限整包失败，不保证任意“形状合法”但编码过大的构造都可保存。编码用有限UTF-8累计器逐chunk限额，不能先生成无限字符串再只查长度。解码先限每文件和总bytes，JSON整数token最长11位（须容纳固定协议常量`duration_max_us=86400000000`），各字段仍分别检查自身数值上限，不能把11位通用解析上限当作记录数或byte_count的许可上限。浮点必须有限，拒绝重复键/非标准常量/解码和递归错误；再验证全部精确结构。不能更改全局`sys.set_int_max_str_digits`或CSV设置。

2026-11-07审查修订：初稿将整数token上限写为10位，仅考虑byte_count而遗漏11位的duration常量，导致decode会拒绝encode自己的manifest。主控明确决定改为11位，保留上述逐字段数值限制；实施时须加入固定协议自编码/解码往返及12位token拒绝的RED/GREEN用例。当前只修正设计，尚未执行这些测试。

标准库JSON解码可能在结构检查前分配对象，bytes上限不等于RSS硬配额。不要承诺20MiB内存或操作系统隔离，也不为本包新增大型流式JSON依赖。

## 8. 保存、完成标记和失败残留

1. 输入result/segments纯校验与全部五文件有界编码完成，协议/守恒/字节错误在建目录前发生。输出目录绝对路径、父目录已存在且普通；即使现存目录为空也拒绝。
2. 通过独占mkdir取得目录身份，每成员用独占`xb`；不写临时成员再rename，不接管未知实体，不覆盖任何文件。
3. 各写入阶段核目录实体和当前成员集合；写句柄`fstat`核普通实体及身份，检查实际写入长度、flush/关闭失败。关闭后验证路径仍对应原实体，按有界稳定读模式回读并与预编码bytes全等。未知成员或身份变化立即失败，不递归清理。
4. 三数据文件全部完成后写manifest；上述四文件全部已回读后最后写COMPLETE，并再次检查目录、全部成员身份和精确集合。
5. 不自动重试、不恢复、不删除失败残留、不修复半包。确定性纯校验失败不新建目录；I/O或外部修改失败可能保留空目录/部分文件/完整文件对，需要另行处置。

**完成的精确定义**：加载器能验证五个完整canonical文件、闭合成员集合、正确摘要绑定及内部关系。仅有COMPLETE文件名、status字符串或一个hash不够。COMPLETE不证明保存函数曾成功返回；写标记后最终检查/关闭/返回通道失败，仍可能留下可重开的一致包。不能要求“任何异常绝不留下可接受包”。要区分操作调用失败与磁盘快照恰好满足包协议，两者都保留真实记录。

不承诺目录原子快照、断电耐久、fsync覆盖整个文件树或恶意并发者不可规避。强杀可能留下残留；没有源聚合scratch在本包内可清理，不加入新恢复机制。

## 9. 加载、路径与替换边界

- 只接受显式绝对本机路径。拒绝NUL、`..`、UNC/设备前缀、驱动器相对、Windows单正/反斜杠root-relative、ADS、非普通文件/目录、符号链接/Windows reparse；先查词法祖先，不能先resolve后掩盖链接。单正斜杠绝对路径仅在POSIX主机按POSIX语义放行；Windows主机的`/x`仍属root-relative，不能绕过本机绝对路径要求。不同平台不互套路径语法。
- 本包所有文件额外要求`st_nlink==1`，并拒绝成员间重复dev/inode；当前旧helper没有这项，所以由包专用小函数明确实现。目录不要求nlink==1。普通复制搬迁可用，硬链接搬迁不支持；不把同内容不同实体误作hardlink。
- 有界扫描目录，看到第六个成员即拒绝；五个名字精确相等，无嵌套。先核物理大小/总量、普通实体，再按COMPLETE→manifest→minutes/labels/diagnostics顺序读，读每文件按剩余额和单文件上限取limit+1，不信manifest自报大小。
- 每次读取均在同一打开句柄做：前路径lstat/祖先检查→打开后fstat与前签名一致→有界读→同句柄fstat未变→关闭→路径身份/大小/mtime再次一致。实际payload长度必须既不超过该文件预算，又等于这些稳定签名的st_size；提前EOF或短读不得仅靠manifest自报byte_count和摘要一致而通过。最终目录实体和所有已读成员签名、成员集合再核。身份签名包含dev/inode/mode/size/mtime_ns/相关Windows attributes/nlink，目录比较用实体字段而不依赖写入中自然变化的目录mtime。
- 摘要、UTF-8/JSON解码及全部关系校验必须消费同一份已读payload；属性访问不能再读路径。拒绝读取前/中/后可观察替换、大小变化和成员插入。无法承诺阻止所有保持元数据的对抗并发，也没有跨目录/全部文件的原子时点。
- 上述读取模式参照`release_audit_cli._read_spec`，不直接import CLI的`_Output`或candidate高层。旧candidate读取只有路径前后lstat、缺句柄fstat，不应原样复制并夸大保证。此限制已由独立存取边界审阅核对。

## 10. 搬迁与一致性攻击的可检测范围

普通复制五文件到新普通目录，字节不变且通过路径/成员规则即可加载；manifest身份保持，absolute path、inode和mtime变化不影响内容身份。不要把保存时的路径/inode/mtime写进manifest要求永久相等，它们只用于当前一次I/O稳定性观察。

修改一个成员只更新它的SHA但未同步上下文/依赖文件，按摘要或跨文件关系拒绝。改源顺序或段边界且未同步三个data文件context SHA，拒绝；改轴/label/diagnostic仍须通过全部关系。若对方完整自洽修改context、所有数据、manifest和COMPLETE，内部检查可能通过，但manifest身份必不同；这不应被包装为“防伪失败”。没有外部可信的预期manifest SHA，不能认证其来源。

可由调用方另存预期manifest身份做当前结果比对，但本批不加“外部可信注册表”、签名、作者认证、旧人工fixture白名单或源重放。源顺序只是声明的逻辑输入顺序；结果无法证明原聚合实际按该顺序读过。

## 11. 错误和公开面

统一`ReleaseMinutePackageError(code)`，code限定：INVALID_PACKAGE_ARGUMENTS、INVALID_PACKAGE、INCOMPATIBLE_PACKAGE、RESOURCE_LIMIT、INTEGRITY_MISMATCH、INCONSISTENT_PACKAGE、INVALID_PACKAGE_PATH、INPUT_UNAVAILABLE、OUTPUT_EXISTS、PACKAGE_CHANGED、OUTPUT_ERROR。W1只抛结构/版本/限额/摘要/关系类别；W2处理路径/文件/输出类别，不把任意底层消息拼到公共错误。

固定安全码无路径、段ID、原标签、异常堆栈；可`raise ... from None`抑制链，但不宣称任意外部调用者的未捕获栈会自动被擦除。本批无CLI/HTTP，未来外壳必须按固定码投影，不直接回显异常。不捕获BaseException做“修复”或删除；KeyboardInterrupt等保留正常中断语义和现场。

## 12. 最小验证矩阵（全部待执行）

W1先RED后纯契约：固定完整schema、13列顺序、三政策与标签分离；最大轴/数值/UTF-8/字节边界；133或任意错误维度/重复键/未知字段/非有限/负零拒绝；未登记缺口不补轴、相邻不同段仍分开；空桶未知、全域unplaced导致所有行null且eligible不清零；协议通道互斥、记录/标签/原因关系；unknown压过attack、Attempted三向映射与原标志边界。

W2先RED后存取：已有目标、符号/reparse/硬链接、别名/子成员/额外第六成员、声明/实际大小、短写/读错误/关闭错误、各阶段实体替换、有界读取、标记损坏/缺失、失败保留不接管、普通搬迁成功。同句柄读取测试须实际验证被打开实体，不能只mock lstat而声称真实替换已测；主机不允许的操作明确skip并说明。

联合安装验收：新造小型、变值full91 CSV组只跑一次既有聚合；包含Protocol0、其他非法码、重复副本、段边界/缺口、空桶与标签异常，必要用两个小案例分开无效全域污染。保存后在独立进程从新安装加载，逐字段比现有结果及独立人工算式，不重跑210万行容量。包有界、模型导入守卫零触发，原文件/包保持，新输出独立。

负例在副本上改字段、顺序、绑定或计数并选择性重算hash，证明内部矛盾被拒绝；完整自洽重写只证明新identity而不是作者认证。新包交给现有人工candidate records/inputs/IF/AE入口应在包识别阶段拒绝，不以修改旧validator或evidence_kind使其通过。无真实载荷、拟合、训练、评分或校准。

文档应分别记录：纯契约、文件系统、安装、人工聚合往返、研究状态和Git/CI；只有包存取实测通过后才能称“full91原始分钟结果可持久化并重开”，不能称“真实13/26输入就绪”。

## 13. 已接受的工程选择、分工与风险

主控已接受以下选择，不重复要求用户批准普通实现细节：

1. 两个专用模块、固定五文件：标签物理分离，诊断独立，摘要关系无循环。
2. 总上限20MiB、每数据文件8MiB、manifest64KiB、完成标记4KiB。先以人工最大结构验证；超限须复核设计，不能自动放宽。
3. 所有文件拒绝hardlink，支持普通复制搬迁；不改旧模块规则。
4. 本批不新增CLI或源重放；通过安装后的受控人工进程验证公开Python接口。

W1独占纯契约、协议fixture和纯测试；W2独占文件存取及相应测试；W3独占独立手算fixture和消费边界测试，不新增页面。主控负责接口冻结、安装人工进程往返、独立审查和Desktop发布；W0维护设计、计划及后续证据。详细文件归属以实施计划为准。

主要风险：错误地把无效桶eligible清零；把原因计数当互斥记录计数；把全域U重复计入全局；大整数float舍入被称精确值；标签边际统计被称完整标签重放；晚期失败有完整标记却被描述成绝无完成包；路径前后相同被称读取句柄相同；hash一致被称作者/执行认证；新包被赋SYNTHETIC_ONLY后绕入旧模型。上述均已在接口/检查/验收中给出明确边界。

本设计不批准真实数据采用、最终Attempted、有限试点、生产迁移或模型运行。Data Gate仍BLOCKED；真实预处理/训练/评分/Q99和正式实验NOT_RUN。设计接受不代表实现或包存取验收通过，须按实施计划逐项取得证据。
