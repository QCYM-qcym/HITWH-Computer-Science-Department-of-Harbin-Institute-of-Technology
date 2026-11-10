# Release 人工 CSV 示例 v1

日期：2026-11-11。状态：W0依用户自主工程授权采用，builder check通过；源码、完整回归、14阶段新安装人工链及独立复核已接受，详见[验证记录](../research/2026-11-11-release-example-verification.json)；本批Desktop与准确新CI仍为PENDING_AT_SNAPSHOT。基线 `b588448c754dc1a53495dd6593a09675992e548a` 已经Desktop推送并核对官方远端与首页。本项不登记为最终标签、主数据或真实研究采用决定。

## 目的与取舍

使新克隆仓库或安装后的 core 能用一个 `create` 命令生成明确人工的 91 列 CSV、可直接供现有聚合命令消费的 spec 和小型配方说明，再显式调用既有 raw→prepare→IF→inspect/verify→serve。

考虑过直接发布测试值对象包、扩展旧 candidate demo、一键串联新训练流程。前者保留假声明源身份，第二项 artifact 不兼容，第三项引入不必要的部分成功编排。采用**只生成源文件与配置**；完整链继续使用已有命令。保存结果评价桥后置。

不下载数据，不接受外部 CSV、配方、标签或参数覆盖，不聚合、不拟合预处理、不训练／评分，不自动启动服务。本批同时窄修已发布 `release_if_result_cli.py` 的同类错误码读取中断出口，新增独立回归文件；数值计算、阈值、参数及结果格式不变。原269项基线留存，268项保持原身份，唯一既有源码差异按显式清单核验。其他旧源／测试、契约、依赖、API、134/268维和标签解析器不改。S2 / Data Gate `BLOCKED`，真实研究 `NOT_RUN`。

## 两模块公共 seam

`src/core/traffic_anomaly/release_example.py` 提供：

```python
EXAMPLE_PROFILE_ID = 'release-artificial-example-v1'
EXAMPLE_MEMBER_NAMES = ('artificial.csv', 'aggregate-spec.json', 'recipe.json')
EXAMPLE_MEMBER_BYTE_LIMITS = (
    ('artificial.csv', 1048576), ('aggregate-spec.json', 65536), ('recipe.json', 16384))
EXAMPLE_TOTAL_BYTE_LIMIT = 1130496

@dataclass(frozen=True, slots=True)
class ReleaseExample:
    profile_id: str
    members: tuple[tuple[str, bytes], ...]

class ReleaseExampleError(ValueError): ...  # safe .code
def build_release_example(*, source_csv_path: Path) -> ReleaseExample: ...
```

返回三个严格固定顺序的不可变 bytes 成员。函数调用不读写文件、查询 stat、resolve 路径、读取时间／环境配方或调用业务计算。允许标准库和既有 `_release_csv.EXPECTED_HEADER`，不依赖 `tests/` 或新资源文件。纯 builder 的 source 参数只表示未来 CSV 路径。

source_csv_path 必须为当前平台实际 `Path` 类型的绝对本机路径，basename 恰 `artificial.csv`；拒绝相对、`..`、NUL、lone surrogate、UNC，Windows沿既有本地盘／保留名／ADS语义。只做词法判断，不宣称目录存在或物理别名安全。非法参数为 `INVALID_EXAMPLE_ARGUMENTS`；超成员／总字节上限为 `RESOURCE_LIMIT`；其他构造异常安全映射 `EXAMPLE_ERROR`，KeyboardInterrupt继续传播。ReleaseExampleError只允许这三个码，未知构造码归 `EXAMPLE_ERROR`。

`src/core/traffic_anomaly/release_example_cli.py` 提供 `main(argv: Sequence[str] | None = None) -> int` 和常规模块入口，仅支持：

```text
python -m traffic_anomaly.release_example_cli create --output ABS_NEW_DIRECTORY
python -m traffic_anomaly.release_example_cli --help
```

不新增 console script、包元数据、配置层或第三产品模块。CLI只允许复用 `release_input_package._lexical / _signature / _directory` 三个路径／stat helper；builder不复用它们。不得调用任何原包 loader、固定旧成员的 `_inventory / _read / _write`、prepare、aggregate 或模型入口。

