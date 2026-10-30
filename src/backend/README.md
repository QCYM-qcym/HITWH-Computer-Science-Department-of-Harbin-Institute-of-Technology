# W2-01 后端与任务管理

## 2026-10-30 保存区间一致性

[保存校验](../../docs/guides/backend-interval-consistency.md)现在同时核六项汇总和现有producer的完整intervals列表，复用一次纯evaluate，保留原字节。旧包仅次序不一致也会拒绝，不自动重写；这不是新增HTTP全局排序保证。新18/完整后端100及原核心8项通过，三个新FakeAPI场景通过。高负载语义仍未检查。

## 2026-10-30 合成详情写入修复

[FakeExecutor通道绑定](../../docs/guides/fake-channel-mapping.md)改为显式timestamp映射，所有详情验证并精确核对字段顺序；缺项null、显式预热current保留，重复拒绝。新13/完整后端82项通过，API/mock四响应一致。只影响新合成包，原数据/真实执行器及保存读取路径保持。

日期：2026-10-21。版本：0.1.0。状态：**SYNTHETIC_ONLY**。共同基点为 `codex/integration-mvp` 的 `74f163bf69559f02ad70ae1d5bb730e1f10d15bf`，开发分支为 `codex/backend-tasks`。仅实现 W2-01，不合并 main。

后端使用冻结的核心类型与统一 fixture：FastAPI 接收登记 ID，SQLite 事务及唯一索引限制一个 queued/running 任务，独立后台线程执行，文件锁限制同一数据库只有一个服务拥有 worker。请求不等待执行完成。状态只按 queued→running→succeeded/failed 转移，queued 登记后失败可直接 failed；终态不能回退。重启将旧 running 标为 failed/WORKER_INTERRUPTED，持久化 queued 继续处理。线程异常退出会记录失败；短暂存储错误会暂停接收并重试失败状态写入。持久性存储故障仍需要恢复存储或重启服务。

## 安装与运行

