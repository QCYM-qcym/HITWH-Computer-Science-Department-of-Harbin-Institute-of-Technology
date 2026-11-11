# Release Saved-Prediction Label Audit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. W0负责冻结与Desktop提交，W1/W2/W3只写分配的新文件。

**Goal:** 对显式绑定的release保存预测输出三政策test分钟标签敏感性及null原因，无新增模型或生产契约迁移。

**Architecture:** 一个pure evaluator返回≤16384B规范bytes，一个独立readonly CLI只加载/配对并写bytes。复用现有verify、confusion和codec，不新建报告包、存储/任务/API/UI层。

**Tech Stack:** 现有Python3.14、stdlib JSON/path、锁定NumPy/Pydantic及已有core；无新依赖/元数据。

**Spec:** [保存预测标签敏感性评价v1](../../design/release-if-evaluation-v1.md)。状态：W0已采用，独立builder check PASS；基线 `16082f7e787de162d1aa63050108a11a2388da50` 已完成实际人工接受与准确Desktop远端发布。当前基线CI另核，不借B；本计划功能实现、源码验证和七阶段新安装实际运行已完成；独立规格和质量后验复核后已由主控实际接受；发布待核。

## Global Constraints

- W0已确认C批独立接受、保全结束与准确Desktop远端发布，现据准确新基线采用/公开并派工；保留旧失败、草稿和全部运行证据。本采用仅工程，不升级研究Gate。
- 仅两新产品模块 `release_if_evaluation.py / release_if_evaluation_cli.py`，不改旧Metrics/schema/src/tests/configs/deps/API/UI或134/268。
- profile `c17-release-iforest-fixed-prediction-label-audit-v1`，evaluator只返回canonical UTF8bytes≤16384（含LF），16顶层字段/9政策字段及所有有限码严格按spec。
- labels逻辑P_U/P_B/P_A；policies为三精确键对象，JSON规范序P_A/P_B/P_U。固定保存预测，不训练/校准/选择政策；audit_fit_policy保留，全部AUDIT_ONLY/NOT_AUTHENTICATED。
- test AND common/scored分母，unknown/unscored排除confusion且分别报告；零分母null+原因，不point-adjust、不从效果调整区间或图样。
- 产品无create/save/source CSV/aggregate/prepare/replay/fit/score/阈值选择。saved-score Q99复核允许，model fit/score/Q99均0，不能把验证矩阵工作说成“零数值工作”。
- Gate D1-D6/S2仍BLOCKED，真实研究NOT_RUN；不下载、不联系作者、不认证source真假或历史执行，不构造研究采用批准。
- 所有owner新文件独占可并行；共享文档/Vault/实际安装/发布只W0，Git写操作仅Desktop、不合main。

## Review Focus

1. unknown True、unscored None、非test报警被误计FP/TN；完整calendar与scored分母不守恒。
2. P_U/P_B/P_A tuple列映射与canonical对象字母序错位，或把保存audit_fit_policy误当输出政策/三次训练。
3. 零test/零normal/零attack/无positive指标被写0或整组null；F1零值与无定义混淆。
4. 修改fixture标签后未重新封印raw/prepared/result身份，或用产品confusion自己生成expected。
5. readonly CLI透传save/model码、error getter中断逃逸、stdout短写/flush部分输出或模块退出120；以及任何包/源写改或源重开。

## Task 1 · W1 pure evaluator、封印fixture与单测

**Create:** `src/core/traffic_anomaly/release_if_evaluation.py`；`tests/core/release_if_evaluation_cases.py`；`tests/core/test_release_if_evaluation.py`。

**Consumes:** 精确ReleaseIFResultPackage/ReleaseModelInputPair；现有verify一次与confusion算术；既有raw/prepared/result codec仅用于test setup封印。

**Produces:** EVALUATION_PROFILE_ID/EVALUATION_BYTE_LIMIT、ReleaseIFEvaluationError及`evaluate_release_if_result(package,pair)->bytes`；测试helper `sealed_evaluation_case(*, scenario: str='mixed', view: str='current13')` 返回具名/简单对象，其字段固定 `raw / prepared / pair / result / package`，全部合法内部身份。scenario恰mixed/no_test/no_normal/no_attack/no_positive/all_unknown；不是公开产品参数。W2/W3可复用helper，但数值expected必须各自literal。

