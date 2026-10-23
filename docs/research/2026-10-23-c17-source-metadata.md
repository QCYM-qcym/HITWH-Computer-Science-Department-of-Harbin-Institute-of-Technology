# C17官方入口、生成版本与时间语义复核

日期：2026-10-23；续接基点：`480c57fdeceb345e526f19f0923dbb8518e0bc55`。状态：**元信息与既有前缀增量核查完成；C17载荷未取得，候选NOT_PASSED，S2/Data Gate仍BLOCKED**。对应[机读证据](2026-10-23-c17-source-metadata.json)、[数据与表示决定包](../project/CANDIDATE-DATA-DECISION-2026-10-23.md)及[候选清单](2026-10-23-candidate-manifest.json)。

本轮没有新增CSV/ZIP/PCAP载荷传输，没有训练、改用2018或修改生产契约。C方向和C17-G12审计设计已经获准，无须重新决定；主数据采用、生产迁移和额外载荷获取仍未批准。三个只读子任务分别核入口、生成版本和本地C18-S一致性，由主控统一成稿。

## 1. 官方入口可读，目标包身份仍未取得

[UNB 2017页](https://www.unb.ca/cic/datasets/ids-2017.html)分别命名GeneratedLabelledFlows.zip与MachineLearningCSV.zip；这不是目录或ZIP成员清单。页面下载href实际为HTTP，301至[HTTPS资料表单](https://cicresearch.ca/CICDataset/CIC-IDS-2017/)。表单GET可读，尚未执行注册成功流程。

**勘误：**旧证据把文本抽取中的“Server error”当成实际故障。复核原HTML发现该节点初始`display:none`，inline JS仅在错误分支显示它。因此撤回“本次表单已发生服务器错误”的解释，保留旧观察及更正原因；不推断正规提交必定成功或失败。本轮未填表、POST、联系作者或绕过403。

以下HEAD逐跳禁止自动重定向，日期均2026-10-23 UTC；未读取任何数据包体。

| UTC | 对象 | 状态与目标 | Content-Type / Content-Length |
|---|---|---|---|
| 08:55:39 | `http://cicresearch.ca/CICDataset/CIC-IDS-2017/` | 301至同路径HTTPS | HTML；未返回长度 |
| 08:55:40 | HTTPS表单根目录 | 200 | text/html；10535字节 |
| 08:55:40 | 同目录`browse.php` | 匿名403 | text/html；未返回长度 |
| 08:55:41 | [既有Generated ZIP URL](https://cicresearch.ca/CICDataset/CIC-IDS-2017/Dataset/CSVs/GeneratedLabelledFlows.zip) | 302至UNB数据集总页 | HTML；未返回长度 |
| 08:55:42 | [既有学习包URL](https://cicresearch.ca/CICDataset/CIC-IDS-2017/Dataset/CSVs/MachineLearningCSV.zip) | 302至同一总页 | HTML；未返回长度 |
| 08:55:43 | [UNB数据集总页](https://www.unb.ca/cic/datasets/index.html) | 200，旧URL重定向终点 | text/html；108784字节 |

表单的Last-Modified=`Sat, 21 Feb 2026 23:06:02 GMT`、ETag=`"2927-64b5d94dfca80"`及Accept-Ranges=bytes均只描述HTML；108784字节也只属于总页。不能当作ZIP大小、版本、Range支持或校验。UNB介绍页GET另为75847字节HTML。HEAD没有命中目标ZIP，不能据未返回校验头推断ZIP无校验。

表单action为`insert.php`、POST；可读JS在`data.ok`成功分支才打开`data.redirect`或缺省`browse.php`，重试链接也初始隐藏。所读HTML/JS没有具体包链接、文件数组、成员、字节数或哈希。仅两条官方域名有界搜索亦未补齐；未猜目录、构造校验文件路径或转镜像。

| GeneratedLabelledFlows所需身份字段 | 本轮结果 |
|---|---|
| 官方介绍页、获取流程入口 | 已核实；不等于有效包直链 |
| 当前有效载荷URL、版本、包Last-Modified/ETag | **null** |
| 完整ZIP成员、成员字节、逐字表头 | **null** |
| 压缩字节、解压合计字节 | **null** |
| 官方SHA256/MD5/其他校验 | **null**；仅说明本轮来源范围内未取得 |

不能把MachineLearningCSV、第三方TrafficLabelling或研究者重生成包的大小/时间/字段套入这些空值。

## 2. 工具源码不是原包生成绑定

官方页及[正式原论文§5的可检索段落](https://www.scitepress.org/PublishedPapers/2018/66398/pdf/index.html)支持CICFlowMeter提取后按每日攻击计划标注的工具家族关系；没有在本轮取得的相关段落中找到精确生成绑定。不声称已搜索PDF全文或官方所有历史。

| 固定快照 | 可核事实 | 不能据此认定 |
|---|---|---|
| [98a5ebad…](https://github.com/ahlashkari/CICFlowMeter/commit/98a5ebad0df579cc8b43eedd3421b3ae87699901) | 2022-01-05T15:41:44Z，Update LICENSE.txt | 不是已认证的2017生成版本 |
| [eaa853dd…](https://github.com/ahlashkari/CICFlowMeter/commit/eaa853dd82f08ba5288bb7f295b471de7313f883) | 2018-02-13T16:27:18Z，当前可见默认分支BasicFlow/PacketReader最早文件上传条目 | 不证明2017软件不存在，也不证明原包用同一实现 |
| [1d4e34ee…](https://github.com/ahlashkari/CICFlowMeter/commit/1d4e34eee43fd2e5fc37bf37dbae0558ca7c17fe) | 2018-07-04T15:50:28Z，另一个时间实现快照 | 不能从2018的V3或当前README的V4倒推2017 |

UNB 2017页的旧ISCX链接现到作者[ahlashkari仓库](https://api.github.com/repos/ISCX/CICFlowMeter)，repository id=121274905；[Applications页](https://www.unb.ca/cic/research/applications.html)的机构旧链接现到[UNBCIC仓库](https://api.github.com/repos/CanadianInstituteForCybersecurity/CICFlowMeter)，id=238022807，fork=true、parent为作者仓库。两者不是同一repository id；共享提交不认证数据生成。作者仓库tags/releases本次均空，仅代表当前API结果，不排除历史二进制发行。

| 时间问题 | 固定源码证据 | 目标Generated包仍未知 |
|---|---|---|
| start / end | [早期BasicFlow](https://github.com/ahlashkari/CICFlowMeter/blob/eaa853dd82f08ba5288bb7f295b471de7313f883/src/main/java/cic/cs/unb/ca/jnetpcap/BasicFlow.java#L118)首包设start/lastSeen，输出Timestamp取start，Duration=lastSeen−start | 逐字列、提取版本、单位与实际起止语义未绑定；不能把Timestamp称导出时间 |
| 单位 | [早期PacketReader](https://github.com/ahlashkari/CICFlowMeter/blob/eaa853dd82f08ba5288bb7f295b471de7313f883/src/main/java/cic/cs/unb/ca/jnetpcap/PacketReader.java#L125)IPv4用micros、IPv6用millis | 不认证原包包含IPv6或实际发生单位混用 |
| AM/PM | [早期普通/Ex](https://github.com/ahlashkari/CICFlowMeter/blob/eaa853dd82f08ba5288bb7f295b471de7313f883/src/main/java/cic/cs/unb/ca/jnetpcap/BasicFlow.java#L1066)均为`dd/MM/yyyy hh:mm:ss`；[7月Ex](https://github.com/ahlashkari/CICFlowMeter/blob/1d4e34eee43fd2e5fc37bf37dbae0558ca7c17fe/src/main/java/cic/cs/unb/ca/jnetpcap/BasicFlow.java#L1076)带`a`，普通仍不带 | 必须限定快照和路径；不能笼统认定所有Ex都有AM/PM，不按攻击标签补下午 |
| 精度 | 早期输出只有秒；正epoch的微秒start经`/1000L`传毫秒再格式化，存在截断路径 | 原包是否走此路径或后续格式化未认证，不能强定原时间误差区间 |
| 时区/DST | [早期DateFormatter](https://github.com/ahlashkari/CICFlowMeter/blob/eaa853dd82f08ba5288bb7f295b471de7313f883/src/main/java/cic/cs/unb/ca/jnetpcap/DateFormatter.java#L8)默认SimpleDateFormat，[7月Ex](https://github.com/ahlashkari/CICFlowMeter/blob/1d4e34eee43fd2e5fc37bf37dbae0558ca7c17fe/src/main/java/cic/cs/unb/ca/jnetpcap/DateFormatter.java#L33)用systemDefault | 生成主机/JVM配置未知；不按地理位置猜，不标UTC |
| 完成与导出 | [FlowGenerator](https://github.com/ahlashkari/CICFlowMeter/blob/eaa853dd82f08ba5288bb7f295b471de7313f883/src/main/java/cic/cs/unb/ca/jnetpcap/FlowGenerator.java#L81)含后续包触发timeout、FIN及current/finished输出；[离线Worker](https://github.com/ahlashkari/CICFlowMeter/blob/eaa853dd82f08ba5288bb7f295b471de7313f883/src/main/java/cic/cs/unb/ca/jnetpcap/worker/ReadPcapFileWorker.java#L138)可至EOF才dump | 最后包、逻辑完成、写出、实际可用不同；默认参数不证明统一120秒延迟或原包配置 |

已接受的C17-G12仍只是**流结束时间作为理想化离线可用时刻代理**。即使以后确认start和duration，也不等于验证实际导出延迟或实时可用性。生成提交/二进制、运行配置、时区/DST和是否二次格式化继续待证。

## 3. C18-S仅复用：五项内部编码一致性

复用[既有四前缀](2026-10-23-c18-structure-sample.md)，每份4194304字节，总16777216字节，58608完整流记录，丢弃624尾字节。四份SHA256分别与获取回执和公开清单匹配，核查前后不变。原始数据仍只在忽略目录。本小节无新增网络请求。

令D=Flow Duration，F/B=Tot Fwd/Bwd Pkts，LF/LB=TotLen Fwd/Bwd Pkts，按CSV数值直接计算：

| 检查 | 预期公式 | 可计算 / 匹配 / 不匹配 |
|---|---|---|
| Flow Pkts/s | `(F+B)*1e6/D` | 58608 / 58608 / 0 |
| Fwd Pkts/s | `F*1e6/D` | 58608 / 58608 / 0 |
| Bwd Pkts/s | `B*1e6/D` | 58608 / 58608 / 0 |
| Flow Byts/s | `(LF+LB)*1e6/D` | 58608 / 58608 / 0 |
| Flow Pkts/s | `Fwd Pkts/s + Bwd Pkts/s` | 58608 / 58608 / 0 |

每项扫描58608行、不可计算0；D全正。规则为`abs(observed−expected) <= max(1e−8, 1e−7*max(abs(observed),abs(expected)))`，是报告采用的数值容差，不是官方精度规格。纯相对容差atol=0、rtol=1e−8时，五项不匹配依次为42/44/1/0/0；rtol=1e−9为1596/1600/14/0/9，rtol=1e−7均0。不能改写成逐位相等或省略atol。完整最大差、分对象和敏感性在机读证据中保留。

后向count/rate均0的8077行、总字节count/rate均0的41451行仍可直接验公式；仅反推比例`D*rate/count`时应排除0/0，比例有效分母分别50531和17157，总包/前向均58608。

**这支持10^6比例的内部编码一致，不独立证明真实elapsed单位。** 若生成器把毫秒D误当微秒并统一计算所有rate，同源字段仍会通过本检查。列名“每秒”不构成独立时间真值，C17与C18之间也不能互相认证生成版本。

58608个时间文本均符合日/月/年、秒精度、小时1—12且无AM/PM/时区后缀；没有独立export/available或IP族列。不能消歧小时制、时区/DST、实际可用性或Protocol0。获取回执的2026时间和S3修改时间不是2018逐流时间。2476个Benign仍仅是流记录，未计算正常分钟、空桶、采集覆盖、四段或H预热供应。

## 4. 下一步的具体交接与停止条件

当前缺少实际包URL及字节，**尚不能形成可执行的新载荷获取方案**。旧C17-P的1GiB网络/4GiB解压值只是假定停止预算，不是估计、实测或批准；不建议据此批准整包。无需追加C18-S，已用完的16MiB不得续传。

用户可自行从UNB按钮进入正规表单，完成本人资料流程后，仅交接GeneratedLabelledFlows对应项的以下非私人元信息；这是外部事实缺口，不是再次询问研究路径：

1. 官方浏览页来源、查询日期、准确文件名/路径、包字节数、修改时间及版本说明。
2. 官方manifest/完整成员和解压字节信息（若提供）；未提供保留null。
3. 官方校验文件/算法（若提供）；后续本地SHA不能冒充官方公布值。
4. 有效官方包URL的公开部分；私密授权参数、Cookie、Token和表单个人资料不入公开仓库。
5. 如有生成说明，提供该包绑定的提取器版本/二进制或commit、配置、IP族路径、时区/DST、原始时间格式/精度及二次处理依据。

收到元信息后先核发行物一致性，再列确切对象、传输方式、预计与上限字节、解压/本地总量、是否可只读成员及失败停止条件，等待独立载荷批准；不得先取包/central directory再补申请。若正规流程失败，保留实际状态，由用户选择是否自行经[官方联系入口](https://www.unb.ca/cic/about/contact.html)询问上述问题；本轮没有代发。

## 5. Gate与未执行范围

| 判定对象 | 结果及限制 |
|---|---|
| 官方入口元信息核查 | 已执行：正规表单可读；匿名目录403，目标归档身份未取得 |
| C17结构/时间/标签与四段供应 | 载荷审计NOT_RUN；未知不补值，不冻结四段 |
| C18-S局部结构及算术一致性 | 已执行，限四个字节前缀；不认证真实时间与分钟供应 |
| C17-G12审计设计 | 已批准；无采用/迁移/额外获取/训练的自动授权 |
| 真实短片段工程验证、真实训练、正式FPR及比较 | BLOCKED / NOT_RUN；无实际运行ID或真实模型产物 |

沿用现行八项Gate和S0—S9验收分母。原UGR零正常测试分母及时间/许可关系不变；本轮未发现需修改生产实现的错误，仅修正证据解释。代码、合成CI、元信息和真实研究证据分别记录。
