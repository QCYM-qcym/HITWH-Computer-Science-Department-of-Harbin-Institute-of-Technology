> 公开归档副本。保留原文版本与当时状态；当前进度以仓库项目规划和最新报告为准。原始附件与个人信息留在本地。

# 网络AI、时间动态与概念漂移文献核验

- 核验日期：2026-10-08。
- 研究上下文：《面向动态网络环境的时间感知流量异常检测方法研究》。UGR16为主数据候选，Isolation Forest与轻量AE为拟验证起点，尚未完成Data Gate/训练/复现。
- 本文件核验24个出版/研究条目，按题名去重；ReCDA会议与期刊版本属于同一家族，因此不等于24种独立方法。STAD为通用流式参考，DeepAID/OWAD/CADE含多种安全任务，不应全部算成网络专用方法。E2D2仅取得作者仓库的一手说明，正式出版尚待核验。
- S/A/B是阅读优先级；S不意味着必须复现。全部本机运行状态均为source-verified-not-run，未据此确认8GB GPU硬件可行性。
- 只使用出版社、会议、作者PDF/仓库及所属大学的一手记录。空DOI/代码为未核实，不表示不存在。摘要核验不等于全文精读；unknowns保留待查信息。
- 所列局限同时包含原文可见边界和面向本课题的审计判断；后者不是原作者的实验结论。论文性能不横向排序，不据此宣称创新或固定最终方法。

## 证据入口

