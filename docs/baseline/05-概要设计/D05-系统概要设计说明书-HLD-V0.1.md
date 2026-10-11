> 公开归档副本。保留原文版本与当时状态；当前进度以仓库项目规划和最新报告为准。原始附件与个人信息留在本地。

# D05 系统概要设计说明书

版本：V0.1　日期：2026-09-24　状态：设计草案，待评审

本轮仅进行设计与文档化；未开展数据下载、模型实验或业务实现。题名为WORKING TITLE，模型、数据版本和性能指标尚未冻结。

## 1 设计目标
以最小原型支持研究方法执行、实验追溯和Replay。研究与工程双主线在证据与验收汇合。
## 2 设计原则
Research-driven：功能服务RQ；Modular：单一职责；Reproducible：版本可追溯；Extensible：算法可替换。P0单机，不默认微服务。
## 3 总体架构
数据文件经Ingestion与Processing形成统一特征；AI和Temporal分别评分，Fusion生成判定；Experiment编排，Storage保存，API与Frontend查询展示。
## 4 分层架构
数据层保存原始/派生文件与清单；研究计算层含特征、时间、AI、融合、实验；应用层含运行管理及查询；展示层含时间线与对比。
## 5 模块划分
| ID | 模块 | 输入输出 | 边界 |
|---|---|---|---|
| Ingestion | Data Ingestion | 版本文件与来源→校验清单 | 无数据内容变换 |
| Processing | Data Processing | 原始记录→特征批与预处理版本 | 仅训练拟合 |
| Temporal | Temporal Analysis | 当前与过去状态→时间分数 | 不读未来或测试标签 |
| AI | AI Detection | 训练批/模型→连续评分 | 不操作展示和数据库 |
| Fusion | Score Fusion | 两路分数→联合判定 | 校准与阈值版本化 |
| Experiment | Experiment Engine | 配置→运行、模型与评价 | 唯一控制运行状态 |
| Storage | Result Storage | 产物与清单→持久化索引 | 部分产物不可冒充完成 |
| API | Backend API | 查询或运行请求→状态和结果 | 不重复实现AI算法 |
| Frontend | Frontend Visualization | 只读结果→曲线与交互 | 不在浏览器重新计算指标 |
## 6 模块职责
上表为职责基线；每个模块接受版本化契约并返回可追溯产物。模型训练与推理由同一Python检测器负责，应用服务不得复制评分公式。详情见D06/D07。
## 7 模块依赖
Processing依赖Ingestion清单；AI/Temporal依赖Processing；Fusion依赖同ID评分；Storage接收Experiment登记的产物；API读取Storage并向Experiment提交配置；Frontend只访问应用边界。禁止AI依赖Frontend，避免循环依赖。
## 8 数据流
原始→校验→时间切分与特征→AI与历史评分→联合结果→标签独立评价→存储→图表。标签旁路进入评价，不流入测试推理。
## 9 控制流
运行状态：CREATED→VALIDATING→RUNNING→COMPLETED，错误转FAILED，取消转CANCELLED。完成必须校验产物清单；重试创建关联新运行，不能覆盖失败证据。取消响应时间TBD，批间检查候选。
## 10 部署架构
P0候选为同一Windows开发机上Python研究进程、本地产物目录、可选应用服务和浏览器。并发先串行，避免显存竞争；不需要云GPU。答辩机未知，本地推理→历史结果Replay→视频依次降级，所有模式标注。
## 11 技术栈候选
Python承担Data Science、Feature Engineering、Temporal Analysis、Model Training、Model Inference、Experiment Runner。
Java/Spring Boot候选承担Application API、Experiment Management、Result Query、System Integration；若单机需求可由轻量Python API满足，可经设计复审移除Spring Boot。Vue候选承担Dashboard、Traffic Timeline、Experiment Comparison、Anomaly Visualization。
数据存储先按文件产物和运行索引设计，SQLite为轻量候选；MySQL、TDengine、Redis均无已证明必要性，不默认加入。版本和框架选择待小规模环境核验，不在PHASE0安装运行。
## 12 扩展点
Online Detection由输入适配器扩展；Concept Drift由受控状态与模型版本扩展；LLM Explanation只读取脱敏核查证据，P2且不影响P0检测。扩展须重新审查资源、预算与泄漏边界。