## 固定人工记录配方

无随机数。四个源钟面半开分钟段如下；CSV按段序、段内 local=0..length-1 输出，总计176条，只有一个源文件。

| id | role | start | end | 分钟／行数 |
|---|---|---|---|---:|
| artificial-train | train | 2026-01-01T00:00:00 | 2026-01-01T00:48:00 | 48 |
| artificial-validation | validation | 2026-01-01T01:00:00 | 2026-01-01T01:40:00 | 40 |
| artificial-calibration | calibration | 2026-01-01T02:00:00 | 2026-01-01T02:40:00 | 40 |
| artificial-test | test | 2026-01-01T03:00:00 | 2026-01-01T03:48:00 | 48 |

每个注册分钟有一条明确人工流，开始秒10，`Flow Duration='1000000'` 微秒，完成在本分钟秒11。不填跨段／间隔桶，不把空桶当正常，不声称生成钟面为已认证UTC。

CSV严格使用既有91列表头顺序、逗号、标准CSV最小引号、UTF-8无BOM、LF且最后恰一行终止。所有值先写为ASCII字符串：

- 默认所有91列为 `'0'`，随后覆盖以下已决定字段；未使用数值列的0为明确人工占位，不能称真实流测量值或旧134维补零。
- `id=str(global_index)`，global_index=0..175；`Flow ID=f'artificial-{global_index:04d}'`；`Src IP='ARTIFICIAL_SRC'`、`Dst IP='ARTIFICIAL_DST'` 是非捕获标识，不假称真实网络端点。
- `Timestamp` 为该分钟秒10，格式 `%Y-%m-%d %H:%M:%S.%f`，精度固定六位；时长如上。
- `p=1+local%3`；仅测试 local36/40 将 p 乘8；`b=0 if local%5==0 else 1`。`Total Fwd Packet=str(p)`、`Total Bwd packets=str(b)`、`Total Length of Fwd Packet=str(10*p)`、`Total Length of Bwd Packet=str(10*b)`；列名大小写及单复数与 `EXPECTED_HEADER` 精确一致。
- 普通 `Protocol=str((6,17,0)[local%3])`；测试 local36/40 强制 `'0'`。0始终走已有独立 unresolved/U 通道，不删除、不推断物理TCP/UDP。
- 默认 `Label='BENIGN'`、`Attempted Category='-1'`；仅测试 local36 为 `('DoS Hulk','-1')`，local40 为 `('SSH-Patator - Attempted','0')`，local44 为 `('ARTIFICIAL_UNKNOWN','-1')`。其余列保持明确人工默认。

三个特殊标签均按**当前实际parser**解释：明确攻击三政策均attack；合法Attempted按P_U/P_B/P_A为unknown/normal/attack；人工未知标签三政策均unknown。协议0包含正常、明确攻击和Attempted人工记录。训练／校准源标签全部正常；测试图样在任何模型执行之前固定，不按报警效果调整。CSV内容不认证物理合法性、官方C17来源或检测效果。

## 三个成员的内容与稳定性

aggregate-spec.json 严格为现有 raw CLI 接受的 `version=1 / sources / segments / budget`，没有新增字段。sources仅一个对象：`path=str(source_csv_path)`、`bytes=len(csv_bytes)`、`sha256=SHA256(csv_bytes)`；segments为上表精确字段。

budget固定：`max_total_source_bytes=1048576`、`max_rows=512`、`max_database_bytes=8388608`、`max_elapsed_seconds=30`、`max_minutes=240`。均为整数；SQLite预算为合法4096倍数。它们不替代外部进程／OS监督。

recipe.json 精确顶层字段：`version=1`、`profile_id`、`evidence_kind='ARTIFICIAL_ENGINEERING_EXAMPLE'`、`format_schema_id='c17-release-91-v1'`、`source_authentication='NOT_AUTHENTICATED'`、`time_basis='SOURCE_WALL_CLOCK_COMPLETION_PROXY'`、`policy_status='AUDIT_ONLY'`、`generation='FIXED_RECIPE_NO_RANDOMNESS'`、`notice='Artificial format-compatible example; not an official CICIDS2017 dataset.'`、`source`、`segments`。

