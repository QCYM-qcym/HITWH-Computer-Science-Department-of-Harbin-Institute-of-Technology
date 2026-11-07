# 原始13维分钟包 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将已完成的完整91列发布记录聚合结果保存为有界五文件包，并独立加载回等值、深度不可变的原始13维结果。

**Architecture:** W1负责纯结构、关系校验及canonical编码；W2只负责固定成员的独占保存、稳定有界读取和残留规则。W3提供独立手算人工案例与消费边界检查；主控冻结接口、安装验收、复审和发布，W0维护记录。没有新CLI、HTTP、源重放、预处理、历史输入或模型接入。

**Tech Stack:** 现有Python 3.14、标准库dataclasses/json/hashlib/pathlib/os/stat与pytest；沿用锁定NumPy 2.5.4的既有结果类型依赖，不新增依赖，不更改pyproject、锁或生产contracts。

**Spec:** [原始13维分钟包设计 v1](../../design/release-minute-package-v1.md)。已冻结设计及更新后的实施计划均经主控接受；本公开版本仅调整发布措辞、链接和本地执行入口表示，产品接口与预算保持。执行者须读设计和本计划。

日期：2026-11-07，Asia/Shanghai。状态：**ENGINEERING_PLAN_ACCEPTED / INITIAL_EXECUTION_NOT_RUN**。本次公开登记的实施、测试、安装与业务验收步骤初始均未勾选，不将设计接受等同实现通过。主控已接受两个专用模块、固定五文件、20MiB/成员硬限、拒hardlink且支持普通复制、无CLI/源重放等工程选择；这不是用户对最终标签、真实试点、主数据或研究协议的批准。

容量展示批已通过GitHub Desktop发布，本批基点为`c3e4396032a2af46cd282690767ae1c998255400`，仍在`codex/candidate-flow-adapter`推进，不合并main。公开计划只登记新批初始状态，后续以实际测试与验收记录更新。

## 实际执行收口（2026-11-07）

Task0—6本地实现、独立复核及安装人工验收完成；实际705通过/10跳过，不与分项相加。首次构建FAILED_GUARD保留；第二次使用明确的进程内离线pip适配，并非未经适配的pip。Windows真实链接尝试保留权限跳过，不把复选框解释为所有平台分支通过。执行记录见[验收JSON](../../research/2026-11-07-release-minute-package-verification.json)。Task7公开维护和发布分别跟踪，Desktop仍待恢复，无本批新CI。

## Global Constraints

- 固定包profile `c17-release-minute-package-v1`、源schema `c17-release-91-v1`、协议 `c17-release-raw13-rules-v1`。
- 固定 `NOT_AUTHENTICATED`、`SOURCE_WALL_CLOCK_COMPLETION_PROXY`、`PACKAGE_INTERNAL_CONSISTENCY_ONLY`；无UTC认证、聚合执行认证或包内SYNTHETIC_ONLY标签。人工身份只写外部验收记录。
- 不读真实CSV/ZIP、旧模型/旧运行包，不下载、不拟合/训练/评分/校准，不构造26维或H15/H30，不修改生产134/268契约或选择Attempted政策。
- 五成员按 minutes.json、labels.json、diagnostics.json、manifest.json、COMPLETE.json 写入；所有字段/嵌套键/顺序/关系严格采用Spec§4—6。
- 每个数据文件≤8388608字节；manifest≤65536；COMPLETE≤4096；五文件合计≤20971520；均含末尾LF。没有调用方放宽参数。
- 来源1—5、段1—7、分钟1—10000、记录≤2500000、声明源总字节≤2147483648；这些是表达域，不是读取授权。
- UTF-8 canonical JSON：ensure_ascii=False、sort_keys=True、紧凑分隔符、禁非有限数、恰一LF；JSON整数token≤11位且各字段另有数值限额。duration_max_us=86400000000；不得再用10位通用上限。
- Windows与POSIX按当前主机语义检查绝对本机路径；无NUL/父跳转/UNC/设备路径/ADS/链接/reparse；普通文件st_nlink须1，目录不套nlink规则。
- 保存失败不重试、不接管、不删残留。晚期失败可能留下可被load接受的完整包；成功标记不证明save成功返回、断电耐久或跨文件原子性。
- 只在现有隔离工作区分目录并行。主控独占公共记录和Git写入；全部Commit/Push通过GitHub Desktop，不合并main，不在任务步骤运行git add/commit/push。
- 截止仍为主控当前授权的11月7日12:00，11:30后仅收尾；没有放行真实研究，Data Gate BLOCKED，真实模型及正式实验NOT_RUN。

