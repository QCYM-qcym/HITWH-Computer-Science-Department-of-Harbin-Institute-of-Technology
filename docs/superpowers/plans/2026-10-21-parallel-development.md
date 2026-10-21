# 时间感知流量异常检测：并行开发实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement each assigned worktree task. Use superpowers:subagent-driven-development only when delegated execution is explicitly selected. 每个执行者只实施分配的任务；主控负责跨模块检查、契约变更与集成。

**Goal:** 交付可复跑的分钟流量检测、方法比较与本地网页回放系统，检验历史增强对误报、漏报及运行成本的影响。

**Architecture:** Python共享核心先完成命令行闭环，FastAPI和Vue页面通过固定契约接入。一个主控管理集成，三个独立worktree分别负责数据与检测、后端、前端。代码允许并行编写，真实数据与研究实验按依赖顺序运行。

**Tech Stack:** Python、PyTorch、scikit-learn、FastAPI、Vue 3、TypeScript、Pinia、ECharts。SQLite任务元数据和Parquet结果文件作为本计划的首版实现建议，须在W0-01中记录采用决定；它们不是V0.40已冻结的要求。依赖版本在环境验证后锁定。

**Spec:** [开题报告V0.40公开文本](../../reports/开题报告-V0.40-公开文本.md)，重点为§3、§4.1.1—4.1.7及§5；[提交规范](../../../CONTRIBUTING.md)、[仓库分区](../../project/REPOSITORY_LAYOUT.md)、[隐私规则](../../project/PRIVACY.md)。

日期：2026-10-21。版本：V1.0。状态：开发计划，待审阅；所有下述任务未执行。依据现有仓库，业务目录只有说明文件，没有可复用的业务程序、依赖锁或真实实验结果。用户已表达启动开发及并行work的意向；本轮交付计划，不将该意向登记为导师批准或任何研究Gate通过。

## Global Constraints

- 范围：本地单机、离线分钟检测与回放；首版一次运行一个真实检测任务。开发worktree并行不代表系统同时训练多个模型。
- 输入：UGR16v3提供方整理的134维分钟特征；自己完成数据适配与核验，不能把提供方特征提取列为个人成果。
- P0：隔离森林、当前134维AE、当前134维＋历史偏离134维的增强AE，以及统一评价和网页回放。USAD、特征删组及其他数据表示为条件允许时的补充；大语言模型不进入本轮范围。
- 四类主要攻击为dos、scan11、scan44、botnet；仅背景标签blacklist、udpscan、sshscan、spam的分钟不进入主要指标；攻击与背景重叠仍记攻击。八标签均零只表示正常候选。
- 保留提供方测试范围；原训练范围再按时间划分训练、参数验证、阈值校准三段，实际日期在Data Gate记录，不能照搬旧比例当作已确认日期。
- 缩放只拟合训练正常候选；训练和校准使用的当前分钟及所需历史都须为正常候选。各方法使用共同可用分钟；标签绝不进入模型特征。
- 历史只取当前时刻之前连续H分钟；先评分后更新。分段、缺口或无效输入均重置历史，历史不足不可评价。测试历史不得根据测试标签清除攻击。
- 当前AE以134维均方重构误差评分；增强AE对268维取均方误差，两组134维等权。历史偏离与重构误差分别展示。
- 每种方法分别用独立校准段共同正常分数的99%分位点定阈值；严格大于阈值才报警。测试不选窗口、不调阈值、不回调模型。
- 主要指标使用共同有效分钟，报告正常/攻击覆盖率和被排除攻击数量；一次命中不扩展为整段命中。
- 高负载阈值取训练正常候选的流记录数90%分位点；须先核实五类协议计数互斥且覆盖全部流记录，不能将134列相加。
- 新业务代码进入src，公开文档进入docs，参数进入configs；原始数据、权重和运行产物留本地。公开文件不含私人身份、绝对个人路径或凭据。
- 所有提交、推送使用GitHub Desktop，保留现有hook；每次提交更新status.json和README进度。维护工具测试、合成数据测试、真实实验分别登记，不互相替代。

