# 作者修订版离线审计工具与续接说明

日期：2026-10-23。性质：**隔离审计准备，SYNTHETIC_ONLY验证；不是生产适配器或真实研究结果。** 依据[本轮证据及C17-I1预算](../research/2026-10-23-c17-improved-preparation.md)。用户已批准improved优先审计与工具准备；本对象下载、正式采用、标签映射、四段和生产迁移未批准。

## 工具边界

[c17_improved.py](../../tools/data_audit/c17_improved.py)只用标准库，提供`audit_csv(paths, config)`和`check_archive(path, limits)`，不导入检测核心、不联网、不解压、不训练、不评分。需要既有Python；W0实际测试使用`.venv`中的3.14。人工输入为[fixture JSON](../../tests/fixtures/data_audit/c17_improved_synthetic.json)，测试为[test_c17_improved.py](../../tests/data_audit/test_c17_improved.py)。

输入、配置、输出均显式指定；输出独占创建，不覆盖既有文件或输入。聚合使用input_N和文件SHA，不输出本机绝对路径、IP/流身份明细或逐行原时间。原始标签及category以聚合频数保留，可疑含地址等字符串用哈希替代；公开前仍须隐私复核。运行失败必须检查退出码，不能把部分扫描当完整供应。

配置声明不等于证据认证：`REAL_LOCAL_AUTHORIZED`只是操作者身份标记，不能解锁生产系统或代替用户获取授权；UTC、单位、覆盖、标签词表必须先独立核验。工具报告相应未验证边界，不会令Gate自动通过。

## 可复跑人工CLI

在仓库根PowerShell运行。所有生成文件均在忽略目录，以下目录已存在时会失败，请使用新的运行名；不删除/覆盖旧结果。

```powershell
@'
import csv, json, zipfile
from pathlib import Path
fixture = json.loads(Path('tests/fixtures/data_audit/c17_improved_synthetic.json').read_text('utf-8'))
task_root = Path('.runtime/improved-synthetic-demo')
task_root.mkdir(parents=True, exist_ok=False)
with (task_root / 'input.csv').open('x', encoding='utf-8', newline='') as stream:
    writer = csv.writer(stream)
    writer.writerow(fixture['header'])
    writer.writerows(fixture['rows'])
with (task_root / 'config.json').open('x', encoding='utf-8') as stream:
    json.dump(fixture['config'], stream)
with zipfile.ZipFile(task_root / 'synthetic.zip', 'x') as archive:
    archive.writestr('README.txt', 'SYNTHETIC_ONLY')
'@ | .venv\Scripts\python -X utf8 -

.venv\Scripts\python -X utf8 tools/data_audit/c17_improved.py --input .runtime/improved-synthetic-demo/input.csv --config .runtime/improved-synthetic-demo/config.json --output .runtime/improved-synthetic-demo/report.json
.venv\Scripts\python -X utf8 tools/data_audit/c17_improved.py --archive-check .runtime/improved-synthetic-demo/synthetic.zip --config .runtime/improved-synthetic-demo/config.json --output .runtime/improved-synthetic-demo/archive-report.json
.venv\Scripts\python -X utf8 -m unittest discover -s tests/data_audit -p "test_*.py"
```

fixture只有12条手工流，任意s/d/y/a列名、四个40分钟人工分区及人工完整覆盖声明，不能用来认证真实表头/UTC/四段供应。为验证H15/H30，完整但无完成事件的人工桶也保留；其正常身份另有人工定义，不由complete覆盖自动推出。归档是人工生成的文本ZIP，不是下载样本。

## 配置和计数含义

| 配置 | 要求 |
|---|---|
| schema / identity | `C17_IMPROVED_AUDIT_V1`；`SYNTHETIC_ONLY`或已获准本地审计身份 |
| columns | 必填start/duration/label/attempted原列；可显式加protocol、fwd_packets、bwd_packets、fwd_length、bwd_length，拒绝重复映射/重复表头，不猜同义列 |
| time | 显式strptime格式、UTC依据、us/ms/s单位及依据、两种量化步长；`precision_model=TRUNCATION`及precision_evidence必填，仅支持已知截断区间。未知舍入/未消歧12小时应停下，不填假依据 |
| labels | 明确normal/attack/attempted原词、attempted_empty和attempted_categories允许值；policy只能AUDIT_ONLY，attempted取unknown/normal/attack；不允许伪称正式APPROVED |
| segments | 显式id、train/validation/calibration/test角色及UTC半开整分钟区间；不得照搬旧源钟面加Z；所有角色/范围由操作者审计配置提出，不冻结研究协议 |
| capture | 显式complete/gap/unknown区间；complete/gap须说明依据，未覆盖处默认unknown。上游dropna风险未解决时不能仅凭CSV宣称complete |
| empty_normal | 空完成桶默认unknown；只有另给start/end区间及独立normal_evidence才可成为正常候选。complete采集掩码本身不够，真实缺依据时不配置该许可 |
| identity_columns | 可选、内部比较身份；同身份碰撞不自动去重，标冲突并污染候选桶；真实流段可能合法复用身份，启用前须核语义 |
| limits | 总输入字节、行数、分钟数、字段长度、最长流均必填；超限退出，不把部分结果当全量。实际大包性能未验证，不无限放大上限 |
| archive_limits | 采用C17-I1的360MiB/100成员/2GiB单成员/4GiB总量/200倍压缩比硬上限 |

每个配置的完整采集区间作为独立epoch，输入历史不跨epoch；跨午夜本身不自动断开，须依真实采集分段/缺口证据决定。长流跨gap/unknown或采集epoch会污染完成桶，不能删去后继续当干净。

