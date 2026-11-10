# Release IF 保存结果包 v1

日期：2026-11-10；状态补记：2026-11-11。源码实现与独立复核完成；已观察的人工安装、保存及独立重载功能经单独运行后核对接受，原控制器整轮FAIL/退出1保持。详见[运行指南](../guides/release-if-result-package.md)与[验证及失败保留记录](../research/2026-11-11-release-if-results-verification.json)。沿用[已接受IF内存接口](release-iforest-engineering-v1.md)、[保存输入](release-input-package-v1.md)与[配对接口](release-model-input-pair-v1.md)。本次只补状态与证据链接，不改变下述契约，也不升级真实研究准入。

## 目的、取舍与范围

将已计算的单个current13或h30_26结果保存为可移动、可独立读取的有限JSON包，为离线只读展示提供分数、阈值、人口和源钟面分区。保存的是结果，不是可继续评分的sklearn模型；不使用pickle/joblib或权重文件。

考虑过：仅保存现有result而无轴（最小但不能定位源分钟）；强制每次打开结果都提供raw/prepared（可重核外部字节但不独立）；保存时显式绑定pair，仅将有限segments写入自包含结果包（采用）。segments已能展开完整时间轴，无需重复存10000个时间串或标签/输入矩阵。此取舍由主控依据用户自主工程授权作出，不登记为用户已确认最终研究协议。

S2/Data Gate BLOCKED、真实C17训练/评分/Q99/正式实验NOT_RUN、来源NOT_AUTHENTICATED、源钟面完成代理、AUDIT_ONLY及生产134/268未迁移边界保持。包不能认证真实/人工数据来源、作者、模型执行或研究效果；本批实际验收仅用已知人工输入。

## 公共类型和接口

新增 `traffic_anomaly.release_if_result_contract`（纯对象、codec、校验）与 `traffic_anomaly.release_if_result_package`（固定文件I/O）。旧IF module不改。

- `ReleaseIFResultPackageError(ValueError)`：安全code，str(error)==code，不带原异常/路径/数据。
- frozen/slots `ReleaseIFResultIdentity(profile_id, context_sha256, manifest_sha256, manifest_byte_count)`，字段及类型与既有四字段identity模式相同，但精确class与profile独立。
- frozen/slots `ReleaseIFResultContext`，字段恰下节Context；segments为既有ReleaseSegment的tuple，model_configuration为既有ReleaseIFConfiguration，raw/prepared引用分别为既有精确identity class。
- frozen/slots `ReleaseIFResultLoadReport(profile_id, scope, byte_integrity, structure, saved_score_q99, source_authentication, model_execution)`。值恰新包P、`SAVED_RESULT_INTERNAL_CONSISTENCY_ONLY`、`MATCHED`、`MATCHED`、`MATCHED`、`NOT_AUTHENTICATED`、`NOT_AUTHENTICATED`。
- frozen/slots `ReleaseIFResultPackage(identity, context, result, load_report)`；result为现有ReleaseIFResult。
- `make_release_if_result_package(pair: ReleaseModelInputPair, result: ReleaseIFResult) -> ReleaseIFResultPackage`。
- `encode_release_if_result_package(package: ReleaseIFResultPackage) -> tuple[tuple[str, bytes], ...]`，按写序返回三个成员。
- `decode_release_if_result_package(members: dict[str, bytes]) -> ReleaseIFResultPackage`。
- `save_release_if_result_package(package: ReleaseIFResultPackage, output_directory: Path) -> ReleaseIFResultIdentity`。
- `load_release_if_result_package(directory: Path) -> ReleaseIFResultPackage`。
- `verify_release_if_result_pair(package: ReleaseIFResultPackage, pair: ReleaseModelInputPair) -> None`，不匹配抛错；返回None不认证外部原包字节或模型执行。

常量：P=`c17-release-iforest-result-package-v1`；R=`c17-release-iforest-engineering-v1`；SOURCE=`c17-release-91-v1`。公开`PACKAGE_MEMBER_NAMES`/`PACKAGE_MEMBER_BYTE_LIMITS`/`PACKAGE_TOTAL_BYTE_LIMIT`。