- [x] 写首项 `test_mixed_fixed_predictions_report_only_common_test_minutes` 并实际RED（缺新接口，非坏fixture）；先清楚标注每个手算TP/FP/TN/FN/count/metric会抓住的错误。
- [x] 先完成有界新helper：人工raw声明在label/roles变更后一致地encode/decode取得内部身份；test setup使用既有真实人工prepare，再prepared codec封印；公开pair；手写有限scores/cal0或手核Q99/strict predictions；结果make/codec封印。setup的人工预处理如实记录，不运行估计器；被测操作期禁止prepare/producer/model，不能借hand_pair硬编码ID后splice标签或复刻history/qualification实现。
- [x] 实现精确参数type→verify恰一次→三个政策test bool masks→confusion+FNR→守恒/精确types→规范有界bytes；不加副作用或新generic codec。
- [x] 补 `test_policy_mapping_uses_fixed_saved_predictions`、`test_other_roles_unknown_and_unscored_do_not_enter_confusion`；mixed fixture含test normal/attack/unknown的True/False及unscored/非test报警。分别手算三政策，保留原audit_fit_policy，检查JSON键序为canonical而label列没错位。
- [x] 按表写no_test/no_normal/no_attack/no_positive/all_unknown有效正例；zero-test保留合法非空train/cal，优先在raw封印前将四段末角色一致改为calibration；31+31只是可行备选。精确覆盖FPR0.0与null、F1=0.0与null、unknown True排除及各null原因恰对应。both views分母相同且不强求预测相同/孰优。
- [x] `test_verify_precedes_label_arithmetic_and_runs_once`用窄spy委托真实verify，错误输入先拒绝；错身份/axis/population/threshold先由真实verify拒绝。保持正例封印，变异负例不冒充合法包。
- [x] pure五域码与verify六码映射、未知/子类/跨域/非str/getter错误、中断传播；缩小本模块cap验含LF限额，无path/private原文泄漏。模型入口/import与文件I/O护住，fixture setup和被测pure操作分界清楚。
- [x] 运行 `.venv/Scripts/python.exe -X utf8 -B -m pytest tests/core/test_release_if_evaluation.py -q --tb=short`；保留RED/GREEN日志、实际调用边界和新文件hash，交W0冻结。只新文件，不跑全量或安装。

## Task 2 · W2 standalone readonly CLI与单测

**Create:** `src/core/traffic_anomaly/release_if_evaluation_cli.py`；`tests/core/test_release_if_evaluation_cli.py`。

**Consumes:** Task1常量/精确错误类/evaluator；result/raw/prepared loaders、pair；只复用prepared I/O的无I/O `_lexical`，不借旧RUN/SAVE CLI宽表或执行入口。

**Produces:** `main(argv: Sequence[str]|None=None)->int`、唯一evaluate/standalone help及普通module entry，stdout成功为evaluator原bytes。

- [x] 写首项 `test_evaluate_loads_result_raw_prepared_then_pairs_once` 有效RED；用完整合法helper值和窄边界spy，验证实际输出内容、调用顺序/各一次及helper未执行producer。W1 seam尚未就绪可先写测试，不能临时更名。
- [x] 实现strict parser与三个原spelling词法检查后固定load→pair→evaluate；精确bytes/非空/限额消费、write/flush和safe stderr、模块失败fd保护。无save/output目录/用户源访问。
- [x] help/argv=None/两种选项写法；重复/未知/缩写/@/空/混help/非str/坏命令均无load。相对/..NUL/surrogate/UNC/Windows保留名/ADS在loader前失败；真实非法目录/成员由loader界定，不重复假锁/完整库存代码。
- [x] 按spec每精确异常类码表测试全部允许和代表性拒绝：raw OUTPUT_EXISTS、prepared DERIVATION_MISMATCH/NONFINITE_FIT_STATE、result INPUT_BINDING_MISMATCH、helper INVALID_PACKAGE_ARGUMENTS、跨类/子类/非str/code getter普通错误均INTERNAL_ERROR；对应pure binding码则可透传。
- [x] caller异常与error.code getter KeyboardInterrupt（包含_safe_code的except分支）均exit2/INTERRUPTED；write/shortwrite/flush stderr失败/partial stdout、宿主流不夺取与module fd保护。shape错INVALID_RESULT、超bytescap RESOURCE_LIMIT，不重解析第二份JSON语义。
- [x] 运行 `.venv/Scripts/python.exe -X utf8 -B -m pytest tests/core/test_release_if_evaluation_cli.py -q --tb=short`；如实标spy边界/普通物理模块未验，hash冻结；不运行fullsuite/model/安装。

## Task 3 · W3真实保存包I/O集成与指南

**Create:** `tests/integration/test_release_if_evaluation.py`；`docs/guides/release-if-evaluation.md`；私有小型`installed-acceptance-proposal.md`。

**Consumes:** Task1合法封印helper，现有三package save/load（仅setup保存），新CLI与pure。现有C批source generator指南仅作导航，不在此重跑producer。

