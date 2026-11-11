# Release 保存预测标签敏感性评价 v1

日期：2026-11-11。状态：W0按持续自主工程授权采用，独立builder check通过。基线 `16082f7e787de162d1aa63050108a11a2388da50` 的19文件人工源链已验收并通过GitHub Desktop推送，官方ref／远端README与全部Git blob已核对；该基线CI仍以准确工作流实况为准，不借旧CI。本设计的实现与完整源码验证已完成，七阶段新安装实际运行通过；独立规格和质量后验复核后主控已实际接受，公开提交与新CI待核，不构成研究政策采用。

## 目的与边界

给既有release结果提供显式输入绑定后的测试分钟误报/漏报算术：一个pure evaluator返回小型规范bytes，一个独立readonly CLI读取三个保存包并原样输出。旧candidate评价已有独立格式，不复用其SYNTHETIC_ONLY声明；不改已发布run/inspect/verify、Metrics/sharedschema、依赖、134/268、API/UI或包格式。

同一个保存预测向量按P_U/P_B/P_A解释现有标签，属于**固定预测的标签敏感性**。原audit_fit_policy随报告保留，不能称为三次训练/重新校准/政策选择/模型优劣。产品无create/save/source CSV访问/aggregate/prepare/replay/fit/score/阈值选择。既有codec保存分数Q99复核允许，模型fit/score/模型Q99操作为0；内部验证仍有数值矩阵检查，不称“零数值计算”。D1-D6、S2/Data Gate BLOCKED及真实C17研究NOT_RUN不变。

## 两模块seam

新 `src/core/traffic_anomaly/release_if_evaluation.py`：

```python
EVALUATION_PROFILE_ID = 'c17-release-iforest-fixed-prediction-label-audit-v1'
EVALUATION_BYTE_LIMIT = 16384
class ReleaseIFEvaluationError(ValueError): ...  # finite safe .code
def evaluate_release_if_result(
    package: ReleaseIFResultPackage, pair: ReleaseModelInputPair,
) -> bytes: ...
```

无I/O；只读参数，返回不可变规范UTF-8 JSON bytes。先用`type(...) is`检查两个精确公共类型，错误时不调用verify；随后 `verify_release_if_result_pair(package,pair)` **恰一次**，成功后才读标签并算术。不另写身份/数值验证器、不调用任何producer/model。不能通过可选mask/policy/threshold参数绕过保存契约。

新 `src/core/traffic_anomaly/release_if_evaluation_cli.py`：

```text
python -m traffic_anomaly.release_if_evaluation_cli evaluate --result-package ABS_DIR --raw-package ABS_DIR --prepared-package ABS_DIR
python -m traffic_anomaly.release_if_evaluation_cli --help
```

`main(argv: Sequence[str] | None = None) -> int`及常规模块入口。无输出目录、文件重定向编排、新console script或第三产品模块。读取和stderr/stdout是CLI唯一I/O；不认证源、标签真值、预处理数值派生或历史模型执行。

## 分母与算术

- 完整test轴恰为保存`pair.roles[i]=='test'`；scored test为该条件 **AND `package.result.scored_mask[i]`**，后者已经verify绑定到`pair.prepared_minutes.common_valid`。其他角色的scored/报警行不进入test指标。
- 保存label列索引固定`P_U/P_B/P_A`，每列值为normal/attack/unknown。正常/攻击mask及有效/报警数组必须是一维同长`numpy` bool；禁止int/object数组参与`~alarms`。alarms从保存prediction的精确True构造，未评分None以False投影且由valid排除；unknown即使True也不进confusion。
- 每政策调用既有 `evaluation.metrics.confusion(normal,attack,valid,alarms)` 一次；只投影返回的TP/FP/TN/FN及precision/recall/f1/fpr；FNR=`FN/(FN+TP)`。不调用旧`evaluation.metrics.evaluate`、区间/点调整、高负载分组、AUC或模型排序。
- 分别报告完整/已评分/未评分test按标签细分。每kind scored+unscored=calendar；三kind之和对应各人口；scored+unscored=calendar；FP+TN=scored normal，TP+FN=scored attack。unknown和unscored独立可见，不能归正常或负例。
- 无test段是有效报告：只要原包/训练/校准合法，三政策所有计数0、五指标null且具原因；不能返回伪0或把整个报告拒绝。零normal/零attack/无positive/all unknown同样逐指标判定。

