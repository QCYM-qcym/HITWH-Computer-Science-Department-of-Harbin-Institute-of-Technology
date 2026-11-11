# P1 有界 IF 数值状态层：设计 v1

日期：2026-11-11。状态：W0按持续自主工程授权采用P1，独立builder检查PASS。起点`746ad0fc3ef2f3e8ef808d6a553ae479e5d387fb`已Desktop发布并核对官方远端及README；准确CI分别记录。本P1实现、源码测试和新安装实际运行已通过；主控后验接受已完成，新发布待核。研究S2/Data Gate BLOCKED、真实模型与正式实验NOT_RUN不变。

本P1只定义安全JSON森林状态的encode/decode，以及对有限二维数值矩阵评分的纯函数。状态只描述推理数学，不包含raw/prepared/result身份、语义特征名称、源认证、view、标签、policy、训练/校准分钟、threshold或Q99。无fit、sklearn导出、文件包、CLI、save/load路径、网络或I/O。P2才接真实新人工fit/export、pair绑定和新三成员包；P1通过不能称checkpoint完成。

## 接缝与文件

一个公开深接缝分为两个新增文件，避免并行owner修改同一文件：

- `src/core/traffic_anomaly/iforest_numeric_state.py`：公开值对象、有限错误、状态验证、canonical codec及惰性评分转发；仅stdlib导入。W1独占。
- `src/core/traffic_anomaly/_iforest_numeric_score.py`：私有NumPy矩阵验证、float32快照、精确路由/路径算法；不定义第二格式、不复制状态验证器。W2独占。模块只依赖NumPy、stdlib与上述固定值对象/错误类；禁止sklearn/joblib/torch。

公开调用方只依赖第一模块。其 `score_iforest_numeric_state` 先调用本模块唯一 `_validate_state`，成功后才惰性导入第二模块的 `_score_validated_state(state,matrix)` 并转发；该私有函数信任已验证的精确state，不再重复结构验证，但负责NumPy运行时及完整矩阵验证。第二模块可导入第一模块的类型/错误类，NumPy在私有评分函数内才导入，缺失时映射INCOMPATIBLE_RUNTIME。这样坏state先于缺NumPy/坏矩阵拒绝，也不形成初始化循环。无第三通用框架、注册器、动态算法选择、用户回调或对象反序列化入口。若W0改为单文件，必须改为顺序owner交接，不能两个agent并行编辑同一文件。

与原“把pair、结果身份和森林全放一份state”的方案相比，本层不重复release上下文、不把数值结构通过说成来源认证；手写树可以直接精确验证，无需prepare或模型fixture。代价是P1不能独立证明输入语义/学习来源，也不能直接生成保存结果。P2必须在外层绑定语义特征顺序、人口、输入和结果身份；不能把本层0..width-1列号自动解释为current13/H30或据此使用真实输入。

## 公共API与精确值对象

```python
NUMERIC_STATE_VERSION = 1
NUMERIC_STATE_PROFILE_ID = 'iforest-numeric-state-v1'
NUMERIC_STATE_ALGORITHM_ID = 'iforest16-m32-f32route-f64path-numpy254-v1'
NUMERIC_STATE_BYTE_LIMIT = 262144
NUMERIC_STATE_MAX_ROWS = 10000

@dataclass(frozen=True, slots=True)
class IForestNumericNode:
    left: int | None
    right: int | None
    feature: int | None
    threshold: float | None
    sample_count: int

@dataclass(frozen=True, slots=True)
class IForestNumericTree:
    nodes: tuple[IForestNumericNode, ...]

@dataclass(frozen=True, slots=True)
class IForestNumericState:
    version: int
    profile_id: str
    algorithm_id: str
    input_width: int
    feature_order: tuple[int, ...]
    max_samples: int
    trees: tuple[IForestNumericTree, ...]

class IForestNumericStateError(ValueError): ...

def encode_iforest_numeric_state(state: IForestNumericState) -> bytes: ...
def decode_iforest_numeric_state(payload: bytes) -> IForestNumericState: ...
def score_iforest_numeric_state(state: IForestNumericState, matrix) -> tuple[float, ...]: ...
```

