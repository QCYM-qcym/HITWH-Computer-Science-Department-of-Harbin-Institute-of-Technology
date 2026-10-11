> 公开归档副本。保留原文版本与当时状态；当前进度以仓库项目规划和最新报告为准。原始附件与个人信息留在本地。

# 时间感知网络流量异常检测：首批论文阅读建议

日期：2026-09-28。用途：帮助本科毕设解释检测对象、时间信息、特征、模型和实验评价。状态：来源核查与阅读建议，不等于全文精读或复现通过。本轮未下载数据集、训练模型、冻结算法或修改正式文档。

## 先澄清当前方案状态

此前对话中的“5分钟窗口、12个历史窗口、滚动中位数/MAD与Isolation Forest组合”是助手提出的候选示例，不是已经核验的最终方法或论文结论。IF不会自动学习时间顺序；扫描所需的跨连接行为必须由相应输入特征表达；流级与窗口级分数需要先定义对齐和评价单位，不能直接相加。

## 1. Isolation Forest — Liu, Ting, Zhou；ICDM 2008

[作者提供原文](https://cs.nju.edu.cn/zhouzh/zhouzh.files/publication/icdm08b.pdf)；[scikit-learn实现文档](https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.IsolationForest.html)。

论文通过随机划分隔离样本，利用路径长度构造异常评分。适合作为较易解释的机器学习对照。阅读重点：随机树、路径长度、评分方向、阈值与训练数据假设。泛用异常检测方法，不是识别攻击类型的专用分类器。建议产出：用一个二维例子解释异常样本为何容易被隔离，并定义本题每行输入代表流还是窗口。

## 2. Kitsune: An Ensemble of Autoencoders for Online Network Intrusion Detection — Mirsky et al.；NDSS 2018

[原文](https://arxiv.org/abs/1802.09089)；[NDSS PDF](https://www.ndss-symposium.org/wp-content/uploads/2018/02/ndss2018_03A-3_Mirsky_paper.pdf)；[作者代码](https://github.com/ymirsky/Kitsune-py)。

Kitsune把AfterImage增量统计特征与KitNET小型自编码器集成结合，用重构误差评分。优先读特征提取、特征映射、训练/执行阶段与实验。作者代码已含时间衰减统计，因此“加时间信息”本身不能直接称原创。原流程按包提取特征；不能假定NetFlow CSV可以直接送入完整原流程，单独移植KitNET应记录为改编。建议产出：画清输入→特征→模型→分数→阈值→标签对照的链路。

## 3. UGR’16: A New Dataset for the Evaluation of Cyclostationarity-Based Network IDSs — Maciá-Fernández et al.；Computers & Security 73，2018，411–424

[出版社](https://www.sciencedirect.com/science/article/pii/S0167404817302353)；[大学存档](https://digibug.ugr.es/handle/10481/55280)；[作者稿](https://nesg.ugr.es/nesg-ugr16/dataset_AuthorVersionFinal.pdf)。DOI：10.1016/j.cose.2017.11.004。

该数据集论文直接关注网络流量时间周期结构与检测评价，是当前选题的数据依据候选。建议提取采集环境、时间覆盖、背景/攻击流量组成、标签来源、评价划分与限制。原始数据论文不能证明用户将使用的FeatureData衍生版本保留所有字段、连续性或周期性，需要实际审计。建议产出：字段—时间粒度—标签—检测单位对照表。

## 4. Detecting Spacecraft Anomalies Using LSTMs and Nonparametric Dynamic Thresholding — Hundman et al.；KDD 2018

[原文](https://arxiv.org/abs/1802.04431)；[作者代码Telemanom](https://github.com/khundman/telemanom)。DOI：10.1145/3219819.3219845。

方法用LSTM预测时序，再对预测误差实施动态阈值和误报控制。重点学习模型分数如何变成告警，以及动态阈值的输入、更新信息和实验对照；不用立即移植整套LSTM。实验对象是航天器遥测，不是网络攻击数据，其结果不能作为网络检测有效性的证据，也不是MAD+IF方案的原始依据。

## 5. Towards a Rigorous Evaluation of Time-Series Anomaly Detection — Kim et al.；AAAI 2022，36(7)，7194–7201

[AAAI正式论文页面](https://ojs.aaai.org/index.php/AAAI/article/view/20680)；[原文PDF](https://cdn.aaai.org/ojs/20680/20680-13-24693-1-2-20220628.pdf)。DOI：10.1609/aaai.v36i7.20680。

论文指出point adjustment可能高估时序异常检测表现，甚至令随机评分获得夸大的成绩。它适合帮助定义评价程序：明确流级/窗口级/事件级单位，说明异常段命中规则，报告原始预测指标，避免未经说明把整段异常都算命中。本题的按时间切分、验证集定阈值和测试集冻结还需作为独立协议写清，不能把所有这些规则都归因于本文。

## 6. ReCDA: Concept Drift Adaptation with Representation Enhancement for Network Intrusion Detection — Yang et al.；KDD 2024

[KDD官方论文列表](https://www.kdd.org/kdd2024/research-track-papers/)；[出版入口](https://doi.org/10.1145/3637528.3672007)；[作者代码](https://github.com/kalendsyang/ReCDA)。

近期网络入侵检测漂移适应研究，适合作为研究现状和范围比较。仓库区分representation enhancement与constrained tuning任务；应进一步核查训练、适应、标签和更新成本。建议先读问题定义与实验设置，不直接设为本科P0必复现项。动态阈值调整与模型漂移适应不是同一任务。

## 7. Troubleshooting an Intrusion Detection Dataset: the CICIDS2017 Case Study — Engelen, Rimmer, Joosen；IEEE Security and Privacy Workshops / WTMC，2021

[作者项目页面](https://intrusion-detection.distrinet-research.be/WTMC2021/)；[作者原文](https://intrusion-detection.distrinet-research.be/WTMC2021/Resources/wtmc2021_Engelen_Troubleshooting.pdf)。

分析CICIDS2017的数据生成流程、流构造、特征和标注质量。如果继续选CICIDS2017作补充数据，优先读本文，转成字段、标签和工具版本的审计清单。公开CSV不能不经核查就视为无误真值。

## 阅读顺序与每篇交付

先读IF、Kitsune、UGR’16；随后读动态阈值和评价论文；ReCDA用于近期相关工作，CICIDS2017审计文用于备选数据核查。这是针对当前本科任务的推荐顺序，不是论文质量排名。

每篇只先写一页：研究对象和检测单位；输入字段；训练与评分步骤；分数到告警的规则；数据/标签与切分；比较对象和指标；可借鉴之处与不可直接迁移之处。用自己的话重画一张流程图，不能只翻译摘要。

## 核验边界

核对了以上一手论文页面/可解析原文和相关作者仓库。UGR’16作者PDF及NDSS Kitsune PDF直接抓取遇到限制，使用出版社/大学存档、arXiv与作者仓库交叉核验；不得将其记为完成逐页精读。仓库链接存在不代表依赖、数据、硬件兼容或复现结果已经通过。独立核验细节见同目录2026-09-28-paper-evidence.md。
