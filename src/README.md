# 程序入口

## 已验证候选载荷

[不可变加载API](../docs/guides/candidate-snapshots.md)供后续隔离候选消费者使用，保留旧校验CLI。每文件读一次，实际数值/历史/标签与摘要同时冻结；不重拟合、不注册生产worker。

## 候选产物复查入口

2026-10-30新增[只读候选校验CLI](../docs/guides/candidate-artifacts.md)：复查记录和数值目录、固定版本/哈希/配置、保存参数及H15/H30重放。仅SYNTHETIC_ONLY，不重新拟合、不改变下述生产契约或worker。

2026-10-30新增[人工源记录适配CLI](../docs/guides/candidate-records.md)，显式三政策、完成分钟13项和原数值CLI可串联；只SYNTHETIC_ONLY，不启动真实CSV或模型。

2026-10-29新增独立[候选输入计算](../docs/guides/candidate-inputs.md)：人工13维变换、H15/H30因果偏离和26维拼接、保存重载及有界CLI。仅SYNTHETIC_ONLY，不接生产worker，不改变下述原134/268契约。

W1核心、W2后端和W3前端已顺序合入。运行见[合成快速开始](../docs/guides/quickstart.md)，验证见[W0集成记录](../docs/project/W0-SYNTHETIC-INTEGRATION-2026-10-21.md)。共享契约见[contracts-v1](../docs/design/contracts-v1.md)。

核心CLI和后端调用同一execute_run，任务ID贯穿持久化、产物、HTTP与网页。当前只允许运行人工生成数据，SYNTHETIC_ONLY；真实Data Gate阻塞，真实模型训练和正式实验NOT_RUN。源码、依赖锁与脱敏说明入库；数据、权重、数据库、环境和运行输出留在本地忽略目录。