## Context及唯一字节格式

Context恰16字段，内存/JSON名称相同：

`profile_id:P, result_profile_id:R, view:current13|h30_26, source_schema_id:SOURCE, source_authentication:NOT_AUTHENTICATED, time_basis:SOURCE_WALL_CLOCK_COMPLETION_PROXY, policy_status:AUDIT_ONLY, audit_fit_policy:P_U|P_B|P_A, raw_identity, prepared_identity, configuration_sha256, model_configuration, segments, minute_count, score_direction:NEGATIVE_SCORE_SAMPLES, calibration`。

calibration在内存/JSON均为固定语义而非可变任意dict：内存精确使用frozen/slots `ReleaseIFCalibration(quantile:float, method:str, comparison:str)`，恰0.99/linear/STRICT_GREATER。model_configuration为既有8字段，input_width为13/26，n_estimators16、max_samples=min(32,训练人数)、max_features1.0、bootstrapFalse、contamination auto、random_state42、n_jobs1。configuration_sha256仍是准备配置摘要，不改称IF模型配置摘要；IF配置由新context digest绑定。

raw/prepared identity恰profile_id/context_sha256/manifest_sha256/manifest_byte_count四字段，分别固定既有raw/prepared profile，hash小写hex64，byte_count精确int 1..65536，bool拒绝。segments内存使用既有ReleaseSegment(id,role,start,end)，不新增ordinal字段；JSON每项恰ordinal/id/role/start/end，ordinal从0连续。id沿上游为1..128个Unicode码点，逐字符ord>=32且不等127并拒surrogate，互不相同，role为train/validation/calibration/test且按该角色顺序非递减。start/end为规范无时区源钟面`YYYY-MM-DDTHH:MM:00`，真实datetime合法、start<end、左闭右开整分钟，段按时间有序且不重叠，最多7段。允许同role多段和段间空隙；所有段分钟之和N须1..10000，minute_count恰N。展开轴不填段间空隙。

固定三文件、顺序如下：

1. `result.json`：恰schema_version=1、profile_id=P、context_sha256、scores、predictions、scored_mask、threshold、train_indices、calibration_indices、preprocessing_fit_indices。除前三项外直接保存现有result对应七项，JSON数组映射精确tuple。其余ReleaseIFResult字段从context重建。
2. `manifest.json`：恰schema_version=1、profile_id=P、context_sha256、context、members。members恰result.json一键，ref恰byte_count精确正int与sha256小写hex64。
3. `COMPLETE.json`：恰schema_version=1、profile_id=P、status=COMPLETE、manifest(ref)，绑定实际manifest字节。

写序result→manifest→COMPLETE，读序COMPLETE→manifest→result。所有JSON精确字段/类型；禁止NaN/Infinity、重复键、BOM、未知键、非规范编码。C(x)=UTF8、ensure_ascii=False、sort_keys=True、separators=(',',':')、allow_nan=False、末尾一LF。解析后C(parsed)必须逐字节等于原输入；整数字符最多8、float token最多32，拒绝递归过深、非法UTF8及布尔数值替代。文件体parse/encode前做成员与累计预算，canonical编码按chunk累计，不能先构造无界字符串再查。

预算（含LF）：result1,048,576字节、manifest65,536、COMPLETE4,096，合计硬限1,118,208；Context规范编码另限16,384。限制是应用级有限读取/编码，不声称OS内存/磁盘配额或连续峰值监控。

context_sha256=SHA256(C(Context))，result/manifest同值。manifest成员ref精确绑定本次读入result bytes；COMPLETE精确绑定manifest bytes。新identity取P、context hash、实际manifest hash及长度；无自引用循环。encode须验证对象声明identity/load_report与重新派生值一致；make先用私有编码逻辑生成真实identity再返回，不以placeholder绕过核验。

## 内部关系和绑定边界

