# 候选评价查看与持续开发计划

> **For agentic workers:** Use superpowers:subagent-driven-development task by task. 主控独占状态、计划、知识库和 Desktop 提交；实施代理只修改任务指定文件。

**Goal:** 在 2026-11-06 12:00（Asia/Shanghai）前持续推进已有候选工程，让完整测试评价可以在命令、接口和页面中一致查看，并完成后续有证据支持的工程任务。

**Architecture:** 复用已有 IF/AE 安全加载器与不可变运行快照；纯查询层消费已经核对的保存评价，CLI、HTTP、页面逐层接入。分批实施、独立审查、实际人工包验收和 Desktop 同步；后续任务根据已完成结果追加，不重复已完成研究审计。

**Tech Stack:** 既有 Python/FastAPI、JavaScript 原生候选页面、pytest/Vitest；不新增依赖。

**Spec:** 本文件下列设计约束；研究基础见[报告 V0.40](../../reports/开题报告-V0.40-公开文本.md)、[候选查看页](../../guides/candidate-viewer.md)、[G13U 审计](../../research/2026-10-24-c17-g13u-audit.md)。本轮自主开发指令授权常规工程安排，以下具体实现选择由主控作出。

## 起点及范围

实际起点为 `codex/candidate-flow-adapter` 的 `6d87f40ab5e361e8313cb93f97f5ca78cb801a88`，远端一致。工作树有一份既有未跟踪计划，保留原文且不纳入本批提交。G13U 已审计，历史供应已恢复；不可按旧 C17-I1 汇报重复全部工作。最终标签、有限真实试点和生产迁移仍有未决研究事项。

## Global Constraints

- 仅候选 `SYNTHETIC_ONLY/AUDIT_ONLY` 工程；不下载新数据，不启动真实拟合、训练、评分、校准或正式比较，不将工程验证当作研究通过。
- 保留原生产 134/268 维契约、已存文件身份和 G12/G13U 历史证据；不合并 main。
- 完整评价来自同一运行已核验的 `report.policies`，不是原 evaluation.json 字节导出，不重新计算指标、阈值、标签或历史。
- 现有演示全轴144、测试36、可评分测试6、排除30；曲线分页和时间过滤不改变测试评价分母。
- 三政策 P_U/P_B/P_A 并列显示同一预测的审计映射，不指定最终政策，不排名或选择模型。
- `null` 必须保留原因，数值0不是空值；不添加不存在的高完成流子组指标。
- 运行切换使旧异步响应失效；评价的加载、错误和重试不干扰曲线和详情。
- 无新依赖；先复现失败、再修复；按改动运行必要检查。使用 GitHub Desktop 提交推送并核对远端和 CI。

## Review Focus

- 非法或不匹配快照不能给出看似合法的评价：任务1检查版本、身份、评价校验状态和守恒。
- 零分母与正常0指标不能混淆：任务1覆盖零正常、零攻击、全未知、无评分和非有限值。
- 全轴、完整测试、当前页不能互换：任务1/2使用不相同分母和空曲线测试。
- 切换运行时晚到响应不能覆盖新运行：任务2覆盖 success/error/finally 和 JSON 阶段竞态。
- 终端、HTTP和实际页面不能只在mock里一致：任务3复用旧四包和真实监听服务，核对保存值及资源安装。

## Task 1: 完整测试评价纯查询、CLI 与 HTTP

**Files:** 新建 `src/core/traffic_anomaly/candidate_evaluation_view.py` 与对应核心测试；修改候选 `candidate_view_cli.py`、后端 `candidate_app.py` 及受影响测试夹具。

**Interfaces:** `candidate_evaluation_view(run_snapshot)` 返回独立JSON副本，固定 `schema_version=1`, `evidence_kind=SYNTHETIC_ONLY`, `policy_status=AUDIT_ONLY`, `scope=FULL_STORED_TEST_EVALUATION`, `unit=minute`；含 `run_id/model_profile_id/score_origin_policy/run_source_replay/evaluation_reference/policies`。引用保持 `FULL_STORED_RUN` 文件归属，指标是完整规定测试段。错误固定 `CandidateEvaluationViewError('INCOMPATIBLE_SNAPSHOT')`。

