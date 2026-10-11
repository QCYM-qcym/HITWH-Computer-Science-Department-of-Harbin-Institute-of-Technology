> 公开归档副本。保留原文版本与当时状态；当前进度以仓库项目规划和最新报告为准。原始附件与个人信息留在本地。

# 网络流量时间感知异常检测：论文证据核验

核验日期：2026-09-28。状态：阅读建议，未复现实验。本文是主代理调研的补充证据，不冻结算法、窗口或数据集。对话里的 5 分钟、12 个窗口、MAD + Isolation Forest 均只是此前助手提出的候选。

## 1. UGR'16 数据集原论文

- 标题：UGR’16: A New Dataset for the Evaluation of Cyclostationarity-Based Network IDSs。
- 作者：Gabriel Maciá-Fernández、José Camacho、Roberto Magán-Carrión、Pedro García-Teodoro、Roberto Theron。
- 正式卷期：Computers & Security, 73 (2018), 411–424。DOI 带 2017，官网旧引用也写 2017，但正式卷期是 2018 年，引用时应区分在线发布与卷期年份。[出版社原文页](https://www.sciencedirect.com/science/article/pii/S0167404817302353)
- 已核实贡献：提供真实 ISP NetFlow 背景和受控攻击，用于分析长时间演化、昼夜与工作日/周末差异。它是数据与问题定义依据，不是证明本课题任意时间融合方法有效的论文。[出版社原文页](https://www.sciencedirect.com/science/article/pii/S0167404817302353)
- 作者原文：[Author version](https://nesg.ugr.es/nesg-ugr16/dataset_AuthorVersionFinal.pdf)。本次搜索索引可读摘要，但直接打开作者 PDF 抓取失败；不声称完成逐页精读。
- 官方数据说明：3—6 月 calibration 为真实背景，7—8 月 test 为真实背景和生成攻击，按周提供；背景不应不经审计直接理解为逐条确认的干净正常数据。[UGR 官方页面](https://nesg.ugr.es/nesg-ugr16/august.php)
- 对本题帮助（本次判断）：优先阅读介绍时间规律的部分及数据构造、标注部分，决定“研究昼夜周期还是近期变化”以及数据是否支持该目标。
- 边界（本次判断）：NetFlow 不是原始包序列；不能默认得到包间隔、包长方差、双向收发统计等所有 CICFlowMeter 字段。周期性存在不代表任意下载子集或 FeatureData 均保留足够时间信息。下载文件、时间范围、标签、字段仍需 Data Gate。
- 代码：本论文主要贡献为数据集；本次未核验到与原论文一一对应的作者算法代码，不用第三方仓库冒充官方实现。

## 2. Kitsune

- 标题：Kitsune: An Ensemble of Autoencoders for Online Network Intrusion Detection。
- 作者：Yisroel Mirsky、Tomer Doitshman、Yuval Elovici、Asaf Shabtai。
- 发表：NDSS 2018。[官方录用名单](https://www.ndss-symposium.org/ndss2018/accepted-papers/)
- 原文：[NDSS PDF](https://www.ndss-symposium.org/wp-content/uploads/2018/02/ndss2018_03A-3_Mirsky_paper.pdf)；[作者 arXiv](https://arxiv.org/abs/1802.09089)。官方 PDF 18 MB 导致本次工具完整抓取失败，官方索引摘要可读。
- 核心方法：AfterImage 以带衰减的增量统计提取每个包所在网络通道的历史上下文；KitNET 由小型自编码器组成，用重构 RMSE 形成异常分数。[作者代码](https://github.com/ymirsky/Kitsune-py)
- 对本题帮助（本次判断）：最适合学习“原始流量 → 可计算特征 → 模型输入 → 异常分数”的完整链路，帮助回答导师对特征工程、AI 模块的追问。也提醒时间上下文并非新概念，不能把“加入时间”直接当创新。
- 关键边界：作者实现从 pcap/pcapng/派生 tsv 提取包级特征；不能声称在 UGR'16 NetFlow CSV 上开箱即用。仅把 KitNET 接到自定义流特征上属于改编，须说明与原始 Kitsune 输入不同。[作者 README](https://github.com/ymirsky/Kitsune-py)
- 可复现性边界：作者说明训练需要正常数据、存在学习宽限期，随后执行检测；不能把 online 一词自动解释为永远自动适应概念漂移。Python 实现速度不等于论文优化实现性能，依赖与运行速度要实测。[作者 README](https://github.com/ymirsky/Kitsune-py)

## 3. Outside the Closed World

- 标题：Outside the Closed World: On Using Machine Learning for Network Intrusion Detection。
- 作者：Robin Sommer、Vern Paxson；IEEE Symposium on Security and Privacy, 2010。DOI：10.1109/SP.2010.25。[论文原文（大学课程保存版本）](https://gangw.cs.illinois.edu/class/cs562/papers/Closed_World-IDS-sp10.pdf)
- 核心内容：讨论错误成本、训练数据不足、输入变化、评价困难，以及“统计异常”和“实际攻击”之间的解释差距；不是一篇提供新检测模型的实验论文。[原文第 III—IV 节](https://gangw.cs.illinois.edu/class/cs562/papers/Closed_World-IDS-sp10.pdf)
- 对本题帮助（本次判断）：应在写开题前读其挑战与建议部分，明确具体要检出的行为、可观测字段、误报解释及外推边界。高异常分不等于已识别攻击，单条连接的特征也不足以天然证明跨连接扫描行为。
- 边界：2010 年的部署情况不能作为 2026 年市场现状；参考的是研究方法与问题意识。本文不是代码复现对象，未查到需要推荐的官方算法仓库。

## 4. 正常分布漂移的扩展阅读（按需，不增加 P0）

- 标题：Anomaly Detection in the Open World: Normality Shift Detection, Explanation, and Adaptation；Dongqi Han 等，NDSS 2023。[官方论文页](https://www.ndss-symposium.org/ndss-paper/anomaly-detection-in-the-open-world-normality-shift-detection-explanation-and-adaptation/)；[原文 PDF](https://www.ndss-symposium.org/wp-content/uploads/2023-830-paper.pdf)
- 方法：OWAD 针对正常行为分布变化，进行输出校准、分布变化检测、重要样本解释/选择及适应；作者提供 NIDS 自编码器示例。[作者代码](https://github.com/dongtsi/OWAD)
- 对本题帮助（本次判断）：与“正常行为变化造成误报”紧密相关，用来界定近期波动、周期变化与分布漂移，并检查已有工作覆盖到哪里。
- 边界：完整框架包含样本选择及适应，远超单一滚动基线；不能说是完全无人工成本。作者仓库明确其真实 SCADA 部署数据不公开，公开实现不等于所有实验数据均可复现。[作者说明](https://github.com/dongtsi/OWAD)

## 推荐取舍

优先：UGR'16（数据与时间依据）→ Kitsune（特征与 AI 实现链路）。Outside the Closed World 用于完善开题边界与评价。OWAD 为扩展阅读，主代理已有 ReCDA 时可不加入首轮推荐，避免扩展任务。

所有“对本题帮助”“边界推论”均为本次阅读判断，并非原论文对用户课题的实验证明。本轮未下载数据、训练模型或修改 Vault。
