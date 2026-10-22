# 真实短片段验证准备与下一阶段提示词

更新：2026-10-22。状态：C方向DIRECTION_APPROVED，具体数据/表示待定，准备材料可用，真实执行BLOCKED/NOT_RUN。依据[统一Data Gate判定](../project/DATA-GATE-2026-10-21.md)。现有pipeline仍只允许运行SYNTHETIC_ONLY，不能通过修改报告中的布尔值解锁。

## 有新输入或相关变更时才复跑的核查

本轮官方版本未前移、没有新载荷或解析改动，因此未重复运行下列审计。仅在新证据/文件/实现变化影响既有结论时使用。在忽略的本地配置中指定已存在的五文件目录；不下载或覆盖原数据。PowerShell示例中的占位值由操作者替换：

```powershell
$taskDataRoot = '<既有UGR16v3目录>'
.venv\Scripts\python -m traffic_anomaly.cli audit-provider --mat (Join-Path $taskDataRoot 'UGR16v3.mat') --csv-root $taskDataRoot --report .runtime/data-gate-20261021/recheck.json
# 当前预期退出码2，表示整体Gate仍未满足；不是程序崩溃。
.venv\Scripts\python -m pytest tests/core tests/integration -q
npm --prefix src/frontend run test -- --run
```

报告v2中的train/test指作者全段。project_splits四段NOT_DEFINED，计数null；不能为使CLI可运行而填入随意日期。公开聚合报告不含路径、特征矩阵或逐行标签。

## 真实运行前必须固定的清单

| 项目 | 当前值/状态 |
|---|---|
| 研究路径及批准记录 | 用户已选择C可行性方向；[对照与决定](../project/RESEARCH-PROTOCOL-OPTIONS.md)，具体主数据/表示NOT_SELECTED/NOT_DEFINED |
| 精确数据版本及五文件校验 | 已核实，见data/AUDIT_REPORT.md |
| 使用条件及许可声明关系 | 尚待明确，不公开分发载荷 |
| 原始时间、时区/偏移/DST、桶端点和转换依据 | UNVERIFIED，不设默认 |
| 模型训练/参数验证/独立校准/原测试UTC半开边界 | NOT_DEFINED，不自选片段 |
| 正常候选及共同有效分钟供应 | 每段原始/正常/攻击/背景/未知及当前与历史有效计数，逐方法和窗口交集；作者训练正常2,874不能代替三段供应，测试正常0 |
| 验证目的及协议适用范围 | 工程一致性与正式效果分别登记；新数据独立训练/校准不称泛化，不拼跨集指标 |
| H、epsilon、种子、IF参数、资源上限及片段选择理由 | 真实配置NOT_DEFINED；合成smoke参数不自动沿用 |
| 原始钟面保留、缺口/切分重置、预热状态 | 代码有相应保护；真实配置及转换规则仍需登记 |
| IF真实闭环、AE真实小规模检查 | NOT_RUN，当前无真实运行ID或模型产物 |

