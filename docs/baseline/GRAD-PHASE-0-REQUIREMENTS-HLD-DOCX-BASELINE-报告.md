> 公开归档副本。保留原文版本与当时状态；当前进度以仓库项目规划和最新报告为准。原始附件与个人信息留在本地。

# GRAD-PHASE-0-REQUIREMENTS-HLD-DOCX-BASELINE 报告

日期：2026-09-25。正式产物根目录：`[本地资料]`。Obsidian：`[本地资料]]\毕业设计`。

## 1. 阶段状态

**READY — REQUIREMENTS_BASELINE_READY。** 内部审查已完成，满足PHASE0设计基线条件。导师尚未审阅V0.1；Data Gate及所有后续研究/系统Gate均为`NOT_RUN`。本结论不代表数据、算法或资源实测通过。

## 2. 正式文档

| 文档 | 版本 | 路径 | 状态 | 页数 |
| --- | --- | --- | --- | ---: |
| D01 项目立项与需求分析 | V0.1 | `01-项目立项与需求分析/01-项目立项与需求分析-V0.1.md`及同名DOCX | DRAFT FOR REVIEW | 10 |
| D02 研究内容与技术方案 | V0.1 | `02-研究与技术方案/02-研究内容与技术方案-V0.1.md`及同名DOCX | DRAFT FOR REVIEW | 9 |
| D03 系统概要设计 HLD | V0.1 | `03-系统概要设计/03-系统概要设计-HLD-V0.1.md`及同名DOCX | DRAFT FOR REVIEW | 8 |
| D04 实验设计与验收方案 | V0.1 | `04-实验与验收/04-实验设计与验收方案-V0.1.md`及同名DOCX | DRAFT FOR REVIEW | 7 |
| D05 数据需求与数据集设计 | V0.1 | `05-数据设计/05-数据需求与数据集设计-V0.1.md`及同名DOCX | DRAFT FOR REVIEW | 4 |
| D06 项目计划与风险管理 | V0.1 | `06-项目计划与风险/06-项目计划与风险管理-V0.1.md`及同名DOCX | DRAFT FOR REVIEW | 4 |

各行所列DOCX与Markdown同名，扩展名为`.docx`。另有学校规范摘要MD/DOCX（2页），非六份正式正文。

## 3. 导师评审包

`07-导师评审包/毕业设计前期方案汇总-导师评审版-V0.1.md`与同名DOCX；10页，6张精选图，**已生成、未发送、未获评审**。页面独立呈现研究动机、RQ、AI及时间信息位置、数据候选、系统结构、实验、风险和下一步。

## 4. 图集

17张图的draw.io、JSON语义源、Mermaid源、SVG和PNG均已生成，位于`08-图集/sources`、`svg`、`png`。源家族均为17份。正式DOCX嵌图数：D01 4、D02 5、D03 7、D04 5、D05 1、D06 1、导师包6。所有Markdown图片路径有效。

| ID | 图名 | 可编辑源 | SVG / PNG | 嵌入文档 |
| --- | --- | --- | --- | --- |
| FIG-01 | 问题背景与研究目标 | sources/FIG-01-*.drawio / .json / .mmd | svg/FIG-01-*.svg; png/FIG-01-*.png | D01、导师包 |
| FIG-02 | 系统上下文 | sources/FIG-02-*.drawio / .json / .mmd | svg/FIG-02-*.svg; png/FIG-02-*.png | D01、D03 |
| FIG-03 | 用例图 | sources/FIG-03-*.drawio / .json / .mmd | svg/FIG-03-*.svg; png/FIG-03-*.png | D01 |
| FIG-04 | 研究技术路线 | sources/FIG-04-*.drawio / .json / .mmd | svg/FIG-04-*.svg; png/FIG-04-*.png | D02、导师包 |
| FIG-05 | 系统总体架构 | sources/FIG-05-*.drawio / .json / .mmd | svg/FIG-05-*.svg; png/FIG-05-*.png | D03、导师包 |
| FIG-06 | 项目部署拓扑 | sources/FIG-06-*.drawio / .json / .mmd | svg/FIG-06-*.svg; png/FIG-06-*.png | D03、导师包 |
| FIG-07 | 核心数据流 | sources/FIG-07-*.drawio / .json / .mmd | svg/FIG-07-*.svg; png/FIG-07-*.png | D03 |
| FIG-08 | 数据处理流程 | sources/FIG-08-*.drawio / .json / .mmd | svg/FIG-08-*.svg; png/FIG-08-*.png | D03、D05 |
| FIG-09 | AI异常检测研究框架 | sources/FIG-09-*.drawio / .json / .mmd | svg/FIG-09-*.svg; png/FIG-09-*.png | D02、导师包 |
| FIG-10 | 实验框架 | sources/FIG-10-*.drawio / .json / .mmd | svg/FIG-10-*.svg; png/FIG-10-*.png | D02、D04 |
| FIG-11 | 对比实验设计 | sources/FIG-11-*.drawio / .json / .mmd | svg/FIG-11-*.svg; png/FIG-11-*.png | D02、D04 |
| FIG-12 | 消融实验设计 | sources/FIG-12-*.drawio / .json / .mmd | svg/FIG-12-*.svg; png/FIG-12-*.png | D02、D04 |
| FIG-13 | 实验生命周期 | sources/FIG-13-*.drawio / .json / .mmd | svg/FIG-13-*.svg; png/FIG-13-*.png | D04 |
| FIG-14 | 异常检测运行时序 | sources/FIG-14-*.drawio / .json / .mmd | svg/FIG-14-*.svg; png/FIG-14-*.png | D03 |
| FIG-15 | 概念数据模型 | sources/FIG-15-*.drawio / .json / .mmd | svg/FIG-15-*.svg; png/FIG-15-*.png | D03 |
| FIG-16 | 需求追踪关系 | sources/FIG-16-*.drawio / .json / .mmd | svg/FIG-16-*.svg; png/FIG-16-*.png | D01 |
| FIG-17 | 项目阶段与Gate | sources/FIG-17-*.drawio / .json / .mmd | svg/FIG-17-*.svg; png/FIG-17-*.png | D04、D06 |

