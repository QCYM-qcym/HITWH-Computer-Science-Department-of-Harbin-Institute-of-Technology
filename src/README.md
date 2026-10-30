# 程序入口

## 2026-10-31 候选单分钟详情

[候选单分钟详情](../docs/guides/candidate-minute-details.md)提供无IO的快照配对查询，不重新训练、评分或计算评价，生产契约保持。

## 2026-10-31 候选已验证运行结果快照

[候选运行快照](../docs/guides/candidate-run-snapshots.md)由两个既有验算模块提供IF/AE加载入口，保留原verify报告与生产契约。

## 2026-10-30 后端JSON同字节读取

[后端读取修复](../docs/guides/json-byte-consistency.md)覆盖summary/config/metrics/model metadata/preprocess，保留原业务规则；core独立入口、生产契约与真实研究边界不变。

## 2026-10-30 后端Parquet同字节读取

[后端读取修复](../docs/guides/parquet-byte-consistency.md)覆盖scores/channels/labels，保留原typed规则与独立标签；JSON/core独立loader、生产契约和真实研究边界不变。

## 导出同一份已核验字节

[最终导出读取修复](../docs/guides/export-byte-consistency.md)绑定该次manifest原摘要，Service安全处理后读异常，端点不再重新打开文件。核心与生产契约不变；不能据此宣称完整目录原子快照。

## 保存区间消费核验

[SavedArtifacts](../docs/guides/backend-interval-consistency.md)在原六项汇总后精确核区间，复用一次纯计算；合法HTTP/导出继续返回保存结果。生产契约、核心算法和研究状态不变。

## 合成通道写入一致性

[FakeExecutor映射修复](../docs/guides/fake-channel-mapping.md)按时间和字段顺序保留显式通道、缺项null；不按评分有效性清空已提供的当前特征。生产核心/前端/契约保持，真实研究未放行。

## 合成片段与展示一致性

[片段示例修正](../docs/guides/episode-display.md)保留完整原始攻击段，页面定位预热起点并解释其不属于FN分母。相关Python98/前端25通过；没有改变核心算法或增加后端区间验证。

## 保存评价汇总一致性

[后端核验](../docs/guides/backend-evaluation-consistency.md)在成功前和结果读取时用已有纯函数核完整分数/标签的六项汇总，原响应与导出不改写。候选13/26路径、生产134/268契约和研究状态保持；片段语义差异已知待核。

## 已存候选结果只读核对

[候选比较CLI](../docs/guides/candidate-comparison.md)使用同一上游核对2—4个已有IF/AE运行，安全失败或输出共同资格及原指标；无模型执行/写文件，旧生产接口保持。

## 候选AE结果只读入口

[AE验证CLI](../docs/guides/candidate-ae-run-verification.md)读取五JSON和已核上游，验证权重结构/通道/校准/评价，不导入模型库或重建网络。原生产及IF接口保持，模型得分来源NOT_CHECKED。

## 候选AE独立CPU入口

[candidate_ae_cli](../docs/guides/candidate-ae-synthetic.md)消费原人工源复查后的候选快照，固定当前13或历史26网络；strict JSON权重、独立校准及重载，不接旧worker。仅导入/帮助无torch，显式执行才加载CPU运行时。

## 候选运行只读消费入口

[运行验证CLI](../docs/guides/candidate-run-verification.md)只读候选IF五产物及上游快照，精确验算存储Q99/报警/三政策；不导入模型库或加载weights。报告明确模型得分NOT_CHECKED，旧生产CLI/API不变。

## 候选13维IF工程入口

[独立合成CLI](../docs/guides/candidate-if-synthetic.md)在人工快照上拟合当前13维IF，独立校准、保存当次重载、导出完整轴和三政策评价。它不注册生产worker，也不放宽下述既有134/268模型契约。

## 已验证候选载荷

[不可变加载API](../docs/guides/candidate-snapshots.md)供后续隔离候选消费者使用，保留旧校验CLI。每文件读一次，实际数值/历史/标签与摘要同时冻结；不重拟合、不注册生产worker。

## 候选产物复查入口

2026-10-30新增[只读候选校验CLI](../docs/guides/candidate-artifacts.md)：复查记录和数值目录、固定版本/哈希/配置、保存参数及H15/H30重放。仅SYNTHETIC_ONLY，不重新拟合、不改变下述生产契约或worker。

2026-10-30新增[人工源记录适配CLI](../docs/guides/candidate-records.md)，显式三政策、完成分钟13项和原数值CLI可串联；只SYNTHETIC_ONLY，不启动真实CSV或模型。

2026-10-29新增独立[候选输入计算](../docs/guides/candidate-inputs.md)：人工13维变换、H15/H30因果偏离和26维拼接、保存重载及有界CLI。仅SYNTHETIC_ONLY，不接生产worker，不改变下述原134/268契约。

W1核心、W2后端和W3前端已顺序合入。运行见[合成快速开始](../docs/guides/quickstart.md)，验证见[W0集成记录](../docs/project/W0-SYNTHETIC-INTEGRATION-2026-10-21.md)。共享契约见[contracts-v1](../docs/design/contracts-v1.md)。

核心CLI和后端调用同一execute_run，任务ID贯穿持久化、产物、HTTP与网页。当前只允许运行人工生成数据，SYNTHETIC_ONLY；真实Data Gate阻塞，真实模型训练和正式实验NOT_RUN。源码、依赖锁与脱敏说明入库；数据、权重、数据库、环境和运行输出留在本地忽略目录。
