# 人工源记录到分钟输入：适配与标签审计

日期：2026-10-30。身份：**SYNTHETIC_ONLY**。依据[开题报告V0.40](../reports/开题报告-V0.40-公开文本.md)§4.1.1/4.1.2，本轮补齐源记录到已实现[候选输入数值链路](candidate-inputs.md)的接缝。实施范围见[开发计划](../superpowers/plans/2026-10-30-candidate-flow-adapter.md)，研究建议见[有限试点决定包](../research/2026-10-30-limited-pilot-proposal.md)。最终标签政策及真实操作的批准状态保持。

## 模块与输入

[candidate_records.py](../../src/core/traffic_anomaly/candidate_records.py)接收已归一化的人工记录，不读取作者91列CSV。记录字段为record_key、start、duration_us、protocol、fwd_packets/bwd_packets、fwd_length/bwd_length、label和attempted_category；minute字段为timestamp、partition、segment_id、coverage和empty_label。record_key、标签及Category均不进入13项特征。

时间是明确的人工source clock；无时区ISO开始值加整数duration_us得到名义完成时刻，按左闭右开分钟桶归入。它只实现离线完成代理，不认证真实时区、导出延迟或实时可用性。恰落分钟端点的完成事件进入下一分钟。

人工分钟及记录分别最多10000，fixture不超过1MiB。计数为严格非负整数、单字段<=10^9，duration为0—1日的整数us；这是本轮合成资源界限，不是新增真实数据过滤规则。人工标签原词与Category为有界ASCII词或null，不自动改大小写或trim来造已知标签。

Protocol6/17分别进入TCP/UDP，1/2/132进入已知other，0进入独立未解析来源计数；0没有被认证为物理合法协议，其他码和非法数值使完成桶无效。13项聚合沿用已登记顺序，duration使用秒、median/linear P95；不补维度。start或duration不可定位即拒绝整个输入，不静默丢记录。

所有记录都参与原标签、Category及原始通道计数，范围外和坏记录也保留排除原因。逐条合格记录仍可能位于被其他坏记录污染的桶，不能把部分记录聚合成完整可用分钟。全局raw=eligible+excluded，原因计数可重叠；协议通道分别核对raw和eligible守恒。

record_key是人工源记录身份；相同统计但不同key保留为两条记录。重复或冲突key的整组记录无效，不只留下第一条；这不等于已实现作者原始91字段行指纹，真实行身份适配仍NOT_RUN。

## 缺口、空桶与标签分离

| 人工coverage | 数值输入 | 标签处理 |
|---|---|---|
| observed且有合格记录 | 聚合13项；坏记录污染时整桶无效 | 三政策独立聚合 |
| observed但没有完成记录 | 无效empty_unconfirmed | unknown，不推断正常 |
| missing | 无效capture_missing，即使有记录也不能修复缺失证据 | unknown |
| confirmed_empty且无记录 | 明确人工证据支持的完成记录空桶，13项采用零约定 | 只有显式empty_label=normal才normal，否则unknown |
| confirmed_empty却出现记录 | 无效empty_evidence_conflict | unknown，原标签保留 |

confirmed_empty仅表示人工已确认没有完成源记录；不声明物理网络无流量，也不改变真实G13U既有空桶无效规则。真实profile是否有这类证据仍待决定。无效向量为整行null且valid=false，绝不作为正常0分。

记录不能跨分区、segment变化、分钟缺口或missing区间后使新桶看似完整。即使segment名称在中间变化后又恢复原名，内部边界仍会被检查；后续数值历史继续独立按原轴重置。

正常BENIGN及明确攻击要求Category=-1；合法Attempted词/Category在P_U记unknown、P_B记normal候选、P_A记攻击相关活动。其他未知或矛盾在三政策中均unknown。同分钟unknown优先，保留source_attack_label_present以披露被排除攻击；正常与明确攻击混合则为attack。原标签计数不被政策替换，不使用UGR八标签语义。

## 命令行链路

[candidate_record_cli.py](../../src/core/traffic_anomaly/candidate_record_cli.py)仅接收显式SYNTHETIC_ONLY、synthetic_source_clock的严格JSON。policy必须显式传入，没有默认主政策；以下P_U仅用于人工开发，不构成最终研究决定。输出父目录需存在，目标目录必须为新目录。

```powershell
.venv\Scripts\python -X utf8 -m traffic_anomaly.candidate_record_cli --fixture tests/fixtures/g13u-records-v1.json --policy P_U --output .runtime/records-adapt-example-v1
.venv\Scripts\python -X utf8 -m traffic_anomaly.candidate_cli --fixture .runtime/records-adapt-example-v1/minute-fixture.json --output .runtime/records-inputs-example-v1
```

第一步只做适配，输出minute-fixture.json、label-audit.json及最后写入的manifest.json；不拟合变换或模型。label-audit保留三政策、normal掩码、原词/Category与每分钟原因。第二步使用原候选链路，只在人工训练正常共同资格上拟合数值变换，再构造13/26输入；没有模型或评分。

适配器在创建目录前，以实际UTF-8序列化格式及平台换行核验minute-fixture也不超过下游1MiB限制。源文件较小不保证派生JSON同样小；超限安全拒绝，不生成COMPLETE后让下游失败。两个命令都拒绝覆盖已有目录，manifest绑定配置、源fixture与文件SHA/大小。失败只返回安全错误码，不回显路径或内部堆栈。

本轮对旧candidate_cli做兼容扩展：valid=false可接整13项null，原有限占位输入继续支持；valid=true的null、部分null、NaN和负值仍拒绝。原生产API、契约及worker未变更。

## 本轮验证与研究状态

[人工fixture](../../tests/fixtures/g13u-records-v1.json)包含4段各36分钟、576条唯一记录、每分钟6/17/1/0四通道，144条0源记录含两条Portscan及两条Attempted；原词与Category保留。三政策适配及候选数值CLI都实际exit0，144分钟/24共同输入，训练拟合和校准正常资格各6。测试共同当前normal为P_U4、P_B5、P_A4；三政策的13项、变换值和历史值相同，标签不驱动数值变化。

主控按源记录独立复算1872个原始数值坐标，三政策共5616次比较，核原标签572 BENIGN/2 Attempted/2 Portscan、通道与记录守恒、manifest SHA和重载。完整脱敏汇总见[本轮验证JSON](../research/2026-10-30-candidate-records-verification.json)。测试入口为[适配模块](../../tests/core/test_candidate_records.py)与[适配CLI](../../tests/core/test_candidate_record_cli.py)。最终根回归375项与56subtests通过（仅既有TestClient弃用警告）；适配器26项、新CLI38项、原CLI48项通过，独立Spec/Quality复审PASS。仓库13项与进度check通过，worktree隐私/作者406文件0问题；288个本轮Markdown链接和新日志5个Wiki Links有效。Desktop与本次CI按实际完成另报。

这批工作属于自主迭代中的工程交付，不是整体毕业设计完成。原真实G13U供应、G12失败、UGR阻塞及V0.40保留；主数据、最终标签及生产迁移未被本轮选择取代。真实CSV读取0、新下载0，真实变换/模型/评分/Q99/真实联调和正式实验NOT_RUN，Data Gate/S2仍BLOCKED。