## 5. 需求统计

- FR：17项；全为P0。
- NFR：8项。
- P1：0项强制需求；扩展范围保留为未来路线。
- P2：0项强制需求；扩展范围保留为未来路线。

## 6. 当前 Research Questions

RQ1：所选正常流量是否存在可利用且稳定的时间结构？

RQ2：统计、传统机器学习与轻量AI在相同协议下有何差异？

RQ3：固定AI与调参预算后，时间信息有何增量作用？

RQ4：结果来自哪个分支或融合机制？

候选融合不是已确认的最终方法或创新结论。

## 7. TBD

共26项（TBD-001–TBD-026），已登记问题、重要性、证据、决策触发点及状态。关键项：最终题名/模型/主数据集、窗口与融合策略、阈值、时间切分、性能门槛、答辩部署、工期、资源空间与数据授权条件。

## 8. Risks

共8项（RISK-001–RISK-008），均含Probability、Impact、Mitigation、Fallback、Trigger与Status。High Impact共6项：时间规律不足、方法重合、数据泄漏、工程范围膨胀、同届边界不清、导师要求调整。此为定性计划判断，不是统计估计。

## 9. 一致性检查

- RQ → Experiment：PASS。RQ1–RQ4映射时间结构审计、受控基线、时间信息配对对照、分支/融合消融。
- Research Question → Metric：PASS。Precision、Recall、F1、FPR、PR-AUC及有条件的Detection Latency均有口径。
- Requirement → Design：PASS。17 FR、8 NFR均映射设计模块。
- Design → Test：PASS。需求追踪矩阵列有TC-FR / TC-NFR。
- Test → Acceptance：PASS。测试结果、验收条件及证据列已对应。
- 数据泄漏边界：PASS（设计级）。时间切分优先，测试标签不进入拟合/推理/阈值选择；实测仍未执行。
- 研究线与软件工程线：PASS。AI异常检测是研究核心，系统作为运行、记录和展示验证载体。

未发现重大内部冲突。Fusion、最终模型/数据集、部署与部分实验参数均明确标候选或进入TBD注册表。

## 10. DOCX QA

八份DOCX全部以WPS打开并导出PDF，再将全部页渲染为PNG目视检查；页数总计54。版面、表格、图片、中文/英数分字体、图题、标题、截断和乱码检查：全部PASS。未发现空白页、Mermaid源码泄漏或未解决图片链接。学校指南摘要要求正文中文宋体小四、英文数字Times New Roman，已落实。无动态目录域，标题样式可导航。详细记录：`99-历史版本/生成及质量检查记录-V0.1.md`。

## 11. Obsidian同步

更新：`00-总览/毕业设计-MOC.md`、`00-总览/CURRENT_CONTEXT.md`、`00-总览/Milestones.md`、`12-决策记录/DECISIONS.md`、`12-决策记录/CHANGELOG.md`、`11-导师沟通/导师反馈记录.md`；建立/更新：`09-系统设计/前期设计文档索引.md`、`TBD-Registry.md`、`Risk-Register.md`、`12-决策记录/ADR-PHASE0设计决策.md`、论文映射记录及阶段日志/复盘。索引列明正式文档路径、版本、状态与评审触发条件。未复制整份正式文档到Vault。

## 12. 当前阻塞

PHASE0设计交付无阻塞。导师评审、正式截止时间与答辩环境确认仍待发生；最终模型、主数据集及实测可行性由后续证据决定。

## 13. Gate

**REQUIREMENTS_BASELINE_READY。** 20项PHASE0条件已逐项映射并完成内部核查。该Gate不授权自动执行PHASE1；所有研究验证及系统Gate仍为`NOT_RUN`。

## 14. 下一阶段

PHASE 1 — DATA GATE（仅计划）：确认环境和磁盘空间；取得并固定UGR’16 FeatureData版本与哈希；完成Schema、Timestamp、Missing Value、Temporal Continuity、Label和Temporal Leakage审计；分析日内/周内/长期模式；形成Data Gate Report后判断数据适用性。只有`DATA_GATE_PASS`后才考虑Baseline。本轮没有执行上述工作，现依停止条件结束。
