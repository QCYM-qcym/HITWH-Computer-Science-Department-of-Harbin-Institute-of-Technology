# Release Artificial Example Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax; W0 publishes only through GitHub Desktop.

**Goal:** 为新release链提供不依赖私有Temp包的固定人工CSV／聚合spec生成命令。

**Architecture:** 一个无I/O的固定配方bytes builder与一个有限排他写CLI。用户后续显式调用已有聚合、prepare、IF和只读展示，不新增训练编排或package加载器。

**Tech Stack:** 既有Python3.14及标准库CSV/JSON/hash/datetime/path；下游沿现有锁定core和backend依赖，不加依赖或元数据。

**Spec:** [Release人工CSV示例v1](../../design/release-example-v1.md)。W0已采用且builder check通过，基线 `b588448c754dc1a53495dd6593a09675992e548a` 已Desktop推送并核对官方远端；源码、完整回归和14阶段新安装人工链已经独立验收，见[验证记录](../../research/2026-11-11-release-example-verification.json)；本批Desktop／准确新CI仍待核。

## Global Constraints

- 前一CLI阶段保全窗口已结束且16文件已Desktop推送；其独立审查、4469项完整回归及13进程安装验收通过。本轮后续独审复现同类错误出口缺口，允许仅窄修既有release_if_result_cli.py，另加独立测试；其他旧src/tests/configs及原运行证据不得修改。269原基线不重写，以268原身份＋1项显式前后身份核查。
- W0派工前确认前阶段发布／保全已收束，冻结新设计、公共seam和基线；W1/W2/W3仅写各自新文件。
- profile `release-artificial-example-v1`，三成员 `artificial.csv / aggregate-spec.json / recipe.json`，caps分别1048576/65536/16384，total1130496；固定176行，budget.max_rows512。
- source摘要来自真实构造并最终读回的CSV；只在aggregate spec含实际绝对路径，不用测试假SHA或不随包分发的fixture。
- CSV／recipe不依赖输出目录；spec路径相关。NOT_AUTHENTICATED／SOURCE_WALL_CLOCK_COMPLETION_PROXY／AUDIT_ONLY保持；真实研究S2/BLOCKED/NOT_RUN。
- 不下载、不新增标签解释／研究采用／134维迁移／后台UI功能；生成器不做aggregate/prepare/model动作。
- 旧数据、失败及草稿保留；未执行不填写PASS或效果。Git写操作仅W0通过Desktop，无main合并。

## Review Focus

1. source路径含Unicode、空格、非法原拼写或足以超过spec预算；builder保持纯函数，CLI在创建前安全拒绝。
2. 两个不同输出根的三个文件不能全部相同；只比较CSV／recipe稳定性，spec必须准确指向各自真实CSV。
3. Protocol0、Attempted合法token与未知标签可能被悄悄丢弃或归正常；真实聚合保留U通道及三审计标签差异。
4. 父目录／链接／已有目标／竞争者／写入读回出错时，不能覆盖、删残留或打印成功。
5. create保存后stdout失败可能留下完整三文件；main返回值、模块实际exit、下游可读取性必须分别证明。

---

## Task 1 · W1 纯配方builder与单测

**Files:** Create `src/core/traffic_anomaly/release_example.py`; Test `tests/core/test_release_example.py`。

**Consumes:** 只读既有 `_release_csv.EXPECTED_HEADER`及spec固定配方。

**Produces:** `ReleaseExampleError`、frozen/slots `ReleaseExample(profile_id, members)`、spec列出的四个EXAMPLE常量，以及 `build_release_example(*, source_csv_path: Path) -> ReleaseExample`。

- [x] 先写 `test_builder_returns_three_bounded_immutable_members`：当前绝对目录下future artificial.csv路径，恰三个有序bytes成员、profile与caps精确、immutable/slots；实际RED证明缺少接口。
- [x] 实现固定配方和规范编码。source参数只词法检查，不调用open/stat/resolve/clock/model；同一输入路径重复调用bytes相同。
- [x] 写 `test_csv_records_match_fixed_recipe`：独立csv.reader读真实builder bytes，91列等于既有header，176行；核首尾时间／秒10与1s／unique id、p/b、精确列 `Total Length of Fwd Packet`／`Total Length of Bwd Packet` 的 `10*p`／`10*b`、Protocol循环和两个override、local36/40/44精确标签；其余数值人工0。期望按spec文字独立列出，勿把产品返回值当自己的expected。
- [x] 写 `test_paths_change_only_aggregate_spec`：两个不同根（含中文空格）CSV／recipe相同，spec.sources[0].path分别精确；两JSON规范UTF8/LF，source实际len/SHA及segment/budget正确；CSV／recipe不含两绝对路径或spec hash。
- [x] 写 `test_builder_is_pure_and_rejects_bad_path_or_limits`：护住filesystem业务入口、prepare/aggregate/model；相对/..错误basename/UNC/NUL/surrogate按平台检查；对资源分支可缩小本模块cap而非造巨payload。所有失败仅安全码。
- [x] Run `.venv/Scripts/python.exe -X utf8 -B -m pytest tests/core/test_release_example.py -q --tb=short`（按现有core导入环境）。记录RED/GREEN／hash／未执行项，冻结后交W0；不操作其他owner文件或Git。

