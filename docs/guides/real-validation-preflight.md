# 真实短片段验证准备与下一阶段提示词

日期：2026-10-21。状态：准备材料可用，真实执行BLOCKED/NOT_RUN。依据[统一Data Gate判定](../project/DATA-GATE-2026-10-21.md)。现有pipeline仍只允许运行SYNTHETIC_ONLY，不能通过修改报告中的布尔值解锁。

## 现在可复跑的核查

在忽略的本地配置中指定已存在的五文件目录；不下载或覆盖原数据。PowerShell示例中的占位值由操作者替换：

```powershell
$taskDataRoot = '<既有UGR16v3目录>'
.venv\Scripts\python -m traffic_anomaly.cli audit-provider --mat (Join-Path $taskDataRoot 'UGR16v3.mat') --csv-root $taskDataRoot --report .runtime/data-gate-20261021/recheck.json
# 当前预期退出码2，表示整体Gate仍未满足；不是程序崩溃。
.venv\Scripts\python -m pytest tests/core tests/integration -q
npm --prefix src/frontend run test -- --run
```

报告v2中的train/test指作者全段。project_splits四段NOT_DEFINED，计数null；不能为使CLI可运行而填入随意日期。公开聚合报告不含路径、特征矩阵或逐行标签。

## 真实运行前必须固定的清单

| 项目 | 当前值/状态 |
|---|---|
| 精确数据版本及五文件校验 | 已核实，见data/AUDIT_REPORT.md |
| 使用条件及许可声明关系 | 尚待明确，不公开分发载荷 |
| 原始时间、时区/偏移/DST、桶端点和转换依据 | UNVERIFIED，不设默认 |
| 模型训练/参数验证/独立校准/原测试UTC半开边界 | NOT_DEFINED，不自选片段 |
| 正常候选及共同有效分钟供应 | 作者训练正常2,874；三开发段未划分；测试正常0 |
| H、epsilon、种子、IF参数、资源上限及片段选择理由 | 真实配置NOT_DEFINED；合成smoke参数不自动沿用 |
| 原始钟面保留、缺口/切分重置、预热状态 | 代码有相应保护；真实配置及转换规则仍需登记 |
| IF真实闭环、AE真实小规模检查 | NOT_RUN，当前无真实运行ID或模型产物 |

未来具备准入条件后才生成冻结配置与哈希，先IF、不调参搜索；独立输出根、数据库、端口，不覆盖合成产物。各入口优先读取同一份已完成manifest产物，核对run_id、配置、有效分钟、分数、阈值、报警、完整指标与导出。真实短片段仅证明工程链路；零正常时FPR仍null，不做正式效果结论。准入逻辑变更须主控评审并绑定证据，不提供通用跳过开关。

## 供用户自行发送的问题草稿（未发送）

> Subject: UGR16 Feature data v3 timestamp, labels and license clarification
>
> Dear maintainers,
>
> For non-commercial university research, we inspected the five UGR16v3 MAT/CSV files at commit 760863d31413739a129b3be2d1d52cde217962e8 of UGR16_FeatureData. We plan no data redistribution.
>
> Could you confirm the timezone/UTC offset and DST rules for obs_l/obs_lt and CSV Row; whether the minute label denotes interval start or end; and which flow timestamp field and generation configuration were used?
>
> All 27,697 test rows have positive blacklist counts, while the final 2,874 training rows have eight zero labels. Is this expected for these files? Is there an official erratum, additional v3 file, or documented interpretation? We have not reclassified blacklist as normal.
>
> The November 2024 DMP states GPL-3.0 for the data; the 2025 Data paper states CC-BY-NC. Which license(s), version and URL apply to these exact feature and label files? Are these alternative licenses or a correction? May they be retained and fitted/evaluated locally for non-commercial academic research, with only aggregate metrics and citations published?
>
> A version-specific clarification or generation configuration would help us preserve the original split and avoid incorrect timestamp or label assumptions.

## 下一阶段完整提示词

> 请继续本毕业设计的“Data Gate证据澄清与研究协议决定”阶段，不新建用户聊天。先按AGENTS读取知识库及当前仓库，核对分支、worktree、未提交工作和远端；从主控本轮最终交付的准确SHA安全续接，不能假定main已合入。读取docs/project/DATA-GATE-2026-10-21.md、三份data-gate研究证据、聚合JSON、当前需求、报告V0.40及实施计划。公共文件仅主控维护。
>
> 当前真实计数是作者训练72,644中正常2,874、攻击0、仅背景69,770；测试27,697中正常0、主要攻击932、仅背景26,765，攻击全部与blacklist重叠。五文件及连接已核实，不能靠删背景列、换同标签blob变体、挪训练到测试或按效果挑区间解除阻塞。源时区/DST及v3专用桶端点仍未核实，许可声明范围重叠差异未解决；不得默认UTC或Madrid。四段均NOT_DEFINED，不把作者train当模型train。
>
> 先检查是否有用户提供的作者回复、官方勘误、运行配置或明确研究决定；记录其适用版本、来源、日期与可信度。允许只读查官方文本和既有载荷，不大规模下载，不擅自联系作者。没有充分新证据则保留BLOCKED，明确尚需哪些具体答复。优先维持八标签全零正常政策和原测试范围；若用户考虑背景报警率补充评价或更换数据，先写方案、RQ影响、许可/时间证据、代价和迁移范围，取得明确决定再实施，不把它命名为正常FPR。
>
> 只有相关准入条件实际满足且没有未批准变更时，才登记真实片段、选择理由、四段UTC半开边界、数据/配置哈希、H/epsilon/种子、资源上限和目的。先以IF做有界工程验证，预处理仅拟合训练正常候选，独立校准共同正常分数99%分位点、严格超过报警；历史先评分后更新，不跨缺口或分段，测试历史不读取标签删攻击，不做point-adjust。无正常FPR为null及原因，正式比较须另满足共同有效分钟与正常分母条件。若现有Gate定义需要拆分，先登记理由与批准，不为放行降标准。
>
> 修复先写失败测试，运行受影响检查；如有真实运行，核对同一产物CLI/API/网页/白名单导出身份和数值、失败原因及预热。同步知识库、状态、README、路线图和维护记录，真实验证/正式实验分别登记，未运行保留NOT_RUN。提交推送必须GitHub Desktop，核对远端SHA和实际CI，不合并main。交付证据、新旧计数、Gate分项判定、用户待决事项及下一完整提示词。
