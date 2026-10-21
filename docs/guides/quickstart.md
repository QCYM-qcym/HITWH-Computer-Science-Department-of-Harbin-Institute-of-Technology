# 合成系统快速运行

日期：2026-10-21。状态：SYNTHETIC_ONLY。本指南运行人工生成数据，真实 Data Gate、真实模型训练和研究比较仍未通过或 NOT_RUN。操作在仓库根目录执行；Python 3.14、Node 24.18.x，Windows PowerShell。

## 安装与验证

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r src/backend/requirements-lock.txt --extra-index-url https://download.pytorch.org/whl/cpu
.venv\Scripts\python -m pip install --no-deps -e src/core -e src/backend
npm --prefix src/frontend ci
.venv\Scripts\python -m pytest tests/core tests/backend tests/integration -q
npm --prefix src/frontend run test -- --run
npm --prefix src/frontend run contracts:check
npm --prefix src/frontend run typecheck
npm --prefix src/frontend run build
```

后端锁包含本轮共同 CPU 依赖。每个 work 独立安装，不共用虚拟环境或 node_modules。合成联调不需要 GPU。

## 准备人工数据与运行 CLI

```powershell
.venv\Scripts\python -m traffic_anomaly.cli demo --workspace .runtime/w0-demo/input
.venv\Scripts\python -m traffic_anomaly.cli run --workspace .runtime/w0-demo/input --config configs/core/smoke.example.json --run-id cli-demo
.venv\Scripts\python -m traffic_anomaly.cli verify --run .runtime/w0-demo/input/runs/cli-demo
'{"database":".runtime/w0-demo/tasks.sqlite3","output":".runtime/w0-demo/output"}' | Set-Content .runtime/w0-demo/settings.json -Encoding utf8
```

demo 拒绝覆盖既有源文件；重跑用新的运行目录或新的 run_id，不删除已有产物。该数据共160分钟、134个人工字段，四段各40分钟，H=3、种子42、10棵树仅为技术检查配置。不能当作真实参数选择。

## 启动 HTTP 与网页

第一个终端：

```powershell
.venv\Scripts\python -m traffic_api.app --settings .runtime/w0-demo/settings.json --fixture tests/fixtures/contracts-v1.json --core-workspace .runtime/w0-demo/input --core-config configs/core/smoke.example.json --config-id smoke-v1 --port 8102
```

第二个终端：

```powershell
$env:VITE_API_MODE='http'
$env:TRAFFIC_API_TARGET='http://127.0.0.1:8102'
npm --prefix src/frontend run dev -- --port 5175
```

访问 `http://127.0.0.1:5175/`，确认 HTTP、synthetic-w1、SYNTHETIC_ONLY，选择数据→提交任务→完成→分析→漏报片段→实验对比→导出。默认界面仍保留 mock 开发模式；不设置 VITE_API_MODE 时只显示四分钟手工契约样例。若省略两个 core 参数，API 仍是旧的 FakeExecutor，不能称核心联调。core 两个参数必须成对提供，且仅允许人工数据登记。

HTTP 只提交 dataset_id/split_id/method/config_id；路径仅由本地命令行管理员配置。一个服务登记一个固定模型配置，请求的方法必须与它相符，否则422。AE联调可复制示例配置到忽略目录后明确改 method，再单独启动服务；不要与正在工作的服务共用数据库或端口。

API 接受的 run_id 从 SQLite、worker、核心执行、manifest、summary、metrics 一直用于页面和导出。CLI 可把同一 ID 传入独立输入工作区，用于逐文件复核；在同一输出根目录重复 ID 会被拒绝。合成测试自动验证三个方法的同 ID、完整评分表、阈值/报警、评价分母、通道和服务重启后的产物一致性。

## 运行边界与恢复

首版单 worker；活动任务返回409。退出服务不会在网页上伪装任务取消；异常终止后重启，遗留 running 变 failed/WORKER_INTERRUPTED，queued 可继续处理，succeeded 保留查询。失败后重提交产生新 ID，不覆盖失败记录。产物校验完成后才能 succeeded；缺失或损坏文件不能导出。

只导出完整 scores.parquet、metrics.json、config.json。筛选时间为 UTC 整分钟、[start,end)，分页和图表密度不改变完整评价。原始真实数据、环境、数据库、权重、缓存、输出和验收截图都留在忽略目录；网页不得传任意服务器路径。

本轮实际证据与限制见[合成集成记录](../project/W0-SYNTHETIC-INTEGRATION-2026-10-21.md)，数据阻塞见[来源核验](../research/2026-10-21-UGR16v3-provenance.md)。
