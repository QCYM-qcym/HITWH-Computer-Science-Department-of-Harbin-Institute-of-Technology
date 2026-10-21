# 开发环境与 W0 交接

用途：契约安装、检查与各工作区入口。日期：2026-10-21。状态：SYNTHETIC_ONLY；业务核心、API、页面及真实实验尚未实现。依据：[计划](../superpowers/plans/2026-10-21-parallel-development.md)、[契约](../design/contracts-v1.md)。

本轮实际验证 Windows、Python 3.14.0、Node v24.18.0。Python 主版本暂限 3.14，核心契约只依赖 NumPy/Pydantic；导入不加载 PyTorch/sklearn。CPU 依赖完整版本见 `src/core/requirements-cpu-lock.txt`，不含个人路径及 editable 包。前后端依赖锁由 W2/W3 在各自任务中建立，本轮未声称已安装 Vue/FastAPI。

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

PyTorch 实测 2.14.1+cpu，cuda_available=False；这是 CPU 构建的检查结果，不能认定设备没有 GPU。CUDA/驱动兼容检查 NOT_RUN，不阻塞 CPU 工作。真实数据、模型实验和端到端联调 NOT_RUN；检测 CLI 留给 W1-03 实现。

W0 独占 contracts.py、OpenAPI、需求及根级配置；W1 独占其余 core、核心测试和实验；本轮 W0 新建的 test_contracts.py 为契约测试，后续跨模块变更先提交 W0。W2/W3 直接采用 JSON 样例和 OpenAPI，不能自行改字段。公共 README/status 合并由 W0 按已验证事实整合。

共同基点为 Desktop 提交并经远端验证的 contract-v1 提交。未拿到确切提交号前可阅读样例和接口，不能各自建立不同版本契约。各 work 从同一基点建立分支/worktree；使用独立端口、SQLite、缓存及输出目录，真实数据目录只读共用。已有活动任务拒绝新任务。输入和输出路径保存在忽略的本地配置，网页只传登记 ID。

提交前运行 CONTRIBUTING 中的进度、链接、隐私和作者检查；所有 Commit/Push 由 GitHub Desktop 执行，未完成推送时明确标记未同步。合成检查不会升级 Data/Model/Experiment Gate。
