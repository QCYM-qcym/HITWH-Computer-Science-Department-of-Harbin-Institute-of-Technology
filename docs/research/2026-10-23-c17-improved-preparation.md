# CICIDS2017作者修订版：获取准备与适用性审计

后继状态：用户已明确批准C17-I1并完成唯一对象获取；[实际载荷审计](2026-10-23-c17-i1-payload-audit.md)接续本方案。本文和JSON保留获取前的事实、预算及未批准边界，不将后续批准回写成既往已获准。

日期：2026-10-23；续接：`07e5cf2dbb1021c893a9c56abac245b2ae79efb9`。范围：来源/HTTP元信息、版本特定适配与隔离审计工具准备。**用户已决定优先审计CICIDS2017_improved，原Generated镜像备选；未批准本对象下载、最终采用、Attempted映射或生产迁移。** C17-G12保留为参考设计，报告V0.40及生产契约不变。候选NOT_PASSED，Data Gate/S2仍BLOCKED。

关联：[机读身份与预算](2026-10-23-c17-improved-preparation.json)、[工具指南及下一完整提示](../guides/c17-improved-audit.md)、[实施记录](../superpowers/plans/2026-10-23-improved-audit-prep.md)、[原适用性分析](2026-10-23-cicids-suitability-analysis.md)、[旧C17-G12决定包](../project/CANDIDATE-DATA-DECISION-2026-10-23.md)。旧分析的“助手建议”是当时状态，由本次用户明确决定更新为审计优先级批准，不回写成既往已批准。

## 1. 发行物身份与来源证据

