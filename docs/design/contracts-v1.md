# 跨模块契约 v1

用途：W0 维护、W1/W2/W3 共用。日期：2026-10-21。版本：1.0。状态：合成契约，不代表 Data Gate 或研究验收通过。依据：[当前需求](../requirements/current-requirements.md)与[实施计划](../superpowers/plans/2026-10-21-parallel-development.md)。

权威类型为 `src/core/traffic_anomaly/contracts.py`；HTTP Schema 由 `tools/contracts/export_openapi.py` 生成 [OpenAPI](openapi-v1.yaml)。[合成样例](../../tests/fixtures/contracts-v1.json)与 Python/JSON Schema 双重校验。修改类型后须重新生成并验证，字段变化由 W0 同步各分支。

## 内存数据与接口

`MinuteBatch`：datetime64[ns] timestamps、float32(n,134) features、唯一且不含标签字段的 feature_names、bool(n) row_valid、int64(n) segment_ids。时间须已排序、无重复、无 NaT；真实时区先由 DatasetSchema 的来源证明，归一为 UTC 后转为无时区 numpy 值。无效行可含非有限值但必须标 row_valid=False。缺分钟不补零，断点与无效输入必须切段。此类型表示审计后记录，不接收未审计的乱序原始数据。

`LabelBatch`：独立 timestamps 及八个非负整数标签数组，键必须正好为 dos、scan11、scan44、botnet、blacklist、udpscan、sshscan、spam。模型只接收特征矩阵。`DatasetSchema` 保存数据版本、134 字段顺序、时间来源、源时区及标签名称；合成字段不得用于真实 Data Gate。

`HistoryBatch`：timestamps、current、residual、valid、invalid_reason，矩阵(n,134)。无效行保留时间位置，理由 warmup/gap/invalid_input；标签筛选由编排层单独处理，不塞进历史计算。`SplitBoundaries` 四段使用半开区间 [start,end)，顺序不重叠，实际时间必须由 Data Gate 登记。

W1 实现以下接口，W0 此轮只建立 Protocol 与类型，不提供空实现冒充完成：

```python
load_minutes(source: Path, schema: DatasetSchema) -> MinuteBatch
load_labels(source: Path, schema: DatasetSchema) -> LabelBatch
audit_dataset(source: Path, schema: DatasetSchema) -> AuditReport
split_minutes(batch: MinuteBatch, boundaries: SplitBoundaries) -> dict[str, MinuteBatch]
build_history(batch: MinuteBatch, window: int, epsilon: float) -> HistoryBatch
calibrate(scores: np.ndarray, quantile: float = 0.99) -> float
execute_run(config: RunConfig, workspace: Path) -> RunResult
```

`Detector.fit(x_train, x_val=None)`、`score(x)`、`save(directory)`、`load(directory)`；score 一维且越大越异常。输入134或268维由方法决定。模型加载须同时核对特征顺序、变换版本和方法；容差 rtol=1e-5、atol=1e-6，报警须一致。

模型包的`ModelMetadata.schema_version`固定1.0，未知版本解析时拒绝。`validate_model_compatibility(metadata, feature_names, preprocessing, config)`已实际实现：检查审计后字段顺序与模型、预处理完全相同，方法、输入宽度、预处理版本及配置版本一致，失败抛ValueError，不自动重排或重新拟合。W1后续加载时先按类型解析JSON、核对manifest摘要及产物完整性，调用该检查，再调用具体Detector.load；W0没有实现模型加载/执行流水线。

## 数值及配置

初版顺序：原始非负计数→log1p→StandardScaler（训练正常候选拟合）→按完整时间轴构造历史中位数/MAD偏离→当前通道与偏离通道拼接。残差 `(current-median)/(MAD+epsilon)`，保留符号；不额外裁剪或二次缩放。epsilon 默认 1e-6 仅供合成开发，真实数据检查数值范围与零 MAD 后固定；不得将默认值视为已验证。候选 H=15/30，每次运行必须记录 H，即使当前 AE/IF 也用同一 H 确定共同分钟。多窗口比较在所有窗口交集评价。

| 身份 | 项目 | 当前含义 |
|---|---|---|
| 报告约束 | 134/268维、连续中位数/MAD、独立99%校准、共同分钟 | 依V0.40保留，不由合成结果调整 |
| W0实现决定 | log1p→StandardScaler→历史、SQLite/Parquet、API状态与产物格式、linear分位数 | 用于共同实现；变更先记录兼容影响 |
| 待验证配置 | H候选15/30、epsilon=1e-6、seed=42、隐藏层[64,16]、epochs=10、batch_size=128、learning_rate=0.001、IF树数100/max_samples=256 | 均为开发默认或候选，不是最优或已验证设置；真实参数仅在参数验证段检查后固定 |

统一fixture使用H=1便于手工核对预热和分钟身份。样例中的分数为手工指定，未由模型预测；不能由这些数值反推真实参数或效果。

