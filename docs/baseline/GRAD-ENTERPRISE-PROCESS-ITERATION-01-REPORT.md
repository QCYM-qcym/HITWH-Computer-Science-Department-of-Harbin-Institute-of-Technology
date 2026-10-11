> 公开归档副本。保留原文版本与当时状态；当前进度以仓库项目规划和最新报告为准。原始附件与个人信息留在本地。

# GRAD-ENTERPRISE-PROCESS-ITERATION-01 报告

日期：2026-09-27。范围：企业软件工程流程差距审计、文档/架构/实验设计补齐、流程图映射、计划与风险管理更新、Obsidian同步。没有进入正式业务开发或PHASE 1。

## 1. 阶段状态

**READY：文档基线迭代完成。** 当前内部状态为`ENTERPRISE_PROCESS_BASELINE_READY`。这表示要求的过程、设计、跟踪和评审材料已形成并通过文档级检查，不表示选题实测可行、导师批准V0.2、数据Gate通过或详细设计/代码已就绪。

## 2. 审计依据与范围

复核现有D01–D06、D02A、导师评审包、旧SRS/追踪/测试/计划材料、PHASE 0–8研究Gate、学校理工类写作指南（2022年10月版摘要）和已登记导师反馈。学校/学院正式模板为最终写作依据。差距审计见[毕业设计企业流程差距审计-V0.1.md](<00-规范与模板/毕业设计企业流程差距审计-V0.1.md>)。

## 3. 原有正式基线状态

| 文件 | 原版本 | 本轮处理 | 状态 |
|---|---|---|---|
| D01 项目立项与需求分析 | V0.1 | 保留；需求基线仍为参考 | DRAFT FOR REVIEW |
| D02 研究内容与技术方案 | V0.1 | 保留；RQ/研究方案未改写结论 | DRAFT FOR REVIEW |
| D03 系统概要设计 HLD | V0.1 | 增量更新为V0.2 | V0.1保留 |
| D04 实验设计与验收方案 | V0.1 | 增量更新为V0.2 | V0.1保留 |
| D05 数据需求与数据集设计 | V0.1 | 保留；实际数据未审计 | DRAFT FOR REVIEW |
| D06 项目计划与风险管理 | V0.1 | 增量更新为V0.2 | V0.1保留 |
| 导师评审版 | V0.1 | 增量更新为V0.2 | 10页，未发送/待反馈 |

## 4. 本轮正式文档及位置

| 文件 | Markdown | DOCX | 版本/页数/状态 |
|---|---|---|---|
| D03 系统概要设计 HLD | [MD](<03-系统概要设计/03-系统概要设计-HLD-V0.2.md>) | DOCX（原始附件保留本地） | V0.2 / 8页 / DRAFT FOR REVIEW |
| D04 实验设计与验收 | [MD](<04-实验与验收/04-实验设计与验收方案-V0.2.md>) | DOCX（原始附件保留本地） | V0.2 / 8页 / DRAFT FOR REVIEW |
| D06 项目计划与风险 | [MD](<06-项目计划与风险/06-项目计划与风险管理-V0.2.md>) | DOCX（原始附件保留本地） | V0.2 / 3页 / DRAFT FOR REVIEW |
| D02A 需求追踪矩阵 | [MD](<02-需求分析/D02A-需求追踪矩阵-V0.2.md>) | DOCX（原始附件保留本地） | V0.2 / 3页 / 25项DESIGNED / NOT_RUN |
| 导师评审包 | [MD](<07-导师评审包/毕业设计前期方案汇总-导师评审版-V0.2.md>) | DOCX（原始附件保留本地） | V0.2 / 10页 / DRAFT FOR REVIEW |

补充材料：差距审计、六阶段计划、技术决策矩阵、编码规范、Detailed Design Readiness Checklist、部署/答辩方案、缺陷登记、论文映射V0.2、FIG-PM-01、项目管理Dashboard/Action/Blocker/CR/周报模板。工作区总索引为[README.md](<README.md>)。

## 5. 导师评审包

路径：`[本地资料]`，10页，位于用户目标的8–12页范围。独立涵盖研究问题与范围、AI/时间路线、系统逻辑架构、数据候选、实验和验收、软件工程六阶段、风险、候选部署与需导师确认事项。只选择FIG-01/04/05/06/09/17。未发送，未获得本轮反馈。