## Review Focus

1. 内容有效但实际文件更长或读句柄被换：W2 Task3核同一payload长度等于稳定st_size，并用另一个真实同尺寸文件句柄复现，不只mock路径。
2. 有合格记录但整分钟污染：W1 Task2和W3 Task5保留eligible>0而values全null，不能清零或把全域U重复计成原记录。
3. 所有文件自洽重写：W1 Task2/W3 Task5应接受合法的新身份，仍NOT_AUTHENTICATED；只拒内部矛盾，不能承诺来源防伪。
4. 标记写完之后失败：W2 Task4保留异常及残留，单独load可能成功；不得为制造“失败无标记”而删除可疑实体。
5. 源树遮蔽安装包或后台加载源/模型：主控Task6用源码外cwd/新进程核安装来源，导入前设置模型与网络守卫；load阶段禁止重新打开人工CSV。

---

## 文件归属与交接图

| 所有者 | 新建文件 | 责任 |
|---|---|---|
| W1 | src/core/traffic_anomaly/release_minute_contract.py | 值类型、固定常量、纯encode/decode、严格语义与字节限制 |
| W1 | tests/core/test_release_minute_contract.py | 纯契约及故障变体 |
| W1 | tests/core/release_minute_package_cases.py | 仅测试用人工full91行构造、结果构造、合法变体辅助 |
| W1 | tests/fixtures/release-minute-protocol-v1.json | 独立预期完整协议对象；不从被测模块动态导出作为期望 |
| W2 | src/core/traffic_anomaly/release_minute_package.py | 固定文件load/save；不复制语义规则 |
| W2 | tests/core/test_release_minute_package.py | 文件路径、替换、短读写、关闭、搬迁、残留 |
| W3 | tests/fixtures/release-minute-hand-cases-v1.json | 独立手算小案例与完整预期计数/数值 |
| W3 | tests/core/test_release_minute_hand_cases.py | 手算期望与往返消费边界；不依赖模型 |
| 主控 | 本地测试守卫、安装/验收工具、冻结清单及独占日志，不进入公开包 | 守卫、隔离安装、实际小型验收、集成 |
| W0 | 本公开计划及docs/design/release-minute-package-v1.md；验收后docs/guides/release-minute-package.md、docs/research/2026-11-07-release-minute-package-verification.json | 脱敏说明、实际证据、研究限制 |

当前W0只公开已审设计与本计划，并补容量批本地知识库发布收尾；根README/status/ROADMAP/DECISIONS/MAINTENANCE_LOG、docs导航及本批验收记录待实际验收后由主控统一安排，不提前升级状态。无`__init__.py`重导出、无第三个通用存取框架。W1冻结接口后W2可联调；W3可先独立手算，联调须等W1/W2。三方不得互改对方文件，问题交主控统一决定。

## Task 0 — 主控：建立可执行基点与防越界记录

**Files:** 本地工程冻结清单和统一测试守卫工具，不改源码、不随包公开。

**Interfaces:** 消费主控冻结设计身份及实际已发布容量批HEAD；输出包含base_commit、Python绝对位置/版本、源码/新增文件归属、准确测试列表、人工预算、开始时间/截止、research=BLOCKED_NOT_RUN的freeze。

- [x] 核容量批已完成Desktop同步及其CI实际状态，确认无同目录写入冲突；保留旧Oct31未跟踪计划。旧自动任务10-31已删除，不恢复它。新基点以现场HEAD写入freeze。
- [x] 校验主控接受的原始设计稿与对应本地冻结身份一致；公开设计另登记其文件SHA及同义审阅关系，不把原稿SHA直接用于校验公开稿。确认新文件尚未存在或属于本批已登记进展，不能覆盖未归属工作。
- [x] 以现有`.venv/Scripts/python.exe`核Python3.14及依赖已在本地；缺依赖报告，不安装网络新包。私有测试runner在import pytest/目标模块前阻止torch/sklearn/joblib及socket网络，记录尝试、已加载模块、退出码。既有NumPy允许；不要把父进程守卫外推到无守卫子进程。
- [x] 先保存短名称的测试ID规则和原始RED/GREEN日志位置；避免把MiB载荷塞进参数ID。日志须记录collection/setup错误与行为RED的区别。