## Review Focus

1. 乱序、重复、冲突、缺失及不明时区：不能静默覆盖或补零；由W1-01的数据审计测试负责。
2. 历史跨段、跨缺口或使用测试标签清洗：不能读取未来或拼接不连续正常行；由W1-02和W1-04负责。
3. 零MAD、非有限分数、空校准集：不得产出貌似正常的评分或NaN阈值；由W1-02、W1-03负责。
4. 后台崩溃、重复提交和服务重启：任务最终状态与失败原因可追查，不能永久运行中；由W2-01、W2-02负责。
5. 页面抽样、无报警及完全漏报片段：指标仍基于完整分钟，漏报能独立查找，CLI/API输出一致；由W3-01、W0-02负责。

## 先交付什么

第一个可运行版本使用隔离森林走通：短连续数据片段→预处理→训练→校准→逐分钟评分→保存与重载→导出。下一步让网页提交同样任务并查看同一份产物；随后加入当前AE与历史增强AE。

首版以可复跑、计算正确和结果一致为完成标准。方法效果由实验决定；减少误报但增加漏报必须一并报告，没有提升也保留结果。

## 并行组织与依赖

| 工作区/建议分支 | 独占范围 | 第一轮工作 | 依赖与交付 |
|---|---|---|---|
| W0 主控，`integration/mvp` | 契约、根级配置、总文档、集成测试 | W0-01，随后负责合并 | 先给出契约v1及合成样例，再放行W1/W2/W3 |
| W1 核心，`feat/core-pipeline` | `src/core/`（冻结契约除外）、`tests/core/`、`configs/core/`、`experiments/`、`data/` | W1-01/02/03 | 先合成测试与Data Gate，后真实模型；向W2交付CLI及产物 |
| W2 后端，`feat/backend-tasks` | `src/backend/`、`tests/backend/`、`configs/backend/` | W2-01 | 契约固定后用假执行器开发；真实接入等待W1最小闭环 |
| W3 前端，`feat/frontend-replay` | `src/frontend/` | W3-01 | 契约固定后用模拟接口；真实联调等待W2接口与W1产物 |

冻结契约包括`src/core/traffic_anomaly/contracts.py`、`docs/design/contracts-v1.md`、`docs/design/openapi-v1.yaml`和`tests/fixtures/contracts-v1.json`，仅W0修改。其他工作区提出变更申请，不各自重命名字段。

依赖顺序：W0-01 → W1-01/02/03；W0-01 → W2-01与W3-01。W1-01数据通过＋W1-03隔离森林真实闭环 → W2-02 → W0-02首轮联调。W1-02/03 → W1-04真实历史增强比较 → W0-03研究验收与交付。W2/W3可在W1开发期间完成模拟联调。

W0是协调角色，不要求另开持续运行的训练进程。首轮建议同时运行三个开发work；单机真实训练由W1串行调度，其他work只跑轻量单测和页面服务。

### worktree与合并规则

1. W0-01完成并通过检查后提交，记录该提交为`contract-v1`基点；各work从同一基点建立独立分支和worktree。若存在平台原生worktree入口，优先使用；目录与分支必须一一对应。
2. 每个work开始先核对分支、未提交改动和本任务范围；读取本计划、V0.40、CONTRIBUTING及隐私规则。本地AGENTS和私有配置可能不随worktree复制，约束由任务提示一并传递，禁止为方便将它们公开入库。
3. 每个work独立虚拟环境、端口、任务数据库和输出目录；建议API端口依次8101/8102、页面端口5173/5174，实际分配写入忽略的本地配置。输入数据可共用只读外部目录，预处理缓存和运行目录不能多人写。
4. 一个work只提交自己的业务与测试文件。每次Desktop提交仍须更新本分支的status.json/README；这些公共进度文件的合并冲突由W0按已验证事实整合，不简单选择某一侧。
5. 小步交付，每个可验收任务提交一次；Desktop负责Commit/Push，读取和测试命令可用CLI。不要在其他work尚未提交时切换或重置其分支。
6. W0串行集成：契约→数据/历史→IF闭环→API→页面→AE/增强与评价；每次合入都运行对应测试及已具备的集成测试，再把集成更新同步到尚在工作的分支。
7. 接口变更先由W0更新契约版本和样例，再同步各work；模型维度、特征顺序或预处理版本不匹配时拒绝加载。禁止靠改前端字段名掩盖后端Schema差异。
8. 每个交付附变更文件、验证命令与实际结果、未执行项、依赖提交和剩余风险。未拿到真实数据时标记`SYNTHETIC_ONLY`，不能写Data Gate通过。

