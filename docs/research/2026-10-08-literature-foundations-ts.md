> 公开归档副本。保留原文版本与当时状态；当前进度以仓库项目规划和最新报告为准。原始附件与个人信息留在本地。

# 基础方法与通用时序文献核验（2026-10-08）

研究主题：《面向动态网络环境的时间感知流量异常检测方法研究》，当前工作题名。此文件是开题文献矩阵的背景证据包，不代表用户已精读、方法已选定或复现通过。

## 核验范围

共 22 篇原始方法/工具/基准论文。范围为传统异常检测、深度异常检测、通用多变量时序、动态阈值、漂移基础及工程基准。网络专门方法、数据集论文和综述由其他证据包补充。本轮没有安装库、下载大型数据或训练模型。

优先级 S：建议先理解的候选锚点；A：支撑相关工作/实验设计；B：复杂方法背景及查重。优先级不等于最终模型和必做复现清单。核验分为摘要级、全文局部、源页面；“全文局部”也不是完整精读。未确认 DOI、作者代码为 null，不从第三方复现仓库补造。

输入单位、切分、阈值、评价单位必须一起审计。下列多变量时序工作常用传感器、遥测或资源指标，这些不是网络流、网络包或校园业务流量。跨任务应用属于需要验证的适配。

## 可用于开题的结论与边界