输入有效性与标签完整性分开：合法攻击/Attempted/未知标签记录仍参与完成事件及测试历史，标签方案不能删输入。混合BENIGN+确认攻击为attack；attack+unknown或保守Attempted为unknown总体，保留attack_present和label_incomplete。normal/attack/unknown三类总体互斥；mixed、attempted等辅助标记可重叠。

流的开始加持续时间只作结束代理；跨分区、过长、精度跨桶、无效数值及歧义碰撞污染可能桶。不能定位的坏时间/单位会使全部候选分钟不可信。完全相同行或显式身份冲突不会自动删除并继续计正常，而是排除并标受影响桶无效。原始逆序、跨日/跨分钟及排除原因保留聚合。

每文件报告流数、SHA、观测完成桶；**逐文件完整分钟为null**，原因是全局覆盖掩码无法安全分摊到各文件。全局按日/候选分区报告分钟及连续区间。`common_valid`是已配置输入规则下H15/H30交集，不能称所有模型已验证共同分钟；模型级共同数保持null/NOT_VERIFIED。即使映射了五个可选数值列，也没有生产12/24向量、协议支持或长度语义认证。

H窗口只看当前之前连续输入分钟；分区、缺采/无效桶重置，标签未知/攻击本身不重置输入历史。训练/校准正常资格另要求当前及所需历史全正常。高完成流门槛只取共同训练正常资格的原始记录数linear Q90，再严格大于固定门槛分测试高组；训练资格为空时门槛及普通/高组计数均null并给原因；有门槛但高组为空时计数0且不可评价，无模型效果指标。

归档检查只读EOCD/中央目录，在批量解析前有界核真实中央目录条数，不只相信EOCD声明；拒绝多卷/ZIP64、危险/碰撞路径、特殊类型/加密/不支持压缩及超限；不读成员内容、不验CRC或认证来源。目录检查通过后，未来解压仍须白名单、逐块实际解压计数和CRC检查，不能直接无界extractall。本轮没有对真实归档执行任何读取。

## 下一阶段完整提示词

> 请继续毕业设计“CICIDS2017_improved有界获取与载荷适用性审计”。从W0最终交付的准确分支/提交续接，先按AGENTS读取Vault四入口及仓库规范，核工作区、改动、远端。读取c17-improved-preparation的Markdown/JSON、candidate-manifest、C17-G12参考、当前Gate及本指南。用户已决定improved优先、原Generated镜像备选，不重问A/B/C或审计优先级。
>
> 先核后续用户是否明确批准C17-I1确切对象/预算。仅有优先级和工具准备批准时，不发ZIP GET/Range/在线预览；所有不依赖载荷成果已准备，等待该具体批准。C18-S授权不可移用。若已批准，仅主控按固定作者URL取得CICIDS2017_improved.zip；HEAD重核343549013字节、ETag与Last-Modified，变化/重定向/类型不符即停。一次GET、累计HTTP体≤377487360字节、重试0、30秒连接/读取、30分钟总时限；失败字节计入。新目录独占写入，SHA流式并复算，保留GET头/实际字节/失败记录，不下载PCAP、2018或备选镜像。
>
> 获准下载后、解压前运行离线中央目录检查：≤100成员、单文件≤2GiB、总解压≤4GiB、压缩比≤200，拒绝不安全路径/类型/冲突/加密/ZIP64等；目录通过不等于CRC或数据通过。未来只受控流式读取白名单CSV/说明，实际解压也执行上限，临时/审计≤1GiB、任务目录≤6GiB，不覆盖旧成果，不执行包内代码。超限先交失败证据，不自动提高预算。
>
> 先记录实际成员、逐字表头、原始时间格式/精度/单位/UTC生成依据、版本和过滤信息，再配置审计。源码快照支持UTC微秒新路径但旧导出/reader分支仍在，不能用攻击标签恢复时钟。完整流只进start+duration末包代理桶，不称实时可用；精度舍入未知不伪配TRUNCATION。上游全列dropna使CSV完整读取不能独自认证采集；区分确认空完成桶、记录缺失和采集未知；空完成桶需独立正常依据，不由complete掩码直接归正常。跨文件碰撞/跨分区长流保留污染审计，受影响桶无效、重置输入历史。
>
> 保留原Label和Attempted Category，先核词表/编码/矛盾。P_U/P_B/P_A只作明确标记的审计计数，共享合法输入，不删除Attempted后称正常；推荐保守P_U仍未获正式政策批准。unknown不正常，确认攻击+unknown保留attack_present并退出主要评价。训练/校准需当前及历史均正常；测试历史不按标签删除或重置。四段旧09—17源钟面不能直接改UTC；按独立时间和采集证据提出候选，拟合前固定，不根据模型效果改范围。
>
> 逐文件/日/候选四段报流和分钟、排除原因、覆盖/连续段、H15/H30及模型真正共同有效资格；工具当前common_valid仅是配置输入和窗口交集，模型级与12/24向量仍未验证。高完成流Q90仅取共同训练正常资格，固定到测试普通/高组，报分母和持续片段；无组不可评价，不用测试Q90造组。供应不足在任何拟合前提出具体修改及代价，保持独立校准Q99和strict >。不启动IF/AE拟合、评分、校准或正式比较。
>
> 分别判定对象获取、字段时间标签、四段供应、Attempted/表示/主数据采用及生产迁移；本次获取批准不自动批准后几项。原包和修订版同采集、不称跨网络泛化。保留原UGR阻塞、V0.40和生产契约，未执行NOT_RUN、未解决BLOCKED。维护知识库与公开记录、状态/README/路线图；新缺陷先失败测试后修复，只跑相关检查。使用GitHub Desktop提交推送、核远端SHA与实际CI，不合并main。交付实际下载与校验、真实审计分母/未知、准入决定及下一完整提示。
