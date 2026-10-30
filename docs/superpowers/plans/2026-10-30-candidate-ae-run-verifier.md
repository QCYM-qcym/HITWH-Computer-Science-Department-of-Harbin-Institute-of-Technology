# 候选AE五JSON只读验算

日期2026-10-30；状态IMPLEMENTED_SYNTHETIC_ONLY；基点5312eefe。依据[V0.40](../../reports/开题报告-V0.40-公开文本.md)的保存/复现与评价边界，补齐[候选AE五产物](../../guides/candidate-ae-synthetic.md)的独立消费入口；原IF验证器及生产134/268保持。

`verify_candidate_ae_run(run_directory, record_directory, input_directory, *, source_fixture=None) -> dict`，CLI仅run/records/inputs和可选source。五JSON固定白名单，weights单1MiB、其他单16MiB、总32MiB，先检查词法祖先链接/重解析，再规范化；每文件有界读取一次并核前后身份，不根据manifest路径打开其他文件。

以已核快照的轴、资格、字段、预处理与五摘要，加固定AE配置及受限run_id/版本/CPU线程声明重建expected binding；不能让weights.binding自证。严格核八tensor键、float32精确值/shape及参数数，但不构造网络。不导入torch/sklearn/joblib，不训练、评分或反序列化模型。

核完整轴null/valid、当前与历史误差非负、两通道固定归约、独立正常校准linear Q99与strict>、三政策分母/指标和未定义原因。训练/校准索引必须来自快照，loss只核五个有限非负声明和跨文件一致。数值溢出安全拒绝，不以warning暴露路径，不加容差改变报警。

成功只认证存储一致性。model_score_replay、training_execution、training_loss_replay为NOT_CHECKED，network_reconstruction为NOT_PERFORMED；版本只声明一致、源缺失NOT_PROVIDED，摘要不认证作者。合法修改权重并重封，或自洽修改保存分数/通道/评价，都可能通过本验证；必须用正例测试这一证明范围，不能假称模型已重放。

- [x] 核心测试与CLI保存完整缺模块RED，再实现最小只读模块。
- [x] 重封摘要后语义篡改、资源/路径/类型边界及无模型依赖验证。
- [x] 实际复查原三个AE运行，有/无人工源；SHA/mtime和内容读取次数核对。
- [x] 独立审查、相关测试、仓库隐私/链接/作者、公共记录与Vault同步。
- [ ] Desktop提交推送并核准确远端/CI；实际SHA另记持续台账。

主控独占实现和公共材料，核心测试子任务因容量中断后由主控接管；独立任务写CLI/测试，另一任务只读审查。测试准备仅生成合成包，被测验证器不执行模型。真实CSV/下载/模型/真实Q99/正式实验NOT_RUN；最终Attempted、主数据采用及生产迁移仍待决定，Data Gate/S2 BLOCKED不变。