值对象构造器不自动I/O、fit或评分。每个公共函数重验自己的输入；不能因为是frozen dataclass或先前decode过就跳过验证。公共参数和所有嵌套值对象使用 `type(value) is ExpectedType`，tuple及元素精确类型；拒绝子类、缺字段的未初始化对象、np标量替代Python字段、bool冒充int。状态验证通过私有 `_validate_state(state)->None` 共享，私有名称只供两个新文件使用，不承诺对外API。

`feature_order` 必须精确等于 `tuple(range(input_width))`，不存在任意重排。树feature直接引用传入矩阵相同列号；这里只冻结列索引，语义特征名/变换/历史拼接不在P1。input_width精确int且只能13或26；m=max_samples精确int、1..32；森林恰16棵。没有n_train声明，也不推断每树训练样本来自哪里。

## 唯一节点表示与完整验证

每树nodes为精确非空tuple，先检查长度≤63再访问节点；16树总节点≤1008。节点ID是其tuple下标，root固定0。

- 叶节点恰为 `left=right=feature=threshold=None`，sample_count精确int、1..m。禁止-1/-2哨兵、额外kind字段或“部分None”别名。
- 内节点四项都非None：left/right为不同精确int，均在[0,node_count)且大于父ID；feature为0..width-1精确int；threshold为精确Python float且有限（允许-0.0，禁止int/npfloat代替）。sample_count精确int、1..m。
- root.sample_count=m；内节点两个子sample_count之和精确等于父count。所有节点必须由root可达，root入度0、其他入度1，无环/重复child/游离节点；显式遍历推导深度，不信任任何缓存字段。
- 最大边深度 `ceil(log2(max(m,2)))`，用 `(max(m,2)-1).bit_length()` 得到，无浮点log舍入。最大5。节点总数还应满足≤2m-1；拓扑和正样本守恒本已蕴含此约束，仍可显式核对。m=1合法且只能根叶；不新增最低32样本门槛。
- 不检查或认证这些counts真由训练产生；有限阈值也可能构成任意手写数学树。几何分区中是否有真实训练记录、树是否来自sklearn，均不由P1结构验证证明。

任何不一致整体拒绝，不剪枝、修正index/count、重排节点、填缺省或跳过坏树。每层先核精确类型/容器长度再遍历；被调用对象不得触发用户定义getter/迭代器。

## 精确JSON格式与限额

顶层恰7字段：version/profile_id/algorithm_id/input_width/feature_order/max_samples/trees。tree对象恰nodes一字段；node对象恰left/right/feature/threshold/sample_count五字段。tuple仅在JSON中投影为数组；无任意说明、路径、元数据、缓存平均路径、权重blob或可执行对象字段。

编码为 `ensure_ascii=False, sort_keys=True, separators=(',',':'), allow_nan=False` 的UTF-8，无BOM、末尾恰一个LF；含LF总bytes≤262144。encode实际检查输出预算，不返回截断JSON。规范投影已由固定树/字段数量限制，仍应采用有界iterencode或等价的实际bytes检查。

decode只接受精确bytes，先核bytes限额再decode/parse。拒重复JSON键、NaN/Infinity、非有限浮点、未知/缺失字段、任意尾随内容、非规范空白/键序/数值拼写及BOM；重新规范编码的完整bytes必须等于原payload。parse_int token最多8字符，parse_float token最多32字符，超长token直接拒绝；之后做严格int/float验证，1不能代替1.0 threshold，1.0/bool不能代替int。-0整数字面量、1e0替代1.0等因非规范bytes拒绝；合法threshold的-0.0规范表示可保留。

解析递归/Unicode/数值/结构错误安全拒绝；262144B限制是载荷预算，不宣称等于解析RSS上限。无eval、exec、pickle/joblib、动态module/dtype、用户函数或字符串表达式解释。decode/encode都不得打开任何文件或推断路径。

## 矩阵与返回值

matrix必须为精确 `np.ndarray`，二维，shape=(N,state.input_width)，N为0..10000。只接受本机native float32或float64 dtype；拒list/tuple、ndarray子类（含memmap/MaskedArray）、int/bool/object/complex/structured/float16/longdouble及非本机字节序。输入可只读、F序或非连续；不能为了内部方便拒绝合法切片或修改原数组flags/data。