## 文件与接口基线（由W0-01实际建立）

以下路径是未来任务的交付位置，当前尚不存在对应业务实现。

```text
src/core/pyproject.toml
src/core/traffic_anomaly/
  contracts.py      # W0维护的数据类型、配置与返回类型
  data/            # 读取、审计、时间切分、标签策略
  features/        # 训练拟合的变换、因果历史与有效行
  detectors/       # IF、AE和统一保存/加载
  evaluation/      # 校准、共同分钟、指标、片段
  pipeline.py      # 唯一的训练/评分/评价编排
  artifacts.py     # 原子写入、文件清单与摘要
  cli.py           # 命令行入口
src/backend/       # FastAPI、单worker、任务持久化
src/frontend/      # Vue页面、类型、API客户端和测试
configs/core/      # 可公开配置，不含真实数据绝对路径
tests/core/        # 计算、时间边界、泄漏、重载
tests/backend/     # API、状态、失败与恢复
tests/integration/ # CLI/API结果一致与最小流程
tests/fixtures/contracts-v1.json  # 小型手工合成样例
experiments/PROTOCOL.md
docs/design/contracts-v1.md
docs/design/openapi-v1.yaml
docs/requirements/current-requirements.md
docs/requirements/traceability.md
docs/guides/       # 实现后记录真实安装、运行和复现方式
```

核心接口由W0定义，W1实现；标签只在编排层筛选训练/校准样本及独立评价中使用：

```python
@dataclass(frozen=True)
class MinuteBatch:
    timestamps: np.ndarray       # datetime64[ns]，统一时间基准须有来源
    features: np.ndarray         # float32，形状(n, 134)，不含标签
    feature_names: tuple[str, ...]
    row_valid: np.ndarray        # bool(n,)
    segment_ids: np.ndarray     # int64(n,)，缺口或无效记录处分段

class Detector(Protocol):
    def fit(self, x_train: np.ndarray, x_val: np.ndarray | None = None) -> None: ...
    def score(self, x: np.ndarray) -> np.ndarray: ...  # 一维，越大越异常
    def save(self, directory: Path) -> None: ...
    @classmethod
    def load(cls, directory: Path) -> "Detector": ...

def build_history(batch: MinuteBatch, window: int, epsilon: float) -> HistoryBatch: ...
def calibrate(scores: np.ndarray, quantile: float = 0.99) -> float: ...
def execute_run(config: RunConfig, workspace: Path) -> RunResult: ...
```

`HistoryBatch`定义为`timestamps`、`current`、`residual`、`valid`、`invalid_reason`；两组矩阵为(n,134)，缺历史行保留原始位置并由valid标识。`RunConfig`至少含`schema_version`、`dataset_id`、`split_id`、`method`、`window_minutes`、`seed`及模型/预处理配置；`method`取`iforest/current_ae/history_ae`。`RunResult`含`run_id`、`manifest_path`、`summary_path`、`scores_path`。数据位置通过workspace和登记表解析，不由网页传入任意服务器路径。

W0-01需把上述类型补为可校验的完整定义，并确定预处理与历史计算的先后顺序；报告只限定训练拟合与因果边界，不能把旧稿细节当作已经冻结。建议先试训练拟合的log1p/缩放、15/30分钟窗口及轻量AE；epsilon、网络宽度、训练轮数等在验证段检查后记入配置，不能为赶接口而声称已验证。

HTTP契约v1：

