# 候选AE人工工程演练

日期2026-10-30；状态IMPLEMENTED_SYNTHETIC_ONLY；基点b372687。依据[V0.40](../../reports/开题报告-V0.40-公开文本.md)的当前/历史AE、独立校准和可复现要求，延续[候选输入](../../guides/candidate-inputs.md)与[不可变快照](../../guides/candidate-snapshots.md)。这是独立13/26维候选工程，不修改生产134/268契约。

只消费经原人工源复查的SYNTHETIC_ONLY快照。当前网络13→8→3→8→13，历史网络26→8→3→8→26；各自288/509参数，固定CPU float32、seed42、5轮全batch Adam(0.001)，无验证择优或早停。历史模式显式选15或30；资格均为H15/H30交集，训练/校准还要求完整历史正常。配置是ENGINEERING_TOY_ONLY，不代表真实推荐、收敛或容量匹配。

评分先把实际float32输入及重构提升为float64，再作差、平方和均值；历史两组等权。历史偏离输入与重构误差分别记录。每模型独立正常校准Q99(linear)，严格大于才报警；完整分钟轴无效处为null，固定预测沿用三政策评价及缺失指标原因。任何数值非有限都失败，不裁剪或删样本凑结果。

五个输出为weights.json、model-state.json、scores.json、evaluation.json和最后manifest.json。权重仅允许固定八tensor键、float32、精确shape和有限标量；有界严格JSON校验，硬编码CPU网络重建并copy参数，无pickle或torch.load/save。绑定run_id、模型/预处理/字段顺序/版本/上游摘要与配置，重放当次模型的参数、分数、阈值、报警及评价后才完成。权重1MiB、其他单JSON16MiB、总32MiB；独占新目录、不覆盖上游或旧失败产物。

不改线程设置；CPU RNG保存/定seed/恢复，不查询加速器。导入、JSON校验和CLI帮助不导入torch/sklearn/joblib。CPU RNG是进程全局，当前仅串行独立CLI，不接入并发服务。

- [x] 核心/权重/CLI分别先完整RED，再最小实现；主控独占公共状态。
- [x] 核训练隔离、因果资格、精度/梯度/状态有限性、RNG恢复、严格JSON及安全错误。
- [x] 当前/历史两种模式实际人工运行、自存重载、独立摘要与三政策核验，保留负结果。
- [x] 独立Spec/Quality审查，相关回归、仓库隐私/链接/作者检查和Vault记录。
- [ ] Desktop提交推送及准确远端/CI，实际SHA另记持续台账。

本批真实CSV读取/下载/预处理拟合/模型训练评分/Q99/正式比较NOT_RUN。最终Attempted端点、主数据采用、生产迁移及有限试点研究决定仍待明确批准，S2/Data Gate BLOCKED不变。
