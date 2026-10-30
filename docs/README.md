# 文档导航

## 候选13维IF合成运行

[运行与五产物](guides/candidate-if-synthetic.md)、[实际阈值/分母/漏报与测试记录](research/2026-10-30-candidate-if-verification.json)。当前只有SYNTHETIC_ONLY工程演练，真实模型/正式实验NOT_RUN，Data Gate BLOCKED。

## 候选产物消费接缝

[不可变快照接口](guides/candidate-snapshots.md)、[实际验证](research/2026-10-30-candidate-snapshots-verification.json)及[第三批计划](superpowers/plans/2026-10-30-candidate-verified-snapshot.md)。同次读取、实际值保留、数组和元数据隔离已经验证；独立候选13维IF尚未实现，真实Gate仍BLOCKED。

## 自主开发第二批入口

[候选产物只读复查](guides/candidate-artifacts.md)、[实际验证](research/2026-10-30-candidate-artifacts-verification.json)及[实施记录](superpowers/plans/2026-10-30-candidate-artifact-verifier.md)。人工产物三政策有/无源6次复查通过；保存参数不重新拟合，缺源不冒称核验。真实Gate仍BLOCKED。

当前自主迭代：[源记录到分钟整链](guides/candidate-records.md)、[具体有限试点建议](research/2026-10-30-limited-pilot-proposal.md)、[10月30日合成证据](research/2026-10-30-candidate-records-verification.json)。仅工程SYNTHETIC_ONLY，真实Gate仍BLOCKED；下方保留前批与真实审计入口。

最近开发：[候选13/26输入计算](guides/candidate-inputs.md)、[自主实施计划](superpowers/plans/2026-10-29-candidate-inputs.md)、[合成数值证据](research/2026-10-29-candidate-inputs-verification.json)。10月29日程序与人工验证完成；真实审计结果及其研究边界见下方，Data Gate仍BLOCKED。

最近真实审计入口：[G13U获准发布记录供应复算](research/2026-10-24-c17-g13u-audit.md)、[完整聚合](research/2026-10-24-c17-g13u-audit.json)、[独立运行与续接](guides/c17-g13u-supply.md)。10月28日已完成本地真实复算：共同开发资格150/88/148、测试1831分钟，供应仍有限；最终标签政策、主数据采用和生产迁移未批准，真实模型及正式实验NOT_RUN。原G12失败证据逐字保留。

修订2026-10-30；用途：当前公开材料与版本对应。报告/答辩均为草稿，待审阅；没有最新稿确认记录。公开文本对应同版本本地原稿，私人路径映射保留本地。

## 当前材料

历史设计记录：[CICIDS2017候选与论文要求对照](research/2026-10-23-cicids-suitability-analysis.md)。当时给出150/90/150理想上界；现已由G12失败证据和本轮G13U实际150/88/148供应补充，未替代数据采用决定。

历史来源记录：[GitHub数据检索与镜像元信息](research/2026-10-23-github-dataset-search.md)。该次只核元信息；随后C17-I1获准获取作者修订版，本轮只复用本地载荷，未改变正式选型或Gate。

历史入口核查：[C17官方入口、生成版本及既有C18-S一致性](research/2026-10-23-c17-source-metadata.md)。原官方归档身份待确认，不与后续实际获取的作者修订版混同；该次无新增载荷或Gate升级。

设计与获取历史：[C17-G12决定包](project/CANDIDATE-DATA-DECISION-2026-10-23.md)、[C18-S四前缀16MiB核查](research/2026-10-23-c18-structure-sample.md)。当前[文件与资源清单](research/2026-10-23-candidate-manifest.json)已登记C17-I1获取及G13U复算，供应审计完成；主数据采用、最终标签和生产迁移仍待决定。

方向选择历史：[协议三路径与决定](project/RESEARCH-PROTOCOL-OPTIONS.md)、[增量证据与候选筛选](research/2026-10-22-data-gate-evidence-update.md)。C方向与G13U审计设计已获准，具体主数据/表示正式采用仍待决定。

Data Gate最新判定：[阻塞核查](project/DATA-GATE-2026-10-21.md)。本轮之后的完整提示见[G13U续接指南](guides/c17-g13u-supply.md)；[preflight](guides/real-validation-preflight.md)保留早期真实验证准备记录。

当前程序见[合成快速运行](guides/quickstart.md)、[W0联调记录](project/W0-SYNTHETIC-INTEGRATION-2026-10-21.md)和[UGR16v3证据核验](research/2026-10-21-UGR16v3-provenance.md)。