| 接口 | 约定 |
|---|---|
| `GET /api/v1/datasets` | 已登记数据集、版本、时间范围、可用性；模拟与真实身份明确 |
| `POST /api/v1/runs` | 请求dataset_id、split_id、method、config_id；返回202、run_id、status |
| `GET /api/v1/runs/{run_id}` | 返回状态、时间、配置摘要、错误码及错误说明 |
| `GET /api/v1/runs/{run_id}/series` | 按范围、分页返回时间/score/threshold/alarm/valid/invalid_reason；非有限值使用null并标无效 |
| `GET /api/v1/runs/{run_id}/alarms` | 可分页报警记录 |
| `GET /api/v1/runs/{run_id}/evaluation` | 独立评价、覆盖率、误报及未报警攻击片段；标签缺失返回不可评价说明 |
| `GET /api/v1/runs/{run_id}/minutes/{timestamp}` | 当前特征、历史偏离、逐特征重构误差，通道分开 |
| `GET /api/v1/runs/{run_id}/exports/{kind}` | 白名单导出scores/metrics/config；导出完整分钟，不能导出任意服务器文件 |

任务状态固定`queued → running → succeeded/failed`。首版已有活动任务时新提交返回409 `RUN_BUSY`；不存在返回404；输入错误返回422。服务重启发现旧running任务时标记failed、错误码`WORKER_INTERRUPTED`，不盲目续写半成品。UI可重新提交新run_id。

产物`manifest.json`记录配置、提交号、数据/特征/切分版本、种子、依赖锁摘要和各产物校验值；`scores`保存原始完整分钟，`metrics.json`保存分组指标及分母，`model/`保存模型与预处理、阈值。先写临时文件，全部核对后标任务成功；成功状态不能早于文件完成。任务数据库/权重/Parquet与原始数据均不进入公开提交。

## 任务分解

### W0-01：需求对齐、契约与可运行环境基点

**Files:** 新建`docs/requirements/current-requirements.md`、`traceability.md`、`docs/design/contracts-v1.md`、`openapi-v1.yaml`、`src/core/traffic_anomaly/contracts.py`、`src/core/pyproject.toml`、`tests/fixtures/contracts-v1.json`、`tests/core/test_contracts.py`、`docs/guides/development.md`；根级配置由W0统一维护。

**Interfaces:** 消费V0.40；产出上文全部数据/HTTP类型、合成样例和各模块安装/测试约定。模型类型不得在导入契约时加载PyTorch或执行训练。

- [ ] 对齐旧17FR/8NFR与V0.40，逐项标保留、替代或延期；七项预期成果映射到本计划任务。登记已知开题反馈，未知反馈保持待登记，不阻断可逆环境与契约准备。
- [ ] 编写`test_feature_width_and_label_separation`：134维被接受，133/135维及夹带标签列被拒绝；`test_mock_sample_matches_api_schema`核对字段、枚举、null及错误结构。
- [ ] 运行`python -m pytest tests/core/test_contracts.py -q`，确认新测试先失败；再实现contracts和最小包配置，重复运行通过。
- [ ] 在开发说明确定Python/Node及依赖版本，先验证CPU的张量训练、保存和重载；GPU单独检查，失败仍可用CPU推进，不等待CUDA阻塞前后端。
- [ ] 冻结初版预处理顺序、配置字段、artifact格式及API；建立synthetic样例，明确其不能用于研究结论。选择SQLite/Parquet时在设计记录说明。
- [ ] Desktop提交契约基点，检查远端哈希；W1/W2/W3从该基点出发。此任务不升级Data/Model/Experiment Gate。

### W1-01：数据审计与时间切分

**Files:** 新建`src/core/traffic_anomaly/data/{reader,audit,splits,labels}.py`、`data/AUDIT_PLAN.md`、`tests/core/test_data_audit.py`、`test_splits.py`、`test_label_policy.py`、`configs/core/dataset.example.json`。

