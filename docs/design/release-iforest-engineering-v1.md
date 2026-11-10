# Release 13/26 → IF：最小设计

2026-11-10；主控按自主开发授权决定本轮工程范围，独立设计与修订前源码复核均PASS，修订前源版本已实现并完成新安装后的两个实际人工模型视图；本次前置长度检查修订后的全量回归与新安装模型smoke待执行。工程默认不代表研究参数定案。基点 `fa6cd630befab70c3d4c142266199fca05bc81e7`。

## 选择与范围

新增独立 `src/core/traffic_anomaly/release_iforest.py`，直接消费已配对的保存值。旧 `candidate_iforest.py` 要求 `VerifiedCandidateArtifacts/SYNTHETIC_ONLY`；旧 `detectors/iforest.py` 的实际 fit/score/load 固定134列（通用矩阵检查虽列出134/268）。因此不转换旧对象、不补列、不改旧契约。另一方案是先改造成通用检测器，但会扩大持久化兼容面，本轮不采用。只提供内存函数及摘要，无CLI、持久化、HTTP、页面、新依赖或研究评价指标。

## 接口

`fit_release_iforest(pair: ReleaseModelInputPair, *, view: str) -> ReleaseIFResult`。运行时仅接受精确字符串 `current13` / `h30_26`，其他值报 `INVALID_IF_ARGUMENTS`。

`ReleaseIFResult` 为 frozen/slots dataclass，字段：`profile_id: str`、`view: str`、`raw_identity: ReleaseMinutePackageIdentity`、`prepared_identity: ReleaseInputIdentity`、`configuration_sha256: str`、`scores: tuple[float|None,...]`、`predictions: tuple[bool|None,...]`、`scored_mask: tuple[bool,...]`、`threshold: float`、`train_indices: tuple[int,...]`、`calibration_indices: tuple[int,...]`、`preprocessing_fit_indices: tuple[int,...]`、`configuration: ReleaseIFConfiguration`。三个身份字段沿用pair原字段名、精确类型及值；两个identity可保留同一不可变对象，不重建含路径的替代物。不返回可变模型。配置也是 frozen/slots dataclass：`input_width: int, n_estimators: int, max_samples: int, max_features: float, bootstrap: bool, contamination: str, random_state: int, n_jobs: int`；固定16、min(32,n_train)、1.0、False、auto、42、1。profile为 `c17-release-iforest-engineering-v1`。

`summarize_release_iforest(result: ReleaseIFResult) -> dict` 只给白名单：version/profile_id/status/view/configuration、`raw_identity`、`prepared_identity`、`configuration_sha256`、分钟/已评分/训练/校准/预处理fit计数、threshold、Q99/linear/STRICT_GREATER、校准等于/大于阈值计数、以下限定。两个identity摘要各自仅有 `profile_id, context_sha256, manifest_sha256, manifest_byte_count` 四个原字段。raw/prepared的profile分别固定 `c17-release-minute-package-v1` / `c17-release-prepared-input-package-v1`；两个hash及configuration_sha256均精确str、64位小写十六进制，byte_count精确int（拒绝bool）且1..65536。结果和摘要均检查这些结构，摘要不重新核验外部字节，也无法识别一个结构合法但被替换的任意hash是否属于原包；只有执行时从pair原样保留的断言与独立运行收据建立对应关系。

状态只能 `ENGINEERING_COMPUTED`，不出现ACCEPTED/VERIFIED/GATE_PASSED或效果优越结论。摘要先验证结果的精确类型、轴长、None/mask对应、有限阈值/分数、索引和预测比较一致性；train/cal必须非空、递增、互斥且为scored_mask子集，train还须为preprocessing_fit_indices子集，后者允许未评分行；配置精确类型、view宽度和max_samples必须一致。摘要不重新计算Q99：仅拒绝非有限或导致预测不一致的阈值，结构自洽但不是原始Q99的手构值不能由摘要认证；精确Q99由独立smoke验算。摘要可手工构造，不是可信执行收据。结果不携带标签、路径、原始值或认证标志。

## 先验证，再取数

pair是公开可构造dataclass，不能把其类型视为资格证明。现pair工厂只检查选中资格为真时“当前common+角色+当前标签正常”，其6分钟手写单测甚至故意没有合法30分钟历史；该fixture不能直接用作模型合法输入。