## 规范输出：精确16个顶层字段

JSON `ensure_ascii=False, sort_keys=True, separators=(',',':'), allow_nan=False`，UTF-8无BOM，末尾恰一个LF；**含LF总字节≤16384**。无数组、任意说明文本、路径、当前时刻、逐分钟预测、标签、阈值向量或权重。

| 字段 | 精确类型和值 |
|---|---|
| version | 精确int `1`（bool不接受） |
| profile_id | 固定EVALUATION_PROFILE_ID |
| status | `SAVED_PREDICTION_LABEL_AUDIT` |
| scope | `SAVED_RESULT_LABEL_SENSITIVITY_INTERNAL_CONSISTENCY_ONLY` |
| unit | `minute` |
| result_identity | 本结果四字段身份 |
| input_references | 恰raw/prepared两个四字段身份，来自已绑定pair |
| configuration_sha256 | 已绑定准备配置的小写64位摘要（非模型权重认证） |
| view | 保存的current13或h30_26 |
| audit_fit_policy | 保存的P_U/P_B/P_A，不随报告政策改写 |
| policy_status | `AUDIT_ONLY` |
| source_authentication | `NOT_AUTHENTICATED` |
| time_basis | `SOURCE_WALL_CLOCK_COMPLETION_PROXY` |
| model_execution | `NOT_AUTHENTICATED` |
| prediction_basis | `FIXED_SAVED_PREDICTIONS_NO_REFIT` |
| policies | 恰P_U/P_B/P_A三键对象，各值为下述report |

每个identity恰 `profile_id / context_sha256 / manifest_sha256 / manifest_byte_count`；profile为相应既有包固定值，两摘要为小写64位，最后是1..65536精确int。JSON对象规范键排序使policies的**序列化顺序为P_A/P_B/P_U**；与保存label tuple的逻辑索引P_U/P_B/P_A分别处理。

每policy report恰9字段：`calendar_test_minutes / scored_test_minutes / excluded_unscored_test_minutes / calendar_by_kind / scored_by_kind / unscored_by_kind / confusion_counts / metrics / undefined_reasons`。前三为0..10000精确int；三个by_kind对象各恰normal/attack/unknown同范围int；confusion_counts恰tp/fp/tn/fn同范围int；metrics恰precision/recall/f1/fpr/fnr，值为有限float[0,1]或null；undefined_reasons恰含null指标键，值如下，其他键不存在（全有定义时为`{}`）。有定义的零保留0.0。

| 指标 | 零分母 | 唯一reason |
|---|---|---|
| precision | TP+FP | NO_POSITIVE_LABELED_TEST_PREDICTIONS |
| recall | TP+FN | NO_SCORED_TEST_ATTACK |
| fnr | FN+TP | NO_SCORED_TEST_ATTACK |
| fpr | FP+TN | NO_SCORED_TEST_NORMAL |
| f1 | 2TP+FP+FN | NO_ATTACK_OR_POSITIVE_LABELED_TEST_PREDICTIONS |

这些reason从现有confusion返回的null/分母映射，不改Metrics的`undefined_reasons: list[str]`。报告无N长度数组，16384限额足够但仍执行实际字节检查；限额失败不能输出截断JSON。

## Pure错误域：五个有限码

`ReleaseIFEvaluationError`只接受精确str且在 `INVALID_EVALUATION_ARGUMENTS / RESOURCE_LIMIT / INPUT_BINDING_MISMATCH / INVALID_EVALUATION_INPUT / EVALUATION_ERROR` 中；未知构造值收敛为EVALUATION_ERROR，无路径/原异常文本。KeyboardInterrupt继续传播。