## 6. 图集与嵌入情况

FIG-01—FIG-17原图均保留：各有可编辑源（draw.io、JSON、Mermaid辅助源）、SVG、PNG。正式图号按论文实际章节另行重编。图源和版式见[图集索引](<08-图集/图集索引.md>)。本轮只新增FIG-PM-01；用既有图映射满足用例、上下文、DFD、概念模型、时序、生命周期等用途，不重复画图。

| ID | 图名 | Source | SVG / PNG | 嵌入正文/评审包 |
|---|---|---|---|---|
| FIG-01 | 问题背景与研究目标 | sources/FIG-01-问题背景与研究目标.drawio/.json/.mmd | svg/、png/FIG-01-问题背景与研究目标 | D01、导师包 |
| FIG-02 | 系统上下文 | sources/FIG-02-系统上下文.drawio/.json/.mmd | svg/、png/FIG-02-系统上下文 | D01、D03 |
| FIG-03 | 用例图 | sources/FIG-03-用例图.drawio/.json/.mmd | svg/、png/FIG-03-用例图 | D01 |
| FIG-04 | 研究技术路线 | sources/FIG-04-研究技术路线.drawio/.json/.mmd | svg/、png/FIG-04-研究技术路线 | D02、导师包 |
| FIG-05 | 系统总体架构 | sources/FIG-05-系统总体架构.drawio/.json/.mmd | svg/、png/FIG-05-系统总体架构 | D03、导师包 |
| FIG-06 | 项目部署拓扑 | sources/FIG-06-项目部署拓扑.drawio/.json/.mmd | svg/、png/FIG-06-项目部署拓扑 | D03、导师包 |
| FIG-07 | 核心数据流 | sources/FIG-07-核心数据流.drawio/.json/.mmd | svg/、png/FIG-07-核心数据流 | D03 |
| FIG-08 | 数据处理流程 | sources/FIG-08-数据处理流程.drawio/.json/.mmd | svg/、png/FIG-08-数据处理流程 | D03 |
| FIG-09 | AI异常检测研究框架 | sources/FIG-09-AI异常检测研究框架.drawio/.json/.mmd | svg/、png/FIG-09-AI异常检测研究框架 | D02、导师包 |
| FIG-10 | 实验框架 | sources/FIG-10-实验框架.drawio/.json/.mmd | svg/、png/FIG-10-实验框架 | D02、D04 |
| FIG-11 | 对比实验设计 | sources/FIG-11-对比实验设计.drawio/.json/.mmd | svg/、png/FIG-11-对比实验设计 | D02、D04 |
| FIG-12 | 消融实验设计 | sources/FIG-12-消融实验设计.drawio/.json/.mmd | svg/、png/FIG-12-消融实验设计 | D02、D04 |
| FIG-13 | 实验生命周期 | sources/FIG-13-实验生命周期.drawio/.json/.mmd | svg/、png/FIG-13-实验生命周期 | D04 |
| FIG-14 | 异常检测运行时序 | sources/FIG-14-异常检测运行时序.drawio/.json/.mmd | svg/、png/FIG-14-异常检测运行时序 | D03 |
| FIG-15 | 概念数据模型 | sources/FIG-15-概念数据模型.drawio/.json/.mmd | svg/、png/FIG-15-概念数据模型 | D03 |
| FIG-16 | 需求追踪关系 | sources/FIG-16-需求追踪关系.drawio/.json/.mmd | svg/、png/FIG-16-需求追踪关系 | D01 |
| FIG-17 | 项目阶段与Gate | sources/FIG-17-项目阶段与Gate.drawio/.json/.mmd | svg/、png/FIG-17-项目阶段与Gate | D04、导师包 |
| FIG-PM-01 | 六阶段相对甘特图 | sources/FIG-PM-01-毕业设计六阶段相对甘特图.json及可编辑SVG | svg/FIG-PM-01-毕业设计六阶段相对甘特图.svg；png/同名.png | D06 V0.2；Obsidian甘特图索引 |

FIG-PM-01的W1–W24仅为相对顺序刻度，不是24周承诺或日历日期。本图没有Mermaid源，避免在未知日期时编造日历排期；SVG和JSON为可编辑源。无效的数字日期Mermaid草稿已移除。