独立验证阶段先限制1..10000分钟、精确嵌套类型/元组/bool/int及固定profile/schema/scopes/AUDIT_ONLY/NOT_AUTHENTICATED/时间代理。由pair字段重建 `ReleaseInputContext`，复用纯验证 `release_inputs._validate_content`：完整轴、历史有效性结构、配置摘要、保存fit mask及资格重算；它会读sidecar确定合法人口，但不拟合、不重新派生数值。再逐项比较pair角色/segment_ids和segments、人口policy/三个mask/三个index与保存sidecar、selected-policy资格完全一致（不是子集），检查无重复/负数/bool索引、train/cal不交叉且角色正确。检查raw值与raw_valid、身份格式及 `joined_h15/joined_h30` 与保存current+residual逐格一致。只做内存一致性，不重新读取包、不核验来源、身份对应的包字节或预处理统计真实性；这些限制须保留。

校验完成后剥离为私有数值输入（矩阵、common、train/cal索引），后续fit/score/calibration代码完全不接收标签。`current13`也只能在同一 `common_valid` 轴取行；H30取current后接residual的26列。预处理fit索引只作provenance，绝不替代模型train。合法零train/零cal分别 `NO_TRAINING_NORMAL` / `NO_CALIBRATION_NORMAL`，均须在导入/构造模型前拒绝；伪造空mask应是结构错误。选中common矩阵先转float32并检验有限性，阻止1e39等有限float64溢出；也在模型构造前完成。

## 数值与错误

模型仅fit(train)，对common一次score_samples并取负。分数必须是一维、长度准确、实数且有限；不允许广播、NaN、Inf、complex或bool。阈值只取calibration索引分数，用既有 `evaluation.calibration.calibrate` 的线性Q99，随后再检验有限值。阈值相等不报警，严格大于才True。全轴common以外 score/pred 都None，scored_mask=False，不计正常负例。

`ReleaseIFError(ValueError)` 仅输出白名单code并 `from None`：`INVALID_IF_ARGUMENTS, INVALID_IF_INPUT, RESOURCE_LIMIT, NO_TRAINING_NORMAL, NO_CALIBRATION_NORMAL, INVALID_INPUT_NUMERIC, INVALID_MODEL_SCORES, MODEL_UNAVAILABLE, MODEL_ERROR, INVALID_IF_RESULT`；未知传入code收敛为INVALID_IF_INPUT。轴/段超上限映射RESOURCE_LIMIT；上游ReleaseInputPreparationError的其他结构/完整性错误映射INVALID_IF_INPUT。两个模型人口皆空先报NO_TRAINING_NORMAL。缺可选sklearn映射MODEL_UNAVAILABLE，fit/score调用异常映射MODEL_ERROR；返回值形状/dtype/有限性及Q99非有限或溢出映射INVALID_MODEL_SCORES。先检查模型返回值原dtype与形状，再转float64并取负，避免bool/complex隐式接受或无符号绕回；不泄漏原始异常/路径。KeyboardInterrupt不吞并为成功。摘要固定声明：ENGINEERING_DEFAULTS_ONLY、AUDIT_ONLY、NOT_AUTHENTICATED、SOURCE_WALL_CLOCK_COMPLETION_PROXY、DERIVATION_REPLAY_NOT_PERFORMED、NOT_REESTIMATED、EXTERNAL_ACCEPTANCE_NOT_ESTABLISHED；来源/研究权限不由输出升级。

已读取项目skills/README及scikit-learn入口。沿既有Python3.14、NumPy2.5.4、scikit-learn1.9.1锁定依赖，不安装依赖、不运行技能通用示例；其Pipeline建议不触发本轮重新fit预处理。沿保存时间分段，不随机划分、不调参、不重复看测试集选参数。S2/Data Gate仍BLOCKED；真实fit/train/score/Q99和正式实验NOT_RUN。实际范围见[工程验证记录](../research/2026-11-10-release-iforest-engineering-verification.json)；该工程验收不完成真实研究准入。

## 已裁定的设计复核边界

标签改变不会自行取消数值common；合法修改校准/测试标签时必须同步受影响的保存资格，完整验证可接受缩小人口，拒绝仍声称旧资格的对象。H15/H30各按自己的history.valid拼接，H15就绪但H30预热时不可把两者一起置空。留出段标签不变性只比较数值结果、人口索引、阈值与配置；两份结果身份分别等于自己的输入，保存标签变更允许manifest摘要不同。内存replace沿用identity只作为结构反例，不宣称另一个包有同一哈希。消费者禁止I/O测试限定包/CSV/外部数据路径，不以全进程禁用底层导入I/O误判sklearn加载。