**Interfaces:** `load_minutes(source: Path, schema: DatasetSchema) -> MinuteBatch`；标签单独读为`LabelBatch`（时间戳及八个标签数组）；`audit_dataset(...) -> AuditReport`；`split_minutes(batch, boundaries) -> dict[str, MinuteBatch]`。完整签名在W0契约中补齐，不能在别处分裂实现。

- [ ] 先建人工可核对样例：乱序、同值重复、同分钟冲突、缺一分钟、NaN、八标签全零、仅背景标签、攻击与背景重叠。断言冲突被单列、缺口未补零、主要攻击身份正确。
- [ ] `python -m pytest tests/core/test_data_audit.py tests/core/test_splits.py tests/core/test_label_policy.py -q`先失败，再实现读取与审计，重复运行通过。
- [ ] 核对提供方版本、获取条件、校验值、CSV/MAT时间及标签对应；只获取当前审计需要的载荷，下载与运行写真实记录，不在各work重复下载。
- [ ] 固定作者测试范围和前段三分边界，核实时间基准；四段互不重叠，未知时区不静默设为本机时区。保留完整性、标签及排除计数。
- [ ] 形成Data Gate报告和样例哈希，满足数据检查后才放行真实训练。数据缺条件时交付适配器/失败报告，其他work继续合成联调。
- [ ] 由Desktop提交脚本与脱敏审计说明，原始记录和私人路径留本地。

### W1-02：训练预处理与因果历史

**Files:** 新建`src/core/traffic_anomaly/features/{preprocess,history,eligibility}.py`、`tests/core/test_preprocess.py`、`test_history.py`、`test_eligibility.py`。

**Interfaces:** 实现`build_history(...) -> HistoryBatch`；预处理提供`fit/transform/save/load`。共同训练/校准掩码由原始时间轴构造，不能先筛正常行再拼历史。

- [ ] 写手算测试：H=3，历史`[1,2,3]`的中位数2、MAD=1；当前5的残差为`3/(1+epsilon)`。改变未来值不改变此前输出，当前值不进入自己的历史。
- [ ] 写分段/缺口预热、零MAD有限值及训练段缩放参数不随验证/测试极值变化的测试；训练/校准窗口含非正常候选则整窗不可用，测试历史不读取标签。
- [ ] `python -m pytest tests/core/test_preprocess.py tests/core/test_history.py tests/core/test_eligibility.py -q`先失败；实现冻结顺序和数值规则后通过。
- [ ] 在真实短片段报告两通道数值范围、非有限数量、零MAD比例和可用分钟，验证epsilon后冻结。若需要裁剪或额外缩放，先登记契约/配置变更再实施。
- [ ] Desktop提交；历史单测通过只说明计算实现通过，不等于时间方法有效。

### W1-03：隔离森林与当前AE的命令行闭环

**Files:** 新建`src/core/traffic_anomaly/detectors/{iforest,autoencoder,registry}.py`、`evaluation/calibration.py`、`pipeline.py`、`artifacts.py`、`cli.py`、`tests/core/test_detectors.py`、`test_calibration.py`、`test_artifacts.py`、`configs/core/smoke.example.json`。

**Interfaces:** 实现Detector协议及`execute_run`；CLI约定`python -m traffic_anomaly.cli run --config <配置> --workspace <运行根目录>`，再提供`score --model <模型目录> --config <配置> --workspace <目录>`。所有入口调用同一pipeline。

- [ ] 写测试：IF分数方向统一为越大越异常；AE误差按输入维度平均；训练/校准均不消费测试标签；校准空集或非有限分数明确失败，分数等于阈值不报警。
- [ ] `python -m pytest tests/core/test_detectors.py tests/core/test_calibration.py tests/core/test_artifacts.py -q`先失败；先实现IF与产物编排，通过后加入当前AE。
- [ ] 保存/重载测试：相同输入和特征顺序，分数`rtol=1e-5, atol=1e-6`内一致且报警一致；不兼容维度、特征顺序和不完整模型包必须拒绝。
- [ ] Data Gate通过后用冻结的真实短片段运行IF闭环；写明取样范围，短片段结果仅为技术验证。随后对当前AE验证CPU训练和重载，依赖及设备写manifest。
- [ ] 验收后将CLI、产物样例结构与测试结果交给W2；真实产物不进Git。Desktop提交和远端核对。

