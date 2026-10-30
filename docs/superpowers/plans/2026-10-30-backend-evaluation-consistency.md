# 后端保存评价汇总的一致性修复

日期2026-10-30；状态IMPLEMENTED_SYNTHETIC_ONLY。从已同步的候选结果核查基点续接；依据 V0.40 §4.1.4 的已存结果一致、失败可定位要求。范围为旧134/268生产接口的实现修复，不迁移候选13/26输入、不改变研究协议。

现有SavedArtifacts只核Evaluation自身Schema和身份，未把汇总计数与保存分数、标签关联。结构合法且摘要重新封装的“完美指标”可能被worker标成功并由API返回。核心保存验算已具备相应检查，后端缺失。

- [x] 用现有FakeExecutor合成文件复现：错误汇总+更新摘要仍成功；保留完整RED。
- [x] 最小修复：对已读类型化行调用现有纯评价函数，只核available、metrics、normal_coverage、attack_coverage、excluded_attack_minutes、background_only_minutes六项。不重新读大文件、不调用检测器、不生成替代响应。
- [x] 验证worker失败/安全错误、成功后篡改拒绝查询与导出，以及原fixture、缺标签/零分母正例；独立审查。
- [ ] 同步文档/知识库/状态，执行相关后端与集成、仓库检查，通过Desktop提交推送并核远端CI。

已知范围限制：原统一fixture漏报片段为00:01–00:02，而当前核心episode函数包括前一无效攻击分钟，输出00:00–00:02，列表排序也不同。本批不核intervals、不改这项规则或历史样例；另行核查既有片段定义。high_load字段和说明文字不重算或覆盖，原NULL及原因保留。只称六项汇总一致性修复，不称全部跨产物语义已认证。

人工fixture/HTTP验证与真实数据、模型效果分开。无真实CSV、下载、拟合、训练、模型评分或真实阈值校准；Data Gate保持BLOCKED，正式实验NOT_RUN。
