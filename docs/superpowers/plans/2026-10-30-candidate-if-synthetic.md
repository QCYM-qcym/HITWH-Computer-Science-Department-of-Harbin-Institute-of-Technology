# 候选13维IF合成演练计划

日期2026-10-30；状态IMPLEMENTED_SYNTHETIC_ONLY。基点b224c2e。用户要求汇报实际成果后继续原自主迭代、不合并main；本批只使用现有人工fixture，依据[V0.40 §4.1.3/4.1.7](../../reports/开题报告-V0.40-公开文本.md)、[快照入口](../../guides/candidate-snapshots.md)及[协议待决包](../../research/2026-10-30-limited-pilot-proposal.md)。

## 约束与设计

独立候选13维IF消费同次验证快照；生产134/268模型、UGR八标签及worker不变。必须显式提供原人工source，SYNTHETIC_ONLY/AUDIT_ONLY；用当前13维，资格仍为既有H15/H30共同集合。仅train全历史正常共同分钟拟合；不重新拟合预处理。独立calibration全历史正常共同分钟Q99 linear，strict>；完整轴预热/无效score与alarm为null，当前unknown仍评分、只从正常/攻击评价分母排除。

固定16棵树、max_samples=min(32,N_train)、max_features=1、bootstrap=false、seed42、单线程；均为ENGINEERING_TOY_ONLY，无样本最少32的门槛，不为凑样本扩张fixture。没有调参、AE、真实数据或研究效果结论。同一模型/阈值/报警固定后，三政策只映射标签计算敏感性，不跨政策重训。

CLI必需records/inputs/source-fixture/run-id/output，不接受外部model/resume/policy或搜索参数。输出新独占且不重叠目录，固定model-state.json、weights.bin、scores.json、evaluation.json，manifest最后COMPLETE。run_id、版本、特征顺序、配置及上游五摘要全程绑定；scores字节摘要进入evaluation。只重载本次进程刚产生且字节相同的joblib数据，不开放任意外部pickle读取。单weights8MiB、单JSON16MiB、总32MiB，buffer写入即限制；失败不留COMPLETE，保留其他partial，仅可删除本次创建且写失败的manifest。

## 分工与验收

- 主控：candidate_iforest.py与测试；训练隔离、float32溢出、方向、独立Q99/strict>和自产重载。
- 独立任务：candidate_evaluation.py及测试；normal/attack/unknown互斥守恒、FPR/FNR零分母null+原因。
- 独立任务：candidate_if_cli.py及测试；实际子进程、目录/文件/资源、ID与摘要、安全失败及只读输入。
- 只读审查：先看设计边界，再Spec/Quality复核；公共状态/契约和Vault均主控维护，不新建聊天。

- [x] 各模块完整先失败测试，再最小实现通过。
- [x] 独立审查修复；实际人工144分钟跑一次，核训练/校准各6、共同24及三政策正常分母4/5/4，不期待具体检测效果。
- [x] 相关回归、仓库/隐私/作者/链接与知识库维护。
- [ ] Desktop提交推送，核远端/CI；准确自身SHA在交付台账登记。

本批新下载/真实CSV读取0，最终标签/主数据采用/生产迁移未批准；真实预处理、模型训练/评分/Q99和正式实验NOT_RUN，Data Gate/S2 BLOCKED。旧失败证据保留。自主截止仍为2026-10-31北京时间12:00，11:30后仅收尾。
