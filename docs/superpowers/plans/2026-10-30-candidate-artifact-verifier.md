# 候选合成产物只读复查计划

用途：自主开发第二批；日期2026-10-30；状态IMPLEMENTED_SYNTHETIC_ONLY。基点为已由Desktop同步、三项CI成功的0d69b54。依据[V0.40 §4.1](../../reports/开题报告-V0.40-公开文本.md)、[记录接缝](../../guides/candidate-records.md)和[数值入口](../../guides/candidate-inputs.md)。

## 范围与决定

新增隔离的`candidate_artifacts.py`与`candidate_verify_cli.py`，复查现有SYNTHETIC_ONLY两步输出，不改变生产契约、现有写入格式或研究准入。主控维护核心与公共材料，独立实现者仅维护CLI及其测试，另一只读任务审查边界和实现。沿用当前隔离worktree和codex分支。

`verify_candidate_artifacts(record_directory, input_directory, *, source_fixture=None) -> dict`：两个目录必需；可选原始人工记录fixture。固定白名单文件、摘要和字节数、profile/config/特征顺序、跨目录minute-fixture摘要必须一致。加载保存参数进行transform和H15/H30重放，复核完整时间轴、null、资格掩码及分段摘要；不调用fit/prepare，不重估参数，不声称认证训练拟合来源。提供源样例时再重放人工记录适配和标签审计；未提供时明确NOT_PROVIDED。

数值浮点重放固定rtol=atol=1e-12；结构、布尔、整数、时间、枚举及哈希精确匹配。仅证明本版本人工产物内部一致，不证明作者身份、真实数据适用性、模型效果或实时可用性。

## 有界读取

源fixture和分钟fixture各1MiB，manifest各64KiB，预处理状态16KiB，标签审计16MiB，数值产物64MiB；超限在解析前拒绝，读取最多上限+1。目录只允许各自三项既有产物，拒绝链接/重解析点、非普通文件、缺失或多余项以及manifest路径注入；不加载pickle/模型，不联网、不写输出。并发恶意文件替换不是本地只读复查工具的安全保证。

## 执行与验证

- [x] 核心先写失败测试：合法搬迁、可选源、no-fit、哈希断链、重算摘要后的语义篡改、维度/特征/状态/掩码/标签/null、资源与路径边界。
- [x] 实现最小只读验证，人工源重放与保存参数重放分开报告。
- [x] 独立CLI先RED后GREEN，真实子进程验证成功、安全失败和只读快照。
- [x] 独立审查修复，运行相关及必要整链回归；实际复查上一批三个政策输出并记录。
- [x] 更新运行指南、验证记录、公共状态、路线图、维护和已有Vault日志；仓库/隐私检查通过。
- [ ] Desktop提交推送及远端CI按实际完成写入持续台账，不为回填尚未产生的提交循环发布。

## 不变边界

新下载和真实CSV读取0；原G12/G13U失败与供应证据保留，Attempted最终政策、主数据采用和生产迁移仍待批准；真实变换拟合、训练、评分、Q99及正式实验NOT_RUN，S2/Data Gate BLOCKED。截止2026-10-31北京时间12:00，11:30后仅收尾。
