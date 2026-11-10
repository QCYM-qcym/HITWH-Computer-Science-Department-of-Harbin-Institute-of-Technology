# Release IF Saved Results Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. 用户指定W0–W3并行、自主工程设计与执行；不再逐项索批。任务只读各自brief及正式spec，不读取整份历史。Git写入由W0通过Desktop统一完成。

**Goal:** 将已接受的release IF内存结果保存、独立重载并用同轴双view只读页面展示，完成安装后的人工工程闭环。

**Architecture:** 纯三文件codec与声明pair绑定→有限磁盘I/O→双包启动前精确匹配/冻结分页API→独立静态页面。core不持久化模型，网页不触发模型；旧契约不变。

**Tech Stack:** 现有锁定Python/NumPy/FastAPI/uvicorn与原生JS/CSS、既有pytest/Vitest；无新增依赖或全新依赖环境承诺。

**Spec:** [结果包](../../design/release-if-result-package-v1.md)、[只读展示](../../design/release-if-result-view-v1.md)。二者是唯一公共契约，旧discovery建议不构成要求。

## Global Constraints

基点8da0a2b4c4ceae4afc64a9a92f3caee12e31c668，沿既有隔离worktree与codex/candidate-flow-adapter。S2/Data Gate BLOCKED、真实C17训练/评分/Q99/正式实验NOT_RUN；不下载/联系作者/真实数据处理、不改标签政策或生产134/268。保留旧Oct31草稿、原包和失败收据，不合并main。此次用户工作截止北京时间2026-11-11 12:00；子阶段完成后继续下一有用工程迭代。

包P、IF R、源/时间/政策固定值均逐字按结果包spec；N1..10000、segments1..7，ID沿上游1..128 Unicode码点。三文件result.json/manifest.json/COMPLETE.json，字节上限1048576/65536/4096，总1118208，Context16384；encode/decode严格canonical UTF8+LF/有限标量/唯一键/精确字段。身份、语义及保存cal分数Q99精确校验，不认证来源/执行。Q99四数精确2.9699999999999998，字面量2.97是1ULP反例。

双view app固定5 GET，source/identity/segments/展开轴/逐位mask和三人口完全匹配；固定0基100行分页，summary16384、series131072、单静态65536、总16777216字节。summary相等/严格超过仅指校准分钟。请求只发送启动前冻结bytes，无load/编码/prepare/重放/fit/score/calibrate/文件访问。UI保持0/false/null区别、源钟面和分区断点，原分数/预测，不发布标签评价或政策/排序/详情控件。

用户授权并发仅用于分离文件owner；共享接口变更由W0裁决并同步。W0统一跑最终完整回归，worker仅适当专项/邻接回归并明确范围，避免并行未完成模块导致伪失败或重复完整模型套件。无运行放行的worker不启动build/install/server/browser或真实数据；公开文件无个人路径/载荷/权重/环境。

## Review Focus

1. 包字节自洽与pair声明绑定不同：自洽改写可通过内部格式，但换身份/轴/人口的显式binding必须拒，不称外部字节认证。
2. preprocessing-fit不必scored：只要求合法train角色及model-train子集；新loader不得误删或误计未评分行。
3. 四数Q99的1ULP/溢出与负零：共享binary64算法精确匹配，literal2.97不能偷用容差；原summary契约不变。
4. Unicode128与10000轴预算：真实最坏编码、码点非UTF16长度、型别先限后遍历，页面不能以64KiB旧限额拒合法新页。
5. 并行/冷请求/取消：错同长度轴/人口不得拼合，首次GET亦零文件/模型调用；非合作fetch/body旧success/error/finally与destroy都无越代DOM写。

### Task 1: Pure result contract and codec — W1

**Files:** Create `src/core/traffic_anomaly/release_if_result_contract.py`, `tests/core/test_release_if_result_contract.py`。可为后续共享独立手写案例另建 `tests/core/release_if_result_cases.py`，只能放测试构造/期望，不把测试钩子放产品。