执行入口（后续各步均在当前开发工作区根运行；本公开登记不声称命令已执行）：

主控已提供本地统一测试守卫。运行前将环境变量`MINUTE_PACKAGE_TEST_RUNNER`设置为该工具的实际位置，并核对本地冻结清单中的SHA；它不属于公开软件包。此变量只是脱敏路径入口，不允许换用无守卫脚本。后续接手者须取得同一工具或在明确记录覆盖差异后重建等价守卫，不能把下列命令当成全新克隆即可运行的自包含入口。

```powershell
.venv\Scripts\python.exe -X utf8 "$env:MINUTE_PACKAGE_TEST_RUNNER" --receipt-name w1-contract-red-01 tests/core/test_release_minute_contract.py -q
```

runner要求每次提供新的短ASCII `--receipt-name`，独占保留该次日志/收据；旧名拒绝复用。它只接受显式tests/core测试目标及常用pytest选项，不配置全仓库自动扫描；每次仅运行相应新测试/必要相关切片。主控提供runner后各work复用，不自创不同守卫。

2026-11-07执行入口冻结时，统一runner仅完成AST静态检查和help，未执行测试。模型导入与网络守卫先于pytest；吞掉违规也强制非零。覆盖仅当前pytest进程，不是OS网络隔离、文件白名单或子进程守卫；子进程必须有各自证据。原独立审查稿保留在本地，本版纳入已接受的唯一收据名称和守卫范围澄清，不改变设计或产品范围。

## Task 1 — W1：冻结纯接口、规范字节与摘要关系

**Files:** 上表W1四文件。

**Interfaces（供W2直接导入，首轮冻结后不得静默改名）:**

```python
class ReleaseMinutePackageError(ValueError):
    code: str  # 固定安全码；str(error)==code，不带路径/原字段

@dataclass(frozen=True, slots=True)
class ReleaseMinutePackageIdentity:
    profile_id: str
    context_sha256: str
    manifest_sha256: str
    manifest_byte_count: int

@dataclass(frozen=True, slots=True)
class ReleaseMinutePackage:
    identity: ReleaseMinutePackageIdentity
    minutes: ReleaseMinuteResult
    segments: tuple[ReleaseSegment, ...]
    scope: str

PACKAGE_MEMBER_NAMES: tuple[str, ...]  # 五名，按写入顺序
PACKAGE_MEMBER_BYTE_LIMITS: tuple[tuple[str, int], ...]  # 同序五对
PACKAGE_TOTAL_BYTE_LIMIT: int  # 20971520

def encode_release_minute_package(minutes: ReleaseMinuteResult,
    segments: tuple[ReleaseSegment, ...]) -> tuple[tuple[str, bytes], ...]: ...
def decode_release_minute_package(members: dict[str, bytes]) -> ReleaseMinutePackage: ...
```

错误码精确沿Spec§11的11项；错误类由W1定义，W2复用，不产生第二套异常。W1可内部使用固定协议常量，但不提供任意profile注册或动态版本开关。W2只需要上列三个字节常量和四个类型/函数中的decode/encode/identity/error。

测试辅助接口由W1独占：`make_result(rows_by_source: tuple[tuple[dict[str,str],...],...], segments: tuple[ReleaseSegment,...]) -> ReleaseMinuteResult`。基础91字段先置字符串0，再设Flow ID=artificial、Src IP=192.0.2.1、Dst IP=192.0.2.2、Protocol=6、Timestamp=2026-01-01 00:00:00.000000、Flow Duration=0、fwd/bwd packets=2/1、fwd/bwd length=20/10、Label=BENIGN、Attempted Category=-1；每行覆盖字典必须明确id及Timestamp，其余按案例覆盖。通过既有内存parse/aggregate造结果，不导入旧模型/工具审计链。辅助`plain_members(result, segments)`可调用被测encode制造变体，但不能生成独立期望协议或手算答案。