| 来源 | 映射 |
|---|---|
| 两参数不是精确公共类型 | INVALID_EVALUATION_ARGUMENTS，verify未调用 |
| 精确ReleaseIFResultPackageError，code=RESOURCE_LIMIT | RESOURCE_LIMIT |
| 同精确类，code=INPUT_BINDING_MISMATCH | INPUT_BINDING_MISMATCH |
| 同精确类，code为INVALID_PACKAGE/INCOMPATIBLE_PACKAGE/INTEGRITY_MISMATCH/INCONSISTENT_PACKAGE | INVALID_EVALUATION_INPUT |
| 实际输出超过本模块限额 | RESOURCE_LIMIT |
| 其他Exception、verify未知类/子类/跨域码/非str code、算术/守恒/内部构造或JSON失败 | EVALUATION_ERROR |

只读取上述精确异常类的code，getter普通Exception安全收敛；getter KeyboardInterrupt也传播。`INVALID_PACKAGE_ARGUMENTS`在精确参数已检查后的verify链不可达；磁盘/输出类码也不在pure域，不能透传。验证后的projection/count/type守恒失败视内部构造错误，不重训“修正”或输出部分成功。

## CLI解析、顺序与每类安全码

只接受evaluate及三个各一次必需选项；允许`--name value`/`--name=value`。`-h`/`--help`仅独占；拒绝重复/未知/缩写/@file/额外位置参数/空值/混help/非str token、str/bytes代argv序列，INVALID_ARGUMENTS且无业务I/O。

三个原字符串全部先作本机绝对路径词法检查：拒绝NUL/lone surrogate/`..`/UNC；Windows本地盘、保留名、ADS沿既有`release_input_package._lexical`。先检查原拼写后才Path，不resolve、不以Path预先吞掉坏原拼写。只复用这一个无I/O helper；实际普通目录/单链接成员/身份/总额/读回由各loader负责，不额外重写inventory、锁或假设三包原子快照。

成功顺序固定：`load_release_if_result_package`一次 → `load_release_minute_package`一次 → `load_release_input_package`一次 → `pair_release_model_inputs`一次 → `evaluate_release_if_result`一次（内部verify一次）。每次失败立即停止后续；只向stdout写evaluator原bytes。CLI仅验返回是精确bytes、非空和≤16384；语义/规范JSON由pure契约负责，不新建第二报告decoder。help固定小bytes。成功exit0/stderr空。

精确 `_CLIError(ValueError)`保存内部code不自动收敛；其允许码为 `INVALID_ARGUMENTS / INVALID_PACKAGE_PATH / INVALID_RESULT / RESOURCE_LIMIT / OUTPUT_ERROR`。以下按**精确异常类型**匹配，不使用isinstance；code必须精确str且在对应集合，未知/跨类码、子类、非str或code getter普通错误一律INTERNAL_ERROR：

| 精确异常类型 | 全部允许输出码 |
|---|---|
| 新_CLIError | 上述五码 |
| ReleaseIFEvaluationError | 上述pure五码 |
| ReleaseMinutePackageError | INVALID_PACKAGE, INCOMPATIBLE_PACKAGE, RESOURCE_LIMIT, INTEGRITY_MISMATCH, INCONSISTENT_PACKAGE, INVALID_PACKAGE_PATH, INPUT_UNAVAILABLE, PACKAGE_CHANGED |
| ReleaseInputPreparationError | 同上八码，另加INVALID_PREPARATION_CONFIG |
| ReleaseIFResultPackageError | 同上八码（不含INPUT_BINDING_MISMATCH：磁盘load不绑定，pure已转换绑定错误） |
| ReleaseModelInputPairError | INVALID_PAIR_ARGUMENTS, INVALID_PAIR_STRUCTURE, INCOMPATIBLE_PAIR, RESOURCE_LIMIT, UPSTREAM_IDENTITY_MISMATCH, PAIR_ALIGNMENT_MISMATCH |