## Task 2 · W2 create CLI与单测

**Files:** Create `src/core/traffic_anomaly/release_example_cli.py`; Test `tests/core/test_release_example_cli.py`。

**Consumes:** Task1精确类型、常量和builder；仅复用 `release_input_package._lexical / _signature / _directory`，可读既有CLI安全流写入习惯，不能修改旧helper或复用旧固定成员I/O／宽错误码表。

**Produces:** `main(argv: Sequence[str] | None = None) -> int` 和真实 `python -m traffic_anomaly.release_example_cli` 入口；唯一create和独占help。

- [x] 写 `test_create_calls_builder_once_and_persists_actual_members` RED，使用临时绝对新目标；首个RED须是缺少CLI功能而非坏fixture。W1尚未就绪时可先写测试，公开seam不临时换名。
- [x] 实现固定解析、原始路径预检、builder回值shape/cap检查、exclusive mkdir/xb、flush/stat／成员与有界读回、白名单成功JSON；不新增generic package decoder或训练任务调度。
- [x] 写 `test_help_and_bad_arguments_have_no_actions`：argv=None一次，两种output写法、重复/未知/缩写/@/混help/多位置参数；护住builder和所有创建，断言code/流。
- [x] 写 `test_destination_preflight_and_race_preserve_existing_files`：实际临时目标已存在、缺父、文件父、同前缀合法兄弟、权限／reparse按平台可观测边界；坏目标在builder前拒绝。预检后竞争者获胜也不覆盖、不重试，保留赢家。
- [x] 写 `test_partial_write_readback_and_stdout_errors_retain_residue`：假短写、flush失败、错读回、额外成员／身份变化；成功前不输出CREATED。stdout失败时三文件可真实读出且hash一致，输出可能已部分传送，main不改宿主流。
- [x] 按spec三行精确类型表写allowlist测试：`_CLIError`七码、`ReleaseExampleError`三码、`ReleaseInputPreparationError`只 `INVALID_PACKAGE_PATH / PACKAGE_CHANGED`。至少覆盖跨类 `builder:OUTPUT_EXISTS`／`helper:RESOURCE_LIMIT`、helper未采用的 `INVALID_PACKAGE_ARGUMENTS`、未知类／子类／非str code及带私密消息异常均 `INTERNAL_ERROR`；builder构造器未知码独立验证收敛 `EXAMPLE_ERROR`，CLI异常构造器不自动收敛。
- [x] 验证小I/O边界映射：缺父／权限为 `OUTPUT_ERROR`，目标mkdir竞态为 `OUTPUT_EXISTS`，成员xb竞态为 `PACKAGE_CHANGED`；I/O转码不吞builder/helper跨类错误。另验中断／stderr失败、LF计入输出上限、模块失败描述符保护；不镜像每个私有函数。读取实际目录证据与mocked边界分开。
- [x] Run `.venv/Scripts/python.exe -X utf8 -B -m pytest tests/core/test_release_example_cli.py -q --tb=short`；必要邻接由W0统一选择，勿重复fullsuite。记录日志／source hash并冻结。

## Task 2a · W1 相邻已发布命令的必要兼容窄修

**Files:** Modify `src/core/traffic_anomaly/release_if_result_cli.py`; Create `tests/core/test_release_if_result_cli_error_exit.py`。本项由W0在初审后明确扩展，不改原单测文件。

- [x] 保存既有CLI原始字节／SHA及原269项基线，登记唯一允许差异；原Oct31草稿不在例外中。
- [x] 用无文件／模型动作的两条失败测试复现未知类型code getter和允许类型getter的中断逃逸；未知类型直接INTERNAL_ERROR且不读code，允许类型中断经main返回2／INTERRUPTED。
- [x] 仅改上述安全出口，不扩大精确类型码表，不改解析、路径、模型数值、阈值及结果协议；新增用例与既有103项邻接回归，失败和原发布记录保留。
- [x] 独立复审该差异，最终源清单含前后身份；原268项保持，唯一改动按新冻结SHA保全。安装仍为14子进程，不增加模型运行。

## Task 3 · W3 真实CSV／spec磁盘集成与用法

**Files:** Create `tests/integration/test_release_example.py`, `docs/guides/release-example.md`; private `installed-acceptance-proposal.md`，不启动实际安装／模型。

**Consumes:** 两个新模块公开seam；既有 `release_minute_cli.main`、raw loader、`release_input_cli.main`／prepare与pair接口。测试可写临时人工源、实际聚合和人工预处理，不运行估计器。

**Produces:** 新克隆示例到有效raw/prepared的真实I/O测试，以及显式完整用户命令链。