- [x] 首写 `test_real_disk_saved_packages_evaluate_without_producer_or_model` RED，等待新CLI；setup把人工raw/prepared/result实际保存到独占临时目录，记录完整members/bytes/hash/mtime，再调用真实main，核与手算literal一致。
- [x] 两view实际保存包各评一次，三政策/unknown/unscored/非test口径及回执身份一致；合法no_test也走实际disk正例。操作期护住source CSV open、create/save/prepare/replay/IF/model import，assert无writes；setup行为另计，无真实训练或源消费声明。
- [x] 另一合法封印pair与原结果实际绑定负例、安全错误；损坏一个成员的完整性负例，保持其余原件和失败现场；stdout故障实际完整输入包仍可读取且不变。不修改旧test helper/源契约。
- [x] 指南给唯一evaluate/standalone help，显式三个已保存输入绝对路径、16字段/9政策report解释、固定预测与fit政策区别、null/FNR边界、source/internal-only/no-test说明；不增加新producer/训练流程或声称运行过文档示例。
- [x] 运行 `.venv/Scripts/python.exe -X utf8 -B -m pytest tests/integration/test_release_if_evaluation.py -q --tb=short`；准备小型只读安装提案但不build/install/模型/server。完成日志/hash交W0。

## Task 4 · W0采用、整合、安装只读验收与发布

**Files:** 采用后公开design/plan、验证JSON、README/status/导航/决策/路线图/维护；既有Vault页；私有保全/审查/实际收据。

- [x] 收束C实际/保全/准确Desktop远端发布，以真实C SHA采用；独立builder check通过，冻结seam/精确码表与旧保护文件含原草稿，准备派W1/W2/W3新文件并行。
- [x] 冻结owner源/测试，独立spec+quality review；失败先复现再改、复审差异，保存原记录。统一必要专项与最终完整Python范围，不机械重跑未变UI/browser或捏造效果。
- [x] 另冻新taskroot/新core wheel/新target、所用C accepted结果两包+raw/prepared+其源保护、锁定依赖、runner/observer/argv/cwd/env、各expected exit及预算；不需APIwheel/server/HTTP。core新安装origin与wheel每member/RECORD核验，物理父子exit/reap独立记录。
- [x] 最小候选6个direct child：离线build、install、普通help、evaluate current、evaluate h30、invalidargs负例；total180s/普通child45s/task64MiB/每日志1MiB可作收紧起点，须冻结实际细节后才执行。可加第7个wrong-valid-pair负例，**只在已接受第二合法pair确实可用时**采用，不能为负例新fit/prepare或拿cal0旧Z冒充合法；没跑就NOT_RUN。
- [x] 结果/输入/源完整初始members+bytes+SHA+mtime先落盘，最后复核。actual evaluator/verify/loader计数与saved-score Q99单列；模型fit/score/modelQ99=0，业务进程source CSV内容open=0，禁止producer/replay。controller为保全而读取源hash另计，不能声称整个验收零源读取。独立stdlib读原保存轴/labels/predictions，按test+common手算三个政策counts/ratios/reasons，与两个完整stdout bytes的实际身份与数值核对，不能用新evaluator作oracle。
- [x] 任一意外退出/预算/原件变动/计数不符保留失败停止后续，不重试、不清理或额外生成模型；回收全部已启动进程。无API/UI/browser阶段，将它们明确NOT_RUN而不借旧成功代替。
- [ ] 按实际结果更新公开资料/知识库和维护记录，相关仓库/隐私/作者/进度/链接/diff检查；只Desktop提交推送、核确切远端SHA/README/实际CI，不合main，不循环回填自身SHA。代码/源码测试/只读installed/正式研究分别报告。

## 自检与交付条件

两产品模块职责为pure统计与readonly I/O；没有新报告文件codec、第三生产模块、训练选项、后台任务或页面。五项Review Focus分别落到Task1/2/3。测试封印fixture只证明人工内部一致性，实际安装复用C仍不认证数据或模型；基线核对、W0采用和builder check已完成；功能实现、测试和实际安装已执行；主控已在独立规格和质量后验复核后实际接受；公开资料发布尚待完成。研究Gate保持BLOCKED。


## 执行与发布快照

源码46/117/6切片均包含于完整4746项，不累加。一次core-only七阶段运行退出0/0/0/0/0/2/2，父0、原29成员与325保护项保持；运行数据与边界见[验证记录](../../research/2026-11-11-release-if-evaluation-verification.json)。四个受控业务阶段无新模型或prepare，其保存分数Q99复核6次单列；完整回归不作零模型承诺。

本快照未填写尚未产生的E提交号或CI，主控已实际完成后验接受；公开资料已据接受结果更新，Desktop提交与准确新CI仍待核。root数值状态后继只有私有候选与builder核对，未采用、未实施，不纳入本计划的已完成项。