先验证state，再核NumPy运行版本为精确2.5.4，再检查矩阵类型/shape/dtype/原值有限。对输入做有界C序float32独立copy；在局部np.errstate中拒绝转换溢出及转换后的非有限值，不输出RuntimeWarning。私有副本可置readonly；不改调用方矩阵、不保留其引用、无缓存。零行是合法纯评分，完成state/运行时/shape/dtype检查后返回 `()`。

结果为精确不可变tuple，长度N；每项精确Python float、有限且 `0.0 < score <= 1.0`，方向为越大越异常，即候选参考规则的 `-score_samples`。P1不返回可变NumPy数组、不产生二分类预测。数组同宽不等于语义特征顺序已认证；矩阵/状态在恶意并发修改下无原子快照承诺，但内部copy防止常规别名写入影响后续计算。

## 数值算法必须逐项保留

参考本地pinned sklearn1.9.1 `_iforest.py`/`_tree.pyx`，但P1不是sklearn模型执行证明。实现只以NumPy完成系数、binary64路径及power计算，禁用math.log/math.pow与任何模型库。

1. 路由读取float32私有副本；比较前将特征值显式提升为Python float或np.float64，再与保存binary64 threshold做 `<=` 左分支，否则右分支。不能直接比较np.float32 scalar/vector与Pythonfloat阈值，NumPy2会把后者降精度。
2. 根节点decision depth=1；由拓扑推导每节点decision depth。每节点平均路径系数c：sample_count=1时0.0；=2时1.0；3..32为 `2.0*(np.log(n-1.0)+np.euler_gamma)-2.0*(n-1.0)/n`，int64样本数组/float64输出，与参考NumPy表达式相同。不得采用精确harmonic数替代该近似式。
3. 对每棵树按0..15固定顺序：逐行或有界block求leaf index，然后先计算 `decision_depth[leaf] + c[leaf] - 1.0` 的float64向量，再用 `depths += contribution` 累计。不得改成均值、树score平均、reduction、并行树累加或提前结合减1。
4. normalizer为 `16*c(m)` 的float64，分数使用参考NumPy `2 ** (-np.divide(depths, denominator, out=np.ones_like(depths), where=denominator != 0))`。m=1分母0时该路径输出0.5，不能产生0、1或NaN；m=2的c(m)=1。
5. 算法版本固定NumPy2.5.4。同机显式NumPy操作顺序为首个目标；同版本跨平台的log/power最后位仍需另作实际等价验证，P1不承诺portable bitwise sklearn兼容。不得静默用容差改变算法或自动切换数学库。

score内部只能有最多N×16×5分裂，约80万分支；可按树产生N长leaf/depth数组，不建立N×16×63广播张量。共同输入矩阵上限10000×26×4B约1.04MB；每树≤63节点，树depth/coef及N长float64输出单独有界。载荷限额与工作数组估算不能冒称实际内存峰值。

## 有限错误域与顺序

IForestNumericStateError只输出以下精确str code；构造器未知/非str值收敛为NUMERIC_STATE_ERROR，str(error)==code，不带路径、原JSON、矩阵值或原异常。KeyboardInterrupt始终传播。MemoryError安全收敛RESOURCE_LIMIT，其他非声明普通Exception收敛NUMERIC_STATE_ERROR；无foreign error.code读取逻辑。

| code | 固定情况 |
|---|---|
| INVALID_STATE_ARGUMENTS | state公共参数不是精确IForestNumericState，或decode参数不是精确bytes |
| INVALID_STATE | 状态/节点字段类型错误、缺字段、坏JSON/超长数值token/重复键/非canonical、坏拓扑/样本守恒等 |
| INCOMPATIBLE_STATE | 字段类型正确但version/profile/algorithm/13或26宽度/feature_order不是此固定版本 |
| RESOURCE_LIMIT | payload超262144B、m>32、trees>16、每树nodes>63/总数>1008、matrix行数>10000或MemoryError |
| INVALID_MATRIX | 非精确ndarray、维数/宽度/dtype错误、原值/float32转换非有限等 |
| INCOMPATIBLE_RUNTIME | score的NumPy不可用或版本不是2.5.4；codec本身不需要NumPy |
| NUMERIC_STATE_ERROR | 其他内部异常、评分结果类型/长度/有限性/范围异常 |