| 用途 | 入口 | 状态 |
|---|---|---|
| 开发执行 | [并行开发计划V1.0](superpowers/plans/2026-10-21-parallel-development.md) | 依据V0.40；主控＋三个worktree已交付并顺序合成集成；真实Gate仍阻塞 |
| 开题报告 | [报告V0.40](reports/开题报告-V0.40-公开文本.md) | 公开正文抽取版；草稿，待评审 |
| 报告学习 | [V0.40学习与答辩准备手册](reports/开题报告-V0.40-学习与答辩准备手册.md) | 对应54页Word V1.1，保留原基础内容，新增十图深讲与80项追问 |
| 简短文献综述 | [综述V1.0](reports/时间感知网络流量异常检测文献综述-V1.0.md) | 约千字正文，6篇参考文献 |
| 答辩内容 | [答辩V0.24](reports/开题答辩-V0.24-公开文本.md) | HIT模板；16页主讲＋9页隐藏备用；实际排练待开展 |
| 讲述准备 | [V0.24逐页讲述](reports/开题答辩-V0.24-公开文本.md) | 包含逐页讲稿；实际时长另行登记 |
| 后续工作 | [项目规划](project/ROADMAP.md) | 真实数据Gate阻塞；合成系统已联调，真实训练与实验NOT_RUN |
| 当前进度 | [状态源](project/status.json) | 验收及证据；README由此生成 |
| 范围/风险 | [差异](project/DECISIONS.md) · [风险](project/RISKS.md) | 待对齐不当作已确认 |
| 维护证据 | [复核日志](project/MAINTENANCE_LOG.md) | 本地与远端检查分开 |
| 配图规范 | [项目作图规范](baseline/00-规范与模板/项目作图规范.md) | 沿用项目配色、字体、层级及导出检查 |
| 文字规范 | [报告与 PPT 文字规范](project/WRITING_STYLE.md) | 默认成稿检查，保留事实和学校模板 |
| 当前图形源 | [图集说明](figures/README.md) | V4.0/V5.0保留，新增V6.0技术架构与流程八图 |

## 前期设计基线

以下材料保留当时版本和状态，不自动覆盖最新报告中的方案。后续实现前应核对新报告与旧需求、HLD和验收矩阵的差异。

- [项目立项与需求分析V0.1](baseline/01-项目立项与需求分析/01-项目立项与需求分析-V0.1.md)
- [研究内容与技术方案V0.1](baseline/02-研究与技术方案/02-研究内容与技术方案-V0.1.md)
- [系统概要设计V0.2](baseline/03-系统概要设计/03-系统概要设计-HLD-V0.2.md)
- [实验设计与验收V0.2](baseline/04-实验与验收/04-实验设计与验收方案-V0.2.md)
- [数据需求与数据集设计V0.1](baseline/05-数据设计/05-数据需求与数据集设计-V0.1.md)
- [项目计划与风险V0.2](baseline/06-项目计划与风险/06-项目计划与风险管理-V0.2.md)
- [需求追踪矩阵V0.2](baseline/02-需求分析/D02A-需求追踪矩阵-V0.2.md)

## 研究资料

- [文献与项目调研](research/2026-10-08-毕设相关开源项目与论文调研.md)
- [网络AI与概念漂移文献](research/2026-10-08-literature-network-ai.md)
- [数据集与综述资料](research/2026-10-08-literature-data-surveys.md)
- [时间序列方法资料](research/2026-10-08-literature-foundations-ts.md)

归档文档中的Wiki Links属于本地知识库引用，未在此复制个人知识库。Office/PDF及未审查图片的链接改为文字说明；正文抽取版的图号应配合独立图集阅读。


- [答辩V0.11：15页，恢复V0.32完整配图](reports/开题答辩-V0.11-公开文本.md)

- [开题报告V0.35：恢复V0.32完整配图](reports/开题报告-V0.35-公开文本.md)

- [开题报告V0.36：收缩研究范围与技术细节](reports/开题报告-V0.36-公开文本.md)

- [开题报告V0.37：保留原图与正文简化](reports/开题报告-V0.37-公开文本.md)

- [答辩V0.12：HIT模板与V0.38报告同步](reports/开题答辩-V0.12-公开文本.md)

- [答辩V0.13：开发方案占70%的三分钟版](reports/开题答辩-V0.13-公开文本.md)
- [图集V8.0：结构与视觉优化](figures/V8.0/README.md)

- [答辩V0.14：从需求到联调的开发说明](reports/开题答辩-V0.14-公开文本.md)

- [答辩V0.15：十分钟开题版与计算机专业答疑](reports/开题答辩-V0.15-公开文本.md)

- [答辩V0.16：三分钟八页主讲与六页备用](reports/开题答辩-V0.16-公开文本.md)

- [答辩V0.17：观点与方法版，8页主讲与6页备用](reports/开题答辩-V0.17-公开文本.md)

- [答辩V0.18：本科目录、研究基础与答疑准备](reports/开题答辩-V0.18-公开文本.md)

- [答辩V0.19：场景需求、方法选择与研究论证](reports/开题答辩-V0.19-公开文本.md)

- 上一轮同步材料：[开题报告V0.40](reports/开题报告-V0.40-公开文本.md)、[答辩V0.20与讲稿](reports/开题答辩-V0.20-公开文本.md)、[最小修改记录](reports/开题材料-V0.40-V0.20-最小修改记录.md)。

- 当前答辩版本：[V0.21一图一页版及讲稿](reports/开题答辩-V0.21-公开文本.md)、[拆页记录](reports/开题答辩-V0.21-拆页记录.md)；配套[报告V0.40](reports/开题报告-V0.40-公开文本.md)。

- 当前答辩版本：[V0.22长版分项汇报与讲稿](reports/开题答辩-V0.22-公开文本.md)、[结构与版本记录](reports/开题答辩-V0.22-结构与版本记录.md)；配套报告仍为V0.40。

- 当前答辩版本：[V0.23业务问题与研究主线与讲稿](reports/开题答辩-V0.23-公开文本.md)、[结构与版本记录](reports/开题答辩-V0.23-结构与版本记录.md)；配套报告仍为V0.40。

- 当前答辩：[V0.24公开文本](reports/开题答辩-V0.24-公开文本.md)、[版本记录](reports/开题答辩-V0.24-结构与版本记录.md)。

## 最新有界载荷核查

- [C18-S四前缀16MiB：实际获取、字段、时间与标签](research/2026-10-23-c18-structure-sample.md)：仅结构样本，不认证四段供应，不采用2018为主数据。