- [x] 写`test_protocol_and_five_members_roundtrip`、`test_duration_constant_11_digits_roundtrips`、`test_rejects_12_digit_integer_token`，首轮动态import新模块取得行为RED；固定小型有效变值结果，断言：五成员名/顺序、decode结果逐字段等值、segments等值、scope固定、manifest_byte_count等于实际长度、所有文档恰一LF。
- [x] 写`test_rejects_custom_mapping_and_bool_scalars`、`test_frozen_result_has_no_aliases`及`test_pure_codec_opens_no_paths`：拒Mapping/dict子类/非str键/非bytes值；深层tuple/冻结类型，无可变别名。在导入/夹具准备后禁止open，encode/decode及属性读取仍通过且无打开尝试。固定协议fixture逐项与Spec§5/现有常量核对，期望不调用被测代码生成。
- [x] 用Task0命令运行目标函数，保留缺模块/缺函数的准确失败；语法/收集失败单列修正，不当成有效TDD。
- [x] 实现精确类型、schema/profile/嵌套键/枚举/canonical编码与哈希链。数据三文件绑定context，manifest绑定数据，COMPLETE绑定manifest；decode由同一payload核摘要/解码/返回，不读路径。encode前后共用关系校验，不引入训练或旧candidate高层依赖。
- [x] 加`test_rejects_duplicate_keys_noncanonical_and_unknown_version`：重复键、BOM、尾随第二JSON/空白、非法UTF-8、NaN/Inf、未知字段/版本、成员缺失/多出；分别期望固定安全码，不能让ValueError底层文字泄漏。
- [x] 重跑本任务全部测试，记录实际passed/failed/skipped；向主控和W2交付精确接口/常量冻结及RED/GREEN收据。本步骤不提交Git，等Task2纯契约审查与整批发布。

关键断言示意（实施时对应实际辅助名称，不把该片段本身计作测试）：

```python
members = dict(encode_release_minute_package(expected, segments))
actual = decode_release_minute_package(members)
assert actual.minutes == expected and actual.segments == segments
assert actual.identity.manifest_byte_count == len(members['manifest.json'])
assert actual.scope == 'PACKAGE_INTERNAL_CONSISTENCY_ONLY'
assert actual.minutes.source_authentication == 'NOT_AUTHENTICATED'
```

## Task 2 — W1：守恒、污染、数字与真实字节上限

**Files/Interfaces:** 同Task1，不增加公共接口；消费Spec§6全部规则与Task1固定协议。

- [x] 写参数化`test_rejects_axis_mask_and_feature_contradictions`：错误13维、特征顺序、重复/乱序/非整分钟/带时区、数组长度、segment归属/role/order、id空/129字符/控制字符/孤立代理项、缺口被补轴、有效行null/无效行非null、精确float要求、非有限、负零、duration顺序。保证变体已重签对应hash，以实际命中语义校验。
- [x] 写`test_keeps_eligible_records_when_whole_minute_invalid`：1正常分配＋1无效时间，U=1；全轴invalid/null，但首桶eligible=1；全局U=1而每桶U都1。另测无源行但有表头的empty桶，全局empty=0。
- [x] 写`test_rejects_record_protocol_and_label_conservation_mismatch`：逐类击中Spec§6 R/E/X/O/U、协议计数、八项分配原因/特殊五项、duplicate组/副本、unused描述、三政策T与异常/flags关系。原因不是互斥分母；有效桶raw=eligible、异常标签保留unknown；Protocol0只能走unresolved。
- [x] 写`test_binding_changes_need_all_members`和`test_self_consistent_rewrite_has_new_identity_not_trust`：改源顺序/段/特征声明/文件SHA而不完整更新时拒绝；合法自洽改造形成新identity仍NOT_AUTHENTICATED。禁止反向要求所有合法内容必须由旧fixture签名认可。
- [x] 写`test_maximum_legal_shapes_and_bytes`的两个有限人工值对象：10000有效分钟（每桶250记录，全局2500000）；10000无效分钟（全域U=2500000，桶raw=eligible=0，保留empty与U）。使用7段、合法最长Unicode id、固定域内长数字/最大有限packet/length float；分别编码/解码，记录五文件实测字节与总量。不得把大浮点当舍入前精确整数；不需要造250万CSV行。
- [x] 写`test_member_and_total_limits_before_parse`：各成员cap与cap+1、总量cap与cap+1；字节护栏先于解析。仅限额等于cap不表示任意填充JSON合法；断言未因RESOURCE_LIMIT拒绝再按实际结构结果断言。三个成员各未超8MiB但总量超20MiB必须拒绝；构造时限制总临时bytes，不写巨量日志。
- [x] 运行相关RED，最小实现缺失检查，再重跑Task1/2；最大对象若超硬限，停止并向主控报告实测，不能自动增限/削字段。检查所有异常均固定码、无sys全局数字/CSV设置修改。
- [x] 主控安排纯契约独立审查，确认完整字段、保守必要关系、decode/encode相容、计数未双算及资源限额。W1提交私有交接收据并冻结源码SHA，等待联合验收。