**Interfaces:** 按包spec全部冻结类型及make/encode/decode/verify，I/O接口在Task2。精确ReleaseSegment内存4字段，JSON才ordinal。

- [x] 先写手算双view/合法segments的独立最小正反例，运行确认缺功能RED；环境/路径错误不记有效RED。用importlib受控导入断言缺模块/公开函数，随后正常直接测试；不依赖生产encoder生成预期哈希或阈值。
- [x] 依次覆盖精确字段/类型/canonical/hash、None/mask/索引/role/前30必要界、preprocessing-fit含非scored（segment offset>=30）且拒前30分钟fit、0/false/负零、错合法identity与pair绑定区别、pair纯验证不进model，写最小codec实现。
- [x] 四校准0/1/2/3精确阈值2.9699999999999998；2.97/2.969预测不变仍拒；single/all-equal/strict>、非有限和溢出、校准外报警不改变校准计数。patch sklearn/model/prepare为forbidden，Q99复核可用现有calibrate但不fit。
- [x] 实际N10000/7segments/128码点Unicode/最长有限float三文件往返与成员及Context限额+1、重复JSON键/UTF8/BOM/recursion/版本错误。先长度/字节限再遍历；encode拒假identity/load_report。
- [x] Run `.venv/Scripts/python.exe -X utf8 -B -m pytest tests/core/test_release_if_result_contract.py tests/core/test_release_iforest.py -q --tb=short`，PYTHONPATH=src/core；报告真实RED/GREEN、次数/时长/警告、精确文件SHA，自评与限制。不得改旧IF source/test。
- [x] W0生成任务diff包，独立spec+quality review，必要修复回合后才能记Task1源码接受。

### Task 2: Fixed disk save/load — W1 fresh task

**Files:** Create `src/core/traffic_anomaly/release_if_result_package.py`, `tests/core/test_release_if_result_package.py`。Task1案例可只读复用，不改其产品接口。

**Interfaces:** 消费Task1公开codec/error/限额，产出 `save_release_if_result_package(package, output_directory)->identity`、`load_release_if_result_package(directory)->package`。load不要求外部输入或模型。

- [x] TDD：临时绝对目录三文件save/load，独立重开、输入保全、已有目标不覆盖；校验失败在mkdir前拒；失败残留保持及COMPLETE后失败仍可能load合法包。
- [x] 覆盖不安全路径/链接/额外成员/预算在open前、文件与目录替换/短读短写/flush或读取异常/最终签名变化；复用现有有限I/O模式，不修改旧包模块、不提炼通用框架。
- [x] 最小实现只读一次已取得bytes再decode，写序COMPLETE最后，禁止清理/恢复/自动重试；安全错误/KeyboardInterrupt保持。
- [x] Run `.venv/Scripts/python.exe -X utf8 -B -m pytest tests/core/test_release_if_result_package.py tests/core/test_release_if_result_contract.py tests/core/test_release_input_package.py tests/core/test_release_minute_package.py -q --tb=short`。只专项与邻接，无build/model/server。
- [x] W0独立spec+quality任务复核；与Task1合并后才声明结果保存/重载源码完成，安装验收另列。

### Task 3: Frozen dual-view backend and foreground CLI — W2

**Files:** Create `src/backend/traffic_api/release_if_result_view.py`, `src/backend/traffic_api/release_if_result_serve_cli.py`, `tests/backend/test_release_if_result_view.py`, `tests/backend/test_release_if_result_serve_cli.py`; modify `src/backend/pyproject.toml` 仅将Task4 `release_if_static/results.html`、`release_if_static/results.mjs`、`release_if_static/results.css`逐个纳入package-data（仓库禁止通配符）。旧API/OpenAPI/输入页不动。