选择路径后仍须逐项核查[八项Gate](../project/DATA-GATE-2026-10-21.md#2026-10-22-八项准入复核)。真实短片段启动须满足拟执行阶段全部适用前置条件：数据准入、必要协议决定、四段供应和冻结配置。第6项运行及第7—8项正式评价是分别判定的对象，不把它们的完成状态作为第6项启动前提；验收分母保持。C先核具体发行物、许可、时间和有界获取范围；本轮不选定候选或启动下载。未来具备准入条件后才生成冻结配置与哈希，先IF、不调参搜索；独立输出根、数据库、端口，不覆盖合成产物。各入口优先读取同一份已完成manifest产物，核对run_id、配置、有效分钟、分数、阈值、报警、完整指标与导出。真实短片段仅证明工程链路；零正常时FPR仍null，不做正式效果结论。准入逻辑变更须主控评审并绑定证据，不提供通用跳过开关。

## C方向的有界可行性准备

2026-10-22用户已批准优先核查替换主数据方向，尚未选定数据或表示。CICIDS2017优先检查官方所列GeneratedLabelledFlows与MachineLearningCSV的文件元信息；本轮官方获取页出现个人资料表单和Server error，未提交资料、未得到可验证的压缩包成员/大小。CSE-CIC-IDS2018保留为第二候选，不同步整桶。

下一阶段先完成以下具体交付，未满足时保持相应项BLOCKED：

| 任务 | 有界范围与输出 | 停止条件 |
|---|---|---|
| C-M1 发行物确认 | 限两个既有候选；只读官方清单/HTTP元信息或用户已取得的文件清单。记录URL、版本、字节数和可得校验信息 | 获取要求个人信息提交或访问不可用时登记，不自行提交或换不明镜像 |
| C-M2 时间字段判定 | 查实际发行物是否保留可解释时间戳及流完成依据，明确单位、时区/DST和标签轴；优先核带标签流版本 | 不能认证时间来源时不构造伪连续分钟；缺字段不靠行号恢复 |
| C-M3 样本审计提案 | 列具体文件名/哈希、获取方式、下载与解压上限；建议首轮每候选最多1个小文件或受限片段、合计不超过50 MiB，仅查结构/时间/标签，不训练。该上限是待执行提案，不是已下载大小或授权整包 | 服务器不能提供受限范围、文件超限或必须全包解压时先重提具体方案，不静默升级为全量下载 |
| C-M4 四段供应设计 | 先用元信息判断早期正常与后期混合范围，再以获准载荷逐段统计，固定边界前不引用效果；不从片段样本推断全段供给 | 没有足够独立正常开发/校准/测试或实际连续历史时淘汰/继续阻塞，不拼接正常行 |
| C-M5 迁移决定包 | 输出可选分钟表示、d/2d及标签schema、预处理依据、报告/接口迁移范围和验证清单；保留原契约直到具体决定 | 候选未通过审计时不发布新默认配置，也不宣称适用 |

上述50 MiB限额只为限制初次结构核查成本，不足以证明四段样本充足；若数据已合法在本地，可只读定向核查并登记实际读取范围。真正四段审计与IF运行还需独立准入判定、明确范围及资源预算。

## 供用户自行发送的问题草稿（未发送）

> Subject: Version-specific clarification for UGR16 FeatureData v3
>
> Dear maintainers,
>
> For non-commercial university research, we inspected UGR16v3.mat and its Xtrain/Ytrain/Xtest/Ytest CSVs at commit 760863d31413739a129b3be2d1d52cde217962e8 of UGR16_FeatureData. We do not plan to redistribute the payloads. Could you clarify the following for these exact files?
>
> 1. What timezone/UTC offset and daylight-saving rules apply to obs_l/obs_lt and CSV Row? Does the minute denote interval start or end? Do features and labels use the same flow-time field and bucket convention? Please provide the generating nfdump command, FCParser version/configuration and timezone environment, if available.
>
> 2. We observe 27,697 test rows, all with positive blacklist counts, whereas the README lists 43,200 test rows. What deletion/filtering rules explain the retained range and row count? Is blacklist coverage expected for this exact v3 release? Is there a version-specific erratum or additional official file? We have not treated blacklist as normal. Even an explanation of coverage would not supply normal test samples under our eight-zero-label policy.
>
> 3. The original paper describes blacklist selection using lists from two months before to two months after capture. Does v3 preserve this retrospective annotation unchanged? Is there a known change in label generation or unavailable interval that affects interpretation?
>
> 4. Please give the applicable license name, version and canonical URL separately for the MAT/X feature files and Y label files. The November 2024 DMP (§2.3.1/§2.3.3) states GPL-3.0 for the data, while the 2025 Data paper states Dataset License: CC-BY-NC. Are these alternative licenses, different scopes, or a correction? Which published notice and file version establishes the relationship? Does the 2025-06-24 HTML update concern this issue?
>
> 5. Please distinguish any conditions for original NESG flows, repaired flows, intermediate features and final v3 features/labels. For the final v3 files, what conditions apply to local non-commercial fitting/evaluation and publication of aggregate metrics only? A version-specific public statement would help us document the license chain as well as the permitted use.
>
> Thank you for helping us preserve the original split and avoid unsupported timestamp or label assumptions.

本稿只供用户使用，未发送。作者对事实的答复不能替代研究路径决定；用户选择路径也不能替代作者的时区/许可事实。若不保留UGR16正式实验线，这些问题可保留为原数据阻塞记录，不无限期等待后再考虑新主数据。

## 下一阶段完整提示词

> 请继续毕业设计的“研究协议选择落地与候选数据可行性核查”，不创建新用户聊天。先按AGENTS读取知识库及仓库，核对worktree、分支、未提交修改和远端，从主控本轮最终交付的准确提交安全续接，不假定main已合入。读取RESEARCH-PROTOCOL-OPTIONS、2026-10-22增量证据、当前八项Gate、preflight、需求、报告V0.40和实施计划。
>
> 前置决定：2026-10-22用户已明确选择C可行性方向，selected_path=C、approval_status=DIRECTION_APPROVED，保留误报—漏报核心问题。无需重复询问A/B/C。具体主数据、分钟表示与输入维度仍未批准，dataset_selection=NOT_SELECTED、representation=NOT_DEFINED；先核最新决定，不能把方向批准写成候选通过Gate或导师批准。
>
> 当前UGR16作者训练72,644中正常2,874，测试27,697中正常0、攻击932、仅背景26,765；时区/DST/桶端点及许可关系未解决，四段NOT_DEFINED。澄清时区/许可不会增加正常分母。无新载荷、相关代码变化或影响结论的新证据时，不重跑全量审计，不把背景改正常、不挪训练到测试、不按测试效果选区间、不自行联系作者。
>
> 按C先核候选能否承接原方法问题，再决定主数据与d/2d表示迁移，保留UGR历史。A/B只作备选，不在没有新决定时恢复；独立重训校准不称泛化、不拼跨集分母，正常-only数据不能独立验证完整权衡。CICIDS2017和CSE-CIC-IDS2018当前仅METADATA_ONLY，优先核前者正常日在前的供给线索，后者作第二候选；均未证明适用。
>
> B/C核查须落实具体官方发行物、许可范围、时间及流完成时刻、标签来源、连续正常供给和资源规模，提出明确文件/字节上限的样本获取与四段审计方案。未获准前不大规模下载或训练。流特征不能直接塞入134维契约；若改变维度/标签/预处理，由主控记录批准和兼容迁移，再同步契约、CLI/API/前端及导出。
>
> 仅在拟执行阶段全部适用准入满足、必要协议变更获准、四段与有效历史供应已核查且数据合法在本地时，才冻结片段理由、UTC边界、数据及配置哈希、种子、H/epsilon、缺口/预热规则和资源上限，先做有界IF工程验证。预处理仅拟合训练正常候选；测试不参与选型，独立校准共同正常分数99%分位点、严格超过报警。历史先评分后更新，不跨缺口或分段，不用测试标签删历史，不做point-adjust。保留共同有效分钟和排除计数，不可计算指标null及原因，攻击-only Precision/F1的退化需说明。
>
> 如实际运行，核对同一产物CLI、API、网页及白名单导出的身份/分数/阈值/报警/有效分钟/指标一致。相关修复先失败测试再实现，不为研究阻塞修改代码口径。同步知识库、状态、README、路线图与维护记录；核查、合成、真实工程和正式实验分别记录，未执行NOT_RUN。使用GitHub Desktop提交推送，核对准确远端SHA及实际CI，不合并main。最终交付新增证据、选择及批准依据、分项Gate、验证结果、未决事项和下一完整提示词。