RunConfig 包含 schema_version、dataset_id、split_id、method、window_minutes、seed、preprocess 和 model；请求只含 dataset_id、split_id、method、config_id，后端从可信登记表解析完整配置。不接受网页的任意路径或任意模型参数。99% 校准分位数采用 linear，严格 `score > threshold`。

## HTTP 与分页

数据时刻和查询边界为 UTC 的 RFC3339 整分钟，后缀 Z；任务 created_at/started_at/finished_at 保留秒或小数秒，不把执行时刻截断成分钟，且遵守生命周期顺序。边界查询 start 包含、end 排除。page 从1起，page_size 默认100、最大1000；总数 total 基于该查询筛选后的全部记录。按 timestamp 升序稳定分页。无数据返回 items=[]、total=0。非法/颠倒范围返回422。未知 ID 为404；运行未完成的结果查询为409 RESULT_NOT_READY。

| 路由 | 成功 Schema |
|---|---|
| GET /api/v1/datasets | DatasetList |
| POST /api/v1/runs | 202 RunAccepted |
| GET /api/v1/runs/{run_id} | RunStatus |
| GET /api/v1/runs/{run_id}/series | SeriesPage |
| GET /api/v1/runs/{run_id}/alarms | SeriesPage，仅有效报警 |
| GET /api/v1/runs/{run_id}/evaluation | Evaluation |
| GET /api/v1/runs/{run_id}/minutes/{timestamp} | MinuteDetail |
| GET /api/v1/runs/{run_id}/exports/{kind} | scores: Parquet；metrics/config: JSON |

异常统一 ErrorResponse：`error.code/message/details`。包括 RUN_BUSY、WORKER_INTERRUPTED、NOT_FOUND、VALIDATION_ERROR、RESULT_NOT_READY、EXECUTION_FAILED。FastAPI 默认422需由 W2 转换到此结构。`queued→running→succeeded/failed`；排队登记失败也可 queued→failed。终态不可回退；单 worker 的 queued/running 均占活动名额，事务内检查并登记。运行中重启标 failed/WORKER_INTERRUPTED；此前已持久化 queued 可重新排队，但不得创建第二 worker。

OpenAPI内嵌请求、成功响应和404/409/422/500错误样例，均来自统一SYNTHETIC_ONLY fixture。W2异常处理只返回固定公共错误信息和经允许的字段说明，禁止把异常str/repr、内部堆栈、数据库连接串、绝对私人路径或凭据放进message/details；详细诊断留在本地日志。缺失ID返回NOT_FOUND，不回显内部文件位置。

SeriesPoint.valid=False 时 score/threshold/alarm 都为 null，invalid_reason 必填；有效时三值非空、分数有限、alarm 必须与严格阈值判断一致。flow_count 未核实为 null。曲线分页不能更改完整评价。标签在 Evaluation 与 MinuteDetail 中出现，绝不在模型输入中出现。

Evaluation 包含四个混淆计数、precision/recall/f1/fpr、正常与攻击覆盖分子/分母、排除攻击、误报与漏报片段及高负载结果。标签缺失时 available=False、reason 必填、metrics=null。无报警时指标仍独立计算；零分母为 null，undefined_reasons 必须恰好列出未定义指标名（precision/recall/f1/fpr）。F1 使用 2TP/(2TP+FP+FN)，各值与混淆计数一致；覆盖和排除计数也须相符。片段起止按 [start,end)，类型区分 false_positive/missed_attack。缺少高负载分组指标必须提供原因。

2026-10-30 示例澄清，沿用[原 W1 协议](../../experiments/PROTOCOL.md)：false_positive 将有效、正常且报警的连续分钟分组；missed_attack 表示对齐标签轴上连续的主要攻击片段，其内没有任何有效报警。后者可包含历史不足或其他未评分分钟，minute_count 是原攻击片段的分钟数，不是 FN 或有效攻击分母。全部未评分的片段也可能列出，此时不能宣称这些分钟已构成评价中的漏报。一段中有有效命中时不列入该列表，但其他有效未报警分钟仍逐点计入 FN，不作 point-adjust。

两个分组都在实际时间缺口或相应标签/有效性条件中断处断开；缺标签不能当正常。现有 helper 输出先 false_positive、后 missed_attack，各类内部按时间排列；示例据此对齐，不新增跨类别的全局时间排序保证。现有接口没有采集分段标识，不能识别相邻时间戳之间未编码的采集重置。类型和 Schema 版本保持 v1；本次只校正旧合成示例和解释，未改变算法。历史保存产物不自动重写，后端六项汇总核验仍不包含区间和高负载结果，见[核验范围](../guides/backend-evaluation-consistency.md)。

MinuteDetail 的 current、history_residual、reconstruction_error_current、reconstruction_error_history 分开；缺通道整体 null，存在则正好134维，与 feature_names 对齐。IF 的重构误差为 null。解释是线索，不等于攻击归因。