**Interfaces:** factory、错误码、5路由、summary/series字段和CLI flags完全按view spec。CLI调用Task2两个load各一次；factory再纯验包/同轴匹配后预编码全部页与静态资源。

- [x] 先用独立手写两view数据写RED，包括同N不同完整identity/segments/mask/索引拒绝及preprocessing-fit非scored合法，勿只比较count。未到Task1/2时可准备测试，禁止假产品模块兜底依赖。
- [x] 实现冻结summary与100行pages；equal/above仅cal索引，校准外报警只在series；原index/源钟面/角色/全轴break保留。N10000、128 Unicode码点和最大finite分数真实编码在131072/16MiB内，否则RESOURCE_LIMIT不返回app。
- [x] 首个cold GET与重复GET设置load/encode/prepare/fit/score/calibrate/file IO forbidden，验证五routes、安全头、严格query、404/405/422/500冻结安全体；请求不序列化数值对象。
- [x] CLI先load/factory后bind，固定127.0.0.1/8768/300秒默认，端口1..65535、时长1..300；安全help/错误/资源关闭/中断。受控server测试不是实际服务退出证据。
- [x] Run backend新增两文件与旧 `test_release_input_view.py`/`test_release_input_serve_cli.py` 的相关回归，PYTHONPATH=src/core;src/backend；记录不变OpenAPI/旧路由。Task4资源就绪前不虚称最终GREEN。
- [x] W0独立任务review，源码通过与真正前台服务、安装、浏览器另列。

### Task 4: Independent saved-result page — W3

**Files:** Create `src/backend/traffic_api/release_if_static/results.html`, `results.mjs`, `results.css`, `src/frontend/src/__tests__/release-if-result-viewer.test.ts`。不改旧static或Vue四页，package-data交Task3 owner。

**Interfaces:** 按view spec完整summary/series和字节/时间/Unicode规定；公开JS `mountReleaseIFResultView(root, options={})`，destroy handle。独立手写fixture；将新增case摘要写私有报告供W0真实浏览器验证使用，不制造公开运行结果。

- [x] TDD新module缺功能RED→最小双卡/双图/分页表；0/false/null与身份/calsummary范围、缺view/错snapshot/非有限/非法shape拒绝。保留未评分行和未保存具体原因说明。
- [x] 几何独立测试源分区/时间gap/无效断线、singleton、常数/extreme，不混两纵轴，不重造保存prediction；页首全局break可false但不跨页连线。
- [x] 有界Uint8Array流读取summary16384/series131072、10秒全deadline、fatal UTF8/媒体/长度骗报/限额+1/空chunk循环；summary与page独立controller/generation，坏页清旧图区保summary、明确重试，无自动重试。
- [x] 非合作fetch/body旧success/error/finally、deadline、destroy/pagehide、重复mount无监听叠加；所有外部文本安全textContent，Unicode按码点128和上游字符规则；键盘/触屏/横滚/ARIA状态与错误结构。
- [x] Run `npm test -- --run src/__tests__/release-if-result-viewer.test.ts`，并适当旧release input viewer回归、`npm run typecheck`；不安装依赖/启动服务/浏览器。DOM检查不称视觉通过。
- [x] W0独立spec+quality任务review。静态三资源<=65536/个，有界API与Task3联调一致。

### Task 5: Integration, independent review and bounded installed acceptance — W0

**Files:** 私有本plan workspace的source/review/runtime收据，公开新研究验证JSON/运行指南仅依据实际结果写。用户原包/旧收据只读保全。

