# 开发环境与 W0 交接

用途：契约安装、检查与各工作区入口。日期：2026-10-21。状态：SYNTHETIC_ONLY；业务核心、API、页面及真实实验尚未实现。依据：[计划](../superpowers/plans/2026-10-21-parallel-development.md)、[契约](../design/contracts-v1.md)。

本轮实际验证 Windows、Python 3.14.0、Node v24.18.0。选用已有Python/Node版本，在独立环境实际安装锁定依赖并验证CPU运行，避免仅按版本号认定兼容。Python主版本暂限3.14；Node作为后续Vue工具链的已知基点，本轮没有验证网页构建。核心契约只依赖NumPy/Pydantic；导入不加载PyTorch/sklearn。CPU完整依赖见 `src/core/requirements-cpu-lock.txt`，不含个人路径及editable包。W1/W2共用此Python和核心类型版本；W2增加FastAPI时须检查整个环境的依赖并提交模块锁。W3沿用Node 24.18，建立package-lock并用npm ci验证。前后端具体依赖由各自任务验证后锁定，不将候选版本写成已兼容。

从仓库根目录在 PowerShell 执行，每个工作区使用自己的 .venv：

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r src/core/requirements-cpu-lock.txt --extra-index-url https://download.pytorch.org/whl/cpu
.venv\Scripts\python -m pip install -e src/core --no-build-isolation
.venv\Scripts\python -m pytest tests/core/test_contracts.py -q
.venv\Scripts\python tools/contracts/export_openapi.py --check
.venv\Scripts\python tools/environment/smoke_cpu.py
```

真实检查记录：契约初始 6 项因 core 包未实现而失败，随后实现通过；补充非法日期和秒级任务时间检查先失败、修复后 8 项通过；独立审查补充回归后合计 16 项通过。CPU 张量 8×134、134→8→134 网络、3 次 SGD：损失约 0.398760→0.397616→0.396524，模型 state_dict 保存重载输出完全一致；小型 IF 分数均有限，Parquet 的 null 和 bool 读写一致。均为环境检查，不能据此认定研究 AE/IF 已实现或性能已验证。最终检查数量以[W0 交付记录](../project/W0-01-HANDOFF.md)为准。

PyTorch实测2.14.1+cpu，cuda_available=False。另行执行nvidia-smi，GPU枚举及驱动信息查询成功；CPU包不会据此取得CUDA执行能力。CUDA版PyTorch安装、GPU前向/训练及驱动运行兼容验证仍NOT_RUN，不阻塞CPU工作。真实数据、模型实验和端到端联调NOT_RUN；检测CLI留给W1-03实现。

W0 独占 contracts.py、OpenAPI、需求及根级配置；W1 独占其余 core、核心测试和实验；本轮 W0 新建的 test_contracts.py 为契约测试，后续跨模块变更先提交 W0。W2/W3 直接采用 JSON 样例和 OpenAPI，不能自行改字段。公共 README/status 合并由 W0 按已验证事实整合。

共同基点为 Desktop 提交并经远端验证的 contract-v1 提交。未拿到确切提交号前可阅读样例和接口，不能各自建立不同版本契约。各 work 从同一基点建立分支/worktree；使用独立端口、SQLite、缓存及输出目录，真实数据目录只读共用。已有活动任务拒绝新任务。输入和输出路径保存在忽略的本地配置，网页只传登记 ID。

提交前运行 CONTRIBUTING 中的进度、链接、隐私和作者检查；所有 Commit/Push 由 GitHub Desktop 执行，未完成推送时明确标记未同步。合成检查不会升级 Data/Model/Experiment Gate。

## 并行工作区交接规则

本阶段只准备共同基点和启动提示，不创建或分派业务开发任务。现有其他worktree若早于最终基点，不能作为已完成共同契约同步的证据；保留其未提交修改，待该work的执行者核对后再安全同步。

| 角色 | 独占目录 | 公共文件例外与后续范围 |
|---|---|---|
| W0 | `docs/requirements/`、`docs/design/`、根级配置、`tests/integration/` | `contracts.py`、`test_contracts.py`、统一fixture/OpenAPI生成器仅W0维护；负责总文档和集成 |
| W1 | `src/core/`其余程序、`tests/core/`其余测试、`configs/core/`、`data/`、`experiments/` | 不修改W0契约文件，按W1-01→02→03→04依赖推进 |
| W2 | `src/backend/`、`tests/backend/`、`configs/backend/` | W2-01先假执行器；真实接入W2-02等待W1经Data Gate的IF闭环 |
| W3 | `src/frontend/` | W3-01先固定fixture/模拟API，真实联调等待W2接口和W1产物 |

每个work使用独立.venv或node_modules、端口、SQLite文件、缓存与输出根目录；不得让两个服务共享同一任务数据库。W2开发API建议8101，集成API建议8102，W3页面建议5173，集成页面建议5174，端口冲突时在忽略的本地配置登记调整。真实数据可从一个授权目录只读共享，运行产物按work/run_id隔离，不多人写同一缓存。

共同分支为 `codex/integration-mvp`。本轮交付会产生新的最终提交；以主控最终回复中经远端核对的完整40位SHA为准，不使用先前规划提交或本轮开始前的旧契约提交。各work创建工作区后先核对 `git rev-parse HEAD` 等于该SHA，分支应各自独立，不能三方同时操作同一checkout。私有AGENTS与隐私配置不会自动复制，执行者须读取项目入口并将私人配置留在忽略区。

契约变更先向W0说明消费者、字段、语义与兼容影响；W0修改类型、测试、样例和OpenAPI，运行检查后提交并发布新同步点。若改变字段含义、预处理或模型格式，先登记版本/迁移规则，不能保持旧版本静默改义。各work取得同步点后复跑本模块检查，再继续接入；不各自重命名接口字段。

W0串行合入：契约→数据/历史→IF闭环→API→页面→AE/增强与评价。每次合并运行受影响模块测试和已有集成测试，并检查CLI/API/保存结果的一致性，再将经验证的集成提交同步给仍在工作的分支。不得在其他work未提交时切换、重置其工作区。

各work按CONTRIBUTING维护本分支README/status并经Desktop提交推送。公共进度文件发生冲突时，由W0逐项核对任务、真实命令和证据，保留各自已验证进展，不简单选择ours/theirs；未经执行的研究阶段继续NOT_RUN。交付须附依赖SHA、改动文件、命令和结果、未执行项及风险。后续启动提示见主控最终交付；本说明不构成自动启动授权。

## 2026-10-21 W0合成集成现状（替代上文当时的业务NOT_RUN描述）

W1/W2/W3已按序通过Desktop合入codex/integration-mvp，实际入口见[快速运行](quickstart.md)与[联调记录](../project/W0-SYNTHETIC-INTEGRATION-2026-10-21.md)。本轮CPU人工数据完成共享核心、HTTP、网页与导出一致性，旧契约四分钟mock仍保留；真实W2-02和研究模型NOT_RUN。集成网页实用5175，避免占用已运行的5173；后端8102，使用TRAFFIC_API_TARGET选择代理目标。

tests/core与tests/backend使用包内相对辅助导入，可在同一次pytest中收集。共同CPU依赖采用后端requirements-lock（包含核心）；前端沿用package-lock与Node24.18.x。公共契约未改字段/含义，execute_run仅新增可选执行ID，变更说明见contracts-v1补充。主控最终提交与远端核对后作为下一共同起点；不在其他work未提交时替其更新checkout。
