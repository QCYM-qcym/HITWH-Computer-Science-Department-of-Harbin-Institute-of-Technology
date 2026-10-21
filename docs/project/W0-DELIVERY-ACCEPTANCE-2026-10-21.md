# 三个开发分支的主控接收验收

日期：2026-10-21。用途：记录W1/W2/W3交付核对、主控复跑和后续依赖。状态：模块候选交付已核验，尚未合入集成分支；系统端到端验收与真实研究未通过。共同契约基点仍为 `74f163bf69559f02ad70ae1d5bb730e1f10d15bf`。

本轮只读取并验证已有交付、使用已有载荷复跑审计、整理主控状态。不下载数据，不启动真实训练，不合并业务分支或main，不更改标签、时间范围和评价协议。

## 分支与复跑证据

三个工作区均无未提交修改，远端分支与下列完整SHA相同；四个公共文件contracts.py、contracts-v1.md、openapi-v1.yaml及统一fixture均与共同基点一致。

| 角色 | 分支与提交 | 主控实际复跑 |
|---|---|---|
| W1 | `codex/core-pipeline` / `2e85cd1c69915d651c924d1579470666840a8c2a` | 独立环境执行 `python -m pytest -q`：73项、7个subtests通过 |
| W2 | `codex/backend-tasks` / `4f6c53696cdd1befee05b131c6d51ab3a99098f7` | `python -m pytest tests/backend tests/core/test_contracts.py -q`：71项通过（50后端+21契约），1条TestClient弃用警告 |
| W3 | `codex/frontend-replay` / `2839ac206039857585230a85f82e3a8e7a7e227e` | 22项测试、typecheck、build、contracts:check通过；构建仍有入口包大于500KB提示 |

Python命令使用各work的独立.venv。前端命令依次为 `npm --prefix src/frontend run test -- --run`、`run typecheck`、`run build`、`run contracts:check`。没有把三个包含公共测试的计数相加作为系统测试总数。

每个提交对应的文档/发布检查与核心契约CI均为success。现有CI没有运行各分支的完整业务测试，这些业务测试证据来自本轮本地复跑。

- W1：[交付说明](https://github.com/QCYM-qcym/HITWH-Computer-Science-Department-of-Harbin-Institute-of-Technology/blob/2e85cd1c69915d651c924d1579470666840a8c2a/experiments/W1-HANDOFF.md)、[审计报告](https://github.com/QCYM-qcym/HITWH-Computer-Science-Department-of-Harbin-Institute-of-Technology/blob/2e85cd1c69915d651c924d1579470666840a8c2a/data/AUDIT_REPORT.md)。
- W2：[运行与交接](https://github.com/QCYM-qcym/HITWH-Computer-Science-Department-of-Harbin-Institute-of-Technology/blob/4f6c53696cdd1befee05b131c6d51ab3a99098f7/src/backend/README.md)。
- W3：[运行与交接](https://github.com/QCYM-qcym/HITWH-Computer-Science-Department-of-Harbin-Institute-of-Technology/blob/2839ac206039857585230a85f82e3a8e7a7e227e/src/frontend/README.md)。

## 真实数据审计复核

主控使用W1已经取得的固定载荷运行 `traffic_anomaly.cli audit-provider`，未重新下载；返回码2，gate_passed=False。MAT和四份CSV对应矩阵逐值一致，标签顺序为dos、scan11、scan44、botnet、blacklist、udpscan、sshscan、spam，与契约相同；不能将本次阻塞归因于列顺序误配。

| 口径 | 作者训练范围 | 作者测试范围 |
|---|---:|---:|
| 分钟数 | 72,644 | 27,697 |
| 八标签全零正常候选 | 2,874 | 0 |
| 四类主要攻击分钟 | 0 | 932 |
| 仅背景标签分钟 | 69,770 | 26,765 |

源时区仍为未知，UTC四段边界未冻结。冻结标签政策下测试正常分母为0，正常误报率和正常高负载误报率不可计算；不能将其写成0%或用攻击指标代替课题主要目标。许可、正常候选可信度、四段样本供应和高负载计数口径仍待核验。

Data Gate状态为阻塞/未通过，而不是未执行；真实IF/AE训练、正式窗口/容量对照、效果与效率实验继续NOT_RUN。此报告不把背景分钟重标为正常，不移动提供方测试范围，不更换数据版本或协议。

## 模块衔接的只读检查

没有重新训练模型。使用W1已有SYNTHETIC_ONLY IF完整产物，直接由W2的SavedArtifacts校验和读取：40个测试分钟、37个有效分钟，单分钟MinuteDetail解析成功。这证明该实例的保存格式可被消费者读取，不代表HTTP/CLI/页面已经联调。

W1执行器自行产生 `w1-…` 运行ID；W2任务管理先建立 `run-…` 任务ID，并要求任务、RunResult及所有产物身份一致。主控更换校验任务ID后被明确拒绝，错误为executor result identity mismatch。该拒绝符合安全约定；后续执行器适配必须设计统一ID与登记表/工作区解析，不得通过放宽身份校验或只改数据库字段绕过。W2-01目前仍使用固定IF假执行器，没有真实核心适配。

## 后续队列与边界

1. 可单独安排合成集成：逐个合入模块、整合README/status冲突，设计执行器适配，再核对CLI/API/页面及完整导出。该工作本轮未启动；即使通过，也只登记SYNTHETIC_ONLY。
2. 数据证据核验：先查明提供方标签含义、时钟来源与可能的数据版本差异。若仍无法支撑主要误报目标，再提出研究协议变更供用户决定，不能默认放宽正常定义或测试范围。
3. 合入后补充模块与集成CI，保留TestClient弃用警告和前端分包优化待办；不将现有两项通用CI当作系统验收。

W0-02计划中的真实短片段CLI/API/页面一致性、W2-02真实接入和研究验收均未放行。当前接收结论为：三个独立模块的合成交付证据通过复核，真实数据Gate阻塞，系统集成尚未执行。
