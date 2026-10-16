# 时间感知网络流量异常检测

本仓库管理“面向动态网络环境的时间感知流量异常检测方法研究”的技术文档、研究资料、程序源码和实验记录。目标是研究近期历史信息对异常检测误报、攻击识别和运行成本的影响，并形成可复核的实验与单机展示原型。

![文档与发布检查](https://github.com/QCYM-qcym/HITWH-Computer-Science-Department-of-Harbin-Institute-of-Technology/actions/workflows/repository-check.yml/badge.svg)

<!-- PROJECT-PROGRESS:START -->
## 项目当前进度

最近更新：**2026-10-16**。当前阶段：**需求与研究问题**；本轮主题：报告V0.40十图深讲与答辩追问准备。

```mermaid
flowchart TB
  subgraph G0["范围与基础"]
    direction LR
    S0["需求与研究问题<br/>进行中"]:::active
    S1["文献与方案<br/>进行中"]:::active
    S2["数据审计<br/>未运行 NOT_RUN"]:::notrun
    S3["最小基线<br/>未运行 NOT_RUN"]:::notrun
    S0 --> S1 --> S2 --> S3
  end
  subgraph G1["方法与展示"]
    direction LR
    S4["时间感知方法<br/>未运行 NOT_RUN"]:::notrun
    S5["对比与消融<br/>未运行 NOT_RUN"]:::notrun
    S6["展示原型<br/>未运行 NOT_RUN"]:::notrun
    S4 --> S5 --> S6
  end
  subgraph G2["验收与交付"]
    direction LR
    S7["综合测试<br/>未运行 NOT_RUN"]:::notrun
    S8["论文与答辩<br/>待开始"]:::planned
    S9["归档与维护<br/>待开始"]:::planned
    S7 --> S8 --> S9
  end
  G0 --> G1 --> G2
  classDef done fill:#d8efdf,stroke:#555,color:#111
  classDef active fill:#dceafb,stroke:#555,color:#111
  classDef planned fill:#eeeeee,stroke:#555,color:#111
  classDef blocked fill:#ffe1d6,stroke:#555,color:#111
  classDef notrun fill:#f2e7fa,stroke:#555,color:#111
```

文字与颜色共同表示状态：已完成、进行中、待开始、阻塞、未运行。流程表示依赖顺序，部分文档与测试工作可交叉推进。

| 阶段 | 状态 | 已完成/总验收项 | 证据入口 | 下一步 |
|---|---|---|---|---|
| 需求与研究问题 | 进行中 | 1/3 | [清单与证据](<docs/project/ROADMAP.md>) | 登记评审并对齐旧需求 |
| 文献与方案 | 进行中 | 1/3 | [清单与证据](<docs/README.md>) | 精读并核对方法差异 |
| 数据审计 | 未运行 NOT_RUN | 0/4 | [清单与证据](<data/README.md>) | 审计计划与阶段授权 |
| 最小基线 | 未运行 NOT_RUN | 0/4 | [清单与证据](<src/README.md>) | 数据通过后获准实现 |
| 时间感知方法 | 未运行 NOT_RUN | 0/4 | [清单与证据](<src/README.md>) | 依基线证据确定窗口 |
| 对比与消融 | 未运行 NOT_RUN | 0/4 | [清单与证据](<experiments/README.md>) | 冻结统一评价协议 |
| 展示原型 | 未运行 NOT_RUN | 0/4 | [清单与证据](<src/README.md>) | 确定共享核心契约 |
| 综合测试 | 未运行 NOT_RUN | 0/3 | [清单与证据](<tests/README.md>) | 实现后风险契约验收 |
| 论文与答辩 | 待开始 | 0/3 | [清单与证据](<docs/README.md>) | 基于实验证据撰写 |
| 归档与维护 | 待开始 | 0/3 | [清单与证据](<docs/project/ROADMAP.md>) | 交付后复核版本清单 |

计数口径：2026-10-11阶段验收清单v1；按证据是否满足计数，维护工具测试不计入研究或业务验收。各项条件与证据见[状态源](docs/project/status.json)；文档存在不等于实现或实验通过。不合并为总体百分比；范围变化须登记新分母及原因。

**本次完成事项**

- 学习手册更新V1.1共54页，保留原33页基础内容。
- 新增十图关系深讲与80项针对性追问，按图标出重点题。
- 54页分页和边界核对，新增21页逐页审阅，10张原图字节保持。
- 原报告与旧手册保留，数据、训练、实验及业务仍NOT_RUN。

**当前阻塞或待验证事项**

- 报告V0.40与PPT V0.24待实际送审反馈；长版计时排练、完整数据核验及具体配置仍待开展。
- 旧需求/HLD与当前提案仍有差异；每周投入、资源预算及最终答辩日期待确定。
- 数据、模型、实验、原型及业务验收均NOT_RUN；尚无实验结论、业务运行版本或演示。

**接下来最重要的三项任务**

1. [REV-01](<docs/project/ROADMAP.md>)：登记最新材料的实际送审与评审反馈，并追踪修订影响。
2. [REQ-01](<docs/project/DECISIONS.md>)：对齐当前提案与旧需求、概要设计及验收矩阵；范围改变须有确认记录。
3. [DATA-01](<data/README.md>)：形成数据审计计划与启动条件，待获准后才获取数据并运行审计。

**最新成果入口**

- [开题报告V0.40公开文本（15页、完整10图）](<docs/reports/开题报告-V0.40-公开文本.md>)
- [V0.40学习手册与十图讲解](<docs/reports/开题报告-V0.40-学习与答辩准备手册.md>)
- [答辩V0.24与讲稿、答疑（16页主讲）](<docs/reports/开题答辩-V0.24-公开文本.md>)
- [业务问题与研究主线及版本关系](<docs/reports/开题答辩-V0.24-结构与版本记录.md>)
- [滚动路线图、任务验收与依赖](<docs/project/ROADMAP.md>)
- [本轮复核证据与检查限制](<docs/project/MAINTENANCE_LOG.md>)

业务可运行版本与演示：**尚无，NOT_RUN**。仓库维护工具的可运行入口见[工具说明](tools/README.md)。远端自动检查以工作流徽章和实际运行记录为准；本轮提交前为**待远端检查**。
<!-- PROJECT-PROGRESS:END -->

## 从哪里开始

- [文档导航](docs/README.md)：最新报告、答辩稿、设计基线及研究资料。
- [项目规划](docs/project/ROADMAP.md)：两周任务、中期里程碑与半年以上滚动路线。
- [状态源](docs/project/status.json)：阶段验收条件、已满足项与证据；首页进度由此生成。
- [决策与方案差异](docs/project/DECISIONS.md)：当前提案、历史基线和待确认影响。
- [风险与阻塞](docs/project/RISKS.md)：优先级、解除条件和处理任务。
- [仓库文件管理](docs/project/REPOSITORY_LAYOUT.md)：各分区职责及本地材料的入库方式。
- [开发与提交规范](CONTRIBUTING.md)：使用 GitHub Desktop 提交、推送和维护。
- [隐私与发布规则](docs/project/PRIVACY.md)：正文、文件名、元数据及提交身份检查。
- [变更记录](CHANGELOG.md)：已完成的仓库维护工作。

## 仓库分区

```text
docs/                 可发布技术文档、报告文本、研究资料和图形源文件
  project/            项目规划、状态、仓库管理和发布规则
  reports/            当前报告与答辩的脱敏文本
  baseline/           前期设计文档及版本历史
  research/           文献调研和来源记录
  figures/            可审阅的 SVG 图形源文件
src/                  后续检测核心、后端、前端实现
tests/                后续数据边界、算法和系统测试
configs/              可复用配置与无凭据示例
experiments/          实验协议及可发布结果摘要
data/                 数据来源与获取说明，原始数据本地保存
tools/                仓库检查与维护工具
.github/              文档与隐私检查流程
.githooks/            GitHub Desktop 提交前检查
```

`src/` 等尚未开发的分区目前只有职责说明，不代表已有可运行系统。历史文档保留当时的方案；当前状态以项目规划及最新报告为入口。

## 当前研究方案

拟优先核验 UGR16v3 分钟级特征，以当前特征与过去窗口的中位数/MAD偏离构成历史增强输入，考察轻量自编码器评分。统计规则、Isolation Forest、当前 AE、USAD 适配为候选对照。15/30分钟窗口、70%/15%/15%划分及正常校准分数99%分位数均为初始设计，需在数据审计和实验中核实。

所有方法遵循训练、验证、阈值校准、测试的时间顺序；测试数据不参与参数选择，当前分钟先评分再更新历史。评价拟保留原始分钟评分，并报告误报、攻击召回、模型容量及运行成本。

拟采用 Python 检测核心、FastAPI 后端、Vue 3/TypeScript/ECharts 前端，以及 SQLite 元数据和 Parquet 结果文件。具体依赖版本和部署方式在验证后确定。

## 本地维护

仓库检查工具仅依赖 Python 3.10 及以上版本的标准库：

```bash
python -X utf8 tools/repository/update_progress.py --write
python -X utf8 tools/repository/update_progress.py --check
python tools/repository/check_repository.py --worktree
python tools/repository/check_repository.py --staged
```

在 GitHub Desktop 中选择本仓库，查看 Changes、填写中文提交说明、提交到当前分支，再点击 Push origin。完成标准是远端分支与本地提交一致；单独的本地 Commit 不等于已同步。

原始 Office 文件、沟通记录、个人路径、数据和临时生成目录继续本地保留。本仓库只收录检查后的公开版本。当前报告文本由原稿抽取，保留段落和表格内容，不承诺复现学校排版；图片以单独图形源文件维护。第三方论文、数据和工具的授权仍以各自来源为准。

