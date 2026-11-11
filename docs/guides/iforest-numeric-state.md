# 有界 IF 人工数值状态的内存接口

日期：2026-11-11。状态：P1 源码与新安装运行通过；独立规格和质量后验复核后已由主控实际接受，公开发布待核。设计见[数值状态 v1](../design/iforest-numeric-state-v1.md)，分工见[实施计划](../superpowers/plans/2026-11-11-iforest-numeric-state.md)。

本层接受手写森林状态与二维数值矩阵，完成规范 JSON 字节往返和纯数学评分。它没有模型拟合、sklearn 树导出或 checkpoint，也不提供文件包、CLI、HTTP API 或页面。P2 的训练产物导出与输入、结果绑定尚未采用。研究阶段保持 S2 / Data Gate `BLOCKED`，真实数据模型及正式比较仍为 `NOT_RUN`。

## 最小内存示例

codec 只依赖 Python 标准库，评分时才加载 NumPy，运行版本必须为 **2.5.4**。公开入口均位于 `traffic_anomaly.iforest_numeric_state`。以下例子手写 16 棵单样本根叶树，不调用任何训练或预处理。

```python
import numpy as np
from traffic_anomaly.iforest_numeric_state import (
    IForestNumericNode,
    IForestNumericTree,
    IForestNumericState,
    NUMERIC_STATE_VERSION,
    NUMERIC_STATE_PROFILE_ID,
    NUMERIC_STATE_ALGORITHM_ID,
    encode_iforest_numeric_state,
    decode_iforest_numeric_state,
    score_iforest_numeric_state,
)

width = 13
state = IForestNumericState(
    version=NUMERIC_STATE_VERSION,
    profile_id=NUMERIC_STATE_PROFILE_ID,
    algorithm_id=NUMERIC_STATE_ALGORITHM_ID,
    input_width=width,
    feature_order=tuple(range(width)),
    max_samples=1,
    trees=tuple(
        IForestNumericTree(nodes=(
            IForestNumericNode(
                left=None, right=None, feature=None,
                threshold=None, sample_count=1,
            ),
        ))
        for _ in range(16)
    ),
)

payload = encode_iforest_numeric_state(state)
restored = decode_iforest_numeric_state(payload)
matrix = np.zeros((3, width), dtype=np.float64)
scores = score_iforest_numeric_state(restored, matrix)

assert encode_iforest_numeric_state(restored) == payload
assert scores == (0.5, 0.5, 0.5)
```

将 `width` 改为 26，并同步矩阵列数，即可使用另一合法数值宽度。列索引固定为 `0..width-1`；相同宽度不能证明特征语义、列顺序来源或历史拼接正确。示例中的 0.5 来自单样本分母为零时的固定数学规则，不是校准阈值或分类预测。

## 状态与字节约束

状态、树和节点是冻结的 slots 值对象，嵌套容器使用 tuple。每次 encode 和 score 都重新验证完整状态，decode 也验证完整声明；曾经解码成功不能免除后续输入检查。

森林恰有 16 棵树，`max_samples` 为 1..32；每树至多 63 个节点，总数至多 1008。根节点固定为下标 0，其样本数等于 `max_samples`。内节点两个子样本数之和必须等于父数，子下标大于父下标且唯一可达；叶节点的四个分裂字段必须全部为 None。最大边深度由样本上限推导，最多为 5。

JSON 顶层恰有 `version/profile_id/algorithm_id/input_width/feature_order/max_samples/trees` 七个字段。每树只有 `nodes`，每节点恰有五个节点字段。字节为排序键、无多余空白的 UTF-8 JSON，末尾恰一个 LF，无 BOM；含 LF 总计不超过 **262,144 字节**。decode 只接受精确 bytes，拒绝重复键、额外字段、非规范数值拼写及非有限值，不执行字符串表达式或加载可执行对象。

Python 字段使用精确类型。bool 不能代替 int，整数不能代替内节点的 float 阈值；数组标量、子类或缺字段对象也不作为合法状态值。完整格式、资源检查顺序和图结构条件以设计为准。

## 矩阵与分数

矩阵须为精确 `numpy.ndarray`，形状 `(N, width)`，N 为 0..10,000，宽度为 13 或 26。dtype 仅接受本机字节序的 float32 或 float64，原值必须有限。list、整数数组、object/complex、非本机字节序及 ndarray 子类均会被拒绝。只读、F 序或非连续切片仍可使用。

评分在独立 C 序 float32 副本上路由，转换溢出会被拒绝；调用方数组的内容、flags 和布局保持。特征值先按 float32 舍入，再提升到双精度与保存阈值比较；相等走左分支。阈值保留 binary64 精度，不随输入降低为 float32。

