# 候选IF运行产物只读验算

日期2026-10-30；状态IMPLEMENTED_SYNTHETIC_ONLY；基点8410d2c。依据[V0.40可复现与评价要求](../../reports/开题报告-V0.40-公开文本.md)、[候选IF五产物](../../guides/candidate-if-synthetic.md)及[上游快照](../../guides/candidate-snapshots.md)。本批不生成新模型，补齐已有SYNTHETIC_ONLY输出的有界独立复查入口。

## 接口与证明范围

`verify_candidate_if_run(run_directory, record_directory, input_directory, *, source_fixture=None) -> dict`，CLI必需run/records/inputs，可选原人工source。固定五文件，四JSON身份/配置/版本声明、实际摘要、上游血缘、完整轴及null/valid、train/cal索引必须一致。用存储分数重算linear Q99、strict>及同一预测三政策评价；阈值、配置、布尔和索引精确校验，不用浮点容差放过改判。

weights只作为有界非空bytes核SHA，不反序列化、不执行fit/score，也不导入joblib/sklearn/torch。报告明确model_deserialization=NOT_PERFORMED、model_score_replay=NOT_CHECKED。版本只证明跨文件声明一致，摘要不认证作者或模型来源。任意非空weights若有相同内部摘要仍可能通过字节一致性，这不代表它是可加载或训练正确的模型。

原人工source缺失时保留NOT_PROVIDED，不能从manifest声明摘要推成已核源。只使用已验证快照，不调用要求source必提供的模型执行入口；不重估预处理或参数。

## 读取与分工

单weights8MiB、单JSON16MiB、五文件总32MiB，先stat快拒绝再按剩余预算有界读取；旧上游预算另行继承。拒绝重复JSON键、NaN/Infinity、超界、extra文件、manifest任意路径及符号链接/Windows重解析点，先检查未解析父路径再规范化。每个运行文件只读一次，不写任何输出。

- 主控实现candidate_run_artifacts.py及公共材料。
- 独立任务只写核心测试；另一任务只写薄CLI与子进程测试；只读任务审查设计/实现，不覆盖其他文件。
- [x] 保存完整缺模块RED，再实现核心与CLI。
- [x] 重封SHA后的语义篡改、任意weights不加载、缺源、搬迁、单次读取/预算/安全错误测试通过。
- [x] 独立审查修复，实际复查既有人工run及文件前后SHA。
- [x] 相关回归、仓库/隐私/作者/链接、status/README/路线图/维护和Vault更新。
- [ ] Desktop提交推送，核准确远端/CI；实际自身SHA在持续台账登记。

真实下载、CSV读取、预处理/模型拟合评分、真实Q99和正式实验不在范围；生产134/268、原审计及研究待决保持，Data Gate/S2 BLOCKED。自主截止10月31日12:00，11:30后仅收尾。
