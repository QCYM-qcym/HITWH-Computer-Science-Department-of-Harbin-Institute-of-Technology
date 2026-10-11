> 公开归档副本。保留原文版本与当时状态；当前进度以仓库项目规划和最新报告为准。原始附件与个人信息留在本地。

---
type: defect-register
status: open-for-use
version: V0.1
updated: 2026-09-27
tags: [毕设, 测试, 缺陷管理]
---

# Defect Register V0.1

当前登记条目：**0**。这表示本轮没有正式软件/数据/实验运行可登记的Defect；不代表系统已经无缺陷。D01–D08需求/设计和DOCX排版问题通过文档审查处理，不冒充运行时缺陷。模板已建，代码和Data Gate仍未运行。

## Defect分类

| Type | 范围示例 |
|---|---|
| CODE_BUG | 实现行为与已验收设计契约不符 |
| DATA_BUG | 文件/字段/标签/时间值错误或处理链异常 |
| EXPERIMENT_BUG | split、配置、指标或协议执行与预注册设计不符 |
| DESIGN_DEFECT | Requirement/Module/Interface设计冲突或遗漏 |
| DOCUMENT_DEFECT | 可复现的正式材料错误、断链、错版或格式问题 |
| ENVIRONMENT_ISSUE | 依赖、驱动、权限、设备或部署环境问题 |
| REPRODUCIBILITY_ISSUE | 固定版本和配置无法复算出约定容差内结果 |

## Severity

- **BLOCKER**：停止核心工作/交付，或污染核心研究结论。
- **HIGH**：P0需求/关键实验不满足，且无当前可接受回退。
- **MEDIUM**：存在有界影响，有计划内回避方案。
- **LOW**：局部清晰度或非核心体验问题。

## 记录格式

| ID | Date | Type | Severity | Description | Root Cause | Fix | Verification | Status | Linked RQ/FR/Run |
|---|---|---|---|---|---|---|---|---|---|
| DEF-YYYY-NNN | YYYY-MM-DD | 选择分类 | TBD | 观测现象和复现条件；区分事实/推断 | 未知可写Under investigation | 修改/回退引用 | 测试ID、原始证据、版本 | OPEN | 需求/问题/Run ID |

状态：OPEN→TRIAGED→IN_PROGRESS→FIXED→VERIFIED→CLOSED；拒绝修复用WONT_FIX并说明影响及接受人。只有修复后独立复验通过才能CLOSED。重试不覆盖原缺陷/原run；真实研究负结果本身不自动属于Defect。

## 相关内容

- [[测试策略与缺陷管理]]
- [[周报模板]]
- [[TBD-Registry]]
- [[Risk-Register]]