来源链为[论文作者主页](https://intrusion-detection.distrinet-research.be/CNS2022/index.html) → [下载前说明](https://intrusion-detection.distrinet-research.be/CNS2022/Dataset_Download.html) → [数据目录](https://intrusion-detection.distrinet-research.be/CNS2022/Datasets/) → **CICIDS2017_improved.zip**。它是CNS2022论文作者重新提取和修订标注的发行物，不能称UNB原包或原包的逐字节镜像。只获取网页/说明，目标ZIP仅主控一次HEAD。

| 字段 | 当前证据；未读取包体 |
|---|---|
| 准确对象 | `https://intrusion-detection.distrinet-research.be/CNS2022/Datasets/CICIDS2017_improved.zip` |
| 目录显示 | `328M`；`2023-04-27 16:41`，未注明时区；不是精确字节或版本号 |
| HEAD时间/状态 | 2026-10-23T13:47:02.022947Z；200；禁止重定向，返回同一URL |
| Content-Length / Type | **343549013字节**；`application/zip` |
| Last-Modified | `Thu, 27 Apr 2023 14:41:35 GMT`；对象元信息，不是数据时区 |
| ETag / Accept-Ranges | `"147a2455-5fa525a6eab30"` / `bytes`；ETag不当作MD5，Range未执行 |
| 作者校验、归档成员、解压量 | 所查目录/说明与固定代码树未给出，均null；不声称所有渠道均无 |
| 不可变发行号、生成绑定 | 未取得ZIP与精确提取/标注commit、二进制或运行配置的绑定；同名URL可能变化 |
| 本地载荷 | 五个已知项目工作区的data、运行目录及获取记录未发现本包；没有扫描无关私人目录。既有C18-S是另一对象，不能移用 |
| 本轮新增数据载荷 | **0字节**；没有ZIP/CSV/PCAP GET、Range、在线预览或包内读取 |

发布方法可追溯至[CNS2022_Code固定README](https://github.com/GintsEngelen/CNS2022_Code/blob/f0ce502818e59e6cd062720ab2286c5ff6f2bdec/README.md)：修复/重排PCAP后用修订工具提取，再用fixed标注notebook；这不证明下载包精确版本。代码快照`f0ce5028…`晚于ZIP修改时间，也不能直接当作生成提交。HF原包的283876488字节及LFS哈希不适用于本包。

## 2. 数据、标签与软件使用条件

| 对象 | 一手说明 | 本阶段判断 |
|---|---|---|
| 原始流量/UNB发行物 | [UNB License段](https://www.unb.ca/cic/datasets/ids-2017.html)公开供研究人员使用并要求引用原论文 | 底层来源依据；不自动认证修订对象或所有再分发权利 |
| 作者修订数据及标签 | 作者主页公开重建数据，[下载页](https://intrusion-detection.distrinet-research.be/CNS2022/Dataset_Download.html)讨论研究使用和标签处理 | 对有界本地科研审计有正面来源支持；所查页面无明确标准数据再分发许可，不公开转存载荷。缺标准许可不等同禁止本地获取 |
| CNS2022标注/实验代码 | [固定README](https://github.com/GintsEngelen/CNS2022_Code/blob/f0ce502818e59e6cd062720ab2286c5ff6f2bdec/README.md)要求引用；完整树19项未见LICENSE/COPYING，API license=null | 不自行标MIT/GPL；只读审阅，不复制整份代码入库 |
| 修订CICFlowMeter | [固定LICENSE](https://github.com/GintsEngelen/CICFlowMeter/blob/4dd5319ad36457010d7a406505790b17a5828108/LICENSE.txt)为MIT形式软件授权并要求工具论文引用 | 仅适用所述软件，不套用于数据、标签或另一个仓库 |

当前不公开上传原始ZIP/CSV、身份列或逐流明细，不联系作者。后续论文须保留原数据及CNS2022修订论文引用；若运行修订工具，还核其独立署名要求。正式采用与公开再分发分别判定。

## 3. 一个对象的有界获取方案（待明确批准）

本提案编号 **C17-I1**；仅上述343549013字节对象，不含原包镜像、2018、PCAP或其他日期文件。网络许可与数据公开发布是两件事；此前C18-S授权不适用。

| 资源/条件 | 提案值与执行约定 |
|---|---|
| 身份固定 | URL、Length、ETag和Last-Modified按上表；执行前HEAD重核。任何变化先停，更新方案后再决定，不静默换源 |
| 传输与累计预算 | 一次顺序GET，带If-Match及If-Unmodified-Since绑定上表对象、Accept-Encoding: identity；不分片、不续传；预期343549013字节。所有尝试累计HTTP响应体上限 **360MiB=377487360字节**；自动重试 **0**。失败已读字节计入，不另起新预算 |
| 预算口径 | 应用读取的HTTP响应体，含失败尝试；不声称精确控制TCP/TLS头、底层重传流量。网页/HEAD单独记录 |
| 超时 | 连接30秒、单次读取30秒、总下载30分钟；任一到期停止，不自动重试 |
| HTTP停止条件 | 禁止所有重定向；非200、非application/zip、压缩传输编码、长度/对象标识变化即在读体前停止；读体逐块计数，超过预期/累计预算停止；少于预期亦失败 |
| 落盘与SHA | 新运行目录，以独占创建`.part`写入；不覆盖原文件。流式SHA-256，完整下载后复算并记录实际字节/GET头/时间，成功后同卷改名，无第二份归档副本。此SHA仅本地实测，非作者公布 |
| ZIP落盘预算 | 最多360MiB；含未完成`.part`，不重复保留完整副本 |
| 目录检查 | 下载后、**解压前**只读本地中央目录；在批量解析前有界核真实目录项，成员≤100、单成员≤2GiB、总解压≤4GiB、单成员/总压缩比≤200；声明与实际读取均受限 |
| 路径与格式 | 拒绝路径穿越、绝对/盘符/反斜杠路径、规范路径冲突、符号链接、加密和不支持压缩；不执行包内脚本，不递归打开嵌套归档 |
| 解压和临时预算 | 若目录检查通过，只按白名单读取CSV及文本说明；解压合计≤4294967296字节，单文件≤2147483648字节。未知成员先报告，不自动执行或展开；审计/临时处理≤1GiB |
| 总磁盘上限 | 新运行目录 **6GiB=6442450944字节**；开始前确认空闲≥6GiB，逐步检查。归档+4GiB解压+1GiB临时小于此上限；不是预计解压大小 |
| 本地保存 | 忽略目录`.runtime/c17-improved-<run>/`下archive、extracted、logs、audit分开；原始文件只读共享，审计输出独立。公开仅身份/哈希/脱敏汇总，不含私人绝对路径 |

成员/解压规模未知不阻止提出这个有界方案：它们是获准下载后、解压前的检查项，超限即停止，不调整预算后继续。当前工具不自动联网或解压；批准后由主控按本方案获取，再执行目录检查及有界离线审计。若前置假设失败，保留失败记录与已接收字节，不声称载荷可用或Gate通过。

## 4. 时间、字段与表示适配原则

作者[工具文档](https://intrusion-detection.distrinet-research.be/CNS2022/Tools_Documentation.html)说明UTC微秒输出和流终止修复，这是方法证据；必须与实际包逐字表头、原时间文本及生成路径核对。**不将原版09—12、12—14、14—17直接改成UTC配置，也不借攻击标签反推转换。**

完整流统计只能进入末包/结束代理所属分钟，不能回填开始分钟。即使`start+duration`成立，也缺实际写出/可获取时间，仍仅支持理想化离线回放。分钟为`[m,m+60s)`、窗口结束后使用；秒级或小时制歧义须传播至所有可能桶/分区，不能随意取中点。跨分区长流携带前段信息应保留污染审计，将完成桶标为boundary_contaminated、不评分且重置历史；不能删流后用余桶恢复完整性。跨文件不能按文件边界截断流或静默去重。

缺行和上游过滤会影响分钟完整性；出现BENIGN流、CSV无NaN或文件读完均不能认证完整采集。确认无完成流的桶可以计0完成事件，但不等于网络无流量，也不自动成为可信正常。采集未知、记录缺失、无效桶保持独立原因；空完成桶默认unknown，只有独立正常依据才授予正常资格。每个显式完整采集区间为独立epoch，跨epoch/缺口的流污染完成桶，历史重置；单一确证连续epoch跨午夜本身不触发重置。合法攻击/未知标签输入不因测试标签而删历史；训练/校准另检查当前及所需历史全正常。

实际字段映射、Attempted对照及工具执行边界在以下增量节统一登记；未核ZIP前不构造生产12/24维输入或新标签Schema。

### 4.1 固定源码与字段候选（不是包内表头）

提取器固定为[4dd5319ad36457010d7a406505790b17a5828108](https://github.com/GintsEngelen/CICFlowMeter/tree/4dd5319ad36457010d7a406505790b17a5828108)，标注固定为[f0ce502818e59e6cd062720ab2286c5ff6f2bdec](https://github.com/GintsEngelen/CNS2022_Code/tree/f0ce502818e59e6cd062720ab2286c5ff6f2bdec)。以下依据[FlowFeature](https://github.com/GintsEngelen/CICFlowMeter/blob/4dd5319ad36457010d7a406505790b17a5828108/src/main/java/cic/cs/unb/ca/jnetpcap/FlowFeature.java)和[fixed标注notebook](https://github.com/GintsEngelen/CNS2022_Code/blob/f0ce502818e59e6cd062720ab2286c5ff6f2bdec/Labelling/CICIDS2017_labelling_fixed_CICFlowMeter.ipynb)，actual_header仍null。时间列候选Timestamp，持续时间Flow Duration，标签Label及Attempted Category；id/身份列不进入特征。

| 参考特征 | 源码列名候选 | 定义、单位与结束桶聚合 |
|---|---|---|
| completed_flow_count | 合法流段记录 | 每条计1；不是唯一连接/活跃流数；覆盖另审 |
| fwd_packet_sum | Total Fwd Packet | 非负整数包数求和 |
| bwd_packet_sum | Total Bwd packets | 非负整数反向包数求和 |
| fwd_byte_sum | Total Length of Fwd Packet | 源长度和，字节；协议路径口径待绑定，不称线路总字节 |
| bwd_byte_sum | Total Length of Bwd Packet | 同上，反向 |
| tcp_flow_count | Protocol | 已认证协议值6的记录数 |
| udp_flow_count | Protocol | 已认证协议值17的记录数 |
| other_protocol_flow_count | Protocol | 已认证支持集合中非6/17的记录；缺失/非法/语义未知不硬归other |
| duration_max_s | Flow Duration | 路径认证为微秒后除1e6，取最大；不替换为Total TCP Flow Time |
| duration_median_s | Flow Duration | 同上，取中位数 |
| duration_p95_s | Flow Duration | 同上，linear Q95 |
| no_backward_packet_flow_count | Total Bwd packets | 等于0的记录数；不直接解释为失败连接 |

[PacketReader](https://github.com/GintsEngelen/CICFlowMeter/blob/4dd5319ad36457010d7a406505790b17a5828108/src/main/java/cic/cs/unb/ca/jnetpcap/PacketReader.java)的TCP/UDP/SCTP路径取payload length，ICMP/IGMP不都赋相同长度量，默认0不等于所有协议均已测得零载荷。方向一般按首观测包，可因SYN/ACK反转或流段继承，不是固定内外网方向。协议enum含DEFAULT0、ICMP1、IGMP2、TCP6、UDP17、SCTP132；DEFAULT0语义未清时不能硬归other。三类协议计数须在支持集合审计后互斥覆盖，不能为凑恒等式隐藏未知。

目前源码语义有12维覆盖线索，未发现必须改变宽度的载荷证据，也不代表12/24已获正式采用。隔离工具本轮只审计供应/失败和可选源字段，不构造生产特征向量。真实缺项/单位不一致时先提交最小修订，不补零或伪造UGR八标签。

### 4.2 时间生成路径及上游覆盖

[BasicFlow Ex](https://github.com/GintsEngelen/CICFlowMeter/blob/4dd5319ad36457010d7a406505790b17a5828108/src/main/java/cic/cs/unb/ca/jnetpcap/BasicFlow.java#L1244)调用[DateFormatter](https://github.com/GintsEngelen/CICFlowMeter/blob/4dd5319ad36457010d7a406505790b17a5828108/src/main/java/cic/cs/unb/ca/jnetpcap/DateFormatter.java#L27)，以epoch微秒生成Instant，再把T换空格并去掉Z；小数位可随尾零省略，不应强制恰好六位。无Z文本不等于本地时间，位数少也不自动证明低精度。旧普通输出/getter仍有JVM默认时区的12小时无AM/PM路径。IPv4读取微秒，部分IPv6/helper读取毫秒；默认离线worker读IPv4不读IPv6。这些是指定代码路径，不证明ZIP走哪一路或已混用单位。

标注函数的Unix攻击常量使用纳秒，不是Flow Duration单位。保留原文本、解析规则、精度依据与文件身份；工具配置中的UTC/单位证据是显式输入，不能通过填写一个字符串自动认证真实时间。导出时刻与实际可用时刻均未取得。

fixed notebook前处理先将Infinity变NaN、转数值，再对所有列dropna；即使G12不需要的字段无效，也可能删除整流。故完整读取修订CSV不能独自证明流未遗漏，特别是空桶和正常分钟真值。完整性需额外生成/过滤/采集依据；不足就保持unknown。相同五元组/Flow ID或特征碰撞不必是真重复，超时流段可重复身份；仅在有来源证明的拷贝才去重，其他碰撞保留并标不确定。

### 4.3 Attempted具体待决项

作者[下载说明](https://intrusion-detection.distrinet-research.be/CNS2022/Dataset_Download.html)允许依预处理并入攻击，拿不准时建议归Benign，并不建议作为独立学习类别；这是作者建议，未成为本项目政策。fixed notebook以category=-1初始化，0—6分别表示未发payload、端口/系统关闭、启动/结束artefact、无恶意payload、攻击相关artefact、攻击实现/启动有误、目标无响应。category6尤其不能解释为可信正常业务。

保留Label原词和辅助编码频数，检查两者一致性；缺失/未知编码或组合矛盾为unknown，不默认正常。实际包未读，`<攻击名> - Attempted`只是源码候选；`Infiltration - Portscan`不能因连字符被误认Attempted。

| 审计方案（均未批准） | 合法Attempted映射 | 完整BENIGN+Attempted分钟 | 确认攻击+Attempted分钟 | 代价 |
|---|---|---|---|---|
| P_U（推荐主口径候选） | UNKNOWN | unknown，退出主要评价/正常拟合资格 | 保留attack_present，label不完整，退出主要评价 | 更保守正常分母，但选择性排除攻击伴随场景，必须报覆盖/排除 |
| P_B（作者建议归并对照） | BENIGN | normal candidate并标Attempted相关 | attack，可标混合 | FPR包含失败攻击/副作用等活动，不等于普通正常业务误报 |
| P_A（攻击相关对照） | 对应攻击类别 | attack | attack | 漏报含无恶意行为的尝试流，不解释为成功攻击或纯恶意行为漏检 |

三方案只做审计对照，共享未删去标签相关记录的合法输入；不能看模型效果再择优。真正unknown标签在三方案均未知；确认攻击+真正unknown保留攻击存在事实、主评价排除。同一分钟999条BENIGN和1条确认攻击仍为attack，与占比无关。主总体normal/attack/unknown互斥，mixed/attempted/attack_present为可重叠辅助计数，不能相加作总数。

推荐将P_U提交为主要口径候选，P_B/P_A作敏感性计数；真实频数及分钟影响尚未运行，因此本轮不要求盲选正式口径。**下载/审计批准不批准任何标签映射。** 不把Attempted训练成新类，也不删除其合法特征后伪称完整分钟。

### 4.4 正式迁移仍待独立决定

可复用IF/AE框架、中位数/MAD思路、单worker任务管理、run_id、分页/回放和四页面布局。获准采用后才适配：流读取与覆盖掩码、12维聚合及24维历史；d驱动预处理/模型/重载兼容；三态/混合/Attempted标签与Parquet；公共契约/OpenAPI/TS类型、CLI登记、API产物验证、解释通道及导出；同步需求/报告的数据、维度与结论边界。不能只改134常量、补零或复用旧权重。当前src/configs/公共设计契约均不改，V0.40历史保留。

## 5. 四段、高完成流组与Gate

| 对象 | 当前结果 |
|---|---|
| 每文件/每日原始、有效、无效、排除流及原因 | null / PAYLOAD_NOT_ACQUIRED |
| 四段UTC边界、完整/正常/攻击/混合/Attempted/未知分钟 | NOT_FROZEN；全部null |
| 连续有效段、H15/H30及共同分钟、训练校准全正常资格 | 全部null；工具人工测试不填真实计数 |
| 测试普通正常、高完成流正常、持续片段 | 全部null / NOT_RUN，不能从流数量或论文推算 |
| 真实拟合/评分/阈值校准、CLI/API真实联调、正式比较 | NOT_RUN |

旧三个开发段180/120/180分钟及H15上界165/105/165、H30与共同上界150/90/150只作日历参考。实际按各连续有效段重新预热，不拼接；150分钟不能单独证明AE不可训练，但限制容量选择、验证与99%尾部估计的稳定性。独立正常校准linear Q99、严格大于报警保持；不降低分位点或用测试效果选范围。

建议正常高完成流门槛的资格集合为**所有拟比较方法及H15/H30共同输入有效，且当前和所需历史均正常的训练分钟**；在这些分钟的原始completed_flow_count取linear Q90，固定到测试。测试普通组为共同有效可信正常且计数≤门槛，高组为严格>门槛；训练资格空或测试子组空时null及原因。门槛不取测试分位数，名称不解释为线路带宽或业务压力。此为待审口径，未冻结真实配置。

| Gate分项 | 修订版当前状态 |
|---|---|
| 1 本地只读准备 | 可执行；已核公开来源，不触发真实拟合 |
| 2 结构/数值/标签 | NOT_RUN；只有源码字段能力及人工工具检查 |
| 3 时间语义 | 文档PARTIAL；实际文本/单位/精度/覆盖/导出未核 |
| 4 使用条件 | 本地科研发布依据已核；数据再分发条款未知，载荷不公开 |
| 5 四段与样本 | NOT_FROZEN / NOT_VERIFIED，全部实际计数null |
| 6 真实工程 | BLOCKED / NOT_RUN；没有采用、冻结配置及真实模型产物 |
| 7 正常FPR | BLOCKED / NOT_RUN；真实正常测试分母未知 |
| 8 模型比较 | BLOCKED / NOT_RUN；不将准备或合成测试写成效果证据 |

原UGR八项判定及S0—S9验收分母不变。原包和修订包来自同一底层采集，不是两个独立网络；五天结果至多支持相应场景短期离线回放，日期/攻击/设备混杂须分日列分母，不能据此声称长期规律或外部泛化。

## 6. 本轮实际实现与验证（SYNTHETIC_ONLY）

新增独立标准库工具tools/data_audit/c17_improved.py、48项测试及人工JSON fixture，不修改生产src/configs/公共契约。实现了显式配置、聚合供应、失败原因、独立空桶正常依据、capture epoch/缺口与跨分区污染、H15/H30交集、训练Q90测试分组和有界ZIP目录预检。只认配置字段数值有效性，不认证真实列/单位/协议，不生成12/24向量；模型共同数null。逐文件完整分钟因全局掩码无法分摊而null，按日/候选分区可报工具范围内计数。未实施受控解压、真实流大规模性能验证或生产适配。

测试先行证据：初始25项因工具缺失失败；标签优先级/矛盾及显式精度回归出现6项失败后修正；独立审查新增回归出现9项失败后修正。期间其他针对性新增用例也先失败再实现。原始日志留在忽略目录，公开只记摘要，不提交含本机堆栈的日志。最终C17新增48项、连同C18原10项共58项数据审计测试通过。

两项独立复核的原反例已修复：空桶默认unknown而非自动normal；跨gap/epoch流污染完成桶，窗口同epoch；巨整数/特殊ZIP失败安全编码；伪造EOCD在创建ZipInfo前按实际目录条数拒绝；配置额外备注不回显。训练资格空时Q90及普通/高组都null。确认连续epoch跨午夜可延续；按日无条件重置没有用户依据，未引入该新政策。

主控实际运行：

```text
.venv\Scripts\python -X utf8 -m pytest tests/core tests/backend tests/integration tests/data_audit -q
187 passed, 34 subtests passed, 1既有TestClient弃用警告
.venv\Scripts\python -X utf8 -m unittest discover -s tests/repository -p "test_*.py"
13 tests, OK
```

按指南生成仅12条人工流的CSV和单成员文本ZIP，两条CLI均exit0；归档extracted/member_contents_read/crc_verified均false。人工四段各40分钟，H15/H30输入有效分别25/10；训练normal40、验证normal39/attack1、校准normal40、测试normal37/attack1/unknown2。人工训练共同正常资格10，完成流Q90约1.1，测试普通9/高组1。这些均由人工覆盖/正常声明生成，**不是实际数据供应或模型得分**。无独立空桶正常证据的空CSV反例保持normal0、Q90/子组null。

没有运行真实载荷审计、四段/子组供应、真实IF/AE拟合/评分/校准或真实CLI/API/网页联调；正式比较NOT_RUN。前端无改动，不额外本地重跑其套件，远端CI按实际工作流核验。进度/隐私/身份/链接/暂存及Desktop同步结果见维护记录与最终交付，不预填本次SHA/CI。

## 7. 收敛后的待决项

当前可以审阅并单独批准的仅为**C17-I1一个作者ZIP的有界获取及离线适用性审计**：343549013字节预期、累计360MiB/零重试、6GiB目录及上述归档/解压硬上限；不包含训练或生产迁移。尚未执行，原因是对象与预算未获明确批准。

Attempted主口径推荐P_U但不要求在没有频数时盲选；载荷审计可先做三方案计数，后交真实影响与覆盖代价。UTC四段、空桶覆盖依据、12/24及主数据采用、生产迁移留待实际证据后的独立决定；本轮不再次询问审计优先级或A/B/C。
