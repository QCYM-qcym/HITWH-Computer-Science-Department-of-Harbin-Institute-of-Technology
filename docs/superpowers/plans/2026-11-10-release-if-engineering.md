# Release IF Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. 不再派代理；独立审查由主控安排。本文件保留2026-11-10实施前计划与阶段勾选记录；实施前的待放行/未执行文字均为历史状态，实际执行及其源版本见文末和公开验证记录。

**Goal:** 用独立内存消费者接通release current13/H30_26到固定工程IF，并守住资格、校准及全轴无效值边界。

**Architecture:** 验证pair/保存资格→剥离无标签数值输入→fit/score→线性Q99/严格比较→不可变全轴结果和有限摘要。旧candidate/134维消费者不动。

**Tech Stack:** 沿现有Python3.14、NumPy2.5.4、可选scikit-learn1.9.1锁依赖；无新增依赖，不安装。已读项目skills/README与scikit-learn入口，不运行其示例、不为Pipeline重新fit预处理、不随机划分或调参。

**Spec:** [release-iforest-engineering-v1.md](../../design/release-iforest-engineering-v1.md)。执行方式由主控已指定；不向用户逐项索批。Git写入全部交主控Desktop。

## Global Constraints

仅 `current13` / `h30_26`；1..10000分钟；两视图共用common、train、cal；16trees/min(32,n_train)/seed42/n_jobs1；预处理fit保持独立；零人口先拒绝；`-score_samples`；Q99/linear/严格>；无效None+mask。人工工程证据与真实研究NOT_RUN分开。

## 本轮前置验收与并行顺序

- [x] A：冻结源与测试，离线构建新core wheel，安装到仓库外新target；只复用既有人工A/Z包及独立旧期望，四例退出0/0/2/2、完整输出、来源与RECORD、前后身份均通过。600秒、单进程120秒、64MiB、无重试；依赖复用既有锁定环境，不称全新依赖安装。已有源码环境通过不能替代本项。
- [x] B：另一worker只读复用已接受旧查看安装和人工包，在浏览器提前就绪后顺序启动两例服务，各300秒计时、360秒硬限，总720秒；实际检查13特征、H15/H30、身份、人口与零校准提示，退出/回收/端口及前后保护均完整。页面未提供26维宽度，包的26维证据单列，不伪称浏览器观察。旧失败和INCOMPLETE_BROWSER原收据不覆盖。
- [x] A/B完成并独立复审后解除源码冻结，执行下方IF消费者任务。W0管设计/集成/发布，W1管安装，W2管模型消费者，W3管浏览器；UI仅一名owner，Git写仅W0 Desktop。
- [ ] 收口：当前范围回归、独立最终审查、公开指南/证据/状态/首页与既有Vault维护；未执行研究保持NOT_RUN。通过GitHub Desktop提交推送，核准确远端SHA、远端README与实际CI，保留原Oct31草稿，不合并main。

## Review Focus

1. dataclass手工改人口或历史：逐项一致性与完整31分钟资格，不能只信mask。
2. 标签泄漏：合法holdout改标签/数值不改训练与阈值；资格检查与数值函数隔离。
3. float32溢出及错误模型输出：构造前拒绝溢出，输出有限、无广播。
4. 无效分钟与空人口：None不计正常；合法零train/cal在模型导入/构造前拒绝。
5. 摘要误认证与身份丢失：原样保留raw_identity/prepared_identity/configuration_sha256，拒绝非法身份结构；状态不认证外部字节、安装、实验、研究权限。

### Task 1：release IF消费者

输入验证、模型调用和摘要是同一两文件交付；由一个owner按1A→1B的RED/GREEN顺序完成，整体独立审查。

#### 1A：输入边界和人口验证

**Files:** 新建 `src/core/traffic_anomaly/release_iforest.py`、`tests/core/test_release_iforest.py`；不修改pair老fixture。

**Interfaces:** 私有 `_validated_inputs(pair, view)` 返回只含数值矩阵/common/索引的私有对象；公开 `ReleaseIFError` 白名单见设计。只复用 `_validate_content` 的纯结构/资格检查，禁用prepare/transform/history统计与文件I/O。