不足16树、m<1、节点count超自身m、过深、≤63但超过2m-1等为INVALID_STATE。version等字段类型错误先INVALID_STATE，类型正确但不支持才INCOMPATIBLE_STATE。matrix状态错误优先于运行时、运行时错误优先于矩阵。decode顺序为：精确bytes类型→载荷长度→JSON解析及canonical→固定JSON对象/list形状与容器长度硬上限→完整state类型、兼容性及拓扑验证。JSON投影必须先限长再构造tuple和值对象；不另建一套完整state验证器。feature_order JSON list超过26项时已无兼容宽度，返回INCOMPATIBLE_STATE。

组合多错时，decode的有界投影预检可先报RESOURCE_LIMIT，例如bool version与超过63节点同时存在；单独bad version仍报INVALID_STATE。typed-state的encode/score按唯一validator的类型、资源、兼容和图检查顺序处理；不要求非法组合在两个入口报完全相同的首个错误。任何失败无部分tuple、隐式修正或副作用。

## 人工测试的必要证据

双宽13/26；m=1/2/4/32；m=32满63节点深5平衡树与根叶；零行和10000行；所有合法数组布局/readonly与坏dtype/溢出。手写树不调用prepare/fit/score/sklearn，也不以新scorer生成expected。

**NEP50测试不能只用m=2两叶。** m=2任一路径score都是0.5，错路由可能完全不可见。采用m=4、root左右叶sample_count=1/3的合法非对称树：左贡献1，右贡献1+c(3)，输出不同。令x32=1、阈值t=1-2^-26；正确double比较走右，直接npfloat32比较会走左。同一非对称树还用于原float64→float32舍入边界、等阈值向左与极端有限threshold。

另外用m=4三叶树区分decision depth、leaf sample校正、树序累积；m=32满树阈值按区间中点递归手写，避免所有分支同阈值导致虚构不可达数值区域。expected用列明每行路径/leaf count的手算表、独立常量/规范公式，关键0.5等边界要求精确相等；非简单值同时核路径理由与冻结binary64 literal，不调用产品私有系数/scorer作oracle。

坏图、重复父/child、游离节点、cycle、混合leaf哨兵、错误count/feature、超限及重封canonical后的语义错误必须覆盖；只断异常不能证明路径，须核有限精确code且无I/O/模型入口。encode→decode→score在内存的端到端测试明确叫“人工数值状态”，不能写成真实模型或磁盘包集成。

## P2后续边界与采用条件

P1纯层通过后，P2才可决定：新人工fit并保留模型→受限树导出→以本层评分比较该次原始全部scores→绑定raw/prepared/result及语义特征顺序→新三成员包→普通独立进程重载核完整scores/Q99/预测。旧C结果不能恢复树；P1手写状态也不能升级为新人工fit/checkpoint证据。P2若出现一bit差异须保留诊断并按明确profile决定，不临时放宽阈值或外部pickle加载。

W0已冻结本设计、实施计划、API和owner。本P1是工程采用，不是研究数据、标签或真实模型批准；未执行阶段仍为NOT_RUN，P2未采用。


## W0采用补充裁决

- 公开score只传播本模块精确IForestNumericStateError；未知Exception或领域错误子类安全收敛NUMERIC_STATE_ERROR，不读取foreign code/getter。KeyboardInterrupt传播，MemoryError归RESOURCE_LIMIT；缺字段的精确值对象归INVALID_STATE。
- 非简单浮点测试须有手工路径/叶样本表。可使用采用前独立计算的literal作同环境参考；跨平台若log/power末位未验证，用本机独立规范公式和固定手写路径构造严格expected，不调用产品helper、不放宽路由或运算顺序。半分数等精确边界仍逐位检查。固定树序可用先8左后8右与交替顺序的手写m4样例检查；当前环境两者相差1ULP，不把该差异宣称为所有平台保证。
- feature_order先核tuple长度等于width，再核每项精确int与列号。共享helper签名manual_numeric_state(*,width=13,pattern='root_leaf',max_samples=1)；非root_leaf模式必须显式传对应m，不静默改m。

## 实际工程快照

212/110/44源码切片与完整5112回归重叠，首次full41项setup前提失败保留；新安装四阶段0/0/0/0和双宽12个人工case见[验证](../research/2026-11-11-iforest-numeric-state-verification.json)。原九文件接受字节已归档，后续文档状态更新不替代原源码审查身份。P1仍无fit/export、文件包或CLI，主控后验接受已完成，F准确发布待核，P2/G候选未采用。
