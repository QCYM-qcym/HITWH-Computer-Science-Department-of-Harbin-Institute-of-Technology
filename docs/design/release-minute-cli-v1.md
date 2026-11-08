# 原始分钟包 CLI v1

用途：把显式登记的CSV源、分钟分段和预算交给既有聚合器，保存完整raw13分钟包。日期：2026-11-07。状态：**固定人工安装链已本地接受；Desktop发布待完成**。源码测试、新安装八例和研究阶段分别记录。

依据：[原始分钟包协议](release-minute-package-v1.md)、[输入CLI协议](release-input-cli-v1.md)、[本批验证记录](../research/2026-11-07-release-minute-cli-verification.json)。人工工程、数据供应审计和真实模型实验分别记录；S2/Data Gate BLOCKED不变。

## 接口和操作链

唯一入口为 `main(argv: Sequence[str] | None = None) -> int`，模块命令如下：

```text
python -m traffic_anomaly.release_minute_cli --spec <ABS_JSON> --scratch <NEW_ABS_DIR> --output <NEW_ABS_DIR>
```

三项均必填，无默认值。支持 `--name=value`；拒绝缩写、重复、未知选项、位置参数和@参数文件。`-h`或`--help`只可单独使用，此时不导入产品或读取路径。无下载、解压、glob、force、resume、delete、自动重试和预算回退选项。

实现依次执行：读取并检查spec → 复核源和目录观察 → 一次既有 `_aggregate_release_files` → 确认 `cleanup_status` 为精确字符串 `CLEANED` 且scratch实际不存在 → 再复核输入和目标 → 一次 `save_release_minute_package` → 校验返回身份 → 完整编码摘要 → 写出并flush。只在最后一步成功后返回0。

聚合或关闭/清理失败不能保存。CLI不预建output、不接管已有目录，也不删除失败残留。源CSV由既有reader流式消费并核长度/SHA，不先运行旧audit、预读CSV哈希或重复聚合。输入准备、变换拟合和历史计算属于独立输入CLI，不在本命令中执行。

## spec的精确结构

spec是UTF-8无BOM JSON，实际大小不超过65536字节，顶层恰为 `version`、`sources`、`segments`、`budget`。所有对象拒绝重复、未知和缺失键；拒绝多文档、非法UTF-8、浮点和非有限常量。整数token须为1至10位无符号ASCII数字，再按字段域校验，布尔值不能代替整数。

| 对象 | 字段及规则 |
| --- | --- |
| version | 精确整数1 |
| sources | 有序1至5项，每项恰 `path,bytes,sha256` |
| source.path | 非空绝对本机普通文件路径 |
| source.bytes | 精确整数1至2147483648；声明总和不得超过总源预算 |
| source.sha256 | 精确64位小写十六进制，实际内容由reader核验 |
| segments | 有序1至7项，每项恰 `id,role,start,end` |
| segment.id | 唯一，1至128个Unicode字符，拒绝C0、DEL和孤立代理字符 |
| segment.role | train、validation、calibration、test，按此顺序非降 |
| segment.start/end | 合法 `YYYY-MM-DDTHH:MM:00` 源钟面分钟，无时区/偏移；start小于end，分段有序且不重叠 |

时间段是半开区间。允许相邻同role不同id及段间缺口；仅展开登记段，不补齐缺口。调用既有轴验证，分钟总数受max_minutes约束。该格式不认证UTC或实际流导出时刻。

`budget`恰有以下五项，均须显式给出：

| 字段 | 产品可表达范围 |
| --- | --- |
| max_total_source_bytes | 1至2147483648 |
| max_rows | 1至2500000 |
| max_database_bytes | 65536至2147483648，且为4096的整数倍 |
| max_elapsed_seconds | 1至1800 |
| max_minutes | 1至10000 |

这些是配置域，不是本阶段真实执行许可。当前人工执行另受不超过2源、512行、1MiB、240分钟、数据库8MiB、聚合30秒的范围限制；计划中的新安装验收进一步固定为一源32行。数据库预算的最小可声明值65536并不要求实际数据库至少占65536字节。

spec没有epsilon、政策覆盖、模型或批准标志。13维顺序、Protocol0未解析通道及P_U/P_B/P_A审计语义沿用原始包，不补零变成134维，不认证合法物理协议，不将Attempted自动归正常。

## 路径和稳定读取

绝对本机路径先做词法检查，再逐祖先lstat检查普通实体；不通过resolve隐藏链接。拒绝父跳转、UNC/设备路径、Windows驱动器或根相对路径、ADS、symlink/reparse及非普通实体。Windows所有组件按既有raw规则拒绝保留名、尾点/尾空格，不先strip后接纳；POSIX使用本机路径规则。

scratch和output须未存在，父目录须已存在且为普通目录，二者不能相同或嵌套。判重同时检查文本布局与父实体身份、规范叶名，覆盖Windows长名/有效8.3别名及保守的大小写归一化。同一dev/inode的重复源、源与spec同实体被拒；不同普通文件具有相同内容SHA不据此去重。

spec按路径签名 → 实际打开句柄fstat → 单次最多65537字节读取 → 同句柄fstat → 关闭 → 路径和祖先复核读取。长度必须等于稳定文件大小。文件签名含实体字段、size、mtime_ns和nlink；目录仅记录稳定实体字段，避免把正常目录mtime变化当作替换。聚合前及保存前复核。它不承诺原子快照或消除检查间所有竞态；创建竞争由原存取接口独占裁决。