## Task 3 — W2：稳定、有界的独立加载

**Files:** `src/core/traffic_anomaly/release_minute_package.py`、`tests/core/test_release_minute_package.py`。

**Interfaces:** 消费Task1冻结的三个PACKAGE常量、错误/值类型及decode；产出 `load_release_minute_package(directory: Path) -> ReleaseMinutePackage`。固定读序COMPLETE→manifest→三数据；目录中只能五个固定普通文件。不得导入audit CLI `_Output`或旧candidate reader，不复制W1关系校验。

- [x] 先写load测试（接口未冻结时可写隔离边界RED，但联合通过只能用实际W1）：`test_loads_five_ordinary_members`、`test_load_rejects_sixth_or_missing_member`、`test_path_and_hardlink_rules`；正确包由纯encode bytes写到专用tmp目录。
- [x] 写`test_wrong_real_open_handle_is_rejected`：路径仍指A，打开却返回另一个同尺寸真实普通文件B句柄，要求fstat身份检查失败。写`test_short_read_cannot_hide_stable_file_tail`：签名稳定但读到合法JSON前缀，不得靠manifest/hash自洽接受短读。新读取必须同时len(payload)==稳定st_size且不超剩余预算。
- [x] 写`test_read_and_close_failures_never_return_snapshot`及`test_byte_read_request_is_bounded`：保留真实fileno的短读/异常包装器；记录请求上界、最多观察limit+1、句柄释放、关闭失败和最后成员失败。path/handle前后签名不一致、目录换实体、成员新增/替换均拒绝。
- [x] 运行RED并实现最小load：先词法/祖先/普通实体检查和有界成员扫描；核五文件真实尺寸/总量后逐同句柄读取，签名含dev/inode/mode/size/mtime_ns/attributes/nlink，最后再核目录实体/成员集合/已读签名；同次payload交decode。没有跨文件原子性承诺。
- [x] 补`test_hardlink_outside_package_rejected_but_copy_allowed`、Windows root-relative和POSIX绝对路径对应主机测试。真实链接/替换权限不具备时明确skip；模拟检查与实际操作证据分别记录，不抹去skip。
- [x] 跑本任务测试GREEN；向主控交固定错误类别、实际平台覆盖和源码SHA，不提前把mock decode通过称联合通过。

参考现有 `test_release_file_reader.py` 的 `test_actual_byte_overread_is_at_most_one_before_buffering`、`test_every_stream_failure_releases_handles_and_suppresses_receipts`；可借故障注入手法，不照搬旧helper的保证。

## Task 4 — W2：独占保存、回读与失败残留

**Files:** 同Task3，由同一W2继续，不能两个work并发改同文件。

**Interfaces:** 消费encode/三个预算常量/load结果类型；产出 `save_release_minute_package(minutes: ReleaseMinuteResult, segments: tuple[ReleaseSegment,...], output_directory: Path) -> ReleaseMinutePackageIdentity`。返回保存并回读核对的identity，无自动重命名、恢复或覆盖选项。

