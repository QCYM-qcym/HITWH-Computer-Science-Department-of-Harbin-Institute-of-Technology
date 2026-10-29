# 候选源记录到分钟输入开发计划

> **For agentic workers:** 使用先失败测试再实现；独立审查；Commit/Push仅GitHub Desktop，不合并main。

**Goal:** 补齐人工源记录→完成事件分钟13维→独立标签口径→既有13/26数值入口，形成可运行的适配接缝。

**Architecture:** 新增隔离SYNTHETIC_ONLY适配模块与有界CLI；不读取真实CSV，不改变134/268生产契约。三政策并列计算，用户显式选择输出哪个人工normal掩码，选择不代表最终研究批准。

**Tech Stack:** 现有Python/NumPy/标准库，无新依赖。

**Spec:** [V0.40 §4.1.1/4.1.2](../../reports/开题报告-V0.40-公开文本.md)、[G13U定义](../../research/2026-10-24-c17-g13u-audit.md)、[上批数值模块](../../guides/candidate-inputs.md)。日期2026-10-30，基点26df256；用户批准自主迭代至北京时间10月31日12:00，常规工程由主控决定。原真实训练/标签/主数据/迁移限制保留。

## Global Constraints

- 明确人工源钟面、开始+duration_us完成代理；完成分钟为[t,t+60s)，不声称实际导出时刻或认证UTC。
- Protocol0独立unresolved；已知other1/2/132，TCP6/UDP17；其他码无效。标签和record_key不进入特征。
- 原标签/Category全部保留审计；P_U/B/A只作候选，未知或矛盾优先unknown，不能为增加分母改标签。
- 分区/segment/缺口/采集缺失不拼接；坏记录污染完成桶，保留raw/eligible/excluded守恒。未定位的坏时间/duration整体拒绝，不静默丢弃。
- 人工记录/分钟各最多10000，单字段计数最多10^9，duration<=86400000000us；这些是合成输入资源界限，不用于筛真实数据。
- 数据使用和研究状态不升级：0新下载、0真实CSV读取、真实变换/模型/评分/Q99/实验NOT_RUN；原审计证据不改。

## Review Focus

1. 结束恰落分钟端点须进下一桶；跨分区/采集缺口记录不能使新桶假装完整。
2. observed空桶不能默认为normal；只有confirmed_empty及显式人工empty_label=normal才正常，物理网络零流量仍不作声明。
3. Protocol0原标签保留；未知协议和label未知分别处理，标签改变不能改变13项数值。
4. 相同统计但不同record_key不是重复；重复/冲突key的全部记录均排除，不能只留一条。
5. 输出无效整向量null、候选CLI保持无效；显式合成、目录独占、manifest完成标志与安全错误。

## Task 1：适配模块（主控）

文件：`src/core/traffic_anomaly/candidate_records.py`、`tests/core/test_candidate_records.py`。

`adapt_synthetic_records(minutes, records, *, evidence_kind='SYNTHETIC_ONLY') -> CandidateRecordResult`：minutes为按序dict序列，字段恰为timestamp（无偏移整分钟ISO）、partition、segment_id、coverage(observed/confirmed_empty/missing)、empty_label(normal/unknown)。records为dict可迭代，字段恰为record_key（人工唯一符号）、start（无偏移ISO微秒）、duration_us、protocol、fwd_packets、bwd_packets、fwd_length、bwd_length、label、attempted_category。start/duration无法定位整体报ValueError；其他数值错误可定位则污损完成桶。count字段须严格非负整数<=10^9，protocol严格整数，持续<=1日；原标签/Category为有界字符串或null。

返回对象属性：`batch:CandidateMinuteBatch`（raw13，无效行NaN）、`labels:dict[str,tuple[str,...]]`（键P_U/P_B/P_A，每分钟normal/attack/unknown）、`normal_candidates:dict[str,np.ndarray]`、`audit:dict`（输入/合格/排除、原标签对、协议通道、每分钟原因及计数）；方法`to_fixture(policy, *, epsilon=1e-6)->dict`输出既有candidate_cli schema1、evidence_kind及time_basis；无效行features=[null]*13且valid=false。

标签词表与G13U显式配置对应；Attempted合法词及Category0—6在P_U unknown/P_B normal/P_A attack，正常/明确攻击须Category=-1。unknown/冲突使该政策分钟unknown，即使另一记录为攻击；保留明确攻击在unknown分钟的排除计数。聚合13项顺序沿用上批，duration用linear分位。统计相同但不同key保留；同key全组无效。整体minute输入不因标签改变。

- [x] 手算4记录13项、端点/跨界/缺口、空桶区别、Protocol0/200、标签独立及重复key测试RED。
- [x] 实现并GREEN；与原人工聚合定义交叉核对，不重扫真实文件。

## Task 2：合成记录CLI与链路（独立实现者）

文件：`src/core/traffic_anomaly/candidate_record_cli.py`、`tests/core/test_candidate_record_cli.py`、`tests/fixtures/g13u-records-v1.json`。同时修改`candidate_cli.py`及其测试，仅增加兼容：valid=false的features允许整13项null，valid=true仍要求有限非负数；原有限占位输入继续支持。

命令`python -m traffic_anomaly.candidate_record_cli --fixture <json> --policy P_U|P_B|P_A --output <new-dir>`，policy无默认。顶层恰为schema_version=1、evidence_kind=SYNTHETIC_ONLY、time_basis=synthetic_source_clock、minutes、records、epsilon；<=1MiB，拒绝CSV后缀/重复键/非标准数值。调用Task1，不复制数值/标签算法。

输出`minute-fixture.json`、`label-audit.json`及最后的`manifest.json`，绑定fixture/config/文件SHA、profile与选择的AUDIT_ONLY政策，无私人路径/分数。目录独占；错误exit2，安全错误码。人工fixture覆盖4段各36分钟和三种标签，完整轴连续，record_key唯一，分区/segment语义显式。用导出的minute-fixture跑原candidate_cli，验证13/26与标签掩码一致，无训练模型。

- [x] 先入口缺失/非法输入/目录独占及invalid-null测试RED。
- [x] 实现、保存/哈希核对、真实CLI人工链路GREEN；失败留证，生产入口不接入。

## Task 3：协议材料与交付（主控）

- [x] 汇总实际既有分母与P_U/B/A代价，形成明确推荐的有限试点决定包，建议与批准分开。
- [x] 独立审查、修复及相关回归，仓库要求检查；记录实际CLI产物和未执行阶段。
- [ ] 更新status/README/路线图/维护与Vault，保留旧报告/失败。Desktop提交推送、核远端和CI；实际SHA在交付台账登记。

本地完成证据：[实际运行与验证](../../guides/candidate-records.md)。提交与CI实况在持续开发台账和最终汇报登记，不预填尚未产生的SHA。