source恰 `member='artificial.csv' / byte_count / sha256 / row_count=176`，计数与摘要来自构造出的精确CSV bytes；segments用上表。recipe不含绝对路径、spec哈希、实际生成时刻或个人信息。它描述配方，不是COMPLETE、签名或包加载认证。

两份JSON均 `sort_keys=True / ensure_ascii=False / allow_nan=False / separators=(',',':')`，UTF-8无BOM，末尾单LF。CSV／recipe不依赖输出目录；aggregate-spec包含实际绝对源路径，因此其bytes／SHA可随目录、平台路径拼写变化。不能声称三个文件跨目录逐字节相同。

builder的摘要先绑定待写bytes；CLI读回逐字节一致后才能报告实际写成。后续raw reader还会独立校验同一真实文件流的大小／SHA／EOF。不使用测试里的1字节／a*64假身份。

## create 的路径、保存与输出

解析接受 `--output VALUE`／`--output=VALUE`，只允许一个output；独占`-h`／`--help`返回固定UTF-8帮助＋单LF。拒绝未知／重复／缩写／位置参数、`@file`、空值、混合help、错误命令、非str token及str/bytes代替argv序列，返回 `INVALID_ARGUMENTS`；此时不做业务或路径I/O。

output按原始拼写检查既有本机路径规则；相对／`..`／UNC／NUL／Windows保留名与ADS为 `INVALID_PACKAGE_PATH`。逐级lstat祖先均须普通目录，reparse／symlink／非目录同码；缺父、访问失败或其他OSError为 `OUTPUT_ERROR`。目标已存在（文件、空目录、悬空链接均含）为 `OUTPUT_EXISTS`。预检不写探针，尽可能在builder之前拒绝。

预检后恰调用一次builder，传 `output/'artificial.csv'`；先检查返回类型／profile／三个有序唯一名称／bytes类型及所有限额，不支持异形对象；形状错 `INVALID_RESULT`、限额错 `RESOURCE_LIMIT`，尚不创建目录。不另写语义package加载器。

随后排他mkdir output，再依 EXAMPLE_MEMBER_NAMES 顺序以 `xb` 写、核写入数、flush、有界读回实际文件并精确比较。沿用普通单链接文件、目录身份与成员清单检查；文件句柄／路径身份变化或额外成员为 `PACKAGE_CHANGED`，读回内容不等为 `OUTPUT_ERROR`。不修改旧 helper。最终恰三个成员且通过读回才能生成成功回执。

竞争者在预检后先创建目标时返回 `OUTPUT_EXISTS`，不接管、不覆盖。任何失败均保留本次已创建目录及部分／完整成员，不删除、回滚、换目录或重试。recipe不是完成标记，剩余文件可被独立下游读取也不改变create失败事实。

成功退出0，stderr空，stdout唯一规范UTF-8 JSON＋LF、≤65536B，精确字段：`version=1 / command='create' / status='CREATED' / profile_id / scope='ARTIFICIAL_ENGINEERING_ONLY' / files / source_authentication / time_basis / policy_status`。files按三个固定名称投影各 `byte_count / sha256`，取读回实际bytes；其余三个声明与recipe相同。不输出绝对路径、CSV正文、完整recipe或模型指标。

失败／中断退出2，stderr尽力为 `{"error":"CODE"}\n`，不透传路径／原异常／traceback。create只接受以下精确异常类型与各自码；使用 `type(error) is T`，不按 `isinstance` 或任意 `.code` 透传，code须为精确str且在本行集合中：

| 精确类型 | 允许输出的全部code |
|---|---|
| 新CLI私有 `_CLIError(ValueError)` | `INVALID_ARGUMENTS`、`INVALID_PACKAGE_PATH`、`OUTPUT_EXISTS`、`OUTPUT_ERROR`、`INVALID_RESULT`、`RESOURCE_LIMIT`、`PACKAGE_CHANGED` |
| 新builder `ReleaseExampleError` | `INVALID_EXAMPLE_ARGUMENTS`、`RESOURCE_LIMIT`、`EXAMPLE_ERROR` |
| `release_inputs.ReleaseInputPreparationError` | `INVALID_PACKAGE_PATH`、`PACKAGE_CHANGED` |