### W2-01：任务API与持久化（可以先并行）

**Files:** 新建`src/backend/pyproject.toml`、`src/backend/traffic_api/{app,schemas,repository,service,worker}.py`、`tests/backend/test_runs.py`、`test_recovery.py`、`configs/backend/settings.example.json`。

**Interfaces:** 实现全部HTTP契约；`RunExecutor.execute(config: RunConfig, workspace: Path) -> RunResult`作为可替换执行口，测试用FakeExecutor，真实接入调用W1共享核心。

- [ ] 写POST返回202、非法配置422、未知ID 404、活动任务冲突409、executor抛错后failed与错误保留的测试；请求进程不阻塞在训练中。
- [ ] `python -m pytest tests/backend/test_runs.py tests/backend/test_recovery.py -q`先失败，再实现单worker与持久化，通过后检查服务重启将遗留running标成failed。
- [ ] 实现分页/范围查询及白名单导出；错误不能携带私人路径或堆栈到公共响应。数据缺失、模型不存在及未完成任务访问结果返回可区分的错误。
- [ ] 用合成artifact完成API契约测试，清楚标记fake执行结果。Desktop提交后交给W3模拟联调。

### W3-01：页面与模拟接口（可以先并行）

**Files:** 新建`src/frontend/package.json`、依赖锁、`src/{api,types,stores,views,components}/`及`src/__tests__/replay.test.ts`、`runs.test.ts`、`contract.test.ts`。

**Interfaces:** 只通过openapi-v1客户端访问W2，页面状态与任务枚举一致；同一合成JSON用于API和页面测试。

- [ ] 写任务提交、状态轮询停止、失败提示、空结果、无报警及未报警攻击分钟可查的测试；取消页面订阅只停止轮询，不伪造后台取消成功。
- [ ] 建立Vue/TypeScript及测试配置后，`npm --prefix src/frontend run test -- --run`先失败；完成数据查看、任务、异常分析和实验对比页面后通过。
- [ ] 曲线用时间戳对齐，两种解释通道分开展示。标签与评价是事后核查；模拟数据始终显式标记，不能混入实际结果。
- [ ] 图形抽样只用于显示，主要指标来自完整分钟；null与历史不足显示缺口，不能画成0分。报警列表之外可按时间/评价记录查漏报片段。
- [ ] `npm --prefix src/frontend run typecheck`与`npm --prefix src/frontend run build`通过，检查桌面宽度、长标签及无结果状态。提交页面与测试，记录模拟联调状态。

### W2-02：接入真实核心与结果查询

**Files:** 修改`src/backend/traffic_api/worker.py`、`service.py`；新建`tests/backend/test_real_executor.py`及`docs/guides/api.md`。

**Interfaces:** 直接适配W1的execute_run和manifest；不另写归一化、模型评分或阈值计算。

- [ ] `test_real_executor_matches_cli_artifacts`使用同一冻结输入/配置检查逐分钟时间、有效掩码、分数、报警、指标分母；`test_partial_output_is_not_success`检查半成品。
- [ ] `python -m pytest tests/backend/test_real_executor.py -q`先失败；接入共享核心与原子产物读取，再运行通过。
- [ ] 真实短片段完成一次提交、查询、失败重提与导出；服务重启后已成功结果仍可查询，异常停止保留失败原因。
- [ ] Desktop提交，W3改用真实接口并保留模拟开发入口。

### W0-02：首个端到端演示与回归

**Files:** 新建`tests/integration/test_cli_api_equivalence.py`、`test_task_lifecycle.py`、`docs/guides/quickstart.md`；仅在代码实际存在后写可执行安装和启动命令。

**Interfaces:** 消费W1产物、W2接口、W3页面，输出可复跑IF单机演示及已知问题清单。