- [x] 写`test_validation_precedes_output_creation`、`test_existing_empty_directory_is_not_owned`：非法输入编码先失败且目标不存在；已有空/非空目录都拒绝，原内容和元数据保持。写`test_save_load_and_copy_roundtrip`覆盖五字节完全等于encode、实际SHA/长度、普通复制后identity不变。
- [x] 写`test_partial_write_or_pre_marker_failure_preserves_residue`：每阶段mkdir/xb/短写/flush/close/回读/未知第六成员失败；标记前失败不宣告成功，残留不删除不接管。包装器保留fileno，记录返回写长和原异常；安全码不得暴露路径。
- [x] 写`test_replacement_not_removed_or_overwritten`及`test_keyboard_interrupt_preserves_residue`：独占创建竞争、文件/目录被换、关闭后替换，失败后替换物保留；注入KeyboardInterrupt保持中断类型与现场，不称实际OS信号测试。写`test_late_failure_can_leave_loadable_complete_package`：标记后最终检查注入失败，save报错，单独load可接受仍完整的包，不宣称所有异常都使包无效。
- [x] 运行RED，实现先纯encode全部通过再独占mkdir，按固定顺序xb写、短写检查、句柄/路径身份核对、关闭/回读，最后标记及最终目录检查。不得使用无所有权依据的清理/递归删除，也不通过临时关闭守卫绕替换测试。
- [x] 运行Task3/4全测试及与真实W1的联合往返，独立存取审查逐项核Spec§8—10；记录真实/模拟/skip边界。无HTTP、端口或模型测试。

参考 `test_release_audit_cli.py::test_short_report_write_has_no_complete_marker`、`test_tampered_report_before_marker_cannot_form_valid_completion`；late-failure在Python最终检查处注入，不照搬stdout失败。参考disk的创建/关闭后替换测试，不复用会删除失去所有权路径的旧candidate异常清理。

## Task 5 — W3：独立人工手算与消费边界

**Files:** 上表W3两文件；仅人工内容，不改UI/HTTP。

**Interfaces:** fixture顶层精确`fixture_version:1`、`evidence_kind:SYNTHETIC_ONLY`、`cases:list`；每case含短name、`sources:list[list[dict[str,str]]]`（91列基础行的字符串覆盖）、`segments:list[{id,role,start,end}]`、`expected`。expected固定含timestamps、values、source_valid、label_kinds、全局R/E/X/O/U/duplicate_groups、逐桶r/e/x及关键协议/原因/flags预期；这里SYNTHETIC_ONLY只标测试fixture，绝不加入包。

- [x] 先独立手算并把预期写死，再运行被测代码；不得调用生产聚合器/encode生成期望。四组小案例如下，每个id唯一，只有专设duplicate复制全91列相同内容：
  - **A变值/标签**：00:00四行 `(protocol,fwd,bwd,duration_s,label)=(6,1,0,1,BENIGN),(17,2,1,2,BENIGN),(1,3,2,3,BENIGN),(0,4,0,4,Portscan)`，fwd_length=fwd×10、bwd_length=bwd×5；预期13维 `[4,10,3,100,15,1,1,1,1,4,2.5,3.85,2]`，三政策attack。00:01另1条合法Attempted，预期unknown/normal/attack；00:02未知标签，三unknown但数值有效；00:03空桶invalid/null。明确start为各分钟0秒，duration按微秒写。
  - **B全域U**：1正常分配＋1非法Timestamp，4分钟轴；R2/E1/X1/O0/U1，首桶e1，其余e0，全部invalid/null；每桶U1但全局仍1。
  - **C跨源重复/非法协议/区间外**：两个源中的同一完整行在00:00重复两份、00:01正常1、00:02协议4一条、00:08区间外一条；四分钟轴R5/E1/X4/O1/U0、duplicate_groups1/duplicate_record2；桶r=[2,1,1,0]、e=[0,1,0,0]、valid=[false,true,false,false]。协议0不与4一起放行。
  - **D相邻段/缺口**：train[00:00,00:02)、validation[00:02,00:04)、test[00:06,00:08)。一行start00:01:59/duration2秒完成00:02:01跨段；另一行start00:02/duration0合法但同桶受污染；一行00:04区间外；一行00:06合法。R4/E2/X2/O1/U0；轴六分钟不含04/05，00:02桶e1仍invalid，00:06有效。只查分区/轴，绝不构造历史。