## 7. 需求统计

- 功能需求：17项FR-001–FR-017；D01逐项标记均为P0。
- 非功能需求：8项NFR-001–NFR-008，作为质量约束；原基线没有逐项分配P0/P1/P2。
- P0范围：数据、统计/IF基线、一个轻量AI候选、时间分支/融合对照、实验评价和本地Replay。按FR清单为17项；NFR另列不重复计入。
- P1：第二数据集与扩展实验，为范围项，未拆成可计数FR。
- P2：在线扩展、概念漂移与辅助解释，为范围项，未拆成可计数FR。不得把“未拆分”报告成0项。
- FR/NFR验收和全追踪矩阵见D02A V0.2；所有25项均尚未实现/测试。

## 8. 当前 Research Questions

1. **RQ1：** 所选正常流量是否存在可利用且稳定的时间结构？
2. **RQ2：** 统计、传统ML与轻量AI在相同协议下有何差异？
3. **RQ3：** 固定AI与调参预算后，时间信息有何增量作用？
4. **RQ4：** 结果来自哪个分支或融合机制？

它们映射到E01–E07与指标/证据设计；仍须等待主数据时间戳与标签审计，RQ3/RQ4的可检验性未通过实测确认。

## 9. 端到端追踪结果

- `RQ → Research Content → Experiment → Metric/Evidence`：**PASS（设计映射）**。D02A V0.2含RQ→实验与指标表；D04对应实验/指标/验收设计。
- `Business Need → RQ → FR/NFR → Architecture/Module → Test ID → Evidence → Acceptance`：**PASS（设计映射）**，共25项；共用证据包规则已声明。
- Evidence、测试执行及Gate转换：**NOT_RUN**。没有实际运行记录可判PASS。
- 数据是否能支持RQ1/RQ3、模型是否带来效果、时间信息是否增益：**未验证**，属于Data/Model/Experiment Gate。
- 研究线与软件线当前由D01/D02/D03/D04和RTM连通；原型定位为方法实验与结果审计的验证载体，不以功能数量替代研究。
- 与同届《网络流量基线监测系统设计与实现》的详细边界尚需任务书/导师确认，不对未知技术栈作推断。

## 10. TBD登记

当前共28项：原TBD-001–TBD-026全部保留；本轮新增TBD-027测试覆盖率目标、TBD-028学院/专业最终论文目录结构。关键未决项包括最终题名、主数据/许可、Schema/时间/检测单位、AI模型、窗口/融合/阈值、数据库/服务边界、性能目标、预算/工期与答辩部署。全部按注册表设置Question/Why/Evidence/Decision Deadline/Status。

## 11. 风险登记

共8项RISK-001–008，全部OPEN；其中高影响6项：RISK-001时间规律/数据、003研究重合、004时间泄漏、006范围膨胀、007同届边界、008导师调整。概率目前全部Medium，属于设计阶段定性判断；没有依据写成High或下调。RISK-005已补记实际开发机8GB专用显存与数据规模未实测的区别。

## 12. 文档一致性复核

| 检查 | 结果 | 边界 |
|---|---|---|
| RQ→Experiment/Metric | PASS | 只确认设计映射，不是实验结论 |
| Requirement→Design Module | PASS | 25项已分配逻辑模块 |
| Design→Test | PASS | TC-FR/TC-NFR及研究不变量有编号/检查方案 |
| Test→Acceptance | PASS | 证据、验收条件可追踪；执行均NOT_RUN |
| Dataset支持RQ | NOT_VERIFIED | 尚未审计具体文件/时间戳/标签/许可 |
| AI位于核心检测链路 | PASS（设计定位） | 候选模型和效果未冻结/验证 |
| Prototype定位 | PASS（设计定位） | 作为实验验证载体，不是生产NIDS |
| 内部重大矛盾 | 未发现 | 导师/学校评审仍可能要求变更 |
| 同届课题边界 | PARTIAL | 已标明关注差异；需任务书和导师确认 |

## 13. DOCX视觉QA