- [ ] 先写同一输入在CLI/API分数与报警一致的测试，再修联调缺陷；`python -m pytest tests/integration -q`通过。
- [ ] 人工走通选择数据→提交→完成→曲线→报警/漏报片段→导出；检查空文件、错误时间范围、字段缺失和后台失败。
- [ ] 重启后重查已完成任务，核对页面与导出数量；登记运行耗时和内存，不设没有实测依据的性能达标数字。
- [ ] Desktop合并与推送，记录程序版本。此时只证明最小系统可运行，AE与正式研究效果可继续开发。

### W1-04：历史增强、统一评价与研究实验

**Files:** 扩展`detectors/autoencoder.py`；新建`evaluation/{metrics,coverage,episodes}.py`、`tests/core/test_evaluation.py`、`test_experiment_protocol.py`、`experiments/PROTOCOL.md`、`configs/core/comparison.example.json`。

**Interfaces:** 当前AE和增强AE复用同一网络实现、不同输入维度；评价层消费独立LabelBatch与原始ScoreFrame，产出metrics和片段索引。

- [ ] 写混淆矩阵手算、无正样本、完全漏报片段、背景排除及攻击背景重叠的测试；无分母指标写null及原因，不能伪造为0。
- [ ] 写共同有效分钟交集、被排除攻击计数、分组分母、原始逐点预测保留的测试；高负载总数口径未核验时相应指标不可用。
- [ ] `python -m pytest tests/core/test_evaluation.py tests/core/test_experiment_protocol.py -q`先失败，再实现评价与历史增强，通过后固定实验协议。
- [ ] 在验证段比较预设窗口15/30分钟及数值设置，配置在测试前锁定；同隐藏宽度并补参数数量接近的当前AE，记录实际参数量。随机种子首轮建议42/2024/3407，各次完整保存，建议值标明本计划新增。
- [ ] Data/Model/Temporal技术检查满足后，运行独立测试比较；报告总体与高负载误报、四类攻击召回、持续攻击片段及成本，不只选最优结果。多窗口使用共同有效分钟，逐项报告覆盖与排除。
- [ ] 特征删组、USAD或其他表示比较须在主要比较完成后再排期；发生方法范围变化先登记，不由某个work独自扩大工作量。
- [ ] 实验索引记录数据/配置/代码版本、种子、原始评分及失败；Desktop仅提交脱敏配置、协议和结果摘要。

### W0-03：验收、部署复现与论文材料

**Files:** 新建`docs/guides/reproduce.md`、`delivery.md`、`docs/reports/experiment-summary.md`；更新需求追踪、风险与状态源。

**Interfaces:** 消费各模块运行证据，输出程序/实验/文档分别编号的交付清单及限制说明。

- [ ] 从独立干净环境按依赖锁恢复；运行核心/后端/集成测试及前端test/typecheck/build，执行一条可重载演示。
- [ ] 验收报告§5.2七项：导入与划分(W1-01/02)、检测(W1-03)、历史(W1-02/04)、后端(W2)、网页(W3)、评价(W1-04)、比较导出与结论(W1-04/W0-02/03)。
- [ ] 论文每个数字对应manifest和评分，明确失败、无提升及未执行实验；逐项关闭或接受已知缺陷，不把开题资料视为毕业论文完成。
- [ ] 检查公开/本地交付边界；Desktop提交推送、核对远端与CI后登记实际结果。最终答辩日期未提供，保留学校任务结束2027-05-31作为已知节点。

## 时间安排与近期启动顺序

开题报告原计划为：10月需求设计、11月数据、12月基线、1月历史模型、2月实验、3月后端、4月前端联调、5月论文与交付。并行计划提前后端和前端的模拟开发，真实接入仍等待检测闭环。报告原日期保留，不因本计划改写原稿或认定已获评审。