- [ ] 先用手写快照验证三政策原值、独立副本、身份错误、严格整数计数、有限[0,1]指标及null原因；观察有效失败。
- [ ] 核查 `calendar=scored+excluded`、`scored=normal+attack+unknown`、`fp+tn=normal`、`tp+fn=attack`、未知带攻击计数不超过unknown及三政策共同calendar/scored/excluded。只检查分母为零与null原因对应，不计算比率。原因键恰对应null、值为1–256字符；计数0–MAX_MINUTES且排除bool。
- [ ] CLI增加 `evaluation` 子命令，无过滤参数，仅调用既有run loader一次与纯查询，不另读inputs快照；沿用1MiB输出上限和安全错误。
- [ ] HTTP增加 `GET /candidate/v1/runs/{run_id}/evaluation`，不接受查询键；全部快照在注册时检查评价形状，固定404/422/500规则，端点只消费内存。
- [ ] 运行相关pytest并交独立审查；不为测试新建真实模型。

## Task 2: 页面完整评价区域

**Files:** 候选 `candidate_static/index.html`, `viewer.mjs`, `viewer.css`；独立候选DOM测试。

**Interfaces:** 消费任务1 `/evaluation`，展示三政策人口、TP/FP/TN/FN及precision/recall/F1/FPR/FNR、undefined_reasons和评价文件摘要。

- [ ] 先测试三政策、null/0、空页不改分母、独立错误重试、运行/目录切换及晚到响应失效，观察有效失败。
- [ ] 增加“完整保存评价 · 测试分钟”区域，说明正常和攻击分母及UNKNOWN/排除分钟；不添加排名、政策选择或重新计算。
- [ ] 原因以文本节点呈现；评价独立请求代次/Abort，运行切换与重载目录立即清空，曲线筛选不刷新完整评价。
- [ ] 运行候选DOM、前端相关检查及受影响后端路由测试，独立审查。

## Task 3: 真实工程验收与同步

- [ ] 复用既有四个人工运行包，核对保存evaluation、纯函数、实际CLI和HTTP结果及摘要，保存旧文件前后身份表；不运行模型。
- [ ] 实际页面核对IF/AE分母、null原因、空范围评价保持；安装包资源与源码相符，结束本轮启动的服务。
- [ ] 写使用指南和脱敏验证记录；补齐公开决策日志中已经发生但遗漏的G13U执行事实，不冒称新增研究批准。
- [ ] 更新状态、README、维护日志及既有知识库页面，执行相关检查；Desktop提交推送，核对SHA和CI。

## 后续安排

完成上述批次后，优先选择能直接改善毕设演示和复现的任务：已保存运行的共同条件对照展示、可重建演示入口、必要的真实缺陷修复。每项先登记范围和验收再实施。研究决定包可以整理为具体建议；资料不足时保留明确限制，继续独立工程工作。12:00停止新增长任务，收束正在执行的有界验证并交接实际成果。

## 第一批执行记录

任务1—3的本地开发、独立复审、安装后实际验收及仓库检查已完成；由 GitHub Desktop 提交推送为 `c16df9852073d8127a5d2229a925bc3e7e64b43e`，远端分支已核对。详细测试及限制见[验证记录](../../research/2026-11-06-candidate-evaluation-view-verification.json)。CI 按准确提交单独核查，不用本地测试替代远端结果。

## Task 4: 已保存方法的共同条件对照

本批是候选人工演示扩展，不批准正式政策、真实模型或生产契约迁移。

- 启动器增加显式 `--comparison`，调用既有比较器后，将每行五个实际文件摘要与已加载运行快照绑定。绑定不一致、重复方法槽或共同条件不符时，在监听前拒绝；无此选项时保留单运行及同方法多运行查看。
- 新增只读 `GET /candidate/v1/comparison`，不接受查询参数。比较报告在启动时冻结并限定为1MiB以内；请求只读内存，不读取文件、训练模型或重新评价。目录给出比较是否启用。
- 页面新增独立“同条件方法对照”，四槽固定排序、缺槽明确显示，按 P_U/P_B/P_A 查看原保存映射。展示共同人口、各自混淆计数与五指标；null保留原因。该选择器仅改变展示，不改变训练政策或阈值。
- 全轴分钟、完整测试分钟和测试可评分分钟分开标示。时间筛选、分页、运行切换不改变完整对照；模型容量、分数尺度和历史归因的限制持续可见。不生成排名，不按效果选择政策。
- 先做绑定、兼容、内存端点及DOM竞态的失败测试，再实现；复用原四个人工包核对CLI、HTTP及浏览器，检查原文件身份不变和安装资源一致。采用独立任务复审，主控负责实际验收、文档、知识库及Desktop同步。

## Task 5: 可重建的人工演示入口（待任务4稳定后实施）

目标是在已安装的锁定环境中，用固定随包人工记录从全新目录构建四方法演示，之后只读重启查看。准备、验证、查看分为独立命令；准备明确执行固定人工模型，验证与查看不训练。不得读取任意真实数据、不覆盖既有目录、不静默恢复失败产物。具体资源、失败与回收语义在实施前补入计划和任务说明。