所有现有IF result的精确类型、有限值、固定配置、None/mask/严格>、三索引递增非空/长度<=N/范围/互斥/子集关系均保持。preprocessing_fit_indices可含未评分分钟，不能错误要求其全在scored中。额外核train与preprocessing-fit角色均train，calibration角色calibration，N恰展开轴长。每个segment前30分钟不得scored，也不得进入preprocessing_fit_indices；前者是H30共同资格、后者是固定fit_window30的必要时间下界。其余真值仍不能认证实际输入或正常资格；offset>=30但未scored的preprocessing-fit仍合法。

保存/独立加载均用现有锁定NumPy/共享calibrate的固定0.99 linear算法复核保存calibration分数的Q99，要求有限且与保存threshold精确float相等。不是重新拟合模型或选择阈值；不改旧summary仅做结构检查的契约。数值溢出安全拒绝，single-cal、全同分、等阈值False均合法。

make先校验result并用私有encoder派生包identity，显式verify先对package做完整codec内部校验；二者对pair可复用现有IF `_validated_inputs` 的纯验证，不能fit、score、prepare或重估预处理。然后精确核result与pair的raw/prepared声明identity、configuration_sha256、view长度、common逐位mask、三索引及context全部源字段/segments/audit政策。此时只证明与显式pair一致，不能声称重读或认证外部原包字节。pair验证产生的有限float32矩阵不交给模型，最大10000×26。

独立load没有标签或原矩阵，不能证明common真实、31分钟正常资格真实、分数由IF产生、输入数值推导正确或源认证。自洽改写分数/Q99及hash后可成为另一个合法包；不可把这些边界当成应拒绝的伪造检测承诺。需要外部包字节核对时调用者自行用既有load/pair再显式verify，不隐式重放。

## 文件I/O与失败

沿既有prepared/raw包的有限存取规则：绝对本地路径、拒相对/..、NUL、UNC、Windows保留名/ADS、symlink/reparse/非普通文件/硬链接、父目录异常；恰三个成员，无子目录和额外文件。先lstat预算、open/fstat同对象、有限read(limit+1)、读后及最终目录/成员签名重核；decode只读已取得bytes，不另读原包或模型。它检测可观测变化，不是OS原子快照。

save在创建目录前完成全部encode/语义/预算验证；只exclusive mkdir且父目录存在，成员xb，写入数/flush/读回及身份核对，COMPLETE最后写。不覆盖、删除、修复或重试已有目录；失败残留保留，可能已有独立可加载包，不能许诺事务原子性或掉电持久性。不fsync或使用原子rename而声称新保证。

错误码恰：INVALID_PACKAGE_ARGUMENTS、INVALID_PACKAGE、INCOMPATIBLE_PACKAGE、RESOURCE_LIMIT、INTEGRITY_MISMATCH、INCONSISTENT_PACKAGE、INVALID_PACKAGE_PATH、INPUT_UNAVAILABLE、OUTPUT_EXISTS、PACKAGE_CHANGED、OUTPUT_ERROR、INPUT_BINDING_MISMATCH。未知版本/profile→INCOMPATIBLE；字段/类型→INVALID；合法类型关系/Q99/角色矛盾→INCONSISTENT；digest/声明identity错误→INTEGRITY；与合法pair不符→INPUT_BINDING_MISMATCH。pair结构不合法映射INVALID_PACKAGE；上限优先RESOURCE_LIMIT。未知底层read/write错误分别INPUT_UNAVAILABLE/OUTPUT_ERROR，不泄露异常消息；不吞KeyboardInterrupt等BaseException。

## 必要验收

独立手写结果与分数反例，不重跑模型造期望。覆盖：0./1./2./3.校准的显示近似为2.97，精确binary64阈值为2.9699999999999998；字面量2.97（相邻ULP）或2.969虽预测可相同仍拒；无效None/0/false区分；preprocessing-fit含非scored合法；超长索引先拒；错role、完整改写mask不能冒认pair绑定；换合法hash但自洽包内部可接受而显式binding拒；N10000真实codec往返、7段和最坏字段字节、限额+1；重复键/UTF8/BOM/规范float/未知profile；I/O换文件/目录、硬链、短写、读异常、COMPLETE后失败残留、输入/目标不变。源码测试与安装后save/load/独立新进程核验分列，后者获有界运行放行才执行。
