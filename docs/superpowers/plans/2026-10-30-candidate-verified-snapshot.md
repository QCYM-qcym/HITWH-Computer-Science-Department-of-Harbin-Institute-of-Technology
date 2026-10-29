# 候选产物不可变加载接缝

日期2026-10-30；状态IMPLEMENTED_SYNTHETIC_ONLY。从已同步62d6b166续接，属于自主开发第三批。依据[V0.40可复现要求](../../reports/开题报告-V0.40-公开文本.md)与[只读复查](../../guides/candidate-artifacts.md)。后续候选模型若先verify再独立读JSON，会重复读取并脱离已验证数据；本批先补同次读取的不可变快照，不启动IF或其他模型。

## 实现决定

新增`load_verified_candidate_artifacts(records, inputs, *, source_fixture=None)`，在当前验证器内部返回冻结快照。沿用原有白名单/上限/拒绝行为，同次有界读取的数据完成全部验证后才交给消费者。原`verify_candidate_artifacts`及其CLI仍返回原JSON报告，不新增模型或生产接口。

快照提供prepared/raw13矩阵、完整轴、两窗口历史及原因、共同/训练/校准/测试资格、三政策标签与正常掩码、原攻击存在标志、保存参数，以及实际读取的manifest/fixture/preprocess摘要。映射递归只读，数组由不可写bytes支撑，禁止普通赋值及重新开启writeable；不暴露可变预处理器。`report_dict()`返回独立可修改副本，调用者不能反向改变快照。

source仍可选，缺源明确NOT_PROVIDED；参数来源NOT_REESTIMATED。冻结快照只是进程内值对象，不是签名、研究批准凭证或通用模型加载入口；不保证抵抗故意绕过Python对象约束的本机代码。

## 执行与验收

- [x] 独立先失败测试：同次I/O、report兼容、三政策与可选源、实际SHA、深不可变、可改导出隔离、源文件后改不影响快照、no-fit及拒绝行为。
- [x] 主控最小重构核心，不改生产契约或现有产物写入格式。
- [x] 独立审查与相关回归；实际加载已存在三政策合成产物并核内容/输入快照。
- [x] 更新运行材料、验证/状态/路线图/维护和复用Vault日志，仓库/隐私/链接检查。
- [ ] 仅Desktop提交推送，核远端/CI，准确SHA留在持续台账。

本批不实现候选IF，不执行任何真实预处理、训练、评分或阈值；不新增下载或真实CSV读取。原134/268生产契约、G12/G13U证据和最终研究待决保持，S2/Data Gate BLOCKED，真实模型与正式实验NOT_RUN。