| ID | 年份 | 优先级 | 论文一手来源 | 代码性质 |
| --- | --- | --- | --- | --- |
| NA01 | 2018 | S | [Kitsune: An Ensemble of Autoencoders for Online Network Intrusion Detection](https://arxiv.org/abs/1802.09089) | [仓库](https://github.com/ymirsky/Kitsune-py) |
| NA02 | 2018 | A | [N-BaIoT: Network-based Detection of IoT Botnet Attacks Using Deep Autoencoders](https://arxiv.org/abs/1805.03409) | 未核实 |
| NA03 | 2024 | S | [Network traffic anomaly detection model based on feature grouping and multi-autoencoders integration](https://ietresearch.onlinelibrary.wiley.com/doi/10.1049/ell2.70103) | 未核实 |
| NA04 | 2024 | S | [Enhancing Network Traffic Anomaly Detection: Leveraging Temporal Correlation Index in a Hybrid Framework](https://dro.deakin.edu.au/articles/journal_contribution/Enhancing_Network_Traffic_Anomaly_Detection_Leveraging_Temporal_Correlation_Index_in_a_Hybrid_Framework/28620866) | 未核实 |
| NA05 | 2023 | S | [Robust unsupervised network intrusion detection with self-supervised masked context reconstruction](https://jiansonglei.github.io/files/22RobustIDS.pdf) | 未核实 |
| NA06 | 2024 | S | [Renyi entropy-driven network traffic anomaly detection with dynamic threshold](https://link.springer.com/article/10.1186/s42400-024-00249-1) | 未核实 |
| NA07 | 2024 | A | [ReCDA: Concept Drift Adaptation with Representation Enhancement for Network Intrusion Detection](https://hub.hku.hk/handle/10722/362496) | [仓库](https://github.com/kalendsyang/ReCDA) |
| NA08 | 2025 | A | [Self-Supervised Adaptation Method to Concept Drift for Network Intrusion Detection](https://ece.hku.hk/people/echngai/) | [仓库](https://github.com/kalendsyang/ReCDA) |
| NA09 | 2021 | A | [CADE: Detecting and Explaining Concept Drift Samples for Security Applications](https://www.usenix.org/conference/usenixsecurity21/presentation/yang-limin) | [仓库](https://github.com/whyisyoung/CADE) |
| NA10 | 2022 | A | [ENIDrift: A Fast and Adaptive Ensemble System for Network Intrusion Detection under Real-world Drift](https://researchportal.hkust.edu.hk/en/publications/enidrift-a-fast-and-adaptive-ensemble-system-for-network-intrusio-2/) | [仓库](https://github.com/X1anWang/ENIDrift) |
| NA11 | 2023 | B | [HorusEye: A Realtime IoT Malicious Traffic Detection Framework using Programmable Switches](https://www.usenix.org/conference/usenixsecurity23/presentation/dong-yutao) | 未核实 |
| NA12 | 2021 | A | [Realtime Robust Malicious Traffic Detection via Frequency Domain Analysis](https://arxiv.org/abs/2106.14707) | [仓库](https://github.com/fuchuanpu/Whisper) |
| NA13 | 2024 | A | [NetVigil: Robust and Low-Cost Anomaly Detection for East-West Data Center Security](https://www.usenix.org/conference/nsdi24/presentation/hsieh) | [仓库](https://github.com/microsoft/Yatesbury) |
| NA14 | 2025 | A | [CAEAID: An incremental contrast learning-based intrusion detection framework for IoT networks](https://www.sciencedirect.com/science/article/pii/S138912862500129X) | 未核实 |
| NA15 | 2025 | A | [DUdetector: A dual-granularity unsupervised model for network anomaly detection](https://www.sciencedirect.com/science/article/pii/S1389128624007692) | [仓库](https://github.com/qi-yun/DUdetector) |
| NA16 | 2025 | A | [CDDA-MD: An efficient malicious traffic detection method based on concept drift detection and adaptation technique](https://www.sciencedirect.com/science/article/abs/pii/S0167404824004267) | 未核实 |
| NA17 | 2025 | A | [Contrastive Self-Supervised Network Intrusion Detection using Augmented Negative Pairs](https://arxiv.org/abs/2509.06550) | [仓库](https://github.com/jackwilkie/CLAN) |
| NA18 | 2024 | B | [Applying Self-supervised Learning to Network Intrusion Detection for Network Flows with Graph Neural Network](https://arxiv.org/abs/2403.01501) | [仓库](https://github.com/renj-xu/NEGSC) |
| NA19 | 2026 | B | [E2D2: A Modular Framework for Explanation-Based Drift Detection in Unsupervised Network Intrusion Detection](https://github.com/DLTeamTUC/E2D2) | [仓库](https://github.com/DLTeamTUC/E2D2) |
| NA20 | 2024 | B | [State-transition-aware anomaly detection under concept drifts](https://www.sciencedirect.com/science/article/pii/S0169023X24000892) | [仓库](https://github.com/KDD-OpenSource/STAD) |
| NA21 | 2019 | S | [GEE: A Gradient-based Explainable Variational Autoencoder for Network Anomaly Detection](https://arxiv.org/abs/1903.06661) | 未核实 |
| NA22 | 2026 | A | [REAPER: Real-Time Detection of Malicious Traffic via Deep Time-Series Embedding Analysis](https://www.cs.newpaltz.edu/~lik/publications/Dan-Tang-IEEE-ToN-2026b.pdf) | 未核实 |
| NA23 | 2021 | A | [DeepAID: Interpreting and Improving Deep Learning-based Anomaly Detection in Security Applications](https://arxiv.org/abs/2109.11495) | [仓库](https://github.com/dongtsi/DeepAID) |
| NA24 | 2023 | A | [Anomaly Detection in the Open World: Normality Shift Detection, Explanation, and Adaptation](https://www.ndss-symposium.org/ndss-paper/anomaly-detection-in-the-open-world-normality-shift-detection-explanation-and-adaptation/) | [仓库](https://github.com/dongtsi/OWAD) |

NA13链接的是官方Yatesbury实验基准，不是完整NetVigil实现；NA20仓库对应2023会议版本；NA19参考实现的正式出版信息仍待独立确认。其余非空代码地址由作者论文/仓库引用核实，未运行、未全面许可证审计。

## 可抽取文献矩阵

```json
[
  {
    "id": "NA01",
    "title": "Kitsune: An Ensemble of Autoencoders for Online Network Intrusion Detection",
    "year": 2018,
    "authors": [
      "Yisroel Mirsky",
      "Tomer Doitshman",
      "Yuval Elovici",
      "Asaf Shabtai"
    ],
    "venue": "NDSS 2018",
    "doi": null,
    "source_url": "https://arxiv.org/abs/1802.09089",
    "code_url": "https://github.com/ymirsky/Kitsune-py",
    "group": "网络专用AI异常检测",
    "priority": "S",
    "problem": "低资源设备上的在线无监督网络入侵检测。",
    "input_unit": "每个数据包对应的增量统计特征向量。",
    "datasets": [
      "作者网络攻击抓包数据；具体版本待全文核验"
    ],
    "method": "AfterImage衰减增量统计，KitNET小型AE集成；输出重构误差。",
    "temporal_info": "统计保留发送者/信道近期上下文，不等同显式昼夜周期。",
    "split": "代码区分特征映射、正常训练宽限期及后续检测；论文各数据集时间切分待全文核验。",
    "threshold": "待全文核验",
    "metrics": "待全文核验",
    "limitation": "原始提取器依赖包级信息，UGR16的聚合FeatureData不能直接替代；Python参考实现不具备论文最优速度。",
    "relevance": "理解AI如何根据正常行为重构误差评分，以及轻量AE与时间统计结合已有做法。",
    "verification": "摘要级；作者仓库源页面",
    "unknowns": [
      "论文阈值校准方式",
      "原始各场景划分",
      "与UGR16聚合字段适配",
      "本机实测"
    ]
  },
  {
    "id": "NA02",
    "title": "N-BaIoT: Network-based Detection of IoT Botnet Attacks Using Deep Autoencoders",
    "year": 2018,
    "authors": [
      "Yair Meidan",
      "Michael Bohadana",
      "Yael Mathov",
      "Yisroel Mirsky",
      "Dominik Breitenbacher",
      "Asaf Shabtai",
      "Yuval Elovici"
    ],
    "venue": "IEEE Pervasive Computing",
    "doi": "10.1109/MPRV.2018.03367731",
    "source_url": "https://arxiv.org/abs/1805.03409",
    "code_url": null,
    "group": "网络专用AI异常检测",
    "priority": "A",
    "problem": "识别IoT设备感染后偏离正常通信行为的流量。",
    "input_unit": "设备网络行为统计快照。",
    "datasets": [
      "N-BaIoT；9类商业IoT设备；Mirai/BASHLITE攻击"
    ],
    "method": "利用正常设备行为训练深度AE。",
    "temporal_info": "流量统计包含不同时间尺度；具体窗口构造待全文核验。",
    "split": "待全文核验",
    "threshold": "待全文核验",
    "metrics": "待全文核验",
    "limitation": "设备专用正常模型与校园/企业聚合流量背景不同；不能直接证明日内变化场景有效。",
    "relevance": "支持AE异常检测原理与正常训练条件的说明。",
    "verification": "摘要级；arXiv期刊关联元数据",
    "unknowns": [
      "官方配套代码未核实",
      "时间切分",
      "阈值与实际误报协议"
    ]
  },
  {
    "id": "NA03",
    "title": "Network traffic anomaly detection model based on feature grouping and multi-autoencoders integration",
    "year": 2024,
    "authors": [
      "Yang Zhou",
      "Haoyang Zeng",
      "Zhourong Zheng",
      "Wei Zhang"
    ],
    "venue": "Electronics Letters 60, e70103",
    "doi": "10.1049/ell2.70103",
    "source_url": "https://ietresearch.onlinelibrary.wiley.com/doi/10.1049/ell2.70103",
    "code_url": null,
    "group": "网络专用AI异常检测",
    "priority": "S",
    "problem": "分组特征与多个AE的不同重构能力和评分尺度。",
    "input_unit": "流记录特征分组。",
    "datasets": [
      "UNSW-NB15",
      "CICIDS2017"
    ],
    "method": "按属性/方差及正反方向分组；多AE训练；依据AUC选择模型和权重并融合评分。",
    "temporal_info": "本次可读部分未见显式时间周期分支。",
    "split": "训练/验证划分具体顺序待全文核验。",
    "threshold": "验证ROC及Youden指数选择阈值；最终融合阈值细节待全文核验。",
    "metrics": "AUC、Accuracy、F1；本次未核实PR-AUC。",
    "limitation": "验证标签参与模型/阈值选择；评分融合已有先例；资源与时间协议仍需核验。",
    "relevance": "直接约束‘多AE或评分融合即创新’的表述，可借鉴尺度校准和分组消融。",
    "verification": "全文局部；出版社方法与评价片段",
    "unknowns": [
      "代码未核实",
      "验证是否严格早于测试",
      "融合的精确公式",
      "显存/训练耗时"
    ]
  },
  {
    "id": "NA04",
    "title": "Enhancing Network Traffic Anomaly Detection: Leveraging Temporal Correlation Index in a Hybrid Framework",
    "year": 2024,
    "authors": [
      "A. H. Nasreen Fathima",
      "S. P. Syed Ibrahim",
      "Ansam Khraisat"
    ],
    "venue": "IEEE Access 12, 136805–136824",
    "doi": "10.1109/ACCESS.2024.3458903",
    "source_url": "https://dro.deakin.edu.au/articles/journal_contribution/Enhancing_Network_Traffic_Anomaly_Detection_Leveraging_Temporal_Correlation_Index_in_a_Hybrid_Framework/28620866",
    "code_url": null,
    "group": "网络时间信息与AI",
    "priority": "S",
    "problem": "网络异常检测中的时间相关信息。",
    "input_unit": "待全文核验",
    "datasets": [
      "待全文核验"
    ],
    "method": "题名确认Temporal Correlation Index混合框架；附件所述TMG-GRU-VAE细节尚未取得一手全文核验。",
    "temporal_info": "Temporal Correlation Index；计算定义与因果窗口待全文核验。",
    "split": "待全文核验",
    "threshold": "待全文核验",
    "metrics": "待全文核验",
    "limitation": "目前仅机构元数据核验，不能把第三方全文摘要中的方法、数据和效果当作本次已核实。",
    "relevance": "与你的题名高度相邻，需优先查清已做时间机制和评价边界。",
    "verification": "源页面；Deakin机构记录及VIT官方出版清单",
    "unknowns": [
      "输入粒度",
      "GRU-VAE结构",
      "数据集",
      "时间切分",
      "TCI公式",
      "阈值",
      "原文获取",
      "代码"
    ]
  },
  {
    "id": "NA05",
    "title": "Robust unsupervised network intrusion detection with self-supervised masked context reconstruction",
    "year": 2023,
    "authors": [
      "Wei Wang",
      "Songlei Jian",
      "Yusong Tan",
      "Qingbo Wu",
      "Chenlin Huang"
    ],
    "venue": "Computers & Security 128, 103131",
    "doi": "10.1016/j.cose.2023.103131",
    "source_url": "https://jiansonglei.github.io/files/22RobustIDS.pdf",
    "code_url": null,
    "group": "网络时间信息与AI",
    "priority": "S",
    "problem": "训练污染下的无监督网络检测。",
    "input_unit": "按原顺序形成记录上下文。",
    "datasets": [
      "KDDCUP",
      "UNSW-NB15",
      "CICIDS17-Friday",
      "CICIDS17-Wednesday"
    ],
    "method": "RUIDS：自监督变换与Transformer掩蔽上下文重构。",
    "temporal_info": "上下文内记录相关性；未等同昼夜周期。",
    "split": "§4.1.1/4.1.3：50%正常记录训练，其余正常及全部异常测试；严格时间留出未核实。",
    "threshold": "§4.1.1/4.2：用测试集真实异常数/比例选top-k异常。",
    "metrics": "Accuracy、F1、ROC-AUC。",
    "limitation": "§4.1.2传统基线使用测试集训练并按真实异常比例设参；KDD正常/攻击标签反转。不可照搬为部署评价协议。",
    "relevance": "借鉴上下文和污染消融；同时作为阈值与公平比较审计案例。",
    "verification": "全文局部；§3、§4.1、§4.2",
    "unknowns": [
      "官方代码未核实",
      "严格时间协议",
      "因果可用上下文",
      "无测试标签的效果"
    ]
  },
  {
    "id": "NA06",
    "title": "Renyi entropy-driven network traffic anomaly detection with dynamic threshold",
    "year": 2024,
    "authors": [
      "Haoran Yu",
      "Wenchuan Yang",
      "Baojiang Cui",
      "Runqi Sui",
      "Xuedong Wu"
    ],
    "venue": "Cybersecurity 7, 64",
    "doi": "10.1186/s42400-024-00249-1",
    "source_url": "https://link.springer.com/article/10.1186/s42400-024-00249-1",
    "code_url": null,
    "group": "网络动态阈值",
    "priority": "S",
    "problem": "固定阈值难以跟随网络流量变化。",
    "input_unit": "滑动窗口中的流量特征分布。",
    "datasets": [
      "UNSW-NB15",
      "CICIDS2017",
      "CICDDoS2019"
    ],
    "method": "Rényi熵和改进EWMA预测；历史统计调整阈值。",
    "temporal_info": "近期窗口的熵变化与历史预测。",
    "split": "具体时间切分待全文核验；正文提及编码与过采样，需审计操作范围。",
    "threshold": "预测均值加减γ乘历史标准差的动态边界。",
    "metrics": "Precision、Recall、F1；运行时间与FLOPs。",
    "limitation": "动态阈值/EWMA已有先例；重采样、窗口单位、测试时间协议需审计。",
    "relevance": "必须区分普通动态阈值与拟研究的时间感知AI机制；可作为统计路线参考。",
    "verification": "全文局部；出版社方法、特征和实验部分",
    "unknowns": [
      "官方代码",
      "各窗口单位",
      "γ校准范围",
      "标签及采样处理是否泄漏"
    ]
  },
  {
    "id": "NA07",
    "title": "ReCDA: Concept Drift Adaptation with Representation Enhancement for Network Intrusion Detection",
    "year": 2024,
    "authors": [
      "Shuo Yang",
      "Xinran Zheng",
      "Jinze Li",
      "Jinfeng Xu",
      "Xingjun Wang",
      "Edith C. H. Ngai"
    ],
    "venue": "ACM KDD 2024, 3818–3828",
    "doi": "10.1145/3637528.3672007",
    "source_url": "https://hub.hku.hk/handle/10722/362496",
    "code_url": "https://github.com/kalendsyang/ReCDA",
    "group": "网络概念漂移与适应",
    "priority": "A",
    "problem": "分布变化后网络检测模型失效及适应成本。",
    "input_unit": "网络流量记录表征；具体粒度待全文核验。",
    "datasets": [
      "待全文核验"
    ],
    "method": "作者代码提供Representation Enhancement和Constrained Tuning两阶段。",
    "temporal_info": "概念漂移下的表示与模型适应，不是单纯时间特征。",
    "split": "待全文核验",
    "threshold": "待全文核验",
    "metrics": "待全文核验",
    "limitation": "P1适应候选；弱监督/标注预算、旧知识保留及因果更新必须精读，当前不能作为P0已可运行方案。",
    "relevance": "回答Concept Drift与时间上下文的区别，并作为后续适应路线锚点。",
    "verification": "源页面；HKU机构出版记录与作者代码",
    "unknowns": [
      "漂移构造",
      "标注预算",
      "在线更新顺序",
      "各数据集与指标",
      "本地运行"
    ]
  },
  {
    "id": "NA08",
    "title": "Self-Supervised Adaptation Method to Concept Drift for Network Intrusion Detection",
    "year": 2025,
    "authors": [
      "Shuo Yang",
      "Xinran Zheng",
      "Jinze Li",
      "Jinfeng Xu",
      "Xinchen Zhang",
      "Edith C. H. Ngai"
    ],
    "venue": "IEEE Transactions on Dependable and Secure Computing 22(6), 7632–7646",
    "doi": null,
    "source_url": "https://ece.hku.hk/people/echngai/",
    "code_url": "https://github.com/kalendsyang/ReCDA",
    "group": "网络概念漂移与适应",
    "priority": "A",
    "problem": "网络检测中的自监督漂移适应。",
    "input_unit": "待全文核验",
    "datasets": [
      "待全文核验"
    ],
    "method": "作者仓库列为ReCDA后续期刊论文；新增方法与实验待全文核验。",
    "temporal_info": "分布漂移及适应。",
    "split": "待全文核验",
    "threshold": "待全文核验",
    "metrics": "待全文核验",
    "limitation": "与NA07同一研究家族，不应当作两种独立方法支撑同一结论；DOI未在本次一手页面核实。",
    "relevance": "更新2024会议方法的后续发展，用于漂移相关工作。",
    "verification": "源页面；作者机构出版目录与官方仓库引用",
    "unknowns": [
      "DOI一手核验",
      "相对KDD版增量",
      "在线实验协议",
      "标签成本",
      "数据集"
    ]
  },
  {
    "id": "NA09",
    "title": "CADE: Detecting and Explaining Concept Drift Samples for Security Applications",
    "year": 2021,
    "authors": [
      "Limin Yang",
      "Wenbo Guo",
      "Qingying Hao",
      "Arridhana Ciptadi",
      "Ali Ahmadzadeh",
      "Xinyu Xing",
      "Gang Wang"
    ],
    "venue": "USENIX Security 2021, 2327–2344",
    "doi": null,
    "source_url": "https://www.usenix.org/conference/usenixsecurity21/presentation/yang-limin",
    "code_url": "https://github.com/whyisyoung/CADE",
    "group": "网络概念漂移与适应",
    "priority": "A",
    "problem": "发现并解释安全任务中偏离已有类别的新样本。",
    "input_unit": "安全样本特征；含网络流量分类任务。",
    "datasets": [
      "网络入侵与Android恶意软件数据；版本待全文核验"
    ],
    "method": "对比学习AE低维表示，以距离识别并解释漂移样本。",
    "temporal_info": "检测新分布/新类别，不等同正常日内周期适配。",
    "split": "待全文核验",
    "threshold": "待全文核验",
    "metrics": "待全文核验",
    "limitation": "检测漂移样本与适应模型是不同任务；代码历史TensorFlow/Keras环境需迁移；作者名源页与PDF存在变体待规范化。",
    "relevance": "厘清漂移、未知攻击、异常解释三者边界。",
    "verification": "摘要级；会议页面与作者仓库",
    "unknowns": [
      "数据版本",
      "切分",
      "距离阈值",
      "历史依赖兼容性",
      "作者名PDF变体"
    ]
  },
  {
    "id": "NA10",
    "title": "ENIDrift: A Fast and Adaptive Ensemble System for Network Intrusion Detection under Real-world Drift",
    "year": 2022,
    "authors": [
      "Xian Wang"
    ],
    "venue": "ACSAC 2022, 785–798",
    "doi": null,
    "source_url": "https://researchportal.hkust.edu.hk/en/publications/enidrift-a-fast-and-adaptive-ensemble-system-for-network-intrusio-2/",
    "code_url": "https://github.com/X1anWang/ENIDrift",
    "group": "网络概念漂移与适应",
    "priority": "A",
    "problem": "真实漂移下快速且能更新的网络检测。",
    "input_unit": "包级流式嵌入与数据块。",
    "datasets": [
      "CICIDS2017",
      "MAWILab",
      "RWDIDS"
    ],
    "method": "增量iP2V嵌入、AE/PCA检测器集成及数据块/权重更新；依据作者会议幻灯片。",
    "temporal_info": "不同日期/攻击引起的轻重漂移及流式更新。",
    "split": "会议幻灯片介绍日期变化场景；严格训练/更新/测试协议待论文全文核验。",
    "threshold": "待全文核验",
    "metrics": "幻灯片含F1、耗时、内存及标签延迟研究；公式待全文核验。",
    "limitation": "本次可读17页文件为幻灯片，不应标成论文全文精读；包级输入与UGR16聚合数据不一致。",
    "relevance": "学习更新开销、标签延迟和漂移场景设计，P1参考。",
    "verification": "源页面；作者仓库、机构记录和会议幻灯片",
    "unknowns": [
      "DOI",
      "论文全文",
      "阈值",
      "标签延迟假设",
      "对UGR16适配"
    ]
  },
  {
    "id": "NA11",
    "title": "HorusEye: A Realtime IoT Malicious Traffic Detection Framework using Programmable Switches",
    "year": 2023,
    "authors": [
      "Yutao Dong",
      "Qing Li",
      "Kaidong Wu",
      "Ruoyu Li",
      "Dan Zhao",
      "Gareth Tyson",
      "Junkun Peng",
      "Yong Jiang",
      "Shutao Xia",
      "Mingwei Xu"
    ],
    "venue": "USENIX Security 2023, 571–588",
    "doi": null,
    "source_url": "https://www.usenix.org/conference/usenixsecurity23/presentation/dong-yutao",
    "code_url": null,
    "group": "网络检测工程与实时系统",
    "priority": "B",
    "problem": "IoT恶意流量检测的实时性与误报。",
    "input_unit": "数据平面突发流量；控制平面可疑流。",
    "datasets": [
      "待全文核验"
    ],
    "method": "iForest映射为可编程交换机白名单规则；可疑流再经深度模型。",
    "temporal_info": "突发/流级近期统计；具体时间窗口待全文核验。",
    "split": "待全文核验",
    "threshold": "待全文核验",
    "metrics": "FPR与吞吐量在摘要出现；完整协议待全文核验。",
    "limitation": "依赖P4可编程交换机，当前单机P0不具备完整部署条件。",
    "relevance": "学习两级筛查与研究性能/工程吞吐量的分离。",
    "verification": "摘要级；USENIX会议页面",
    "unknowns": [
      "代码",
      "数据集",
      "交换机硬件",
      "具体阈值",
      "成本"
    ]
  },
  {
    "id": "NA12",
    "title": "Realtime Robust Malicious Traffic Detection via Frequency Domain Analysis",
    "year": 2021,
    "authors": [
      "Chuanpu Fu",
      "Qi Li",
      "Meng Shen",
      "Ke Xu"
    ],
    "venue": "ACM CCS 2021",
    "doi": null,
    "source_url": "https://arxiv.org/abs/2106.14707",
    "code_url": "https://github.com/fuchuanpu/Whisper",
    "group": "网络时间信息与AI",
    "priority": "A",
    "problem": "高速流量下恶意行为检测与扰动鲁棒性。",
    "input_unit": "包序列的频域表征。",
    "datasets": [
      "作者恶意流量实验；MAWI背景流量；具体版本待全文核验"
    ],
    "method": "Whisper：频域特征压缩与无监督检测。",
    "temporal_info": "包序列顺序与频域模式；不等同日内周期。",
    "split": "待全文核验",
    "threshold": "待全文核验",
    "metrics": "检测质量、吞吐与鲁棒性；精确定义待全文核验。",
    "limitation": "完整实时链路依赖Linux/DPDK、高速网卡和大量CPU/hugepages；仓库已归档；当前P0只宜学习方法。",
    "relevance": "解释‘时间信息’可有不同尺度，学习效率实验与部署边界。",
    "verification": "摘要级；作者仓库与arXiv",
    "unknowns": [
      "DOI",
      "各攻击划分",
      "阈值",
      "聚合特征可否保留频域信息",
      "部署资源"
    ]
  },
  {
    "id": "NA13",
    "title": "NetVigil: Robust and Low-Cost Anomaly Detection for East-West Data Center Security",
    "year": 2024,
    "authors": [
      "Kevin Hsieh",
      "Mike Wong",
      "Santiago Segarra",
      "Sathiya Kumaran Mani",
      "Trevor Eberl",
      "Anatoliy Panasyuk",
      "Ravi Netravali",
      "Ranveer Chandra",
      "Srikanth Kandula"
    ],
    "venue": "USENIX NSDI 2024",
    "doi": null,
    "source_url": "https://www.usenix.org/conference/nsdi24/presentation/hsieh",
    "code_url": "https://github.com/microsoft/Yatesbury",
    "group": "网络时间信息与AI",
    "priority": "A",
    "problem": "业务波动和误报下的数据中心东西向攻击检测。",
    "input_unit": "窗口流日志构建的安全图。",
    "datasets": [
      "Yatesbury公开20场景基准",
      "私有生产集群流日志"
    ],
    "method": "领域图特征、对比GNN、相邻图时间损失、平滑及近期清洁日志重训练。",
    "temporal_info": "相邻窗口时间一致性与近期背景变化。",
    "split": "待全文核验",
    "threshold": "待全文核验",
    "metrics": "ROC-AUC、延迟、成本；具体协议待全文核验。",
    "limitation": "公开仓库是Yatesbury基准，非完整NetVigil实现；私有生产数据不可直接获得；图输入适配成本高。",
    "relevance": "具体业务变化场景和时间平滑已有强相关工作；可学习负例与实验场景。",
    "verification": "全文局部；论文设计部分及官方基准仓库",
    "unknowns": [
      "完整方法代码",
      "数据生成偏差",
      "时间切分",
      "平滑是否因果",
      "阈值"
    ]
  },
  {
    "id": "NA14",
    "title": "CAEAID: An incremental contrast learning-based intrusion detection framework for IoT networks",
    "year": 2025,
    "authors": [
      "Zinuo Yin",
      "Hongchang Chen",
      "Hailong Ma",
      "Tao Hu",
      "Luxin Bai"
    ],
    "venue": "Computer Networks 262, 111161",
    "doi": "10.1016/j.comnet.2025.111161",
    "source_url": "https://www.sciencedirect.com/science/article/pii/S138912862500129X",
    "code_url": null,
    "group": "网络概念漂移与适应",
    "priority": "A",
    "problem": "IoT流量概念漂移时无监督/增量适应。",
    "input_unit": "IoT流量特征记录。",
    "datasets": [
      "IoTID20",
      "CICIDS2018"
    ],
    "method": "对比AE、改进EVT自适应阈值、一致性伪标签及周期增量更新。",
    "temporal_info": "分布变化触发模型适应；时间切分待全文核验。",
    "split": "待全文核验",
    "threshold": "改进极值理论自适应边界；校准数据与公式待全文核验。",
    "metrics": "Accuracy、Precision、Recall、F1。",
    "limitation": "伪标签可能把攻击学成正常，需核验更新筛选和标签/未来信息使用。",
    "relevance": "说明AE+自适应阈值+漂移更新已有研究，P1对照。",
    "verification": "摘要级；出版社摘要与引言片段",
    "unknowns": [
      "代码",
      "更新筛选",
      "阈值拟合区间",
      "时间协议",
      "显存"
    ]
  },
  {
    "id": "NA15",
    "title": "DUdetector: A dual-granularity unsupervised model for network anomaly detection",
    "year": 2025,
    "authors": [
      "Haijun Geng",
      "Qi Ma",
      "Haotian Chi",
      "Zhi Zhang",
      "Jing Yang",
      "Xia Yin"
    ],
    "venue": "Computer Networks 257, 110937",
    "doi": "10.1016/j.comnet.2024.110937",
    "source_url": "https://www.sciencedirect.com/science/article/pii/S1389128624007692",
    "code_url": "https://github.com/qi-yun/DUdetector",
    "group": "网络时间信息与AI",
    "priority": "A",
    "problem": "只检测序列无法定位异常包，或逐包检测未利用时间相关性。",
    "input_unit": "先时间段再包级；PCAP派生统计。",
    "datasets": [
      "SSDP Flood",
      "Mirai",
      "IDS2017"
    ],
    "method": "改进Transformer筛查段；残差Conv1d/MaxPool1d-AE定位包；扩展二维jitter统计。",
    "temporal_info": "段内包相关性与包间抖动关系。",
    "split": "待全文核验",
    "threshold": "待全文核验",
    "metrics": "段级/包级F1和FPR。",
    "limitation": "两粒度输入依赖包级提取；不能直接把聚合分钟记录当包；复杂模型成本尚未实测。",
    "relevance": "必须明确检测单位与窗口标签聚合；原始时间机制不等同你的周期背景。",
    "verification": "摘要级与出版社局部；配套作者仓库",
    "unknowns": [
      "时间划分",
      "段/包阈值",
      "正常训练条件",
      "硬件成本",
      "代码许可证"
    ]
  },
  {
    "id": "NA16",
    "title": "CDDA-MD: An efficient malicious traffic detection method based on concept drift detection and adaptation technique",
    "year": 2025,
    "authors": [
      "Saihua Cai",
      "Han Tang",
      "Jinfu Chen",
      "Yikai Hu",
      "Wuhao Guo"
    ],
    "venue": "Computers & Security 148, 104121",
    "doi": "10.1016/j.cose.2024.104121",
    "source_url": "https://www.sciencedirect.com/science/article/abs/pii/S0167404824004267",
    "code_url": null,
    "group": "网络概念漂移与适应",
    "priority": "A",
    "problem": "动态网络流量漂移后的恶意流量识别。",
    "input_unit": "滑动窗口流量序列。",
    "datasets": [
      "4个数据集；名称待全文核验"
    ],
    "method": "LSTM和多头注意力，错误率漂移监测与增量学习。",
    "temporal_info": "窗口时间信息及漂移后的模型更新。",
    "split": "待全文核验",
    "threshold": "漂移及检测阈值待全文核验。",
    "metrics": "F1、TPR和稳定性；定义待全文核验。",
    "limitation": "错误率漂移监测可能依赖及时真实标签；需核验标注延迟，不能默认部署时可获得。",
    "relevance": "帮助区分检测异常与检测模型失效，P1更新研究。",
    "verification": "摘要级；出版社摘要与作者元数据",
    "unknowns": [
      "4个数据集名",
      "标签可获得假设",
      "错误率监测",
      "切分",
      "代码"
    ]
  },
  {
    "id": "NA17",
    "title": "Contrastive Self-Supervised Network Intrusion Detection using Augmented Negative Pairs",
    "year": 2025,
    "authors": [
      "Jack Wilkie",
      "Hanan Hindy",
      "Christos Tachtatzis",
      "Robert Atkinson"
    ],
    "venue": "IEEE International Conference on Cyber Security and Resilience (CSR) 2025",
    "doi": "10.1109/CSR64739.2025.11129979",
    "source_url": "https://arxiv.org/abs/2509.06550",
    "code_url": "https://github.com/jackwilkie/CLAN",
    "group": "网络专用AI异常检测",
    "priority": "A",
    "problem": "正常流量表征与少标注检测。",
    "input_unit": "表格流量特征及其增强样本。",
    "datasets": [
      "Lycos2017"
    ],
    "method": "CLAN：增强负样本对与正常样本正对构建对比表征，可少标签微调。",
    "temporal_info": "本次可读内容未核实显式时间机制。",
    "split": "待全文核验",
    "threshold": "待全文核验",
    "metrics": "二分类AUROC及少标注多分类F1；精确协议待全文核验。",
    "limitation": "少标注分类任务和纯无监督评分任务需区分；增强可能改变语义。",
    "relevance": "2025年开源表征路线参考，不作为P0强制模型。",
    "verification": "摘要级；作者PDF首页与官方仓库",
    "unknowns": [
      "时间切分",
      "增强约束",
      "阈值",
      "算力",
      "是否有严格开放集评价"
    ]
  },
  {
    "id": "NA18",
    "title": "Applying Self-supervised Learning to Network Intrusion Detection for Network Flows with Graph Neural Network",
    "year": 2024,
    "authors": [
      "Renjie Xu",
      "Guangwei Wu",
      "Weiping Wang",
      "Xing Gao",
      "An He",
      "Zhengpeng Zhang"
    ],
    "venue": "arXiv 2024；正式期刊关联待一手核验",
    "doi": null,
    "source_url": "https://arxiv.org/abs/2403.01501",
    "code_url": "https://github.com/renj-xu/NEGSC",
    "group": "网络专用AI异常检测",
    "priority": "B",
    "problem": "网络流关系及自监督表示用于入侵检测。",
    "input_unit": "流关系图/边特征。",
    "datasets": [
      "NF-Bot-IoT",
      "NF-Bot-IoT-v2",
      "NF-CSE-CIC-IDS2018",
      "NF-CSE-CIC-IDS2018-v2"
    ],
    "method": "NEGSC：边特征注意力图编码与中心邻域对比图表征。",
    "temporal_info": "摘要未核实显式时间机制。",
    "split": "待全文核验",
    "threshold": "分类任务阈值/决策协议待全文核验。",
    "metrics": "待全文核验",
    "limitation": "多类别流检测不自动等同正常训练AE；GNN输入构造与内存规模待审计。",
    "relevance": "解释为何暂不选图模型，并辨别自监督表示与异常评分。",
    "verification": "摘要级；arXiv作者指向代码",
    "unknowns": [
      "期刊DOI",
      "正式版本",
      "时间划分",
      "监督使用",
      "显存",
      "另一代码仓库关系"
    ]
  },
  {
    "id": "NA19",
    "title": "E2D2: A Modular Framework for Explanation-Based Drift Detection in Unsupervised Network Intrusion Detection",
    "year": 2026,
    "authors": [
      "Beny Nugraha",
      "Thomas Bauschert"
    ],
    "venue": "TX4Nets workshop, IFIP Networking 2026；会议信息依据作者仓库",
    "doi": null,
    "source_url": "https://github.com/DLTeamTUC/E2D2",
    "code_url": "https://github.com/DLTeamTUC/E2D2",
    "group": "网络概念漂移与适应",
    "priority": "B",
    "problem": "异常检测器解释随时间变化时的漂移发现。",
    "input_unit": "每窗口异常评分解释指纹。",
    "datasets": [
      "CIC-DDoS2019 NTP",
      "CIC-DDoS2019 Portmap",
      "CIC-DDoS2019 Syn",
      "CICIoT2023",
      "5GNIDD"
    ],
    "method": "AE/VAE解释、MAD归一化及XDI漂移强度；组合不同人口视图和聚合策略。",
    "temporal_info": "滑窗解释变化；作者README为W=500、步长250。",
    "split": "仓库声称leakage-safe preprocessing；实际实现与原始时间连续性未核验。",
    "threshold": "README的漂移κ=2；不是已核实的最终异常检测阈值。",
    "metrics": "漂移与计算成本指标具体定义待全文核验。",
    "limitation": "仅作者仓库核验；未独立核验会议正式出版；原实验12GB GPU，用户8GB尚未实测。",
    "relevance": "2026近期解释漂移趋势，P1/P2扩展，不据此扩张P0。",
    "verification": "源页面；作者参考实现README",
    "unknowns": [
      "正式出版元数据",
      "论文全文",
      "漂移合成真实性",
      "异常阈值",
      "本机显存",
      "解释耗时"
    ]
  },
  {
    "id": "NA20",
    "title": "State-transition-aware anomaly detection under concept drifts",
    "year": 2024,
    "authors": [
      "Bin Li",
      "Shubham Gupta",
      "Emmanuel Müller"
    ],
    "venue": "Data & Knowledge Engineering 154, 102365",
    "doi": "10.1016/j.datak.2024.102365",
    "source_url": "https://www.sciencedirect.com/science/article/pii/S0169023X24000892",
    "code_url": "https://github.com/KDD-OpenSource/STAD",
    "group": "通用漂移方法参考（非网络专用）",
    "priority": "B",
    "problem": "正常状态转移与异常在变化数据流中的区分。",
    "input_unit": "一般数据流记录与分布状态。",
    "datasets": [
      "合成与真实数据；名称待全文核验"
    ],
    "method": "AE、统计漂移检验与概率密度估计比较正常状态。",
    "temporal_info": "数据流状态迁移，不直接保证流量日周期有效。",
    "split": "待全文核验",
    "threshold": "待全文核验",
    "metrics": "待全文核验",
    "limitation": "仓库引用2023 DaWaK会议版本，2024期刊扩展实现覆盖未核实；不算网络专用验证。",
    "relevance": "思考正常变化与异常的判别假设，以及状态转移边界。",
    "verification": "摘要级；出版社页面和2023代码引用",
    "unknowns": [
      "2024新增内容",
      "数据集",
      "状态保存/更新规则",
      "严格因果切分",
      "2024配套代码"
    ]
  },
  {
    "id": "NA21",
    "title": "GEE: A Gradient-based Explainable Variational Autoencoder for Network Anomaly Detection",
    "year": 2019,
    "authors": [
      "Quoc Phong Nguyen",
      "Kar Wai Lim",
      "Dinil Mon Divakaran",
      "Kian Hsiang Low",
      "Mun Choon Chan"
    ],
    "venue": "IEEE Conference on Communications and Network Security (CNS) 2019",
    "doi": null,
    "source_url": "https://arxiv.org/abs/1903.06661",
    "code_url": null,
    "group": "网络专用AI异常检测",
    "priority": "S",
    "problem": "网络异常评分及异常发生原因解释。",
    "input_unit": "UGR16 NetFlow派生表示。",
    "datasets": [
      "UGR16"
    ],
    "method": "VAE异常检测及梯度指纹解释。",
    "temporal_info": "UGR16派生特征；时间窗口和顺序协议待全文核验。",
    "split": "待全文核验",
    "threshold": "待全文核验",
    "metrics": "AUC等指标待全文核验。",
    "limitation": "本文没有证明日内上下文机制；第三方GEE仓库不可默认官方实现；精确字段应追原文。",
    "relevance": "UGR16与VAE直接相关，优先核验输入、标签和解释方法。",
    "verification": "摘要级；arXiv及NUS作者PDF",
    "unknowns": [
      "正式DOI一手核验",
      "官方代码",
      "派生字段",
      "划分",
      "阈值"
    ]
  },
  {
    "id": "NA22",
    "title": "REAPER: Real-Time Detection of Malicious Traffic via Deep Time-Series Embedding Analysis",
    "year": 2026,
    "authors": [
      "Dan Tang",
      "Boru Liu",
      "Zheng Qin",
      "Wei Liang",
      "Keqin Li",
      "Wenqiang Jin"
    ],
    "venue": "IEEE Transactions on Networking 34, 872–887；2025早期在线",
    "doi": "10.1109/TON.2025.3610853",
    "source_url": "https://www.cs.newpaltz.edu/~lik/publications/Dan-Tang-IEEE-ToN-2026b.pdf",
    "code_url": null,
    "group": "网络时间信息与AI",
    "priority": "A",
    "problem": "长短流恶意流量的实时检测。",
    "input_unit": "每流包到达间隔、包长度与标志序列；短流按IP动态聚合。",
    "datasets": [
      "20类恶意流量实验",
      "14类加密恶意流量",
      "WIDE 2024良性背景；版本待全文核验"
    ],
    "method": "RNN时序嵌入、VAE潜在不确定性评分、短流动态聚合及DPDK。",
    "temporal_info": "流内序列依赖，不等同分钟/昼夜背景变化。",
    "split": "待全文核验",
    "threshold": "待全文核验",
    "metrics": "ROC-AUC、EER、吞吐量、内存。",
    "limitation": "包序列与DPDK完整链路资源成本较高，不能直接用于UGR16 FeatureData；未核验官方代码。",
    "relevance": "近期时序AI与效率评价参考，帮助界定不同时间尺度。",
    "verification": "全文局部；作者PDF首页和设计片段",
    "unknowns": [
      "数据名称/版本",
      "代码",
      "时间切分",
      "潜在不确定性阈值",
      "硬件成本"
    ]
  },
  {
    "id": "NA23",
    "title": "DeepAID: Interpreting and Improving Deep Learning-based Anomaly Detection in Security Applications",
    "year": 2021,
    "authors": [
      "Dongqi Han",
      "Zhiliang Wang",
      "Wenqi Chen",
      "Ying Zhong",
      "Su Wang",
      "Han Zhang",
      "Jiahai Yang",
      "Xingang Shi",
      "Xia Yin"
    ],
    "venue": "ACM CCS 2021, 3197–3217",
    "doi": "10.1145/3460120.3484589",
    "source_url": "https://arxiv.org/abs/2109.11495",
    "code_url": "https://github.com/dongtsi/DeepAID",
    "group": "网络AI解释与误报分析",
    "priority": "A",
    "problem": "解释深度安全异常检测并利用反馈改进误报。",
    "input_unit": "检测器、异常输入及其分数；含表格/时间序列/图任务。",
    "datasets": [
      "安全异常任务；具体数据版本待全文核验"
    ],
    "method": "约束参考样本/差异解释及Distiller改进。",
    "temporal_info": "由基检测器决定；不是独立时间上下文方法。",
    "split": "待全文核验",
    "threshold": "待全文核验",
    "metrics": "解释保真、鲁棒、稳定、简洁、效率；检测指标待全文核验。",
    "limitation": "属于解释/改进框架，不能误当独立网络检测器；反馈标签及跨模型适用性待核验。",
    "relevance": "P1异常原因展示与误报分析，不扩大当前P0。",
    "verification": "摘要级；作者arXiv与官方仓库",
    "unknowns": [
      "数据版本",
      "反馈预算",
      "改进切分",
      "阈值",
      "解释计算开销"
    ]
  },
  {
    "id": "NA24",
    "title": "Anomaly Detection in the Open World: Normality Shift Detection, Explanation, and Adaptation",
    "year": 2023,
    "authors": [
      "Dongqi Han",
      "Zhiliang Wang",
      "Wenqi Chen",
      "Kai Wang",
      "Rui Yu",
      "Su Wang",
      "Han Zhang",
      "Zhihua Wang",
      "Minghui Jin",
      "Jiahai Yang",
      "Xingang Shi",
      "Xia Yin"
    ],
    "venue": "NDSS 2023",
    "doi": "10.14722/ndss.2023.24830",
    "source_url": "https://www.ndss-symposium.org/ndss-paper/anomaly-detection-in-the-open-world-normality-shift-detection-explanation-and-adaptation/",
    "code_url": "https://github.com/dongtsi/OWAD",
    "group": "网络概念漂移与适应",
    "priority": "A",
    "problem": "开放环境中的正常分布变化导致异常检测器误报。",
    "input_unit": "安全检测器评分及样本解释；含网络检测任务。",
    "datasets": [
      "Anoshift",
      "Kyoto（代码命名与链接版本待核验）",
      "BGL",
      "LANL-CMSCSE",
      "私有SCADA部署"
    ],
    "method": "OWAD：输出校准、分布检验、重点样本选择及选择性重训练。",
    "temporal_info": "正常行为漂移及模型适应。",
    "split": "待全文核验",
    "threshold": "待全文核验",
    "metrics": "待全文核验",
    "limitation": "人工审核/适应条件需审计；正常变化适应不是‘无人监督自动学习所有新流量’；私有部署不可完整复现。",
    "relevance": "与你正常背景变化误报问题直接相邻，适合阐明既有成果及P1边界。",
    "verification": "摘要级；NDSS原文及官方仓库",
    "unknowns": [
      "Kyoto具体版本",
      "审核预算",
      "更新顺序",
      "误报评价协议",
      "阈值"
    ]
  }
]
```

## 重要证据审计与版本冲突

1. **RUIDS不可直接照搬评价协议**：作者PDF的§4.1.1（PDF第6页）明确以测试集真实异常数量设检测边界；§4.2（PDF第7页）解释为按真实异常比例选最高分top-k。§4.1.2（PDF第7页）说明OC-SVM/LOF/IF使用测试集训练并按真实异常比例设参；§4.2对OC-SVM正常训练的解释又与该处存在表述不一致。本课题应另设早于测试的校准集，不能使用测试标签确定阈值。§4.1.1还对KDD正常/攻击标签反转，不能把该表结果当作标准网络攻击检测结论。[原始PDF](https://jiansonglei.github.io/files/22RobustIDS.pdf)
2. **Multi-AE与Rényi论文限制创新表述**：特征分组、多AE融合、EWMA与动态阈值已有研究。不能将这些模块名称单独写成原创；需在时间定义、因果评价、适用边界和实验结果上建立证据。[Multi-AE](https://ietresearch.onlinelibrary.wiley.com/doi/10.1049/ell2.70103)、[Rényi](https://link.springer.com/article/10.1186/s42400-024-00249-1)
3. **ReCDA版本**：2024 KDD作者含Xingjun Wang；2025期刊作者含Xinchen Zhang。官方仓库引用二者，两条文献不是两种独立方法；各版本增量未精读。[机构会议记录](https://hub.hku.hk/handle/10722/362496)、[官方仓库](https://github.com/kalendsyang/ReCDA)
4. **STAD版本**：2024期刊三位作者；仓库BibTeX写2023 DaWaK两位作者。代码覆盖期刊新增内容未核验。[2024出版社页](https://www.sciencedirect.com/science/article/pii/S0169023X24000892)、[代码引用](https://github.com/KDD-OpenSource/STAD)
5. **NEGSC仓库**：论文arXiv明确指向renj-xu/NEGSC；附件为XingGao-cn/NEGSC，二者关系未核验。本池使用原文直接指向的仓库，不判定另一个仓库虚假。[arXiv](https://arxiv.org/abs/2403.01501)
6. **年份与平台**：DUdetector卷期为2025，DOI含2024；REAPER早期在线为2025、卷期为2026。不能按DOI字符串直接决定引用年份。Whisper对应CCS 2021，不是USENIX Security。TCI论文为2024，Deakin记录2025上架是存储库时间。[DUdetector作者引用](https://github.com/qi-yun/DUdetector)、[REAPER作者PDF](https://www.cs.newpaltz.edu/~lik/publications/Dan-Tang-IEEE-ToN-2026b.pdf)、[Whisper](https://github.com/fuchuanpu/Whisper)、[TCI机构记录](https://dro.deakin.edu.au/articles/journal_contribution/Enhancing_Network_Traffic_Anomaly_Detection_Leveraging_Temporal_Correlation_Index_in_a_Hybrid_Framework/28620866)
7. **名称与源类型**：HorusEye采用2023 USENIX网络论文，同名2026医学图像工作无关。ENIDrift的ACSAC 17页可读文件是演讲幻灯片，不能标为论文全文精读。E2D2仅作者仓库说明2026 workshop信息，尚未独立核验正式论文。[HorusEye](https://www.usenix.org/conference/usenixsecurity23/presentation/dong-yutao)、[ENIDrift会议幻灯片](https://www.acsac.org/2022/program/papers/207-Wang-Anomaly_Intrusion_and_Threat_Detection.pdf)、[E2D2](https://github.com/DLTeamTUC/E2D2)
8. **部署边界**：HorusEye需要可编程交换机，Whisper/REAPER高速链路涉及DPDK，NetVigil涉及流图和私有生产数据。这些方法有阅读价值，不适合作为当前单机P0必须完整复现的项目。E2D2原实验为RTX3060 12GB，不能据此确认用户（本地设备参数） 8GB的全实验可行性。[E2D2硬件说明](https://github.com/DLTeamTUC/E2D2)

## 附件B/C种子未纳入本核验池

以下不是“不真实论文”的判定，仅说明本次尚未纳入已核验矩阵的原因。不得直接复制到已确认参考文献中。

| 附件题名 | 原因/下一步 |
| --- | --- |
| Mask-based Self-supervised Network Intrusion Detection System | 尚未独立核验准确作者、刊期和原始全文；与RUIDS等自监督路线相比当前优先级较低。 |
| Strengthening Network Intrusion Detection in IoT Environments with Self-Supervised Learning and Few Shot Learning | 尚未独立核验对应arXiv版本、任务与监督范围；少样本分类与P0无监督评分需区分。 |
| A convolutional autoencoder architecture for robust network intrusion detection in embedded systems | 尚未取得可归档的一手元数据与实验协议，避免凭题名推定轻量/实时可复现。 |
| Anomaly-based network intrusion detection using denoising autoencoder and Wasserstein GAN synthetic attacks | 未核验一手元数据/合成攻击协议；GAN扩展非当前P0核心。 |
| A hybrid model for detecting intrusions using stacked autoencoders and extreme gradient boosting | 未核验正式元数据；监督分类融合与无监督评分任务需区分。 |
| HAE-HRL: A network intrusion detection system utilizing a novel autoencoder and a hybrid enhanced LSTM-CNN-based residual network | 未核验原始方法与数据划分；复杂堆叠不是本项目优先复现路线。 |
| Improved network anomaly detection system using optimized autoencoder-LSTM | 未核验元数据/优化成本；PSO等优化不应默认适配本地资源。 |
| A network intrusion detection framework on sparse deep denoising auto-encoder for dimensionality reduction | 未核验准确题名、元数据与训练/评价协议；降维不自动等同完整异常检测方法。 |
| ResACAG: A graph neural network based intrusion detection | 未核验一手出版信息；GNN由NEGSC/NetVigil提供已核验阅读入口。 |
| BS-GAT: a network intrusion detection system based on graph neural network for edge computing | 未核验一手全文/边缘资源要求；暂不扩张P0图建模。 |
| XG-NID: Dual-modality network intrusion detection using a heterogeneous graph neural network and large language model | 未核验一手元数据与LLM成本；LLM不在当前毕业设计P0研究主链路。 |
| A sequential deep learning framework for a robust and resilient network intrusion detection system | 题名较泛，尚未核验具体文章身份、OOD/对抗任务及协议。 |
| A privacy-preserving Self-Supervised Learning-based intrusion detection system for 5G-V2X networks | 未核验一手全文；5G-V2X隐私约束偏离当前动态流量主问题。 |
| Learn to adapt: Robust drift detection in security domain | 尚未取得可靠的一手方法/出版核验；漂移先以CADE、OWAD、ReCDA为入口。 |
| CD-BTMSE: A Concept Drift detection model based on Bidirectional Temporal Convolutional Network and Multi-Stacking Ensemble learning | 未核验一手元数据；双向时间机制需特别审计未来信息。 |
| Detecting and rationalizing concept drift: A feature-level approach for understanding cause-effect relationships in dynamic environments | 未核验一手全文；特征解释/因果关系不能从题名直接认定。 |
| Learning from Time-Changing Data with Adaptive Windowing | 属于通用流式/统计基础，由主任务其他文献分组核验；本池避免重复。 |
| River: machine learning for streaming data in Python | 属于工具与通用流式基础，由主任务其他分组核验；本池避免重复。 |

## 下一步精读顺序与可执行边界

建议先精读NA01 Kitsune、NA03 Multi-AE、NA05 RUIDS、NA06 Rényi、NA21 GEE；NA04 TCI取得一手全文后补核验。逐篇查清输入单位、窗口因果性、数据时间划分、阈值校准数据、标签可获得条件，再按现有“1个思路、2个绘图、5个句式”模式记录实际阅读成果。

P0不因该池扩充而增加复杂模型。继续保留UGR16 Data Gate→IF→轻量AE的拟验证顺序；时间窗口、时间机制和最终方法待数据与实验支持。ReCDA/OWAD/ENIDrift等适应系统保留P1阅读用途。没有运行或结果时，只能写拟验证，不得写效果已提升。