从本 worktree 根目录执行，Python 3.14，每个 worktree 独立环境。锁文件包含核心 CPU 锁的全部固定版本与后端新增依赖；不含 editable 路径。首次从完整锁安装，再安装两个本地包。

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r src/backend/requirements-lock.txt --extra-index-url https://download.pytorch.org/whl/cpu
.venv\Scripts\python -m pip install -e src/core -e src/backend --no-build-isolation
.venv\Scripts\python -m pip check
.venv\Scripts\python -m traffic_api.app --settings configs/backend/settings.example.json --fixture tests/fixtures/contracts-v1.json --port 8101
```

仅监听 127.0.0.1，单 Uvicorn worker。示例设置使用忽略的 `.runtime/w2/` 存数据库、运行目录与锁。启动命令从工作区根目录执行；自定义设置可保存到忽略的 `configs/backend/settings.local.json`，参数路径按启动目录解析。不要与 W0/W1/W3 共享可写数据库、输出目录或环境。端口占用时另选空闲端口。关闭服务会等待当前执行结束后释放锁；异常进程终止则在下一次启动时恢复任务状态，不继续半成品。

```powershell
$body = @{ dataset_id='synthetic-v1'; split_id='split-v1'; method='iforest'; config_id='smoke-v1' } | ConvertTo-Json
$task = Invoke-RestMethod http://127.0.0.1:8101/api/v1/runs -Method Post -ContentType application/json -Body $body
Invoke-RestMethod "http://127.0.0.1:8101/api/v1/runs/$($task.run_id)"
Invoke-RestMethod "http://127.0.0.1:8101/api/v1/runs/$($task.run_id)/series?page=1&page_size=2"
```

## 接口与产物

实现 datasets、提交/状态、series、alarms、evaluation、minutes/{timestamp}、exports/{kind}。分页从 1 开始，page_size 默认 100、最大 1000；按整分钟 UTC timestamp 升序，范围 [start,end)，total 为筛选后总记录数。空结果为空列表，预热分数保持 null。alarms 只返回有效报警。评价与详情通道直接读取保存文件；后端只对保存评价的六项汇总作一致性核验，不生成替代指标、历史偏离或模型分数，详见[核验范围](../../docs/guides/backend-evaluation-consistency.md)。scores 导出完整 Parquet，metrics/config 导出保存 JSON；导出忽略页面分页，kind 严格白名单，不接受服务器路径。

读取前核验清单全部摘要、文件类型、任务/配置/种子/模型一致性、完整分钟轴与行数。FakeExecutor 在临时目录写入并验证后重命名，再允许 succeeded。失败或半成品无法作为成功结果读取，成功后损坏的文件也拒绝服务。日志保留本地诊断；公共响应统一 error.code/message/details，禁止异常原文、堆栈或私人路径。

既有错误码保持：404 NOT_FOUND，409 RUN_BUSY/RESULT_NOT_READY，422 VALIDATION_ERROR，500 EXECUTION_FAILED。重启原因 WORKER_INTERRUPTED 存于任务错误。固定 details 标签区分 DATASET_UNAVAILABLE、MODEL_NOT_FOUND、RESULT_MISSING、ARTIFACT_INVALID、WORKER_UNAVAILABLE；标签来自代码内白名单，不能来自异常文本。

FakeExecutor 只复制统一 fixture 的手工分数、配置与评价，模型载荷是显式 SYNTHETIC_ONLY 的 JSON 占位，未训练任何模型。首版只接受 fixture 的 synthetic-v1/split-v1/iforest/smoke-v1 组合，H=1。其余方法需待注册与真实核心接入，不能生成假 AE 结果。manifest 的 code_commit 为本轮共同基点，用于合成开发身份；不作为真实实验溯源。

## 验证与交接

```powershell
.venv\Scripts\python -m pytest tests/backend tests/core/test_contracts.py -q
.venv\Scripts\python -m unittest discover -s tests/repository -p 'test_*.py'
.venv\Scripts\python tools/contracts/export_openapi.py --check
.venv\Scripts\python -X utf8 tools/repository/update_progress.py --check
.venv\Scripts\python -X utf8 tools/repository/check_repository.py --worktree --check-author
```

后端测试覆盖生命周期、8 个并发提交只接受 1 个、统一 404/409/422/500、执行失败、SystemExit、短暂数据库读写故障、终态不可回退、单服务所有权、分页和范围、保存评价/详情、完整导出、空结果/缺标签、清单损坏及半成品拒绝。进程级测试启动真实 localhost HTTP 服务，在 running 时终止进程，再启动确认失败与新任务成功；测试使用临时空闲端口及独立数据库。仅测试合成流程，不加载研究模型。

独立审查的两项重要问题已通过失败测试复现并修复：线程异常终止与缺失资源原因区分。Starlette 对 httpx TestClient 给出弃用警告，当前接口测试通过，未来依赖升级再处理。此前对冻结 OpenAPI 时间参数转义的怀疑，经 W0 与 W2 的字符码及匹配检查确认是展示误读，5 处正则均与 UtcMinute 一致，无需修改契约；已新增回归检查。公共契约文件保持基点内容。最终测试数与提交/远端状态以本轮交付回复为准。

以上W2-01记录保留原阶段范围。2026-10-30复核：原134/268维合成CLI/API集成已实现，当前远端合成系统工作流运行后端/核心/集成测试和前端检查；具体结果须核对本次提交的实际CI。六项保存评价汇总一致性修复的相关76项测试和独立审查通过，详见[实际证据](../../docs/research/2026-10-30-backend-evaluation-verification.json)。后端复用核心纯算术规则，不另写研究算法；返回原保存指标和导出字节。

W2-02真实路径、真实Data Gate、真实IF闭环、真实CLI/API数值等价、真实网页联调、研究指标及性能验收继续 **NOT_RUN**。原漏报片段fixture与核心函数有已登记差异，intervals/high_load不在本次六字段核验内；本次未改该语义或生产契约。


2026-10-30 后续澄清：[旧片段示例已按原 W1 规则对齐](../../docs/guides/episode-display.md)，本篇原六项汇总核验范围不变，仍不验证 intervals/high-load。原阶段差异记录保留；未自动修复历史保存包。
