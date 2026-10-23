# CIC候选来源、发行物、时间与标签核查

核查日期：2026-10-23（Asia/Shanghai）。初次元信息阶段基点：`8e6c6ad`，下文保留其当时事实；该阶段未读取新CSV/ZIP/PCAP载荷、发Range GET、填表、联系作者或训练。随后从`9b52c00`续接并获用户批准C18-S，实际四前缀16MiB及局部字段/时间/标签结果见[单独结构记录](2026-10-23-c18-structure-sample.md)，不把元信息阶段的“未读取”沿用为当前状态。初次三个只读子任务核查2017发行身份、2018备选、时间/标签，公开稿由主控汇总。具体方案见[决定包](../project/CANDIDATE-DATA-DECISION-2026-10-23.md)，字段状态及数值清单见[JSON](2026-10-23-candidate-manifest.json)。

证据层次：E1为本轮直接机构文本/官方存储元信息；E2为固定作者代码或研究者自己的实验观察，须限定其版本；P为本项目提案；U为无充分证据。网页文字与代码行为均不能替代目标包实测。

## 本地已有文件检查

对主项目、现有worktree及下载目录枚举候选载荷文件名，包含忽略目录，排除Git、虚拟环境、依赖和技能库。共检索到217个CSV/ZIP/PCAP/PCAPNG/Parquet候选文件路径，未命中CICIDS、CSE-CIC、GeneratedLabelled、MachineLearningCSV、TrafficLabelling、WorkingHours及指定2018日期文件名；未读取不相关文件内容。该结果仅适用于检索范围及名称规则，不能证明任意重命名文件或其他磁盘不存在载荷。知识库已有2017/2018数据笔记及Engelen2021论文笔记，本轮复用并追加，不建同义数据页。

## CICIDS2017发行物与访问结果（E1）