每棵树按固定顺序累计路径长度，叶样本校正采用设计冻结的 NumPy 公式。返回值为不可变 tuple，每项是有限 Python float，满足 `0.0 < score <= 1.0`，分数越大表示数值规则下越异常。零行返回 `()`，但状态、运行时、shape 和 dtype 仍需合法。跨平台 log/power 的最后一位等价性尚未证明，不能据当前平台结果宣称可移植的 sklearn 逐位兼容。

## 有限错误

失败抛出 `IForestNumericStateError`，`str(error)` 只含一个固定 code，不回显状态、矩阵、路径或原异常。它不返回部分分数。

| code | 含义 |
| --- | --- |
| INVALID_STATE_ARGUMENTS | 公共 state 参数或 decode 字节参数的精确类型不符 |
| INVALID_STATE | 字段、JSON、拓扑、样本守恒或规范编码不合法 |
| INCOMPATIBLE_STATE | 类型合法，但版本、算法、宽度或列索引不受支持 |
| RESOURCE_LIMIT | 字节、树、节点、样本或矩阵行数超限，或内存不足 |
| INVALID_MATRIX | 矩阵类型、shape、dtype 或转换有限性不符合要求 |
| INCOMPATIBLE_RUNTIME | NumPy 不可用或不是 2.5.4 |
| NUMERIC_STATE_ERROR | 其他内部异常或非法评分结果 |

score 先检查 state，再检查运行时，最后检查矩阵。`KeyboardInterrupt` 保持传播；普通内部异常安全收敛，内存不足单列为资源错误。

## 当前验证范围

内存集成先观察公开接口缺失的失败，再使用真实 codec 和 scorer 验证双宽完整字节往返。手写多树覆盖不同结构、非对称 1/3 叶样本、float32 舍入与双精度阈值、相等向左、固定树序和 63 节点树；还覆盖只读/F 序/切片、零行与 10,000 行，以及坏矩阵、坏 JSON 和重封后的坏状态。

非简单分数的期望来自明确写出的每树路径和叶样本表，在本机按规范 NumPy 公式独立计算，不调用产品系数、路由或 scorer 生成自己的期望。0.5 等精确边界直接核对。旧平台的冻结 literal 只作为参考，测试不以容差替代固定运算顺序。

测试 setup 只构造人工值对象和小数组，没有 prepare、fit、score_samples 或 tree.apply。操作期护住常见文件、目录、网络和进程入口，禁止模型与其他业务模块导入；这些是高层调用护栏，不是完整 OS syscall 监控。NumPy 手写树路由与数学评分确实执行，不能称“零数值计算”。

本阶段没有数值状态文件包集成、源 CSV 读取或模型来源认证。源码验收时点独立安装仍为 `NOT_RUN`，后续实际安装见下节；另一机器验证、P2 导出及真实研究仍为 `NOT_RUN`；本文代码示例不计为这些阶段的运行证据。

## 新安装实际运行与保留的源码失败

最终源码切片为codec 212、scorer 110和内存集成44项；它们包含在完整回归5112通过/23跳过/1既有警告/56子测试中，不累加。首次完整回归有41项失败，原因是新测试误要求整个共享pytest进程没有模型模块；旧测试此前合法加载的模块应保留。以ModuleType sentinel复现失败后，改为保留已有模块、检查本次setup导入差量，并拦截fresh和cached模型导入attempt；原纯操作护栏保持。第二次独立新目录完整回归通过，首次失败原件保留。

一个新core wheel含82成员，安装到新target共85文件，复用锁定依赖。四个直接子进程为离线构建、安装、合法API runner和错误API runner，均实际退出0、自然回收及正常drain；父进程实际退出0。这里的runner是验收程序，产品仍只有内存API，没有CLI/help。错误runner的0表示成功观测INVALID_STATE、INVALID_STATE和INVALID_MATRIX。

合法runner的12例包含13/26两宽各自的根叶、非对称阈值、tie、两种树序和零行；2例返回空tuple，其余共20个分数。完整3469字节stdout严格匹配独立手路径预期；错误stdout为133字节。两进程均实际证明公开codec导入时未加载NumPy，随后显式加载NumPy再运行受保护的纯操作。模型/prepare为0的范围仅这两个被观察进程；完整回归中的旧人工模型fixture另计。

775保护项和12个人工fixture的初始完整名称/字节/SHA/mtime保持。原复制源79成员保持，构建后完整162成员另存，新增build产物没有冒充原件未变；wheel/target及持久initial收据从盘读回核对。控制器6.5248112秒记录到最终收据组装，3,354,302字节含准备，均不是模型延迟、内存峰值或研究成本。详见[完整验证](../research/2026-11-11-iforest-numeric-state-verification.json)。

前批E准确17文件Desktop发布及三CI见[回执](../research/2026-11-11-release-if-evaluation-publication.json)，不能替代F新提交/CI。本F已由主控后验接受，新提交与准确CI仍待核；学习树导出比较仅私有候选，P2未采用，真实研究Gate不变。
