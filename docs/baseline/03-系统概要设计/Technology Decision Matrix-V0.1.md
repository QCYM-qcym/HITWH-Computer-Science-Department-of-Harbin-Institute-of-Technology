> 公开归档副本。保留原文版本与当时状态；当前进度以仓库项目规划和最新报告为准。原始附件与个人信息留在本地。

---
type: technology-decision-matrix
status: candidate
version: V0.1
updated: 2026-09-27
tags: [毕设, 技术选型, Requirement-driven]
---

# Technology Decision Matrix V0.1

比较原则：Need/Value来自已登记P0用例与NFR；Complexity/Risk为设计期定性判断；“推荐候选”不是已选技术。只有具体需求或原型证据可以推动选型。

| 领域/候选 | Need / Value | Complexity | Risk | P0 Necessity | 当前状态/决策条件 |
|---|---|---|---|---|---|
| Backend: Python Only | 研究计算、AI检测、实验编排同语言；减少跨进程/跨语言契约 | Low–Medium | 应用交互/任务状态需自行组织 | 候选可满足P0 | **优先候选**；用例/运行控制若可通过本地进程与轻量UI满足则保留 |
| Backend: Python + Spring Boot | 适合明确的多客户端、长期API或独立应用管理边界 | High | 双语言部署、协议/序列化和工期膨胀 | 当前无证据 | Candidate；仅当明确接口/用户场景带来净价值且预算可承担才引入 |
| Frontend: Vue | 可定制时间线、告警与比较Dashboard | Medium–High | 前后端构建与接口增加；答辩安装未知 | 非必要 | Candidate；需求走查证明交互收益后选择 |
| Frontend: Streamlit/Gradio | 快速提供本地研究型交互/可视化 | Low–Medium | 复杂交互/部署兼容边界需验证 | Candidate | P0 prototype candidate；不得预先冻结具体框架/版本 |
| Storage: Versioned Files | 直接保留原始输入、配置、模型及指标产物；易复现 | Low | 跨运行查询/并发能力有限 | 当前足以作为起点 | P0 preferred candidate；用manifest和索引维持追踪 |
| Storage: SQLite | 单机结构化查询与状态记录 | Low–Medium | 并发与迁移要求尚不清楚 | 非强制 | Candidate；只有文件查询确实妨碍核心用例再引入 |
| Storage: PostgreSQL/MySQL | 多用户、服务化查询和复杂关系 | Medium–High | 安装、运维和备份成本 | 无P0必要性证据 | TBD；不是默认PASS |
| Storage: Time-series DB | 大量连续实时数据查询与保留策略 | High | 学习/维护成本且当前离线数据为主 | 无 | 当前不需要证据；只有在线/高频查询被纳入范围再复议 |
| Deployment: Native Windows | 与已知开发机相符，低部署成本 | Low | 目标机依赖/版本差异 | Candidate | **优先候选**；先以实际Demo设备试运行 |
| Deployment: Docker | 依赖封装和可复现交付 | Medium | WSL/Docker环境未验证；GPU/图形支持可能增加风险 | 非必要 | Candidate；先证明环境复现或移交需求值得额外配置 |

当前不引入Redis、Kafka、Gateway、Nginx、Kubernetes、云ECS。若Future需求变化须提交Change Request并说明其支持的Use Case/NFR、风险和验证。

## 决策检查点

- 在Data Gate之前：仅选择可安装、可审计所需环境；不要冻结框架和数据库。
- 在Baseline/AI Smoke Test后：记录Python计算接口、资源与模型产物契约。
- 在Prototype集成前：以演示设备和FR-011/015/016决定是否需要Web前后端/数据库。
- Docker只在部署可重复性有证据时决定；Docker/WSL当前未实测。

## 相关内容

- [[03-系统概要设计-HLD-V0.2]]
- [[六阶段计划]]
- [[个人资源与工期约束]]
- [[TBD-Registry]]