本机源码测试中的两项实际8.3别名通过；四项实际symlink创建因权限限制跳过，不能写作通过。reparse属性注入与实际hardlink别名检查分开记录。

## 固定结果和错误

聚合成功stdout为一条紧凑UTF-8 JSON加单LF，顶层恰九项：

| 字段 | 内容 |
| --- | --- |
| version / command / status | 1 / aggregate / SAVED |
| identity | profile_id、context_sha256、manifest_sha256、manifest_byte_count；来自save返回的精确身份类型 |
| source_authentication | NOT_AUTHENTICATED |
| time_basis | SOURCE_WALL_CLOCK_COMPLETION_PROXY |
| source_identities | 按实际reader收据顺序列ordinal、byte_count、sha256 |
| counts | source_count、minute_count、source_valid_minutes、raw_records、eligible_records、excluded_records、outside_records、unplaced_invalid_rows |
| resources | source_content_open_count、source_bytes_consumed、logical_rows、database_bytes_at_close、observed_database_high_water_bytes、cleanup_status |

不输出私人路径、命令行、段id、逐分钟标签/矩阵、内部查询计划或堆栈。完整分钟和独立标签存入五文件raw包：minutes.json、labels.json、diagnostics.json、manifest.json、COMPLETE.json。摘要不能反建完整矩阵，也不包含评价指标。

stdout/stderr各最多65536字节，含LF；先完整JSON编码、检查有限数值与大小，再检查binary write的精确整数写长和flush。编码错误为INVALID_RESULT，超限为RESOURCE_LIMIT，流错误为OUTPUT_ERROR。物理输出可能已发部分字节，不承诺原子输出。

错误形如 `{"error":"OUTPUT_EXISTS"}`；仅底层 `cleanup_failed is True` 时附 `"cleanup_failed":true`。raw包错误限既有11码；reader/disk仅接受精确ValueError、单个字符串和本地49项完整词表，转为大写。未知码、非字符串码、异常子类、自由文本和SystemExit均不直接回显。参数/配置、路径、重复源、资源、清理、中断各返回对应固定码；失败返回2。

模块入口在main非零后尝试将可用标准描述符转向空设备，再正常退出，以避免退出期重复flush。宿主调用main和成功输出不改流；不使用os._exit、不全局禁用警告。无效描述符/资源失败只能best effort，不能由源码测试推断任意宿主或第三方退出处理可靠。本raw CLI本轮N3已单独验证实际断管exit2、固定25字节错误流且无退出flush附加诊断；此结果来自本轮独立安装，不是沿用input CLI的历史结果。任意宿主/资源故障仍不在该有限保证内。

save后输出失败可能留下完整可load包；命令仍失败且保留现场。目录存在、COMPLETE存在或main返回2，分别不能代替残留包独立加载或实际OS退出证据。

## 已有证据与待执行范围

源码最终381项收集、377通过、4跳过；独审56通过是重叠切片，不相加。首次人工CSV用例在main/reader/聚合/save完成后，因测试误把DB预算下界当实际占用下界而失败；实测12288，改为检查正值且不超8388608，产品与配方未改。获准第二轮才完成全部独立加载/字面raw13断言。

源码阶段两次人工CSV消费共64行、内容打开2次、聚合2次、save2次；另12次直接构造值对象save/load不含CSV聚合。预处理fit、保存参数重放和模型均为0。新安装八例一次运行通过，父进程实际退出0；本批远端CI仍NOT_RUN。普通5例未动态profile，受控3例动作格和安装4次启动分列，准确结果见机读记录。

## 固定人工安装链的实际范围

本轮按R1、N3、L1、P1、I1、V1、N1、N2执行八例，无补跑。R1返回SAVED；N3断管返回2/OUTPUT_ERROR且保留raw-R2；L1实际raw_load两次，核R1/R2五成员相同且符合手算。P1 prepare、I1 inspect、V1 verify的summary完全相同；N1/N2分别以OUTPUT_EXISTS/INVALID_ARGUMENTS拒绝。八例自然回收，无强停、超时或清理错误。

R1实际reader摘要为32逻辑行、9294字节、content_open_count=1、32有效分钟、数据库关闭及峰值12288、CLEANED。N3 stdout不可捕获，content_open_count仅为EXPECTED_1_NOT_OBSERVED。普通路径的聚合2次、64总读取行、raw save2次和人工预处理fit1次是已审固定调用链的预期，不是全程动态动作计数；父程序另有一次CSV内容哈希读取。

受控L1仅raw_load=2；I1仅prepared_load=1；V1的prepared_load/raw_load/verify/upstream_bind/transform各1、history=2，其余动作0。三个探针有文件读写，不能称零I/O；网络/模型/动作守卫及监督均有明确Python范围，不认证OS/RSS/native隔离。

保存值经独立审查与冻结手算比对：32行raw13、32行prepared当前零向量，fit索引[30,31]、人口2、13项scale均1，H15有效17、H30/common有效2，预热保留null/warmup。三政策训练完整历史正常资格各2，其余21资格计数均0。包只有人工训练段；没有校准Q99或评价，零校准资格不等于FPR=0。

65份安装产品与66份复制源有真实前后保持证据；另外7份生成metadata只有当前集合检查，不称历史字节保持。20个既有JSON包共100成员保持。本链本地接受不涵盖后继view、真实载荷、模型、研究协议或发布。后继view已放行分项开发，整批接受与页面验收尚未取得，不能预填通过。本链绑定冻结时的输入CLI源码；后续view公共摘要抽取属于新代码，不能用旧安装接受覆盖。