| 阶段 | 启动条件 | 交付与建议节奏 |
|---|---|---|
| 契约与环境 | 现在 | 先W0-01；预计1—3个有效工作日，实际依投入调整 |
| 第一波并行 | 契约提交完成 | W1数据/历史与IF；W2假执行器API；W3模拟页面。先争取两周内各有可审查交付 |
| 最小真实闭环 | Data Gate和IF通过 | W2-02＋W0-02，核对同一短片段的CLI/API/页面 |
| 研究主线 | 当前AE与历史实现通过 | W1-04，按原11月至次年2月研究节点滚动推进 |
| 完整系统与交付 | 研究与API有真实证据 | 对齐原3—5月安排，完成恢复、论文和答辩 |

**2026-10-21至2026-11-03为首个滚动窗口，以下是目标而非完成承诺：**

- [ ] 第1—3个有效工作日：W0-01完成当前范围/契约、包入口、合成样例和CPU验证，记录基点。
- [ ] 契约完成后：三个work同时开工。W1交付真实数据审计或明确失败原因，W2交付任务生命周期，W3交付模拟数据页面。
- [ ] 窗口末：主控检查Data Gate是否满足、IF闭环是否具备；满足则首次真实联调，不满足则继续模拟联调并集中解除数据阻塞。

每周只根据真实证据更新下一两周任务。每周投入、开题反馈、真实数据体量和GPU兼容尚待登记；它们影响节奏，不把已知任务重复退回“是否允许开发”的询问。

## 可直接分发给各work的提示

### W0 主控

> 依据docs/superpowers/plans/2026-10-21-parallel-development.md和开题报告V0.40执行W0-01。先核对仓库与未提交修改，读取CONTRIBUTING及docs/project/PRIVACY.md。完成需求对齐、契约v1、合成样例、核心包入口和CPU最小验证，记录独立worktree共同基点。仅主控修改跨模块契约与根级配置。提交推送必须使用GitHub Desktop并更新状态与README；不能用CLI/API替代。合成测试不计真实研究结果，不改旧报告。

### W1 数据与检测核心

> 从主控给定的contract-v1提交建立独立worktree，读取上述计划、V0.40及CONTRIBUTING，按W1-01→W1-02→W1-03→W1-04推进。独占src/core（contracts.py除外）、tests/core、configs/core、data和experiments。先实现手算/合成边界测试，再审计真实数据；Data Gate通过后运行IF短片段闭环，随后AE与历史增强。首版不做USAD或大模型。保持标签隔离、四段时间边界和共同有效分钟；契约变更先交主控。每次交付写真实验证与未执行项，Desktop提交推送并维护本分支进度。

### W2 后端

> 从同一contract-v1提交建立独立worktree，读取计划、V0.40及CONTRIBUTING，只执行W2-01/02。独占src/backend、tests/backend、configs/backend，按冻结API实现单worker任务状态、持久化、查询和导出。先用FakeExecutor，等待W1产物再调用execute_run，不复制算法或改契约。检查后台失败及重启恢复，模拟结果显式标记。使用本work独立端口、数据库和运行目录；Desktop提交推送并维护本分支进度。

### W3 前端

> 从同一contract-v1提交建立独立worktree，读取计划、V0.40及CONTRIBUTING，只执行W3-01及主控安排的联调。独占src/frontend，基于固定Schema与合成样例实现数据、任务、分析、比较页面，先模拟后接真实API。覆盖失败、无结果、预热缺口及完全漏报片段；页面不重算实验指标，不将模拟数值当真实结果。禁止单独更改后端字段与状态。交付test/typecheck/build结果、页面核查及未执行项；Desktop提交推送并维护本分支进度。

## 本计划自查

- V0.40七项预期成果均有任务和验收位置；四类攻击、背景标签、高负载口径及历史边界未沿用旧稿错误。
- USAD为补充身份；大模型未纳入；未用V0.36均值差值替换现行中位数/MAD。
- 先契约后并发，数据与真实训练串行依赖明确；每个work有独占目录，共享进度冲突由主控处理。
- 文件、类型、方法名和API字段统一；建议配置与报告要求分开。后续任务以实际生成的契约完整类型为准。
- 文档计划、合成技术检查、真实研究与原型验收分别记录；本文件不构成任何业务或研究测试的通过证据。