- [x] 写`test_independent_hand_cases_survive_package_roundtrip`，调用Task1测试helper造结果，逐字段比手算，再save/load比同一手算；未有接口时取得真实缺入口RED，等W1/W2就绪后GREEN。所有字段必须有限且标签不出现在minutes.json。
- [x] 写`test_current_package_identity_cannot_be_old_candidate_identity`：包无旧record/input/model schema和evidence_kind，旧人工格式入口只按现有准入拒绝，不能修改旧validator放行。若检查旧入口会导入模型库，改为只读源码消费边界审阅并明确未运行该入口；不得为了本测试突破无模型守卫。
- [x] 另构造一份完全自洽但新源声明/新context的包，断言新identity且NOT_AUTHENTICATED，明示手工构造通过不能认证解析执行。核对实际结果仍含原三政策标志，不称最终政策。
- [x] 将手算推导、实际RED/GREEN、guard/skip和消费边界独立审查记录交主控。W3不能只对W1 helper返回值自比而称独立验证。

## Task 6 — 主控：隔离安装与有界人工跨进程往返

**Files:** 新私有freeze、install/accept脚本和原始收据；不新增生产CLI。

**Interfaces:** 消费冻结的W1/W2源码与W3手算表；新安装核心wheel中四个公开函数/类型。生成新人工CSV→既有 `_aggregate_release_files(...).minutes`→save；另一个进程仅load+逐字段比手算/首进程结果。全部路径仅私有freeze持有，不写公开产物描述。

固定本次验收预算（不更改包硬限）：每case最多2源/100行、总人工CSV≤1048576字节、轴≤24分钟；`ReleaseDiskBudget(1048576,100,8388608,30)`；每普通验收子进程timeout60秒，build/install各120秒；每wheel≤16MiB，整个独立验收目录≤256MiB。纯契约10000轴测试独立记录，不移入该小型CSV预算。超限停止并留原因，不临时扩大；超时控制是验收父进程机制，不宣称package函数硬实时/RSS上界。

- [x] 复审W1/W2/W3最终文件，冻结SHA和源提交；检查本批无旧模块/生产契约/依赖改变。核Task1/2最大人工结构实测字节，不接受估算替代实测。
- [x] 创建此前不存在的私有验收目录，按冻结清单复制核心包源码和pyproject；从本地现有工具离线build/install到新target。使用 `pip wheel --no-deps --no-index --no-build-isolation --no-cache-dir` 与 `pip install --no-deps --no-index --no-compile --no-cache-dir --target`；禁止网络fallback，不重新装旧模型依赖。
- [x] 安装验收新进程从源码目录外启动，清除指向源码的PYTHONPATH（只放新installed target）；核`release_minute_contract.__file__`、`release_minute_package.__file__`及依赖 `_release_*` 都来自冻结target并字节一致。导入前守卫禁止torch/sklearn/joblib/网络，保留NumPy。不能把源码PYTHONPATH运行当安装证明。
- [x] 逐case只执行一次现有文件聚合并save，按W3手算比值/labels/diagnostics；记录源实际bytes/SHA、reader receipts、scratch成功清理、输出五文件实际bytes/SHA、返回identity。只使用当轮新造人工源，绝不扫描数据目录或找旧包。
- [x] 第二个新进程load原包及普通复制包，逐字段比手算及首进程独立导出的expected-result.json（按dataclass字段投影，datetime.isoformat、tuple转JSON数组；不使用新包codec生成该期望，不用pickle）。核冻结类型另作断言。load进程禁止打开人工CSV，只允许登记包/期望及解释器依赖；读后移走专用副本不影响返回对象。原包/源的前后SHA/size/mtime/members表保持，原品不删除。
- [x] 对另造副本实际执行缺COMPLETE、成员被改、成员多出、路径不普通等代表性拒绝，保存固定错误/退出码；真实链接平台不允许就记录未覆盖，不能靠模拟宣称实际通过。部分写/晚期失败由Task4注入证据承担，不伪称实际断电测试。
- [x] 主控独立核原始stdout/stderr/exit、父子PID/解释器/安装来源、守卫计数、目录总量与源/包前后身份；每个进程有独立证明，不能仅凭父进程日志推断子进程未触模型。安装与往返均通过才进入Task7；失败只修对应缺陷并重跑受影响部分，保留初始失败。

联合测试命令（经Task0守卫runner，实际执行后填结果，不承诺数量）：

```powershell
.venv\Scripts\python.exe -X utf8 "$env:MINUTE_PACKAGE_TEST_RUNNER" --receipt-name joint-green-01 tests/core/test_release_minute_contract.py tests/core/test_release_minute_package.py tests/core/test_release_minute_hand_cases.py tests/core/test_release_csv.py tests/core/test_release_minutes.py tests/core/test_release_file_reader.py tests/core/test_release_disk.py tests/core/test_release_audit_cli.py -q
```

