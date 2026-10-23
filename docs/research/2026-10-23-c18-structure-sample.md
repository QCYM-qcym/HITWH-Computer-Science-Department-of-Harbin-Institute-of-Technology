# C18-S四个有界结构样本：实际获取与离线核查

日期：2026-10-23。范围：用户明确批准的官方2018年2月14、15、16、21日CSV各最多4MiB、总不超过16MiB。状态：**PREFIX_STRUCTURE_INSPECTED / FOUR_SPLIT_SUPPLY_NOT_VERIFIED**。续接`9b52c00`及未提交的C17-G12审计设计批准记录。未采用2018为主数据，未改变生产契约、训练或开展真实联调。机构/版本背景见[候选证据](2026-10-23-cic-candidate-evidence.md)，完整字段和可复算汇总见[JSON证据](2026-10-23-c18-structure-sample.json)。

## 获取范围、身份与字节

来源链为[UNB](https://www.unb.ca/cic/datasets/ids-2018.html)→[AWS官方登记](https://registry.opendata.aws/cse-cic-ids2018/)→官方`cse-cic-ids2018`桶的`Processed Traffic Data for ML Algorithms/`四对象。没有从其他CSV发行物或2017包借用字段结论。四个完整对象合计1,396,786,510字节，本次只取每个开头4,194,304字节，实际共**16,777,216字节**。这是HTTP响应body计数，不含请求头、TLS和TCP开销；读取前若干行并不代表只传输了若干行。

| 官方对象 | 完整对象字节（HEAD） | 实取body字节 | 完整数据记录 | 末尾截断字节 |
|---|---:|---:|---:|---:|
| Wednesday-14-02-2018_TrafficForML_CICFlowMeter.csv | 358223333 | 4194304 | 18935 | 89 |
| Thursday-15-02-2018_TrafficForML_CICFlowMeter.csv | 375945899 | 4194304 | 9125 | 23 |
| Friday-16-02-2018_TrafficForML_CICFlowMeter.csv | 333723605 | 4194304 | 18059 | 138 |
| Wednesday-21-02-2018_TrafficForML_CICFlowMeter.csv | 328893673 | 4194304 | 12489 | 374 |
| 合计 | 1396786510 | **16777216** | **58608** | **624** |

每次先HEAD核对原清单的大小和ETag，再以`Range: bytes=0-4194303`、`If-Match`及identity编码请求。四次GET均206，Content-Range、Content-Length、ETag与目标一致；没有重定向或重复GET。读取前持久化4MiB预算，分块读取上限，单次获取脚本遇到已有GET记录即拒绝重复。四个片段SHA256、起止请求时间和响应元信息完整保存在JSON；片段哈希不是完整对象哈希，完整SHA256仍未知。

最初代理路线的Python及curl HEAD发生TLS握手EOF，尚无载荷GET、body为0。相同官方URL在直连且保留证书校验的HEAD成功后，使用同一路线取得上述四前缀；未关闭证书校验或修改系统代理设置。原始片段和完整本地获取日志留在忽略的数据目录，未公开载荷、逐流记录或设备标识。

## 实测字段与数值结构

四个前缀的表头顺序完全相同，均80列：**78个可数值解析字段、Timestamp及Label**。这不是80个可直接用于模型的特征；`Dst Port`和标签均不纳入既有12维提案。逐字80列表头见JSON。前缀内所有完整记录列数一致，没有重复字段名；数值列未观察到空值、不可解析值或非有限值。这只描述这58,608行，不认证全文件数值质量。

| 设计所需语义 | 本次实测原字段 | 当前认证范围 |
|---|---|---|
| 首包时间候选 | Timestamp | 秒精度文本可按日/月名义钟面解析；生成绑定、时区及小时制未认证 |
| 持续时间候选 | Flow Duration | 非负数值；目标发行物单位未绑定，不据量级推断微秒 |
| 双向包数 | Tot Fwd Pkts / Tot Bwd Pkts | 前缀中为非负整数；方向及观测范围仍待生成链认证 |
| 双向字节候选 | TotLen Fwd Pkts / TotLen Bwd Pkts | 非负整数；不得据列名认证线路总字节或载荷字节 |
| 协议 | Protocol | 观察0、6、17；0的含义未认证，不映射为ICMP或真实other协议 |
| 流标签 | Label | 原词Benign及五个攻击词，未将其改为UGR八标签 |

Protocol=0在四前缀各49、30、42、53行，合计174；固定工具对非TCP/UDP的编码行为不足以将其认证为某协议。没有流ID、源/目的IP或SrcPort，无法在此发行物中直接完成完整五元组去重、IP族认证或设备归因。重复时间文本不能当作重复流，也没有据此删行。

## 时间与标签结果

下表为**未消歧名义钟面**范围，不是UTC时刻或已认证事件时间顺序。日期中的14/15/16/21大于12，支持样本按日/月解析；所有小时均在1—12，没有AM/PM或时区。不能借官方攻击日程把01/02补成下午。钟面比较逆序只是诊断，不能据此断言真实时间逆序。

| 日期 | 名义钟面最小—最大 | 钟面比较逆序次数 | 重复时间文本行数 | 原词Label计数 |
|---|---|---:|---:|---|
| 2月14日 | 08:30:38—10:46:11 | 23 | 18287 | Benign 98；FTP-BruteForce 18837 |
| 2月15日 | 08:25:10—09:50:12 | 306 | 8839 | Benign 69；DoS attacks-GoldenEye 9056 |
| 2月16日 | 08:26:55—10:27:23 | 42 | 17422 | Benign 109；DoS attacks-SlowHTTPTest 17950 |
| 2月21日 | 01:55:46—10:43:21 | 1172 | 10565 | Benign 2200；DDOS attack-LOIC-UDP 1730；DDOS attack-HOIC 8559 |

原词Benign共2,476条流记录，标签空值为0。其余词按原文汇总，尚未建立版本特定的正式标签映射；JSON中的`unmapped_non_benign_rows`仅表示工具未作语义映射的非Benign行数，不是缺失标签数或数据错误率。Benign不能直接认证正常分钟，前缀外的攻击流或采集缺失仍可能影响同一分钟。没有计算分钟混淆矩阵、正常误报率或攻击漏报率。

固定[BasicFlow](https://github.com/UNBCIC/CICFlowMeter/blob/1d4e34eee43fd2e5fc37bf37dbae0558ca7c17fe/src/main/java/cic/cs/unb/ca/jnetpcap/BasicFlow.java)支持首包Timestamp及lastSeen−start的Duration解释，普通输出使用12小时无AM/PM格式，另一输出路径带AM/PM；但未绑定这四CSV的确切生成提交。[PacketReader](https://github.com/UNBCIC/CICFlowMeter/blob/1d4e34eee43fd2e5fc37bf37dbae0558ca7c17fe/src/main/java/cic/cs/unb/ca/jnetpcap/PacketReader.java)的IPv4微秒和IPv6毫秒路径不同。样本又无IP族字段，因此不能把源码某条路径的单位普遍套到这些记录。流结束代理、真实导出和实际可用时刻仍须分开认证。

## 四段供应与候选决定

本次是按字节位置取得的前缀，不是随机样本，也不是最早4MiB时间段。前缀内已出现大量攻击标签且钟面顺序不单调，不能把“文件前N行”用作训练。没有完整日覆盖、采集清单、唯一时间或完整标签证据，不能将跨度中的空分钟补零，不能识别完整正常分钟、混合分钟或连续采集段。

因此训练/模型验证/独立校准/测试各段的正常、攻击及历史预热后有效分钟仍为**null / NOT_VERIFIED**；H=15/30供应没有本次实测结论。未冻结2018四段，未采用2018为主数据；C17-G12继续是已获用户接受的审计与设计方案，其官方包仍未取得。当前结构证据支持保留2018备选，但小时制、单位绑定、Protocol0及正常连续供应增加了必须解决的审计条件。本次没有扩大到完整CSV、其他日期或PCAP，也不提出根据样本攻击比例选择测试范围。

原UGR Gate仍BLOCKED，候选Gate仍NOT_PASSED。真实训练、真实短片段CLI/API/网页/导出验证及正式比较均NOT_RUN。

## 复核方法与验证

实际离线入口为[审计工具](../../tools/data_audit/c18_prefix.py)，不含网络或模型调用。复用本地四前缀及获取日志，输出路径须为新文件：

```powershell
python -X utf8 tools/data_audit/c18_prefix.py --root '<已获准前缀目录>' --output '<新的汇总JSON>'
python -X utf8 -m unittest discover -s tests/data_audit -p 'test_*.py'
```

先运行8项失败测试，再实现离线核查并通过。实际样本暴露原标签拼写为Benign，初稿只识别BENIGN；补充该回归及Protocol0语义保护，观察2项失败后修正，**10项通过**。修复只影响本轮离线审计器，没有改变生产标签契约。真实片段重新离线审计通过；独立复核再次核对四响应、SHA256、字节、完整记录及Benign计数。仓库维护和远端CI按最终提交实际记录，不将合成测试称为研究效果证据。

## 后续本地复用补证（无新增传输）

从480c57f的[时间/速率一致性复核](2026-10-23-c17-source-metadata.md#3-c18-s仅复用五项内部编码一致性)验证四份前缀哈希不变，58608行五项公式在完整报告容差内匹配。同源公式不能独立认证实际elapsed单位、AM/PM、时区或可用性，不升级分钟供应/数据采用状态。