- [x] 适当专项合跑、一次最终完整本地core/backend/integration/data_audit回归，前端全套/type/build和OpenAPI/仓库维护检查；范围重叠不相加。所有源码冻结后整批独立review，按单一修复波与必要复验处理，不无穷扩审。
- [x] 在任何真实人工pipeline前另写并冻结准确runner/输入/源码/环境/命令与停止条件：复用已知人工A raw/prepared，最多两view各一fit/score/模型阈值Q99用于新save/load链路；codec/save/load/启动的保存分数Q99一致性复核另计，不能声称全轮仅两次Q99；不触真实CSV/prepare/重fit预处理/调参，进程与调用数按实际记。
- [x] 预算候选：新离线core/backend wheel及新target（复用锁依赖），总720秒；普通直接child<=120秒，实际前台serve<=300秒、parent硬限360秒；单日志<=1MiB、新任务文件<=128MiB、无自动重试。精确成员数/实际请求数和传输量按收据，不预填旧常数；不是OS硬配额/连续峰值证明。主控可在冻结准备时收紧，不擅自扩大已冻结轮次。
- [x] 正向：实际fit两view→make/save各一→独立新进程load/verify与完整数值/identity→前台CLI/API两个分页/summary/错误/静态→一个双view实际浏览器（先准备tab再启动300秒服务），窄屏键盘/页0和页1、旧页清理/身份与阈值、无效断线；证明实际物理exit、回收、端口关闭和源/包/安装保全。负向CLI错包配对等不训练，准确计数后放行。
- [x] 独立复核实际产物和原始日志，失败原样保留、未到NOT_RUN；源码单测不替代安装、HTTP或浏览器。无条件满足时不跨Gate拿真实数据兜底。

接受补记（2026-11-11）：原一次控制器因全局bind次数断言退出1，原FAIL保留。九子进程、结果、HTTP及浏览器功能经独立后验对账接受；未重跑业务。第二次127.0.0.1:0绑定用途仅作源代码相容推断；正包独立mtime基线和父精确耗时缺失，均保留null/限制。见[验证记录](../../research/2026-11-11-release-if-results-verification.json)。

### Task 6: Documentation, knowledge and Desktop publication — W0

**Files:** 新指南与验证摘要；维护docs/README、project/status/DECISIONS/ROADMAP/MAINTENANCE_LOG及生成根README；Vault复用既有五页、按其规范保留历史，不新建重复笔记。

- [x] 文档以实际工程状态及研究NOT_RUN分列，检查README生成块和静态正文均一致，源码/人工运行/正式实验不混；原失败和snapshot明确时间，避免旧“未完成”冒认当前。
- [x] 进度生成/一致性、仓库13项、worktree隐私/作者、链接、OpenAPI和diff检查；公共文件不含个人路径/数据/权重/环境。冻结本批文件清单和LF blob SHA，排除原Oct31草稿。
- [ ] 仅GitHub Desktop Commit/Push，核本地/官方ref/远端README/准确SHA实际三CI及job日志；不把Commit或旧CI当同步成功，不回填本提交自身SHA造成循环提交。不合并main。
- [ ] 更新私有ledger/续接入口及Vault准确发布事实。此阶段完成只是里程碑，长期goal保持至用户截止。

### Task 7: Continue useful engineering until deadline — W0 plans next batch

- [ ] 本批接受后依据用户目标与剩余时间选择下一有用交付，优先结果包检查CLI/显式生产人工工程链路，随后评估release输入到AE的适配；每批先独立设计/计划/界限再实施，不将未冻结的backlog当公共接口或已完成。
- [ ] 在北京时间2026-11-11 12:00截止时停止新增工作，保全正在进行状态，完成可安全完成的进程回收和实际交接，统一报告已完成、未完成、NOT_RUN和阻塞。若发布仅因电脑锁屏不可操作，继续本地工作并明确未同步，不改CLI/API推送替代。

## 自检与任务状态

任务1/2/3/4拥有分离产品文件；Task1定义类型给2/3，Task3/4共享只读API且不共改文件。W0拥有设计/共享文档/集成；Task3唯一拥有backend pyproject。五类Review Focus各已有明确反例任务。builder两项已裁决，Unicode兼容/预算同步闭合。初始阶段所有产品实现/新运行验收均NOT_RUN；完成勾选及ledger按实际逐步更新。