先新测试，再联合相关切片；只有新增修复/失败/风险才扩大或重复。现有切片内子进程守卫范围单列，不声称所有子进程自动继承Task0守卫。无需前端/HTTP全套、本批无浏览器或端口验收。

## Task 7 — W0记录、独立复审、主控Desktop发布

**Files:** 已公开设计与本计划；实际验收后才新增指南/verification及主控指定维护文件。

**Interfaces:** 消费Task1—6准确源码SHA、RED/GREEN/skip、实际安装收据、人工案例分母、错误/残留/字节预算记录；输出公开脱敏证据及继续阻塞事项，不向研究状态写PASS。

- [x] W0按最终真实接口整理公开设计/指南/验收JSON，标明纯契约、文件测试、独立手算、安装与人工往返、研究状态五类。设计与计划已采用脱敏内容及仓库相对链接；不公开本地路径/完整人工运行包/原始标签明细。所有未执行字段继续NOT_RUN，数目从实际日志统计，避免重叠合计。
- [ ] 主控安排最终独立审查：标准/需求、数值关系、文件I/O和证据陈述。审查必须覆盖上述五个Review Focus，尤其late failure/自洽重写/源钟面/eligible污染；审查缺陷先修复复测，不降守卫或删负例。
- [x] W0按主控授权一次更新status摘要、README生成区、ROADMAP、DECISIONS、MAINTENANCE_LOG及docs导航；Vault查重后复用既有入口/当日日志，按规范校Wiki链接。新工程决定与仍待用户决定的研究事项分开；原G12/G13U证据和开题报告历史不覆盖。
W0收口已实际运行下列维护检查：README生成/核对、13项仓库测试、600文件隐私与作者检查零问题、10份公开文档487条本地链接及6篇Vault新增10条Wiki链接、8个本批产品与测试身份和旧未跟踪计划保持。最终独立文档复核及主控发布前复核另行保留待验项。

- [ ] 主控运行仓库规定检查，并核本次diff/公开隐私/作者/链接；正常完成标准是实际退出0、未泄漏、无未解释失败：

```powershell
python -X utf8 tools/repository/update_progress.py --write
python -X utf8 tools/repository/update_progress.py --check
python -X utf8 -m unittest discover -s tests/repository -p "test_*.py"
python -X utf8 tools/repository/check_repository.py --worktree --check-author
```

- [ ] 仅主控通过GitHub Desktop勾选本批公开文件，检查Summary/Description、通用身份和hook结果，然后Commit/Push；不包含旧未跟踪计划、私有验收目录或容量批未归属文件。建议主题 `feat: 保存并重开有界原始分钟包`，Description用实际结果填写，不预填通过数/未来SHA。客户端失败保留本地成果，不改用CLI/API写Git。
- [ ] 核准确远端分支SHA与本地一致、README对应准确提交、实际三项CI。CI未完成/失败单列，不把本地完成当同步；真实研究仍BLOCKED_NOT_RUN。将准确提交/CI/未提交成果/下一接缝写本地台账，不为回填自身SHA循环提交，不合并main。

## 自检与交付口径

本计划自检映射：Spec§1—3→Task0/1/文件归属；§4—5→Task1；§6—7→Task2/5；§8→Task4；§9—10→Task3/4/6；§11→Task1/3/4；§12→Task1—6；§13→Task0/7。五个Review Focus均有明确用例和所有者。

接口交叉核对：manifest_byte_count始终精确int；decode始终内置dict[str,bytes]；encode始终有序五对tuple；save返回identity、load返回含minutes/segments/scope的冻结包；W2不另造协议/错误，W3不把fixture evidence_kind写入包。任务标记按实际证据更新；平台权限跳过和未发布另列，设计审查的三个小探针不计新实现测试。

分工方法已由主控明确，无需再向用户询问普通工程授权或执行方式。主控从上述已发布基点安排W1/W2/W3；W0在设计登记时仅整理设计与计划；后续按主控授权完成运行指南、验收记录和维护收口，不修改业务源码、不执行Git写入。