可达性依据：三个loader的read/inventory/codec路径能产生八个通用码；prepared decode还调用`_config`，因此INVALID_PREPARATION_CONFIG可达。OUTPUT_EXISTS/OUTPUT_ERROR属于save，NO_TRAINING_NORMAL_MINUTES/NONFINITE_FIT_STATE属prepare，DERIVATION_MISMATCH属replay，MODEL_*属模型；全部不因旧类拥有这些枚举就加入readonly白名单。helper INVALID_PACKAGE_ARGUMENTS在精确str输入下不可达；收到时INTERNAL_ERROR。pair的六个声明码均属所调用验证接口。

任意业务或错误code getter KeyboardInterrupt均由main单独返回exit2/INTERRUPTED；包括“已在except Exception分支中调用_safe_code”的第二层中断。INTERNAL_ERROR/INTERRUPTED是main生成的终端码，不加入domain白名单。一般stdout.buffer获取/write/短写/flush失败仅在该I/O小边界转OUTPUT_ERROR；不包住loader/evaluator把跨类错误洗成输出错误。stderr尽力唯一`{"error":"CODE"}\n`，失败仍返回2。main不关闭/替换宿主流；模块失败入口沿现有描述符保护，避免退出期flush改成120。stdout可能已部分发送，不能把部分JSON当成功；包/源内容及mtime不能由产品写改。

## 测试与后续安装验收边界

单测使用有界人工声明值对象，在test setup调用既有raw builder/codec、真实人工prepare及prepared/result codec封印实际内部字节身份；setup的预处理拟合如实单列，估计器不运行。改label/roles/mask后重新封印全链，不偷改hardcoded hand_pair身份；source声明仍未认证。手算literal expected不调用产品confusion/qualifications当算术oracle。可用新测试helper，无新生产codec。

无test正例优先复用合法四段轴，在raw封印前一致地将末段role改为calibration并重封全链，保持非空train/cal；无需另建通用假轴框架。31分钟train+31分钟calibration、各local30合法的两段构造仅为可行备选，不强制。手写cal score0.0/threshold0.0可以保持合法零阈值边界；模型配置按实际合法训练人口填写。零normal/零attack/无positive/all unknown，以及unknown True/unscored None/非test报警均须覆盖；current/h30分母相同而预测可不同，不断言孰优。

W3磁盘集成仅在测试setup保存这些封印人工包，操作期调用新readonly CLI并核字节/成员/mtime；无CSV/prepare/model。安装验收必须等C批实际accepted且准确发布后，复用其两个保存结果及原输入，只读新core wheel/新target。独立stdlib从已保存轴/label/prediction手算counts/ratios/reasons，不重用新evaluator作oracle；保护包与源初始成员/bytes/hash/mtime并独立核物理退出与无模型/无源重开。无API/UI改动，不启动server或机械重复浏览器。

后续W0另冻有界安装命令/预算/脚本；只需core wheel（无API调用），所有未执行保持NOT_RUN。工程报告通过不能解除真实研究Gate，也不产生统计推断或跨网络泛化结论。


## 实际验证补记

两项源码独审针对运行前封存的九文件，均为PASS；完整Python4746通过、23跳过、1项既有警告、56子测试。新安装core-only七阶段物理退出符合预期，父进程0；双视图完整标签报告与两份独立手算预期一致，原29成员与325保护项含初始mtime保持。模型0及6次保存分数复核仅属四个受控业务进程；旧测试人工setup与完整回归模型活动另记。

以上实际执行已经独立规格和质量后验复核，并由主控实际接受。[验证记录](../research/2026-11-11-release-if-evaluation-verification.json)逐项保留监督器V1失败、诊断raw查询缺失与V2接受的范围。原设计和源代码字节在运行前已封存，后续文档事实更新不冒充原九文件同一hash。当前新Desktop及CI仍PENDING，研究Gate保持BLOCKED。