| DOCX | 页数 | 结果 | 检查内容 |
|---|---:|---|---|
| D03 HLD V0.2 | 8 | PASS | 标题/页眉、表格、系统图、DFD/流程、序列/概念模型、交叉引用与末页 |
| D04实验验收V0.2 | 8 | PASS | Gate表、指标/验收表、实验图、跨页表头、页面完整性 |
| D06项目计划V0.2 | 3 | PASS | 六阶段表、相对甘特图、风险表和交付段落 |
| D02A RTM V0.2 | 3 | PASS | 25项矩阵可读、页间不拆断单条记录、RQ表与追踪规则 |
| 导师评审版V0.2 | 10 | PASS | 8–12页目标、六张精选图、表格、来源附注和末页 |

上述文件均由WPS导出PDF并使用DOCX渲染流程生成页图，在100%尺寸下逐页检查。中间QA文件在`[本地资料]`，不是正式交付内容。上一轮V0.1 QA记录仍在历史记录中；本表只评本轮V0.2。

## 14. Obsidian同步

Vault：`[本地资料]]/毕业设计`。更新了CURRENT_CONTEXT、MOC、Milestones、DECISIONS/Decision-009、七份ADR、CHANGELOG、前期设计文档索引、TBD-Registry（新增027/028）、Risk-Register（复审记录）、导师沟通状态、论文映射记录，以及研究日志/阶段复盘/导师反馈待审记录。新建`15-项目管理`中的Status-Dashboard、Action-Items、Blockers、Change-Requests、2026-W39周报和FIG-PM-01索引。没有复制整套正式文档进Vault。

## 15. 资源、算力、时间与预算

开发机截图登记：AMD （本地设备参数）（6核/12线程）、（本地设备参数） （本地设备参数）、NVIDIA （本地设备参数） 8GB专用显存、Windows；另有AMD集显。截图当时C/D/E剩余约67.3/137/902GB，需复核当前和可分配空间。答辩电脑未知，WSL/Docker、长期可用性、学校/个人服务器、云GPU、API预算、正式截止日期、每周投入均未知。P0设计不依赖大型模型、多GPU或昂贵商业API；即使有（本地设备参数），目标数据/模型耗时和显存仍待实测，因此不报告“已确认算力可行”。W1–W24只表达相对顺序，不是工期估计。

## 16. 决策、ADR与变更控制

已记录CR-001（本次流程基线增量）；V0.1原文件不覆盖。Decision-009采用六阶段交付视图叠加旧PHASE Gate，并保持迭代回退。ADR-001–007记录研究原型与生产监控分离、AI在核心检测链路、P0不引Kafka、数据库暂不冻结、优先时间切分、模块化Detector Interface及单机原型部署；各为待评审设计决定，不代表技术实现冻结。后续导师意见/数据证据触发变更和新版本。

## 17. 当前阻塞

1. 学校正式截止/任务书/开题日、周投入和总预算未知；日历工期无法承诺。
2. UGR'16具体FeatureData未本地锁定和审计；不能通过Data Gate。
3. 答辩电脑、联网、安装权限与Demo现场约束未知。
4. Schema、模型评分契约、窗口/融合/阈值、服务边界未验证；LLD保持`NOT_READY_FOR_LLD`。
5. V0.2导师评审未进行；本轮未发送评审材料。

这些是前置证据缺失，不代表失败实验或软件缺陷。Defect-Register为空模板，因为尚无测试运行。

## 18. Gate结论与下一阶段

- `REQUIREMENTS_BASELINE_READY`：**内部文档核查通过，可供评审**；不表示导师签字。
- `DESIGN_BASELINE_READY`：**内部设计文档可进入PHASE 1计划**；详细设计清单仍未通过，代码尚未授权/启动。
- `TOPIC_FEASIBILITY_READY`：**NOT_READY/未通过**，时间、数据/预算与答辩条件仍缺证。
- `ENTERPRISE_PROCESS_BASELINE_READY`：**READY**。
- 下一阶段只规划为**PHASE 1 — DATA GATE**。计划包括核实当前数据盘/Windows/WSL/Docker、锁定UGR'16 FeatureData文件及哈希/许可、审计Schema/Timestamp/Missing/Continuity/Label/24h/weekday-weekend/long-term/leakage，并出Data Gate Report。本轮没有执行这些步骤；Baseline须等`DATA_GATE_PASS`后。

**停止边界：** 本轮到此结束，等待用户审阅V0.2和导师意见；没有自动进入PHASE 1，没有下载/训练/代码/提交。