- [x] 写 `test_created_csv_spec_aggregates_and_prepares_real_packages` 有效RED，等待CLI存在后接真实create；用actual spec调用现有raw main，检查source单文件实际size/SHA、源字节/行数、源钟面四段、scratch正常清理、独立raw load身份。
- [x] 实际prepare本测试的新人工raw，显式P_U/epsilon1e-6；核窗口、正常训练／独立校准非空及实际共同mask，输入／源成员保持。前置手算来自新48/40/40/48配方和H30每段预热，不挪私有A当新实测。代码注释区别测试准备与被测行为。
- [x] 写 `test_protocol0_and_existing_label_audit_mappings_survive_pipeline`：实际raw U渠道计数、test local36/40/44的三映射、无空桶被自动当正常。护住IF、sklearn、torch等新模型调用；不写“报警必须抓住攻击”的效果断言。
- [x] 指南给一个create命令、raw spec/scratch/output、显式prepare、两view run、独立inspect/verify和serve；所有目录为读者自己的绝对路径占位，source/time/auth/AUDIT_ONLY边界清楚。CSV和recipe可复现、spec路径绑定和失败残留的区别必须可读。
- [x] Run `.venv/Scripts/python.exe -X utf8 -B -m pytest tests/integration/test_release_example.py -q --tb=short`。只准备实际安装验收的有界命令表／资源／source身份，不执行build/install/model/server；不复制庞大旧runner。把新source窗口供应计数留实际收据，预期不是结果。

## Task 4 · W0 整合、实际人工链与发布

**Files:** public design/plan、验证JSON、README/status/导航/决策/路线图/维护日志；既有Vault页；私有审查与运行收据。

- [x] 派工前采用／修订设计、检查旧窗口和worktree／未提交修改、冻结公共seam；W1/W2/W3独占新文件可并行，依赖未就绪时等待，不往旧代码加测试钩子。
- [x] 冻结最终新源／测试／文档，独立spec+quality review；真实问题先RED再修，保留原日志，集中复审修复差异。验证268项旧基线未改、唯一获准CLI修复前后SHA与显式差异清单一致；原269基线和旧失败均保留。
- [x] 统一跑必要专项合测与最终完整Python范围；依赖/API/UI均无改动时不机械重复整个浏览器验收；相关检查和实际CI按证据单列。
- [x] 另行冻结实际新目录、source/环境/脚本字节、exact argv/cwd、每阶段expected code、完整成员及mtime基线、时间/磁盘/日志/HTTP停止条件。已审脚本最终冻结后由W0另行放行，实际只执行一次。
- [x] 安装新的core wheel到新target；若API源码未变可复用已明确身份、CRC/RECORD/逐member确认的API wheel，依赖复用既有锁定环境。普通模块与受控observer的物理进程证据分开，Windows launcher/PID与额外loopback绑定按已知事实记录。
- [x] 实际生成一个全新示例→用其真实spec聚合→prepare→两个IF run→独立inspect/verify→有限只读serve/HTTP兼容。create为零aggregate/prepare/model；整链真实人工预处理fit与两个IF fit/score/模型Q99分别记录，codec保存分数复核另计。不得把下一阶段动作算入上一CLI的13个子进程。
- [x] 新recipe数值和source/hash从实际生成文件及独立读取核对，不与私有A包强求逐字相同。不按结果改图样、不编造FPR／召回优势；任何失败保留并停止后续，无自动第二轮模型。
- [x] 可先以total360s、普通child45s、serve30/hard60s、新任务128MiB、每日志1MiB、手工HTTP1MiB为收紧候选；准确子进程数由新命令表冻结，不能沿用旧常数。这不是OS硬配额／连续峰值保证。
- [ ] 按真实结果更新公开指南／验证／状态和Vault，运行进度、隐私作者、仓库及链接检查，排除旧Oct31草稿和全部生成载荷。仅Desktop提交推送，核准确远端SHA／README／三项CI，不合并main，不回填自身SHA循环提交。
- [ ] 当前用户截止前继续有用迭代；本项仅人工可复现工程，不解除Data Gate。生成器、CLI、实际链、发布与研究状态分别报告。

## 自检

两产品模块对应纯配方与文件I/O两个独立责任；成员名、类型、caps、字段和函数名在各任务保持一致。五类Review Focus均有归属测试。只有W0管理共享文档／运行／发布；W3无需改W1/W2源文件。没有新的研究政策、依赖、模型实现或后台UI。新源码、实际CSV磁盘集成、完整回归与14阶段安装链均已接受；初始NOT_RUN快照、源码／脚本FAIL及工具修正证据保留。本公开快照的Desktop推送及新CI未核，不勾选其合并交付项，持续开发任务仍由W0推进。

本轮局部检查：pure23、create81、真实CSV磁盘集成2、旧CLI兼容新2＋原103合计105；这些与完整4577项范围重叠，不相加。源码环境物理closed-stdout退出2和完整三文件保留已测，安装后physical broken-pipe与wrong-valid-pair负例仍NOT_RUN。发布相关仓库检查另按本次文档实际结果记录。