- [x] 写失败测试：合法A手算轴176，train30..47、cal118..127、common56；拒绝宽度/view错、重复/越界/bool/错序索引、mask与indices或sidecar不一致、改policy、train混入cal/test、伪造warmup/common/历史缺口、H30拼接顺序/值错误、超10000分钟。合法空train（预处理fit仍非空而prepared历史全部无效）/空cal分别正确错误，spy构造器及import钩子均0次。
- [x] 加入独立最小反例：31连续分钟才允许首个资格；前30分钟任一attack/unknown可取消训练或校准资格，但不会自行取消common；拒绝仍声称旧资格的pair，接受同步资格正确缩小且训练/校准仍非空的pair。段边界、预热和无效输入另造伪common=True的反例并拒绝。手工fixture的期望直接列整数，不调用产品资格函数生成期望。
- [x] 实现精确验证、数值输入剥离；common有限float64但float32溢出（训练/校准/holdout各一）均构造前拒绝。用spy证明预处理fit和模型train不相等时只取后者。
- [x] 身份反例：pair的raw_identity/prepared_identity若为dict、错精确类型/错profile、hash不是64位小写十六进制、byte_count为bool/0/65537则在构造模型前拒绝；configuration_sha256若非法或与保存configuration的实际hash不一致同样拒绝。不把仅改变为另一个合法包hash称可检测的字节认证。
- [x] 运行新文件专项，确认上述断言通过；不启动正式数据、模型持久化或服务。

#### 1B：模型、阈值、全轴与摘要

**Files:** 同上；按设计导出 `fit_release_iforest`、`summarize_release_iforest`、`ReleaseIFResult`、`ReleaseIFConfiguration`。

**Interfaces:** 消费1A剥离对象；不传sidecar给数值fit/cal/score。结果不含模型；另将pair的 `raw_identity: ReleaseMinutePackageIdentity`、`prepared_identity: ReleaseInputIdentity`、`configuration_sha256: str` 原样传入结果，保留原字段名。

- [x] 先写spy模型行为测试：传入矩阵宽13/26、只有train行fit、common行score、固定参数、同common索引；预处理fit函数和消费者包/CSV/外部数据I/O设置forbidden（不全进程阻断sklearn正常导入的底层文件访问）。合法holdout标签变更并同步sidecar资格后，scores/predictions/scored_mask/三类索引/threshold/configuration一致，三项身份分别等于各自输入（保存包重建可使manifest改变）；holdout数值变化不改fit输入或cal阈值。训练或校准标签变化只经资格验证改变人口，不能宣称所有标签变化均无影响。
- [x] 独立校准例 `[0,1,2,3]` → 2.97；同阈值、nextafter上下边界对应False/True/False；单cal及全部同分有效。上游结构/完整性失败映射INVALID_IF_INPUT，轴/段超限RESOURCE_LIMIT，两个模型人口空时先NO_TRAINING_NORMAL；fit/score调用异常MODEL_ERROR。stub输出NaN/Inf、二维/错长、bool/complex、巨大有限分数导致非有限Q99时安全拒绝。无符号返回值另设成功例：uint8(1)先转float64再取负得到-1.0，不能被归入bool/complex拒绝组。固定负score_samples方向。
- [x] 实现lazy sklearn导入与模型；None全轴、不可变配置/结果；摘要只白名单。测试摘要拒绝伪造预测/非有限或导致预测不一致的阈值/无效None/mask/索引；不把自洽但非原Q99的手构阈值当可检测，train须为preprocessing-fit子集而preprocessing-fit不必为scored子集，未知error不泄漏路径；不存在VERIFIED/ACCEPTED/GATE提升；缺依赖受控错误。
- [x] 身份保持测试：两视图结果identity分别与pair的同名对象 `is` 相同，configuration_sha256逐字相等；摘要两个同名identity字段仅四键 `profile_id/context_sha256/manifest_sha256/manifest_byte_count`，逐字段等于pair，configuration_sha256同名原值。replace结果为非法identity/hash/profile/byte_count时摘要报INVALID_IF_RESULT；replace为结构合法新hash仅能通过结构检查，测试和文案不得声称发现外部字节替换。
- [x] 运行 `.venv/Scripts/python.exe -X utf8 -B -m pytest tests/core/test_release_iforest.py tests/core/test_release_model_inputs.py tests/core/test_release_model_input_cli.py tests/core/test_candidate_iforest.py -q`（沿主控已有环境/PYTHONPATH）；范围重叠不累加。若可选模型依赖缺失明确跳过真实模型单测，不能计作已通过模型验收。