| 对象/入口 | 本轮事实 | 可作何种判断 |
|---|---|---|
| [UNB数据页](https://www.unb.ca/cic/datasets/ids-2017.html) | License明确列`GeneratedLabelledFlows.zip`、`MachineLearningCSV.zip`，另有PCAP及profiles | 两包为不同发行物；无法由介绍认证某包表头或列数 |
| [官方下载入口](https://cicresearch.ca/CICDataset/CIC-IDS-2017/) | 返回资料表单；Server error是初始隐藏节点，旧故障解释已撤回；未提交（见文末复核） | 未取得匿名可读文件清单 |
| [browse.php](https://cicresearch.ca/CICDataset/CIC-IDS-2017/browse.php) | 普通GET返回403 | 没有构造会话或绕过访问流程 |
| [旧Generated包URL](https://cicresearch.ca/CICDataset/CIC-IDS-2017/Dataset/CSVs/GeneratedLabelledFlows.zip) | HEAD跟随重定向到UNB总页，200、text/html、Content-Length=108784 | **108784是HTML大小，不是ZIP大小**；不能以200声称可下载 |
| [旧学习包URL](https://cicresearch.ca/CICDataset/CIC-IDS-2017/Dataset/CSVs/MachineLearningCSV.zip) | 同上 | 不证明ZIP支持Range或身份稳定 |

2017目标包的实际下载URL、版本、字节数、SHA256、解压量和成员清单仍U。网上常见TrafficLabelling称呼及成员名未在本轮获得包清单认证。官网按日11.0G等数字不能套作两个ZIP的传输量。没有用第三方镜像补齐这些未知值。

## CSE-CIC-IDS2018官方对象身份（E1）

[UNB数据页](https://www.unb.ca/cic/datasets/ids-2018.html)→[AWS登记](https://registry.opendata.aws/cse-cic-ids2018/)→`cse-cic-ids2018`存储桶构成来源链。区域ca-central-1是存储位置，不是采集时区。[根目录](https://cse-cic-ids2018.s3.ca-central-1.amazonaws.com/?list-type=2&delimiter=%2F)列出original与processed两前缀；本轮只枚举[processed目录](https://cse-cic-ids2018.s3.ca-central-1.amazonaws.com/?list-type=2&prefix=Processed%20Traffic%20Data%20for%20ML%20Algorithms%2F)。该目录返回KeyCount=11、IsTruncated=false，包括一个零字节占位和10个CSV；非整个存储桶清单。

| 文件（公共前缀Processed Traffic Data for ML Algorithms/） | 目录字节 | 角色 |
|---|---:|---|
| Wednesday-14-02-2018_TrafficForML_CICFlowMeter.csv | 358223333 | 训练前缀候选 |
| Thursday-15-02-2018_TrafficForML_CICFlowMeter.csv | 375945899 | 验证前缀候选 |
| Friday-16-02-2018_TrafficForML_CICFlowMeter.csv | 333723605 | 校准前缀候选 |
| Thuesday-20-02-2018_TrafficForML_CICFlowMeter.csv | 4054925350 | 本次不取；文件拼写原样保留 |
| Wednesday-21-02-2018_TrafficForML_CICFlowMeter.csv | 328893673 | 后续测试日候选 |
| Thursday-22-02-2018_TrafficForML_CICFlowMeter.csv | 382636202 | 仅目录记录 |
| Friday-23-02-2018_TrafficForML_CICFlowMeter.csv | 382840456 | 同上 |
| Wednesday-28-02-2018_TrafficForML_CICFlowMeter.csv | 209249758 | 同上 |
| Thursday-01-03-2018_TrafficForML_CICFlowMeter.csv | 107842858 | 同上 |
| Friday-02-03-2018_TrafficForML_CICFlowMeter.csv | 352368373 | 同上 |
| 10 CSV合计 | **6886649507** | 不含原始流量；不是本轮下载量 |

四个候选对象经子任务及主控独立HEAD复核，均200、text/csv、Accept-Ranges=bytes，目录与响应头大小一致。HEAD读取响应头，没有读CSV正文；Range支持尚未用206实际验证。

| 完整URL | 字节 | Last-Modified（GMT） | ETag（非MD5断言） |
|---|---:|---|---|
| [14日CSV](https://cse-cic-ids2018.s3.ca-central-1.amazonaws.com/Processed%20Traffic%20Data%20for%20ML%20Algorithms/Wednesday-14-02-2018_TrafficForML_CICFlowMeter.csv) | 358223333 | 2018-10-11 16:09:44 | `46c0f45f8e6fe1edf1f08487448c102f-22` |
| [15日CSV](https://cse-cic-ids2018.s3.ca-central-1.amazonaws.com/Processed%20Traffic%20Data%20for%20ML%20Algorithms/Thursday-15-02-2018_TrafficForML_CICFlowMeter.csv) | 375945899 | 2018-10-11 16:08:48 | `eb1dc2ec76efe09c8995f28bfa4c8656-23` |
| [16日CSV](https://cse-cic-ids2018.s3.ca-central-1.amazonaws.com/Processed%20Traffic%20Data%20for%20ML%20Algorithms/Friday-16-02-2018_TrafficForML_CICFlowMeter.csv) | 333723605 | 2018-10-11 16:03:10 | `e68ef27c09c98ba91fe3c6b1108a18b9-20` |
| [21日CSV](https://cse-cic-ids2018.s3.ca-central-1.amazonaws.com/Processed%20Traffic%20Data%20for%20ML%20Algorithms/Wednesday-21-02-2018_TrafficForML_CICFlowMeter.csv) | 328893673 | 2018-10-11 16:10:12 | `3a1d6b804ba9f6a3085973c2fa425883-20` |
| 合计 | **1396786510** | — | — |

HEAD未返回version-id或独立checksum（包括请求checksum-mode后）；保持null，不推断上游从未提供。ETag/修改时间只识别对象快照，修改时间不是采集或流导出时间。未来获取前重新核对身份元组，取得完整载荷后计算本地SHA256。CSV实际表头、行数、标签枚举、排序和时间精度仍U；官网概述的80余特征不替代该审计。

## 使用条件按对象核对（E1/E2）

| 对象 | 可定位依据 | 当前判断 |
|---|---|---|
| 官方2017原始PCAP、profiles、Generated与学习CSV | [单页License](https://www.unb.ca/cic/datasets/ids-2017.html)及[UNB总页FAQ](https://www.unb.ca/cic/datasets/index.html) | 研究使用说明、使用/再分发须引用数据集与所列论文；总页明确可转载/镜像/再分发。这是本轮新增许可证据，没有标准CC/GPL版本名 |
| 官方2018原始流量、日志与衍生CSV | [UNB §5](https://www.unb.ca/cic/datasets/ids-2018.html)、[AWS License回指](https://registry.opendata.aws/cse-cic-ids2018/) | 允许转载/镜像/再分发，要求数据集引用及AWS链接；不擅写CC-BY或CC0 |
| 随官方CSV分发的标签 | 两数据页均将标注流纳入数据集说明 | 按该官方发行对象的使用条件记录；不是对第三方改标标签的授权判断 |
| CICFlowMeter软件 | [固定LICENSE](https://github.com/ahlashkari/CICFlowMeter/blob/98a5ebad0df579cc8b43eedd3421b3ae87699901/LICENSE.txt) | 软件许可独立，不能替代上述数据条款 |
| WTMC2021/CNS2022等重生成版本 | 各研究者发行入口和生成/标注版本另存 | 本轮未完成其数据许可及文件身份准入，不自动采用 |

这些第一方声明支持后续合法审计方案准备；不等于用户已授权下载，也不构成对任意镜像的身份认证。本轮不公开载荷。数据集原始论文引用：Sharafaldin、Lashkari、Ghorbani，*Toward Generating a New Intrusion Detection Dataset and Intrusion Traffic Characterization*，ICISSP 2018，108–116，[DOI](https://doi.org/10.5220/0006639801080116)。

## 时间与生成链（E2，不冒充包内实测）

2017作者仓库本轮固定到[98a5ebad…](https://github.com/ahlashkari/CICFlowMeter/commit/98a5ebad0df579cc8b43eedd3421b3ae87699901)；2018另核[2018-07-04历史提交1d4e34…](https://github.com/UNBCIC/CICFlowMeter/commit/1d4e34eee43fd2e5fc37bf37dbae0558ca7c17fe)，两者都没有与目标CSV建立精确生成绑定。UNB的V3文字与当前V4仓库不能混为一版。

| 问题 | 固定代码/研究依据 | 对目标发行物的限制 |
|---|---|---|
| Timestamp/Duration | [BasicFlow](https://github.com/UNBCIC/CICFlowMeter/blob/1d4e34eee43fd2e5fc37bf37dbae0558ca7c17fe/src/main/java/cic/cs/unb/ca/jnetpcap/BasicFlow.java)：首包设start，duration=lastSeen−start；[PacketReader](https://github.com/UNBCIC/CICFlowMeter/blob/1d4e34eee43fd2e5fc37bf37dbae0558ca7c17fe/src/main/java/cic/cs/unb/ca/jnetpcap/PacketReader.java)：IPv4微秒路径 | 开始/结束代理的候选解释，不认证CSV单位/格式；其他读取路径不能混用 |
| 日期/AM-PM | 此处固定较晚快照的普通输出`dd/MM/yyyy hh:mm:ss`，Ex加`a`；早期2018-02快照两路均无`a`，见文末复核 | 两条不同路径；不能声称所有文件都缺AM/PM或都已消歧 |
| 时区/DST | [DateFormatter](https://github.com/UNBCIC/CICFlowMeter/blob/1d4e34eee43fd2e5fc37bf37dbae0558ca7c17fe/src/main/java/cic/cs/unb/ca/jnetpcap/DateFormatter.java)依赖默认时区 | 未找到目标发行物的明确时区/DST声明；不按机构所在地或存储区推断 |
| 导出/可用时点 | [FlowGenerator](https://github.com/UNBCIC/CICFlowMeter/blob/1d4e34eee43fd2e5fc37bf37dbae0558ca7c17fe/src/main/java/cic/cs/unb/ca/jnetpcap/FlowGenerator.java)后续包触发超时/FIN处理；[Cmd](https://github.com/UNBCIC/CICFlowMeter/blob/1d4e34eee43fd2e5fc37bf37dbae0558ca7c17fe/src/main/java/cic/cs/unb/ca/ifm/Cmd.java)在EOF导出剩余流 | 最后包可早于导出；120秒默认值不等于每条流的可认证导出延迟 |
| 包长及协议 | [作者PacketReader](https://github.com/ahlashkari/CICFlowMeter/blob/98a5ebad0df579cc8b43eedd3421b3ae87699901/src/main/java/cic/cs/unb/ca/jnetpcap/PacketReader.java)TCP/UDP取payload长度；[CNS2022工具说明](https://intrusion-detection.distrinet-research.be/CNS2022/Tools_Documentation.html)把ICMP支持列作新增 | 不将包长叫线路总字节，不将原表无ICMP当作网络没有ICMP；主控12维提案取消ICMP专列，改用duration_max_s |
| 原版时间质量 | Kokkonen等2019[作者接受稿](https://www.theseus.fi/bitstream/handle/10024/260615/Pdf_file_AAM.pdf?isAllowed=n&sequence=1) §2.2报告其处理数据存在分钟精度、12小时歧义 | 是直接研究观察；不是本次Generated包的字段或错误比例证明 |
| 修订版UTC | [CNS2022工具说明](https://intrusion-detection.distrinet-research.be/CNS2022/Tools_Documentation.html)明确改为UTC和微秒输出 | 只适用于该重生成方案，不能倒写原版已是UTC |

## 标签、四段与结论证据

官方2017页面给周一正常、随后四日分场景攻击；2018 Table 2给14/15/16日最早攻击分别10:32、09:26、10:12，21日有两场DDoS。它们是场景说明，不是逐流真值认证或每分钟完整采集证明。当前没有载荷支持的四段计数；全部null。2018目录没有早于14日的processed日文件，不据此断言无正常数据。

[Engelen等2021作者论文](https://intrusion-detection.distrinet-research.be/WTMC2021/Resources/wtmc2021_Engelen_Troubleshooting.pdf)及[扩展说明](https://intrusion-detection.distrinet-research.be/WTMC2021/extended_doc.html)记录原数据流构造、方向、时间窗和攻击标注问题；原BENIGN需要审计，不能直接称无污染正常。其[再生成版](https://intrusion-detection.distrinet-research.be/WTMC2021/tools_datasets.html)含Attempted与多次更新；[CNS2022数据](https://intrusion-detection.distrinet-research.be/CNS2022/CICIDS2017.html)又是独立对象。未把研究者分类选择改成项目政策。原标签错误经“任一攻击流→攻击分钟”聚合可能放大，这是待验证风险，不伪造受影响分钟数。

两数据集均有日期、工具和设备集中。主控提案因此要求逐日/场景分母，限制为该实验环境的离线顺序比较；不声称生产网络、跨设备或长期周期泛化。正常高负载改为已完成流记录高分位只是一项待批准定义，不证明原业务高峰目标已经得到数据支持。

## 本轮结果与未执行项

实际新增：2017许可FAQ证据及失效入口的准确解释；2018十对象目录、四对象HEAD与字节合计；时间生成链和标签风险；具体12/24维提案、四段候选、元数据/结构样本/全量审计的资源边界。未发现需要本轮修改生产实现的错误。无新载荷下载、包内解析、四段供应审计、真实模型拟合/校准/评分或真实联调。C方向已批准，C17-G12/C18方案和具体下载仍待决定；Data Gate不升级。

## 同日续接复核与新增决定

2026-10-23再次收到较早的协议澄清任务后，从最新有效`9b52c00`复核，未回退。两个独立只读任务分别检查已有材料的要求覆盖和新增直接证据，复用现有报告，不再生成一套相同审计。指定审计、10月22日增量和本日候选证据均已覆盖现有本地材料；本次附件未含作者回复或导师决定，也未检查私人邮箱或全部沟通渠道。

官方核查限三个对象：[UGR main元信息](https://api.github.com/repos/josecamachop/UGR16_FeatureData/commits/main)仍为`760863d31413739a129b3be2d1d52cde217962e8`；[DMP](https://codas.ugr.es/animalicos/doc/deliverable3.pdf)仍标2024-11-20，F.3及数据GPL-3.0文字与已有证据一致，未做历史PDF字节对比；[原始论文](https://nesg.ugr.es/nesg-ugr16/dataset_AuthorVersionFinal.pdf)直接403，未取得新正文。本范围未发现能解除UGR时区/DST/桶端点、许可关系或零正常分母阻塞的新证据；不声称所有渠道都无更新。真实计数沿用10月21日审计，未重算。

本次新增的用户决定为接受C17-G12作为审计与设计方案，明确按其12/24维、结束时间离线代理和高负载限定核验可行性；主数据正式采用及生产迁移仍未批准。随后C18-S另获明确批准并执行，新增的载荷结构证据及离线审计器修复见[实际结果](2026-10-23-c18-structure-sample.md)。仅此四前缀的传输与检查完成，未扩大获取或启动真实运行，Gate维持原判定。

## 从480c57f续接：入口勘误与生成版本边界

[本轮原始来源对照及聚合证据](2026-10-23-c17-source-metadata.md)明确：表单可读、错误节点初始隐藏，旧“发生Server error”推断撤回；匿名browse为403、旧ZIP重定向HTML，注册后有效归档尚未取得。成员、大小及官方校验继续null，不用HTML身份填ZIP字段。

98a5ebad是2022许可提交，eaa853dd为当前可见历史2018早期文件上传；所查快照均未绑定2017包。Ex的AM/PM有版本差异，默认时区/单位分支仅为源码线索。C18-S复用58608行通过五项内部公式检查，不独立证明实际时间单位。没有新增数据载荷、采用/迁移决定或研究Gate升级。