`_CLIError`只保存内部传入code，不自动把未知码变成可接受码；builder构造器的未知码仍按前文收敛为 `EXAMPLE_ERROR`。白名单只作用于异常实例实际持有的code：未知／跨类码、子类、其他异常类型、非str或取code出错均为 `INTERNAL_ERROR`。例如 helper类的 `RESOURCE_LIMIT` 或 builder类的 `OUTPUT_EXISTS` 均不得透传。未知精确异常类型立即映射 `INTERNAL_ERROR`，不读取其code属性；允许类型的code读取若发生 `KeyboardInterrupt`，仍经main的安全中断出口返回2。普通属性读取错误保持 `INTERNAL_ERROR`。`KeyboardInterrupt`单独映射 `INTERRUPTED`；`INTERNAL_ERROR / INTERRUPTED`是main生成的终端码，不加入上述类的白名单。

三个已准许helper的实际已知范围：`_lexical`可抛 `INVALID_PACKAGE_ARGUMENTS / INVALID_PACKAGE_PATH`，`_signature`只抛 `INVALID_PACKAGE_PATH`，`_directory`经祖先／signature可抛 `INVALID_PACKAGE_PATH / PACKAGE_CHANGED`，均为精确 `ReleaseInputPreparationError`；其文件系统调用还可抛原始OSError。CLI在解析后只给 `_lexical` 精确str，故helper的 `INVALID_PACKAGE_ARGUMENTS`在此链路不成立，收到时按 `INTERNAL_ERROR`，不扩大白名单。不准借用其他包／prepare／model异常类或整个现有CLI的宽码表。

I/O边界单独生成自己的安全 `_CLIError`，不改变上表：祖先缺失／权限／其他lstat或mkdir OSError为 `OUTPUT_ERROR`；目标lstat的FileNotFoundError仅表示目标尚未存在，排他mkdir的FileExistsError为 `OUTPUT_EXISTS`；拥有目录后成员xb的FileExistsError为 `PACKAGE_CHANGED`。成员写入／flush／短写／有界读取失败、读回bytes不等及stdout写入／flush失败为 `OUTPUT_ERROR`。原始I/O调用的失败只在该调用的小边界转码，不宽泛包住builder或helper异常，不能把跨类码洗成 `OUTPUT_ERROR`。同名文件、目录／句柄身份或清单变化仍按前文 `PACKAGE_CHANGED`，已观察到不合法文件类型仍为 `INVALID_PACKAGE_PATH`。

允许部分stdout且保留产物，stdout不是提交标记；stderr失败仍返回2。main不接管宿主流，模块入口沿既有失败描述符保护；实际进程退出另验。

## 验收与后续边界

纯builder与CLI单测、真实新CSV→已有聚合／prepare磁盘集成、安装后生成和完整显式人工链分别记录。供给可作前置手算，但新recipe的实际分钟数／资格数必须由新聚合与prepare实测，不把私有A计数挪来当结果。

后续prepare示例显式P_U／epsilon1e-6，仅为工程审计例子，不写成最终研究政策。真实数据许可、来源、绝对时间、最终Attempted口径和试点协议不由此放行。没有新效果指标、模型优劣预言、点调整或按测试效果挑区间。

## 本轮接受范围

一次14阶段人工链已完成，原始CSV、raw与prepared以及两个IF结果均有实际保存和独立核对。完整Python4577通过／23跳过／1既有警告／56子测试；3次HTTP共49536字节覆盖176分钟。两个IF实际fit／score／模型Q99各2次，另18次保存分数复核分列。固定配方与阈值未按结果调整，未计算研究FPR／FNR或模型优势。

源／质量初审发现的getter中断缺口及私有快照完整绑定缺口均保留原FAIL，经失败测试窄修和差异复审后通过。相邻结果CLI只修安全错误出口，不改数值或格式；原269基线留存，268项保持，唯一旧源码差异明确登记。此前已审10文件在保全窗口关闭前归档，当前状态修订不覆盖其运行证据。