### Task 2：主控放行后，一对有界人工smoke

**Files:** 私有新目录 `w2-if/smoke/` 的runner/receipt，由主控冻结；非公共工具。公开文档及状态更新另由主控安排。

- [x] 在接受Task1/2并由主控解除运行冻结后冻结源码、runner及环境/输入哈希；只使用W1/W3已核过的既有手工A/P_U人工包（176分钟），路径由主控绑定。缺包即失败，禁止prepare/save或新造夹具兜底。消费阶段raw/prepared各load1次后pair1次；不触CSV或真实数据，不重新fit预处理。
- [x] 先从最终冻结源码离线直接setuptools构建新core wheel，再安装到新target，依赖仍复用既有venv；成员/RECORD与来源据实际核对，不预填旧成员数。一个安装后消费子进程、全轮预算180秒/每直接子进程不超过120秒，单次 `current13` 与单次 `h30_26`（预计2fit、2score、2Q99），单线程；不自动重试、不扩大样本、不搜索参数。用窄透明observer原样转发真实sklearn与共享calibrate，只记录调用实参形状/返回，明确CONTROLLED_ACTUAL_SKLEARN_OBSERVATION而非普通无插桩命令；若无法可靠观察则只声明实际API调用及其按代码预期内部次数。记录父/子exit、用时、观察范围及保全。缺依赖/超时保留失败，未到项NOT_RUN。
- [x] 独立验收轴176、common56（30..47/78..87/118..127/158..175）、无效120个None、train18、cal10、预处理fit18；模型宽13/26且相同人口，max_samples18。独立用标准库对10个cal分数排序，阈值 `sorted[8] + 0.91*(sorted[9]-sorted[8])`（合理浮点容差）；逐分数核严格>。不硬编码性能/报警率，不要求两视图分数相同。
- [x] 两视图结果/摘要的raw_identity、prepared_identity、configuration_sha256均与本次实际加载pair逐项相等，identity摘要仅设计规定四字段；不将这些值等同外部来源/数值派生已认证。
- [x] 比较消费前后所有输入包与原Oct31草稿哈希不变；写人工工程收据（源码/安装环境分开），正式研究仍NOT_RUN，Gate仍BLOCKED。本次消费者smoke在新core安装target进行，但复用venv依赖，不称全新依赖环境；它不替代W1配对四例、W3浏览器或真实研究结论。

实施前历史自检（2026-11-10，实施前）：五类Review Focus均有归属；接口名称/类型一致；当时无实现正文、无公共文件、无运行结果预填，所有任务尚未执行。

## 执行收口状态

A新安装四CLI与B两实际浏览器已通过。修订前源版本的Task1源码114专项/278相关和独审、Task2新安装两个真实sklearn人工视图，以及完整本地回归4064通过/20跳过/1既有警告/56子测试，均保留为PRE_FIX_SOURCE_ACCEPTANCE，范围包含专项不相加。整体独立复核已给出spec/quality PASS并列出三项Minor；本次修订收紧保存fit_indices的前置长度检查，并更正接口注解和实施时点文字。新源专项117、相关281通过；最终源全量回归4067通过、20跳过、1既有警告、56子测试。修后首次私有比较器因JSON列表与内存元组直接比较而整轮失败，V2原始失败及缺项保留；只修私有比较器并完成29项比较检查后，V3以新安装、新目录运行通过，完整结果与旧源严格一致。最终源、修订和V3运行独立复核均为spec/quality PASS；人工包两视图各训练18、独立校准10、共同56，实际2fit/2score/2Q99。任务1A/1B及本次修订的真实RED/GREEN、阶段准备错误和两处fixture修正见[公开验证摘要](../../research/2026-11-10-release-iforest-engineering-verification.json)；原失败与私有收据保持。Desktop发布/实际CI由主控随后完成，以最终交付及精确远端工作流为准，不循环回填本提交自身SHA。

截至发布快照：代码、安装、浏览器与独立验收已完成；上述收口复选框因仍包含随后Desktop发布及实际CI而保留未勾选，准确远端结果见最终交付与工作流。
