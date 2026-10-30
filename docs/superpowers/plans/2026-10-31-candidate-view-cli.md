# 候选结果的只读查看命令

日期：2026-10-31。状态：IMPLEMENTED_SYNTHETIC_ONLY。起点21dee0b。依据[报告V0.40](../../reports/开题报告-V0.40-公开文本.md)的保存结果回放要求及已完成的[单分钟详情](../../guides/candidate-minute-details.md)、[范围分页](../../guides/candidate-series-pages.md)。

新增 `python -m traffic_anomaly.candidate_view_cli`，提供series与detail子命令，将已有纯查询接到安全加载器。显式互斥选择IF/AE运行目录，不猜测模型或失败后换加载器；records和inputs目录必填，人工source可选。series只调用所选run loader，detail额外加载输入快照并经过既有五摘要配对。顶层与子命令均拒绝缩写参数，解析错误不启动加载。

成功输出原查询的单个JSON；先完整序列化，UTF-8含换行最多1MiB，非有限值/不可序列化结果拒绝。预期错误只向stderr输出安全code、退出2且stdout为空，不回显路径、凭据或内部堆栈。无文件输出开关、数据库、生产接口、模型运行或产物写入。

完整命令加载阶段沿用保存的预处理/历史/Q99/评价关系验算，不称全程零复算；后续纯查询继续不读取文件或计算这些量。detail的额外输入加载有重复读取成本，不承诺目录原子快照。来源状态不因调用命令而升级。

- [x] 先写失败测试，用手写mock覆盖路由、解析、安全错误、输出UTF-8上限及完整输出。
- [x] 独立审查源码与边界，保持旧loader、生产契约、包入口和依赖不变。
- [x] 主控真实执行python -m，复用四个旧人工包核对输出、退出、原值和39文件身份；将实际CLI与另行插桩证据分开。
- [ ] 更新公开记录与既有知识库，执行仓库检查、Desktop提交推送和远端CI核对。

仅SYNTHETIC_ONLY工程消费接口；不新增下载或真实数据处理。主数据采用、最终Attempted政策、134/268生产迁移、真实训练评分校准和正式实验仍未获新批准，Data Gate保持BLOCKED。