## 产物与实现决定

采用 SQLite 存任务元数据（本地单 worker、事务登记与重启恢复），Parquet 存完整逐分钟表（稳定类型和范围读取）；此为 W0 实现决定，V0.40 未冻结具体存储。SQLite/Parquet/权重留本地，不纳入公开提交。

每个运行目录包含 manifest.json、summary.json、scores.parquet、channels.parquet、metrics.json、config.json、model/metadata.json、model/preprocess.json 和实际模型载荷（例如 model/weights.bin）。有标签时额外保存 labels.parquet。RunResult 返回相对于 workspace 的 manifest_path/summary_path/scores_path，路径不得绝对或含 ..。manifest 含 schema_version、run_id、evidence_kind、config、代码提交号、数据/特征/切分版本、seed、依赖锁 SHA256、files 的规范相对路径/SHA256。清单要求包含上述必需文件与至少一个模型载荷，拒绝重复路径、./ 别名及 manifest 自引用；seed 须与 config.seed 一致。

持久化格式按以下类型冻结：

| 文件 | Schema 与列语义 |
|---|---|
| summary.json | RunSummary：run_id、evidence_kind、config、134 字段顺序、row_count/valid_count、elapsed_seconds、peak_memory_bytes、labels_available |
| scores.parquet | SeriesPoint 全部列，完整时间轴；timestamp 为 Arrow timestamp[ns,UTC]，score/threshold/flow_count 为 nullable float64，alarm nullable bool，valid bool，invalid_reason nullable UTF-8 |
| channels.parquet | ChannelRow：timestamp 与四个可空 list<float32> 通道；存在的通道必须134维。current 为原始计数；history_residual 为变换后的历史偏离；两组 reconstruction_error 为相应模型输入的逐字段平方误差。IF 两组重构通道都为 null；不能把无通道写为全零 |
| labels.parquet | LabelRow：timestamp 与八列非负 int64 标签；完整已审计标签轴。无法确定的标签分钟不造零标签；无标签文件时 summary.labels_available=False。评价在时间对齐后独立使用 |
| metrics.json | Evaluation，完整评价与覆盖分母 |
| config.json | RunConfig，完整已解析配置 |
| model/metadata.json | ModelMetadata：method、input_width、134 字段顺序、preprocess_version、threshold、parameter_count、payload 的路径与SHA256；增强维度为268，其余134 |
| model/preprocess.json | version=log1p-standard-v1、feature_names（134字段同序）、mean/scale（各134个有限值、scale严格正）、n_samples_seen（正整数）；StandardScaler零方差字段scale=1 |

Parquet 时间序列均升序无重复，转换为 JSON 时生成 RFC3339 整分钟 Z。scores 与 channels 时间轴及行数完全一致；labels 可缺时间行但不能冲突，缺标签分钟不进入评价。渠道文件的 feature_names 取 summary，模型的 feature_names 须一致。读取前核对文件摘要、config/summary/manifest/run_id/seed和模型维度；summary 有标签则清单必须含 labels.parquet。W1 的产物编排负责跨文件一致性与原子性，W2 从保存文件服务详情，不重算通道。

先临时写入，检查完整清单与摘要，再原子重命名完成目录，最后提交 succeeded 状态；半成品不可被成功接口读取。仅按 run_id 和导出 kind 查清单，不拼接任意路径。

## 2026-10-21 合成核心集成补充

execute_run(config, workspace, *, run_id=None) 和 score_run(config, workspace, model, *, run_id=None) 支持可选运行身份；原两参数执行口继续兼容。显式ID遵守Identifier、已有输出拒绝覆盖，省略时仍自动生成。该关键字属于执行上下文，不放入研究RunConfig，不修改HTTP/模型格式1.0。后端在worker调用前已分配ID；核心所有产物直接使用它。每任务workspace内保存runs/<run_id>/，RunResult路径相对workspace，manifest文件路径相对该run目录；不能混用两个相对根。

CoreRegistration启动时审计并快照可信小型合成输入、配置及登记ID，每任务输出根隔离。仅接收SYNTHETIC_ONLY，且仍经过registered_input；此适配不支持真实数据，也不能以调用者伪造AuditReport放行。前端、API和导出只读保存结果。研究数据Gate及四段真实时间边界保持原要求。

## Data Gate重审补充（字段版本不变）

现有Metrics的null及undefined_reasons继续表达无分母，不新增0分占位或私有枚举。provider-audit-v2是CLI聚合审计报告版本，不是HTTP/模型契约版本；其structure_trusted仅说明字段/计数/文件对齐，不证明UTC或整体Gate。作者train/test与project_splits四段严格区分；后者未冻结时status=NOT_DEFINED、计数null。审计细项见[公开聚合报告](../research/data-gate-2026-10-21-audit.json)。
