# 候选合成结果的只读HTTP

日期：2026-10-31。状态：IMPLEMENTED_SYNTHETIC_ONLY。范围：SYNTHETIC_ONLY。依据[本批计划](../superpowers/plans/2026-10-31-candidate-readonly-http.md)。这是已有候选人工运行包的独立查看入口，原任务后端与Vue页面继续沿用原生产契约。

受信本地启动代码先使用[IF](candidate-run-verification.md)或[AE](candidate-ae-run-verification.md)的安全加载器和[输入快照](candidate-snapshots.md)完成保存关系核验，再把运行与输入快照配对交给 `traffic_api.candidate_app.create_candidate_app`。工厂接受长度1–4的list/tuple，每项是 `CandidateRegistration(run, inputs)`；全部配对通过才产生应用，运行ID直接来自原包，注册集合随后固定。类型检查不能把任意手写快照认证为原始来源，必须保留加载证据。

目录项固定为run_id、model_profile_id、method、history_window、selected_policy、minute_count、score_valid_count及source_replay。score_valid_count明确表示保存分数有效分钟数；来源分别保留run、inputs及取弱项的combined状态。IF的method为iforest、history_window为null，不将缺少源重放的证明升级为VERIFIED。

只在127.0.0.1启动，单worker、关闭reload，使用单独空闲端口；工厂本身不绑定端口。此应用不建立任务库或输出目录，不创建任务或模型。HTTP请求不接受服务器文件路径，也不提供上传、重新加载或文件下载接口；要更换包，应停止服务、重新核验并启动。

以下是受信本地Python启动示例，需要先按[开发说明](development.md)安装核心与后端依赖。路径仅为占位，必须换成已经核验的人工包；这段示例不会生成包。8113只是独立示例端口，使用前确认未占用，停止时使用Ctrl+C。

```python
from pathlib import Path
import uvicorn
from traffic_anomaly.candidate_artifacts import load_verified_candidate_artifacts
from traffic_anomaly.candidate_run_artifacts import load_verified_candidate_if_run
from traffic_api.candidate_app import CandidateRegistration, create_candidate_app

records = Path('.runtime/example-records')
inputs = Path('.runtime/example-inputs')
source = Path('tests/fixtures/g13u-records-v1.json')
run = load_verified_candidate_if_run(
    Path('.runtime/example-if-run'), records, inputs, source_fixture=source)
prepared = load_verified_candidate_artifacts(records, inputs, source_fixture=source)
app = create_candidate_app([CandidateRegistration(run, prepared)])
uvicorn.run(app, host='127.0.0.1', port=8113, workers=1, reload=False)
```

AE包换用 `load_verified_candidate_ae_run`，不能把IF读取失败当成自动换AE尝试的信号。需要多个运行时，显式增加已经核验且run_id不同的配对，最多四项。目录自身不重载模型。

| GET地址 | 参数与含义 |
|---|---|
| `/candidate/v1/runs` | 无参数；返回已登记运行的固定目录，不公开文件路径 |
| `/candidate/v1/runs/{run_id}/series` | 可选start/end/page/page_size；沿用半开时间范围、先过滤后分页，page从1开始，默认100条、最多1000条 |
| `/candidate/v1/runs/{run_id}/detail` | 必填timestamp；返回该分钟的当前输入、历史偏离、原分数与已有重构误差通道 |

时间继续使用没有时区的人工源钟面，不能加Z/偏移或将其解释为已认证UTC。完整语法与空值规则见[分钟详情](candidate-minute-details.md)及[曲线分页](candidate-series-pages.md)。页数与返回条数不是评价分母，FULL_STORED_RUN引用原evaluation身份和既有评价人口。无效分钟保留null和原因，历史H15/H30各自有效，不伪造逐特征重构误差。

所有路由拒绝未知或重复查询参数；页码只接受ASCII数字文本，并检查既有范围。成功体与[查看CLI](candidate-view-cli.md)使用相同查询值，紧凑UTF-8 JSON加单LF，含LF最多1MiB；完整序列化并检查后才输出。内容包含非有限值或不能序列化时不返回部分成功。

| 状态 | 固定错误code |
|---|---|
| 422 | INVALID_QUERY |
| 404 | RUN_NOT_FOUND、MINUTE_NOT_FOUND、NOT_FOUND |
| 405 | METHOD_NOT_ALLOWED |
| 500 | INTERNAL_ERROR、RESOURCE_LIMIT |

错误体仅为 `{"error":"CODE"}`，不回显查询值、路径或内部堆栈。自动OpenAPI、docs、redoc及斜杠重定向关闭，不加CORS，不挂入生产app。空页仍为200，缺失分钟为404；本接口没有任务提交状态。

启动加载会沿用保存的预处理、历史、阈值和评价关系验算；应用请求阶段只查询冻结快照，不重新加载文件、执行模型或重算评价。网络收发与服务器诊断日志不属于这里的“无文件读取”声明。该入口没有原生产worker生命周期，现有后端测试conftest的生产模块导入也不能冒充独立候选进程证据。

新增77项手写快照测试先失败后通过，相关270项通过（旧detail夹具含toy模型准备），仅既有TestClient弃用警告。独立审查修复目录history_window值域。主控实际完成13组HTTP/CLI原字节与保存值对照、16项安全错误和前后目录检查；39原文件身份/成员保持，服务正常停止回收。实际500注入未执行，其行为为单元测试证据；普通CLI进程与受控服务进程分开记录。[完整证据](../research/2026-10-31-candidate-readonly-http-verification.json)。此处的HTTP客户端验收不等于网页验收，不代表真实短片段或研究效果通过。主数据采用、最终Attempted政策、生产契约迁移、真实训练评分校准与正式实验保持未批准或NOT_RUN，Data Gate仍BLOCKED。
