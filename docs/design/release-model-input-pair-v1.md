# 保存输入成对核对协议 V1

日期：2026-11-10。状态：配对核心与薄CLI已实现，限定源码单测通过；核心与CLI及两例joint追加独审均PASS，主控已接受源码，安装配对验收待完成。源码环境四例实际人工双包CLI已通过；独立构建安装与四例安装后CLI仍NOT_RUN。依据：[准备包格式](release-input-package-v1.md)、[运行指南](../guides/release-model-input-pair.md)、[验证记录](../research/2026-11-10-release-model-input-pair-verification.json)。

`pair_release_model_inputs(raw, saved)`接收既有加载器返回的`ReleaseMinutePackage`与`ReleasePreparedInputs`。检查准确类型、保存身份、配置、时间轴、段与角色、标签和必要mask关系；上游身份不匹配或轴不对齐时安全拒绝。分钟数上限10000、段数上限7。检查保存内部关系不证明数据来源、变换执行或模型适用性。

输出为冻结容器。原始13维、保存当前13维及H15/H30两个26维视图保留完整分钟轴；历史视图按当前13列加对应保存残差13列排列，各窗口独立保留有效位，无效行保留26个None。只拼接保存值，不重新计算历史、标准化或拟合。

标签位于sidecar，不能混入数值列。预处理fit人口与所选审计政策的模型训练/独立校准人口分列；保存的零人口原样保留，不据此生成阈值或评价指标。三政策各八类资格计数分别展示。

`summarize_release_model_inputs`仅投影身份、配置、列顺序、计数和证明范围，返回新建JSON友好容器；不输出逐分钟轴、索引、标签、矩阵、预处理均值/尺度或路径。固定声明包括`DERIVATION_REPLAY_NOT_PERFORMED`、`NOT_REESTIMATED`、`MODEL_NOT_LOADED`、`EXECUTION_NOT_GRANTED`及外部案例证据未建立。

CLI只接受必填`--raw-package`与`--prepared-package`，按raw加载→prepared加载→pair→summary各一次执行。准确字典且状态为`INPUTS_PAIRED`后，编码为紧凑排序UTF-8 JSON加一个LF，总长不超过65536字节；完整二进制写入和flush成功返回0，安全错误返回2。独立help不加载包。模块入口仅在失败时尝试封闭进程描述符，直接调用main保留宿主流；源码环境help破管已实际观察exit2；数据载荷输出破管和安装链未验收。

本模块不实现IF，不加载模型，不执行fit/train/score/Q99，不改变生产134/268契约。S2/Data Gate仍BLOCKED，D1—D6、最终政策、主数据、有限真实试点与生产迁移没有由本次工程实现取得批准。