1. Isolation Forest、LOF、One-Class SVM 是不同检测假设的传统对照。它们的原始形式不会因为数据带时间戳就自动利用顺序；本课题必须明确历史特征或阈值更新如何进入链路。[Isolation Forest 原文](https://cs.nju.edu.cn/zhouzh/zhouzh.files/publication/icdm08b.pdf)、[LOF 作者机构页](https://brava.dbs.ifi.lmu.de/publications/676)、[One-Class SVM 作者机构页](https://research.google/pubs/estimating-the-support-of-a-high-dimensional-distribution/)。
2. “AI 是什么”至少需区分隔离评分、单类表示、重构误差、预测残差、重构概率和关联差异。它们检测的异常及分数含义不同，不能在未定义单位/方向/尺度前直接相加。[Deep SVDD](https://proceedings.mlr.press/v80/ruff18a.html)、[DAGMM](https://bzong.github.io/doc/iclr18-dagmm.pdf)、[OmniAnomaly](https://netman.aiops.org/wp-content/uploads/2019/08/OmniAnomaly_camera-ready.pdf)、[Anomaly Transformer](https://arxiv.org/abs/2110.02642)。本句关于融合需先定义单位是研究设计推论。
3. DAGMM 的 KDDCUP 将少数 normal 类视为异常；KDDCUP-Rev 才将抽样的 attack 作为少数异常。它首组实验随机 50%/50% 切分，并以已知异常比例选择高能量样本。因此不能机械引用其 KDDCUP F1 为真实攻击检测或时间外推性能。[原文 §4](https://bzong.github.io/doc/iclr18-dagmm.pdf)。
4. OmniAnomaly 原文将 POT 阈值结果与最佳 F1 分开，并采用 Point Adjustment；作者 README 也列出测试集最佳 F1 搜索。Anomaly Transformer README 明确使用 adjustment。严格毕业设计评价应记录未调整逐点结果，预先限定阈值数据来源；主结果不能用测试真值选阈值。[OmniAnomaly 原文](https://netman.aiops.org/wp-content/uploads/2019/08/OmniAnomaly_camera-ready.pdf)、[作者仓库](https://github.com/NetManAIOps/OmniAnomaly)、[Anomaly Transformer 仓库](https://github.com/thuml/Anomaly-Transformer)。关于主结果规则为本课题设计建议。
5. Telemanom 可启发模型评分之外的阈值与误报控制，但它是航天遥测研究；原文承认实验 Precision 相对实际部署偏乐观，不能直接保证校园网络正常高峰少报或作为 MAD+IF 原创来源。[原文 §3–5](https://arxiv.org/pdf/1802.04431)。
6. ADWIN 对变化作告警，不自动认定攻击；River 提供流式学习工程工具而非唯一算法。需要标签的在线误差评估与重训练仍属于 P1，不能因软件可用就扩张 P0。[ADWIN](https://epubs.siam.org/doi/10.1137/1.9781611972771.42)、[River](https://www.jmlr.org/papers/v22/20-1380.html)。
7. ADBench 主体是表格异常检测，§4.1 使用保留异常比例的分层 70%/30% 切分、三次重复与 ROC-AUC/PR-AUC。其监督/异常类型/污染实验可借鉴，这种切分不能替代本课题时间外推协议。当前不建议搬入其整个实验规模。[ADBench 原文 §4.1](https://arxiv.org/pdf/2206.09426)、[正式出版页](https://papers.neurips.cc/paper_files/paper/2022/hash/cf93972b116ca5268827d575f2cc226b-Abstract-Datasets_and_Benchmarks.html)、[作者仓库](https://github.com/Minqi824/ADBench)。
8. DeepOD 是作者维护的软件库，其当前引用指向 DIF 与 COUTA；本轮未确认独立“DeepOD 原始论文”，因此不把仓库伪装成第 23 篇论文。[作者仓库引用说明](https://github.com/xuhongzuo/DeepOD)。

## 一手来源索引

| ID | 论文/来源 | 年份 | 核验层级 | 作者代码 |
|---|---|---:|---|---|
| FT01 | [Isolation Forest](https://cs.nju.edu.cn/zhouzh/zhouzh.files/publication/icdm08b.pdf) | 2008 | 全文局部 | 未核验 |
| FT02 | [LOF: Identifying Density-Based Local Outliers](https://brava.dbs.ifi.lmu.de/publications/676) | 2000 | 源页面 | 未核验 |
| FT03 | [Estimating the Support of a High-Dimensional Distribution](https://research.google/pubs/estimating-the-support-of-a-high-dimensional-distribution/) | 2001 | 摘要级 | 未核验 |
| FT04 | [Deep One-Class Classification](https://proceedings.mlr.press/v80/ruff18a.html) | 2018 | 摘要级 | [已确认入口](https://github.com/lukasruff/Deep-SVDD-PyTorch) |
| FT05 | [Deep Autoencoding Gaussian Mixture Model for Unsupervised Anomaly Detection](https://bzong.github.io/doc/iclr18-dagmm.pdf) | 2018 | 全文局部 | 未核验 |
| FT06 | [Deep Isolation Forest for Anomaly Detection](https://arxiv.org/abs/2206.06602) | 2023 | 摘要级 | [已确认入口](https://github.com/xuhongzuo/deep-iforest) |
| FT07 | [USAD: UnSupervised Anomaly Detection on Multivariate Time Series](https://www.kdd.org/kdd2020/accepted-papers/view/usad-unsupervised-anomaly-detection-on-multivariate-time-series.html) | 2020 | 摘要级 | [已确认入口](https://github.com/manigalati/usad) |
| FT08 | [Anomaly Transformer: Time Series Anomaly Detection with Association Discrepancy](https://arxiv.org/abs/2110.02642) | 2022 | 摘要级 | [已确认入口](https://github.com/thuml/Anomaly-Transformer) |
| FT09 | [TranAD: Deep Transformer Networks for Anomaly Detection in Multivariate Time Series Data](https://vldb.org/pvldb/vol15/p1201-tuli.pdf) | 2022 | 全文局部 | [已确认入口](https://github.com/imperial-qore/TranAD) |
| FT10 | [Multivariate Time Series Anomaly Detection and Interpretation using Hierarchical Inter-Metric and Temporal Embedding](https://github.com/zhhlee/InterFusion) | 2021 | 源页面 | [已确认入口](https://github.com/zhhlee/InterFusion) |
| FT11 | [Graph Neural Network-Based Anomaly Detection in Multivariate Time Series](https://ojs.aaai.org/index.php/AAAI/article/view/16523) | 2021 | 全文局部 | [已确认入口](https://github.com/d-ailin/GDN) |
| FT12 | [TimesNet: Temporal 2D-Variation Modeling for General Time Series Analysis](https://arxiv.org/abs/2210.02186) | 2023 | 摘要级 | [已确认入口](https://github.com/thuml/TimesNet) |
| FT13 | [Multivariate Time-series Anomaly Detection via Graph Attention Network](https://arxiv.org/abs/2009.02040) | 2020 | 摘要级 | 未核验 |
| FT14 | [Calibrated One-Class Classification for Unsupervised Time Series Anomaly Detection](https://arxiv.org/abs/2207.12201) | 2024 | 摘要级 | [已确认入口](https://github.com/xuhongzuo/DeepOD) |
| FT15 | [Detecting Spacecraft Anomalies Using LSTMs and Nonparametric Dynamic Thresholding](https://arxiv.org/abs/1802.04431) | 2018 | 全文局部 | [已确认入口](https://github.com/khundman/telemanom) |
| FT16 | [Learning from Time-Changing Data with Adaptive Windowing](https://epubs.siam.org/doi/10.1137/1.9781611972771.42) | 2007 | 摘要级 | 未核验 |
| FT17 | [River: machine learning for streaming data in Python](https://www.jmlr.org/papers/v22/20-1380.html) | 2021 | 源页面 | [已确认入口](https://github.com/online-ml/river) |
| FT18 | [PyOD: A Python Toolbox for Scalable Outlier Detection](https://www.jmlr.org/papers/v20/19-011.html) | 2019 | 摘要级 | [已确认入口](https://github.com/yzhao062/pyod) |
| FT19 | [ADBench: Anomaly Detection Benchmark](https://papers.neurips.cc/paper_files/paper/2022/hash/cf93972b116ca5268827d575f2cc226b-Abstract-Datasets_and_Benchmarks.html) | 2022 | 全文局部 | [已确认入口](https://github.com/Minqi824/ADBench) |
| FT20 | [Robust Anomaly Detection for Multivariate Time Series through Stochastic Recurrent Neural Network](https://netman.aiops.org/wp-content/uploads/2019/08/OmniAnomaly_camera-ready.pdf) | 2019 | 全文局部 | [已确认入口](https://github.com/NetManAIOps/OmniAnomaly) |
| FT21 | [LSTM-based Encoder-Decoder for Multi-sensor Anomaly Detection](https://arxiv.org/abs/1607.00148) | 2016 | 摘要级 | 未核验 |
| FT22 | [DCdetector: Dual Attention Contrastive Representation Learning for Time Series Anomaly Detection](https://arxiv.org/abs/2306.10347) | 2023 | 摘要级 | [已确认入口](https://github.com/DAMO-DI-ML/KDD2023-DCdetector) |

## 元数据补充与异常项

- COUTA 正式卷页及 DOI 另核对[新加坡管理大学作者机构出版页](https://smusg.elsevierpure.com/en/publications/calibrated-one-class-classification-for-unsupervised-time-series-/)：TKDE 2024, 36(11):5723–5736。2022 是预印本年。
- DIF 的正式卷页和 DOI 由[作者维护 DeepOD 引用区](https://github.com/xuhongzuo/DeepOD)及[原预印本相关 DOI](https://arxiv.org/abs/2206.06602)交叉确认：TKDE 2023, 35(12):12591–12604。
- USAD DOI、作者和基本方法由[作者机构原文索引](https://www.eurecom.fr/en/publication/6271/download/data-publi-6271_1.pdf)与[作者参与的仓库](https://github.com/manigalati/usad)核对；搜索索引中的原文表 5 确认五个公开数据集和训练速度比较。原 PDF 直接抓取返回 429，切分、阈值及 Point Adjustment 的完整协议保留待全文核验，未写成全文精读。
- TranAD 刊物 PDF 的摘要、正文数据集数量措辞不一致，记录具体列出的数据，但正式矩阵须冻结版本复核，不依摘要数目计量实验。[PVLDB 原文](https://vldb.org/pvldb/vol15/p1201-tuli.pdf)。
- ADBench 正式 proceedings 作者为 Minqi Jiang；仓库 BibTeX 一处为 Mingqi。此文件采用正式稿名字并保留差异记录。[正式 proceedings](https://papers.neurips.cc/paper_files/paper/2022/hash/cf93972b116ca5268827d575f2cc226b-Abstract-Datasets_and_Benchmarks.html)。
- MTAD-GAT 常见社区实现未确认作者身份，故 code_url=null。LSTM Encoder-Decoder 本轮仅确认 arXiv 预印本，不伪标正式会议。

## 可抽取文献对象

字段中“待全文核验”具有明确含义：本轮没有取得足够原文证据，不能默认随机/时间切分、默认固定阈值或默认逐点 F1；unknowns 不是结果。

```json
[
  {
    "id": "FT01",
    "title": "Isolation Forest",
    "year": 2008,
    "authors": [
      "Fei Tony Liu",
      "Kai Ming Ting",
      "Zhi-Hua Zhou"
    ],
    "venue": "IEEE ICDM 2008",
    "doi": null,
    "source_url": "https://cs.nju.edu.cn/zhouzh/zhouzh.files/publication/icdm08b.pdf",
    "code_url": null,
    "group": "传统异常检测基础",
    "priority": "S",
    "problem": "为多维样本建立低成本异常排序。",
    "input_unit": "一个多维实例；映射到网络任务时可是一条流或一个已定义聚合窗口。",
    "datasets": [
      "KDDCUP99、其他公开及合成多维数据；完整列表待精读"
    ],
    "method": "随机子采样建隔离树，以平均路径长度构造异常分数。",
    "temporal_info": "原始模型不显式建模时间顺序。",
    "split": "原文包含随机子采样及正常样本训练实验；不是本课题时间外推协议。",
    "threshold": "主要为异常排序与 AUC；本文分数含 0.5 附近的解释，不能直接作为当前数据的部署阈值。",
    "metrics": "AUC、CPU 处理时间（原文 §5）。",
    "limitation": "输入若没有历史特征，不能仅凭模型名称判断某行为偏离近期模式；异常分数不等于攻击类别。",
    "relevance": "用作轻量非时序对照，检验时间特征/阈值是否提供额外收益。",
    "verification": "全文局部",
    "unknowns": [
      "本地数据规模和时间切分下的性能待实测",
      "原作者代码未核验，常用库实现另行记录"
    ]
  },
  {
    "id": "FT02",
    "title": "LOF: Identifying Density-Based Local Outliers",
    "year": 2000,
    "authors": [
      "Markus M. Breunig",
      "Hans-Peter Kriegel",
      "Raymond T. Ng",
      "Jörg Sander"
    ],
    "venue": "ACM SIGMOD 2000",
    "doi": "10.1145/342009.335388",
    "source_url": "https://brava.dbs.ifi.lmu.de/publications/676",
    "code_url": null,
    "group": "传统异常检测基础",
    "priority": "A",
    "problem": "识别相对邻域密度异常而非只看全局稀少。",
    "input_unit": "多维数据点及其近邻。",
    "datasets": [
      "原文示例与真实数据；具体列表待全文核验"
    ],
    "method": "以局部可达密度及邻域密度比得到 Local Outlier Factor。",
    "temporal_info": "原始算法无显式时间顺序。",
    "split": "待全文核验；不能默认其使用时间切分。",
    "threshold": "输出局部离群程度；具体实验阈值待全文核验。",
    "metrics": "待全文核验。",
    "limitation": "近邻距离、尺度和邻居数会影响结果；历史流量与流级统计需另行定义。",
    "relevance": "为 Isolation Forest 提供密度类对照，帮助区分局部与全局异常。",
    "verification": "源页面",
    "unknowns": [
      "实验数据、切分、阈值与指标待精读",
      "未核验原作者代码"
    ]
  },
  {
    "id": "FT03",
    "title": "Estimating the Support of a High-Dimensional Distribution",
    "year": 2001,
    "authors": [
      "Bernhard Schölkopf",
      "John C. Platt",
      "John Shawe-Taylor",
      "Alex J. Smola",
      "Robert C. Williamson"
    ],
    "venue": "Neural Computation 13:1443–1471",
    "doi": null,
    "source_url": "https://research.google/pubs/estimating-the-support-of-a-high-dimensional-distribution/",
    "code_url": null,
    "group": "传统异常检测基础",
    "priority": "A",
    "problem": "从未标注样本估计分布支持域，识别域外新样本。",
    "input_unit": "一个多维样本。",
    "datasets": [
      "待全文核验"
    ],
    "method": "核函数展开及二次优化构造单类支持向量决策函数。",
    "temporal_info": "无显式序列建模。",
    "split": "待全文核验。",
    "threshold": "决策函数符号划分支持域内外；ν 与核参数的具体设置待全文核验。",
    "metrics": "待全文核验。",
    "limitation": "训练分布、缩放及核参数影响边界；单类学习不自动适应分布漂移。",
    "relevance": "理解正常行为边界及其漂移风险，作为小规模单类对照候选。",
    "verification": "摘要级",
    "unknowns": [
      "正式 DOI 待出版社核验",
      "本地规模计算成本待实测",
      "不把 1999 技术报告年份误作 2001 期刊年份"
    ]
  },
  {
    "id": "FT04",
    "title": "Deep One-Class Classification",
    "year": 2018,
    "authors": [
      "Lukas Ruff",
      "Robert Vandermeulen",
      "Nico Goernitz",
      "Lucas Deecke",
      "Shoaib Ahmed Siddiqui",
      "Alexander Binder",
      "Emmanuel Müller",
      "Marius Kloft"
    ],
    "venue": "ICML 2018, PMLR 80:4393–4402",
    "doi": null,
    "source_url": "https://proceedings.mlr.press/v80/ruff18a.html",
    "code_url": "https://github.com/lukasruff/Deep-SVDD-PyTorch",
    "group": "深度异常检测基础",
    "priority": "A",
    "problem": "使神经表示直接服务于单类异常检测目标。",
    "input_unit": "原文主要为图像实例；时序输入属于后续适配。",
    "datasets": [
      "MNIST",
      "CIFAR-10",
      "GTSRB 对抗样本"
    ],
    "method": "Deep SVDD 将正常数据神经表示约束在紧凑超球体，按中心距离评分。",
    "temporal_info": "原论文不是时间感知网络检测方法；后续加序列编码器需说明适配。",
    "split": "图像单类协议；详细切分待全文核验。",
    "threshold": "中心距离/超球体边界；部署阈值选择待全文核验。",
    "metrics": "待全文核验。",
    "limitation": "原始图像证据不能证明网络流量有效；正常训练数据假设、表示塌缩约束需读方法部分。",
    "relevance": "为 AI 表征与检测目标的关系提供基础，避免把所有 AI 检测都简写为 AE。",
    "verification": "摘要级",
    "unknowns": [
      "原论文方法约束待精读",
      "作者 PyTorch 实现已确认存在但未运行"
    ]
  },
  {
    "id": "FT05",
    "title": "Deep Autoencoding Gaussian Mixture Model for Unsupervised Anomaly Detection",
    "year": 2018,
    "authors": [
      "Bo Zong",
      "Qi Song",
      "Martin Renqiang Min",
      "Wei Cheng",
      "Cristian Lumezanu",
      "Daeki Cho",
      "Haifeng Chen"
    ],
    "venue": "ICLR 2018",
    "doi": null,
    "source_url": "https://bzong.github.io/doc/iclr18-dagmm.pdf",
    "code_url": null,
    "group": "深度异常检测基础",
    "priority": "A",
    "problem": "联合降维和密度估计以保留异常信息。",
    "input_unit": "多维实例；不是原生连续流量序列。",
    "datasets": [
      "KDDCUP",
      "KDDCUP-Rev",
      "Thyroid",
      "Arrhythmia"
    ],
    "method": "AE 编码与重构误差组成低维表示，估计网络联合学习 GMM，按样本能量评分。",
    "temporal_info": "原文基础方法未显式建模时间顺序。",
    "split": "首组实验随机 50% 训练/50% 测试，模型仅用正常类训练（原文 §4.4）。",
    "threshold": "按已知异常比例选择最高能量样本，例如 KDDCUP 的最高 20%。",
    "metrics": "Precision、Recall、F1；多次运行平均。",
    "limitation": "KDDCUP 把少数 normal 当异常，KDDCUP-Rev 才把抽样少数 attack 当异常；随机切分和已知异常比例不是本课题的时间外推/部署协议。",
    "relevance": "学习表征与重构误差的区别，并检查历史论文评价设定是否真正符合网络攻击检测。",
    "verification": "全文局部",
    "unknowns": [
      "最终版本的其他实验设置待精读",
      "原作者代码未核验，不能把第三方复现默认为作者代码"
    ]
  },
  {
    "id": "FT06",
    "title": "Deep Isolation Forest for Anomaly Detection",
    "year": 2023,
    "authors": [
      "Hongzuo Xu",
      "Guansong Pang",
      "Yijie Wang",
      "Yongjun Wang"
    ],
    "venue": "IEEE Transactions on Knowledge and Data Engineering 35(12):12591–12604",
    "doi": "10.1109/TKDE.2023.3270293",
    "source_url": "https://arxiv.org/abs/2206.06602",
    "code_url": "https://github.com/xuhongzuo/deep-iforest",
    "group": "深度异常检测基础",
    "priority": "A",
    "problem": "改善浅层线性隔离的表达能力。",
    "input_unit": "表格、图或时序的适配表示；具体各类张量单位待全文核验。",
    "datasets": [
      "表格、图与时序数据；具体列表待全文核验"
    ],
    "method": "随机初始化神经网络生成多个表示，再在表示空间进行随机隔离。",
    "temporal_info": "时序数据需匹配序列表示实现；不能把任何 DIF 实例都称为时间感知。",
    "split": "待全文核验。",
    "threshold": "待全文核验。",
    "metrics": "待全文核验。",
    "limitation": "随机表示与隔离的改进不等于概念漂移适应；不能默认在 8 GB 显存上复现通过。",
    "relevance": "连接 Isolation Forest 与深度表示，作为相关技术/额外对照候选。",
    "verification": "摘要级",
    "unknowns": [
      "2022 是预印本首发年，正式期刊为 2023",
      "依赖、数据、配置与本地性能未核验"
    ]
  },
  {
    "id": "FT07",
    "title": "USAD: UnSupervised Anomaly Detection on Multivariate Time Series",
    "year": 2020,
    "authors": [
      "Julien Audibert",
      "Pietro Michiardi",
      "Frédéric Guyard",
      "Sébastien Marti",
      "Maria A. Zuluaga"
    ],
    "venue": "ACM KDD 2020:3395–3404",
    "doi": "10.1145/3394486.3403392",
    "source_url": "https://www.kdd.org/kdd2020/accepted-papers/view/usad-unsupervised-anomaly-detection-on-multivariate-time-series.html",
    "code_url": "https://github.com/manigalati/usad",
    "group": "通用时序异常检测",
    "priority": "S",
    "problem": "以较稳定、较快的训练检测多变量时序异常。",
    "input_unit": "多变量时间窗口；具体展平方式和窗口标签规则待全文核验。",
    "datasets": [
      "SWaT",
      "WADI",
      "SMD",
      "SMAP",
      "MSL",
      "Orange 专有数据"
    ],
    "method": "共享编码器/双解码器的自编码框架，通过对抗式训练形成异常评分。",
    "temporal_info": "窗口提供历史上下文；不是原生包级或 NetFlow 攻击检测器。",
    "split": "待全文核验。",
    "threshold": "待全文核验。",
    "metrics": "Precision、Recall、F1 及每 epoch 训练时间；阈值选择和 Point Adjustment 协议待全文核验，不直接复制性能数字。",
    "limitation": "专有可行性实验不能作为用户可获取数据；旧 PyTorch/CUDA 依赖和窗口聚合适配需核验。",
    "relevance": "作为轻量 AE 研究的候选锚点，帮助解释具体输入、重构、评分与工程成本。",
    "verification": "摘要级",
    "unknowns": [
      "作者机构 PDF 本轮直接抓取受限，未假装全文精读",
      "仓库可读，不代表 Windows/（本地设备参数） 可运行"
    ]
  },
  {
    "id": "FT08",
    "title": "Anomaly Transformer: Time Series Anomaly Detection with Association Discrepancy",
    "year": 2022,
    "authors": [
      "Jiehui Xu",
      "Haixu Wu",
      "Jianmin Wang",
      "Mingsheng Long"
    ],
    "venue": "ICLR 2022",
    "doi": null,
    "source_url": "https://arxiv.org/abs/2110.02642",
    "code_url": "https://github.com/thuml/Anomaly-Transformer",
    "group": "通用时序异常检测",
    "priority": "B",
    "problem": "利用时间点的关联模式区分正常与异常。",
    "input_unit": "多变量时间窗口与时间点关联。",
    "datasets": [
      "SMD",
      "MSL",
      "SMAP",
      "PSM",
      "SWaT；完整论文版本列表待核验"
    ],
    "method": "Anomaly-Attention、先验/序列关联差异和 minimax 学习。",
    "temporal_info": "显式建模窗口内时间点关联。",
    "split": "仓库已有数据划分；训练/验证/测试规则待全文与代码联合核验。",
    "threshold": "待全文核验；异常比例参数的来源需另审。",
    "metrics": "作者 README 明确使用 adjustment operation；原始未调整指标与详细定义待核验。",
    "limitation": "Point Adjustment 结果不等同逐点性能；窗口注意力未确认是否满足计划中的因果在线要求。",
    "relevance": "相关工作中展示更复杂时序建模，帮助识别仅使用时间信息已有丰富先例。",
    "verification": "摘要级",
    "unknowns": [
      "仓库评估操作已核验，未运行",
      "因果性、阈值和未调整评价待精读"
    ]
  },
  {
    "id": "FT09",
    "title": "TranAD: Deep Transformer Networks for Anomaly Detection in Multivariate Time Series Data",
    "year": 2022,
    "authors": [
      "Shreshth Tuli",
      "Giuliano Casale",
      "Nicholas R. Jennings"
    ],
    "venue": "Proceedings of the VLDB Endowment 15(6):1201–1214",
    "doi": "10.14778/3514061.3514067",
    "source_url": "https://vldb.org/pvldb/vol15/p1201-tuli.pdf",
    "code_url": "https://github.com/imperial-qore/TranAD",
    "group": "通用时序异常检测",
    "priority": "B",
    "problem": "在复杂时序与有限训练数据下兼顾检测、诊断和效率。",
    "input_unit": "局部多变量窗口及截至当前的上下文。",
    "datasets": [
      "NAB",
      "UCR",
      "MBA",
      "SMAP",
      "MSL",
      "SWaT",
      "WADI",
      "SMD",
      "MSDS；来源版本表述数量不一致，需固定版次复核"
    ],
    "method": "Transformer 序列编码、误差自条件、对抗训练及 MAML 训练方案。",
    "temporal_info": "窗口与位置编码显式引入时间上下文。",
    "split": "正文说明训练序列再分 80% 训练/20% 验证；实际顺序与具体数据版本待代码核验。",
    "threshold": "正文给出评分后阈值判定；具体 POT/配置实现待核验。",
    "metrics": "Precision、Recall、ROC-AUC、F1、训练时间；诊断 HitRate/NDCG。",
    "limitation": "数据版本、选择的子序列、阈值及分段调整需要对齐；多个复杂部件不适宜直接扩大本科 P0。",
    "relevance": "参考效率实验和模块消融，作为复杂时序方法相关工作。",
    "verification": "全文局部",
    "unknowns": [
      "摘要称六个数据集，正文段称七个却列九项；待固定论文版本核验",
      "不采纳其性能提升数字为当前课题保证"
    ]
  },
  {
    "id": "FT10",
    "title": "Multivariate Time Series Anomaly Detection and Interpretation using Hierarchical Inter-Metric and Temporal Embedding",
    "year": 2021,
    "authors": [
      "Zhihan Li",
      "Youjian Zhao",
      "Jiaqi Han",
      "Ya Su",
      "Rui Jiao",
      "Xidao Wen",
      "Dan Pei"
    ],
    "venue": "ACM KDD 2021:3220–3230",
    "doi": null,
    "source_url": "https://github.com/zhhlee/InterFusion",
    "code_url": "https://github.com/zhhlee/InterFusion",
    "group": "通用时序异常检测",
    "priority": "A",
    "problem": "同时建模变量间与时间维度依赖，并解释异常维度。",
    "input_unit": "多变量时间序列窗口。",
    "datasets": [
      "ASD",
      "SMD",
      "SWaT",
      "WADI"
    ],
    "method": "层次 VAE 的随机潜变量分别学习变量间与时间嵌入。",
    "temporal_info": "显式时间嵌入；并行建模变量相关性。",
    "split": "仓库接受独立 train/test/label；具体验证切分与顺序待全文核验。",
    "threshold": "待全文核验。",
    "metrics": "待全文核验。",
    "limitation": "指标异常解释不是攻击原因真值；ASD/SMD 和水处理传感器数据不能直接视为校园网络流数据。",
    "relevance": "帮助明确时间信息与跨特征相关性分别解决什么问题。",
    "verification": "源页面",
    "unknowns": [
      "正式 DOI 待出版社核验；本轮 ACM 跳转受限",
      "旧 TensorFlow/依赖与适配成本未运行核验"
    ]
  },
  {
    "id": "FT11",
    "title": "Graph Neural Network-Based Anomaly Detection in Multivariate Time Series",
    "year": 2021,
    "authors": [
      "Ailin Deng",
      "Bryan Hooi"
    ],
    "venue": "AAAI 2021, 35(5):4027–4035",
    "doi": "10.1609/aaai.v35i5.16523",
    "source_url": "https://ojs.aaai.org/index.php/AAAI/article/view/16523",
    "code_url": "https://github.com/d-ailin/GDN",
    "group": "通用时序异常检测",
    "priority": "A",
    "problem": "检测对传感器间关系的偏离，并提供异常维度线索。",
    "input_unit": "多传感器历史窗口→下一时刻多变量预测。",
    "datasets": [
      "SWaT",
      "WADI"
    ],
    "method": "学习变量图结构、图注意力预测、按预测偏差形成异常分数。",
    "temporal_info": "历史窗口预测与跨变量图关系。",
    "split": "使用正常数据学习；具体验证抽样及时间顺序待全文核验。",
    "threshold": "原文以验证集最大异常分数作为固定阈值。",
    "metrics": "Precision、Recall、F1；模块消融。",
    "limitation": "工业传感器图不等于网络主机拓扑；原文所用机器含多卡不证明复现必需多卡，也不证明 8 GB 实测可行。",
    "relevance": "提供清楚的输入→预测→偏差→阈值实例，参考跨流量统计变量关系。",
    "verification": "全文局部",
    "unknowns": [
      "网络流量图节点/边含义需另行定义",
      "不得把验证集最大值阈值默认为对所有数据最优"
    ]
  },
  {
    "id": "FT12",
    "title": "TimesNet: Temporal 2D-Variation Modeling for General Time Series Analysis",
    "year": 2023,
    "authors": [
      "Haixu Wu",
      "Tengge Hu",
      "Yong Liu",
      "Hang Zhou",
      "Jianmin Wang",
      "Mingsheng Long"
    ],
    "venue": "ICLR 2023",
    "doi": null,
    "source_url": "https://arxiv.org/abs/2210.02186",
    "code_url": "https://github.com/thuml/TimesNet",
    "group": "通用时序建模",
    "priority": "B",
    "problem": "统一表征多周期时间变化。",
    "input_unit": "时间序列窗口转为基于候选周期的二维张量。",
    "datasets": [
      "预测、分类、补全、异常检测任务的多个基准；具体异常检测列表待全文核验"
    ],
    "method": "TimesBlock 自适应选择周期并用二维卷积提取周期内/周期间变化。",
    "temporal_info": "显式建模多周期结构。",
    "split": "待全文核验；不得默认随机划分或直接用于网络流。",
    "threshold": "异常检测任务阈值待全文核验。",
    "metrics": "各任务不同；异常检测指标待全文核验。",
    "limitation": "不能据模型周期机制推断 UGR'16 选定版本必有强日/周周期；其通用任务性能不证明网络入侵收益。",
    "relevance": "供时间特征研究相关工作，说明周期分析须先有数据证据。",
    "verification": "摘要级",
    "unknowns": [
      "2022 预印本与 2023 正式会议年份区分",
      "本地算力、窗口、在线因果性未验证"
    ]
  },
  {
    "id": "FT13",
    "title": "Multivariate Time-series Anomaly Detection via Graph Attention Network",
    "year": 2020,
    "authors": [
      "Hang Zhao",
      "Yujing Wang",
      "Juanyong Duan",
      "Congrui Huang",
      "Defu Cao",
      "Yunhai Tong",
      "Bixiong Xu",
      "Jing Bai",
      "Jie Tong",
      "Qi Zhang"
    ],
    "venue": "IEEE ICDM 2020",
    "doi": null,
    "source_url": "https://arxiv.org/abs/2009.02040",
    "code_url": null,
    "group": "通用时序异常检测",
    "priority": "B",
    "problem": "建模时间与变量依赖，减轻仅独立变量检测的限制。",
    "input_unit": "多变量时间窗口。",
    "datasets": [
      "三个真实数据集；具体名称待全文核验"
    ],
    "method": "MTAD-GAT 并行特征/时间图注意力，联合预测与重构。",
    "temporal_info": "显式时间关联及特征关联。",
    "split": "待全文核验。",
    "threshold": "待全文核验。",
    "metrics": "待全文核验。",
    "limitation": "搜索到的常见 PyTorch 仓库为第三方实现，本轮不标原作者代码；联合预测重构不直接等于创新。",
    "relevance": "为候选双分支方案查重，并参考预测与重构的不同信息来源。",
    "verification": "摘要级",
    "unknowns": [
      "DOI、作者代码、阈值与评估调整待核验",
      "传感器序列到流量序列的适配需独立验证"
    ]
  },
  {
    "id": "FT14",
    "title": "Calibrated One-Class Classification for Unsupervised Time Series Anomaly Detection",
    "year": 2024,
    "authors": [
      "Hongzuo Xu",
      "Yijie Wang",
      "Songlei Jian",
      "Qing Liao",
      "Yongjun Wang",
      "Guansong Pang"
    ],
    "venue": "IEEE Transactions on Knowledge and Data Engineering 36(11):5723–5736",
    "doi": "10.1109/TKDE.2024.3393996",
    "source_url": "https://arxiv.org/abs/2207.12201",
    "code_url": "https://github.com/xuhongzuo/DeepOD",
    "group": "通用时序异常检测",
    "priority": "A",
    "problem": "正常训练数据被潜在异常污染时的单类边界偏差。",
    "input_unit": "多变量时间窗口；具体张量及标签规则待全文核验。",
    "datasets": [
      "十个真实数据集；完整列表待全文核验"
    ],
    "method": "COUTA 用不确定性校准降低污染影响，并生成扰动异常帮助校准正常边界。",
    "temporal_info": "时序窗口；具体编码与因果性待全文核验。",
    "split": "待全文核验。",
    "threshold": "待全文核验；题名校准不能直接读为概率阈值校准。",
    "metrics": "待全文核验。",
    "limitation": "人为扰动能否代表网络攻击需论证；不确定性机制不自动提供漂移适应。",
    "relevance": "提醒训练集是否纯正常需要 Data Gate；可参考污染敏感性实验。",
    "verification": "摘要级",
    "unknowns": [
      "2022 是预印本，2024 为正式 TKDE",
      "DeepOD 是作者维护库中的实现，版本未固定/未运行",
      "DOI/卷页另由作者机构出版页核验"
    ]
  },
  {
    "id": "FT15",
    "title": "Detecting Spacecraft Anomalies Using LSTMs and Nonparametric Dynamic Thresholding",
    "year": 2018,
    "authors": [
      "Kyle Hundman",
      "Valentino Constantinou",
      "Christopher Laporte",
      "Ian Colwell",
      "Tom Soderstrom"
    ],
    "venue": "ACM KDD 2018:387–395",
    "doi": "10.1145/3219819.3219845",
    "source_url": "https://arxiv.org/abs/1802.04431",
    "code_url": "https://github.com/khundman/telemanom",
    "group": "时间阈值与误报控制",
    "priority": "S",
    "problem": "预测遥测行为并从预测误差识别异常，控制运维误报。",
    "input_unit": "遥测通道与历史上下文/指令特征；逐点残差及异常片段。",
    "datasets": [
      "SMAP",
      "MSL"
    ],
    "method": "LSTM 预测、误差平滑、非参数动态阈值搜索及异常片段剪枝。",
    "temporal_info": "历史序列预测；误差历史影响阈值。",
    "split": "专家标注遥测，原文取训练/测试时段；实际切分、阈值缓冲及在线历史界限待完整核验。",
    "threshold": "在平滑残差的均值+z×标准差候选中搜索，按移除高误差后的统计变化及片段数量惩罚选择并剪枝。",
    "metrics": "Precision、Recall、F0.5（片段命中定义需精读）；预测误差。",
    "limitation": "航天遥测不是网络流量；原文承认精度较实际部署乐观，未纳入所有无异常流/时段；不是 MAD+IF 原创依据。",
    "relevance": "直接支持把阈值作为独立研究对象；参考误报/漏报权衡和真实部署限制。",
    "verification": "全文局部",
    "unknowns": [
      "不能把动态阈值本身当新颖方法",
      "本课题仅历史信息阈值需单独定义并验证"
    ]
  },
  {
    "id": "FT16",
    "title": "Learning from Time-Changing Data with Adaptive Windowing",
    "year": 2007,
    "authors": [
      "Albert Bifet",
      "Ricard Gavaldà"
    ],
    "venue": "SIAM SDM 2007:443–448",
    "doi": "10.1137/1.9781611972771.42",
    "source_url": "https://epubs.siam.org/doi/10.1137/1.9781611972771.42",
    "code_url": null,
    "group": "概念漂移基础",
    "priority": "A",
    "problem": "根据变化速度调整保留历史范围，检测分布/概念变化。",
    "input_unit": "顺序到达的数值流/学习误差流。",
    "datasets": [
      "合成与真实数据流；具体列表待全文核验"
    ],
    "method": "ADWIN/ADWIN2 通过子窗口统计差异调整窗口并触发模型更新。",
    "temporal_info": "显式顺序处理和可变历史窗口。",
    "split": "流式评估；具体实验协议待全文核验。",
    "threshold": "由变化检测统计界限及置信参数控制；具体公式/参数待全文核验。",
    "metrics": "论文讨论检测误报/漏报界限；实证指标待全文核验。",
    "limitation": "检测到变化不代表检测到攻击；直接监控模型误差可能需要及时真值标签。",
    "relevance": "为 P1 漂移监测及窗口变化提供基础，不能自行提升为 P0 必做在线重训练。",
    "verification": "摘要级",
    "unknowns": [
      "正式出版 2007，出版站页面上线时间 2013 不是论文年份",
      "原作者代码未核验，River 是另一实现来源"
    ]
  },
  {
    "id": "FT17",
    "title": "River: machine learning for streaming data in Python",
    "year": 2021,
    "authors": [
      "Jacob Montiel",
      "Max Halford",
      "Saulo Martiello Mastelini",
      "Geoffrey Bolmier",
      "Raphael Sourty",
      "Robin Vaysse",
      "Adil Zouitine",
      "Heitor Murilo Gomes",
      "Jesse Read",
      "Talel Abdessalem",
      "Albert Bifet"
    ],
    "venue": "Journal of Machine Learning Research 22(110):1–8",
    "doi": null,
    "source_url": "https://www.jmlr.org/papers/v22/20-1380.html",
    "code_url": "https://github.com/online-ml/river",
    "group": "工程与流式评价",
    "priority": "A",
    "problem": "统一动态数据流机器学习接口与评估工具。",
    "input_unit": "一次一个样本的在线流；是库论文而非单一异常模型。",
    "datasets": [
      "提供流数据生成器/数据集；该论文具体示例待全文核验"
    ],
    "method": "流式学习、变换、性能度量和评估器的统一 Python 架构。",
    "temporal_info": "逐样本流式更新；需要定义先预测后学习顺序与真值可获得时点。",
    "split": "流式/渐进评价支持；不能从库可用性推断本课题协议。",
    "threshold": "依具体检测器；库论文不规定统一异常阈值。",
    "metrics": "依任务/评估器；当前课题指标需独立定义。",
    "limitation": "安装库不等于漂移方法已验证；部分在线监督学习器需要标签，不自动满足无监督 NIDS。",
    "relevance": "为 P1 流式实验与可复现工程提供接口参考，当前不强制引入。",
    "verification": "源页面",
    "unknowns": [
      "2020 为预印本、2021 正式 JMLR",
      "软件当前版与论文描述版本不同，需固定依赖"
    ]
  },
  {
    "id": "FT18",
    "title": "PyOD: A Python Toolbox for Scalable Outlier Detection",
    "year": 2019,
    "authors": [
      "Yue Zhao",
      "Zain Nasrullah",
      "Zheng Li"
    ],
    "venue": "Journal of Machine Learning Research 20(96):1–7",
    "doi": null,
    "source_url": "https://www.jmlr.org/papers/v20/19-011.html",
    "code_url": "https://github.com/yzhao062/pyod",
    "group": "工程与基线实现",
    "priority": "A",
    "problem": "统一多维异常检测算法的调用与工程质量实践。",
    "input_unit": "主要为多维样本矩阵；是工具库论文。",
    "datasets": [
      "库基准/示例；具体论文列表待全文核验"
    ],
    "method": "统一训练、评分 API，提供传统及神经异常算法和测试/可维护性实践。",
    "temporal_info": "2019 论文不建立本课题时间因果协议；新版本支持不应倒推原文。",
    "split": "依调用者设计；论文详细演示待全文核验。",
    "threshold": "依算法及 contamination 等实现配置；不能直接采用测试集异常率。",
    "metrics": "依算法与基准；当前时序/事件评价另定义。",
    "limitation": "统一 API 不保证各算法特征、阈值和标签利用公平；它不是新检测方法。",
    "relevance": "帮助建立可替换 Detector 接口和传统对照实验，减少重复工程。",
    "verification": "摘要级",
    "unknowns": [
      "当前库版本相对原论文已发展，需固定版本",
      "库实现与原作者模型实现不可混同"
    ]
  },
  {
    "id": "FT19",
    "title": "ADBench: Anomaly Detection Benchmark",
    "year": 2022,
    "authors": [
      "Songqiao Han",
      "Xiyang Hu",
      "Hailiang Huang",
      "Minqi Jiang",
      "Yue Zhao"
    ],
    "venue": "NeurIPS 2022 Datasets and Benchmarks Track",
    "doi": "10.52202/068431-2329",
    "source_url": "https://papers.neurips.cc/paper_files/paper/2022/hash/cf93972b116ca5268827d575f2cc226b-Abstract-Datasets_and_Benchmarks.html",
    "code_url": "https://github.com/Minqi824/ADBench",
    "group": "基准与评价设计",
    "priority": "A",
    "problem": "公平比较监督程度、异常类型及数据污染下的算法表现。",
    "input_unit": "表格异常检测实例；不是原生网络时间外推基准。",
    "datasets": [
      "57 个基准：47 个既有+10 个视觉/文本转表示数据（版本待固定）"
    ],
    "method": "30 个算法，多监督程度、异常类型、污染情景与统计比较。",
    "temporal_info": "主要表格设定，不能直接替代时间序列切分。",
    "split": "§4.1：70% 训练、30% 测试，分层抽样保留异常比例；三次独立重复取平均。不是时间外推切分；本课题必须另建时间协议。",
    "threshold": "主比较为 ROC-AUC/PR-AUC 排序评价，无单一决策阈值；若改做 F1/FPR，需要独立规定校准与阈值策略。",
    "metrics": "ROC-AUC、PR-AUC，Wilcoxon-Holm 临界差异比较 p≤0.05；训练与推理时间。PR 积分实现、随机种子及统计检验细节待复现审计。",
    "limitation": "同库运行不自动公平；网络类表格样本不保证具备真实连续时间结构。",
    "relevance": "参考控制变量、污染与监督程度敏感性，不需要照搬 30×57 的实验规模。",
    "verification": "全文局部",
    "unknowns": [
      "正式 proceedings 作者名为 Minqi；repo BibTeX 使用 Mingqi，采用正式稿并记录差异",
      "本地不下载全基准，不宣称复现"
    ]
  },
  {
    "id": "FT20",
    "title": "Robust Anomaly Detection for Multivariate Time Series through Stochastic Recurrent Neural Network",
    "year": 2019,
    "authors": [
      "Ya Su",
      "Youjian Zhao",
      "Chenhao Niu",
      "Rong Liu",
      "Wei Sun",
      "Dan Pei"
    ],
    "venue": "ACM KDD 2019:2828–2837",
    "doi": "10.1145/3292500.3330672",
    "source_url": "https://netman.aiops.org/wp-content/uploads/2019/08/OmniAnomaly_camera-ready.pdf",
    "code_url": "https://github.com/NetManAIOps/OmniAnomaly",
    "group": "通用时序异常检测",
    "priority": "A",
    "problem": "学习多变量正常时序的随机依赖并解释异常维度。",
    "input_unit": "历史窗口→当前多变量时间点的重构概率。",
    "datasets": [
      "SMAP",
      "MSL",
      "SMD"
    ],
    "method": "GRU、VAE、随机变量连接与 planar normalizing flow，按重构概率评分。",
    "temporal_info": "显式历史窗口与随机潜变量的时间依赖。",
    "split": "作者 SMD 前半训练、后半测试，机器分别建模；其他数据具体协议待核验。",
    "threshold": "原文用训练评分 POT 离线阈值；另报告测试标签可计算的最佳 F1，需分开。",
    "metrics": "Precision、Recall、F1（原文采用 Point Adjustment）；解释准确性。",
    "limitation": "Point Adjustment 与最佳测试 F1 不能作为本课题无测试标签调参的逐点结果；SMD 是服务器资源指标而非流数据。",
    "relevance": "学习 GRU/VAE 时序机制、按维度解释，以及将阈值和模型收益分别评价。",
    "verification": "全文局部",
    "unknowns": [
      "旧环境和训练成本待运行",
      "POT 参数与实现完整流程需再审，禁止测试集选阈值作为主结果"
    ]
  },
  {
    "id": "FT21",
    "title": "LSTM-based Encoder-Decoder for Multi-sensor Anomaly Detection",
    "year": 2016,
    "authors": [
      "Pankaj Malhotra",
      "Anusha Ramakrishnan",
      "Gaurangi Anand",
      "Lovekesh Vig",
      "Puneet Agarwal",
      "Gautam Shroff"
    ],
    "venue": "arXiv:1607.00148（本轮仅确认预印本）",
    "doi": null,
    "source_url": "https://arxiv.org/abs/1607.00148",
    "code_url": null,
    "group": "通用时序异常检测",
    "priority": "A",
    "problem": "在不易预测的多传感器时序中用正常行为重构识别异常。",
    "input_unit": "多变量序列窗口。",
    "datasets": [
      "Power demand",
      "Space shuttle",
      "ECG",
      "两个真实发动机数据"
    ],
    "method": "LSTM Encoder-Decoder 学习正常序列，按重构误差判断异常。",
    "temporal_info": "序列编码与重构。",
    "split": "待全文核验。",
    "threshold": "重构误差的异常判定；具体概率/阈值估计待全文核验。",
    "metrics": "待全文核验。",
    "limitation": "论文包含非网络/私有发动机数据；重构误差高不必然是攻击，原文泛化陈述不能替代流量实验。",
    "relevance": "提供预测与重构的清楚对照，支持选择轻量时序 AE 之前理解检测假设。",
    "verification": "摘要级",
    "unknowns": [
      "不将预印本伪标为正式会议发表",
      "作者代码未确认，社区实现需单独标注"
    ]
  },
  {
    "id": "FT22",
    "title": "DCdetector: Dual Attention Contrastive Representation Learning for Time Series Anomaly Detection",
    "year": 2023,
    "authors": [
      "Yiyuan Yang",
      "Chaoli Zhang",
      "Tian Zhou",
      "Qingsong Wen",
      "Liang Sun"
    ],
    "venue": "ACM KDD 2023",
    "doi": null,
    "source_url": "https://arxiv.org/abs/2306.10347",
    "code_url": "https://github.com/DAMO-DI-ML/KDD2023-DCdetector",
    "group": "通用时序异常检测",
    "priority": "B",
    "problem": "用对比表示提高正常/异常可分性，避免仅靠重构。",
    "input_unit": "多尺度多变量时间窗口。",
    "datasets": [
      "多个时序异常基准；具体列表待全文核验"
    ],
    "method": "多尺度双注意力非对称设计、置换环境及纯对比损失。",
    "temporal_info": "多尺度时间关联；在线因果性待核验。",
    "split": "待全文核验。",
    "threshold": "待全文核验。",
    "metrics": "待全文核验，需区分逐点与调整指标。",
    "limitation": "复杂双分支与置换设计已有先例，不能把双分支本身当创新；到网络流量的适配未证明。",
    "relevance": "补充 2023 时序表示相关工作，帮助避免仅以 AE/Transformer 名称更换宣称创新。",
    "verification": "摘要级",
    "unknowns": [
      "DOI 未在一手页面确认，保持 null",
      "作者仓库已读，依赖和评估脚本未运行"
    ]
  }
]
```
