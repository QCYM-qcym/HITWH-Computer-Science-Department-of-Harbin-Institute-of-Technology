# 候选已验证运行分数快照

日期：2026-10-31。状态：IMPLEMENTED_SYNTHETIC_ONLY。起点：6f797c3。依据：[报告 V0.40](../../reports/开题报告-V0.40-公开文本.md)的保存结果与分钟回放要求、[候选结果复查](../../guides/candidate-run-verification.md)和[输入快照](../../guides/candidate-snapshots.md)。

现有 IF/AE 验算器已检查完整分数文件，但公开返回汇总报告；后续分钟消费者尚不能直接取得这些已验证的逐分钟值。本批增加独立候选 Python 加载接口，保留现有 verify、CLI、比较报告及错误语义。它是联调准备，不是既有 CLI 故障修复。

两个 loader 返回冻结、带 slots 的 VerifiedCandidateRun，report 与 scores_document 递归只读；report_dict()/scores_dict()返回独立可修改副本。成功点直接冻结本次已读取并验证的实际 score_doc，不能重开文件或用重算期望值替换。保留完整轴、null、历史原因、分段和分区；AE 两个误差分量保持原字段，IF 不补造通道。缺少源时仍为 NOT_PROVIDED。

复用既有读取上限和验证过程，快照只延长报告与分数文档的保留时间，不持有权重、原始包字节或上游数值快照。不新增生产 API、worker 注册、网页或研究协议。

- [x] 新接口行为测试先失败，再最小实现；记录 RED 与通过结果。
- [x] 检查深只读、独立副本、同次读取、实际保存值、原工具兼容和错误；独立审查。
- [x] 主控复用已有四个人工结果包做有界只读验收，核 SHA/大小/mtime，不运行模型。
- [ ] 维护状态、指南、知识库，完成仓库检查，用 Desktop 提交推送并核远端 CI。

测试准备如运行人工 toy 模型，单独记录，不称整个测试过程无模型。真实 CSV、下载、真实拟合/训练/评分/校准/实验仍 NOT_RUN；Data Gate BLOCKED，最终政策、主数据和生产 134/268 维迁移未获批准。
