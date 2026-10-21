# W0 合成集成联调记录

日期：2026-10-21。状态：SYNTHETIC_ONLY。依据报告V0.40、并行计划W0-02及本轮用户授权。本轮完成合成核心到API和网页的联调，不认定真实W2-02、Data Gate或研究实验通过。此前[接收记录](W0-DELIVERY-ACCEPTANCE-2026-10-21.md)保留其当时状态。

## 合并与实现

在 codex/integration-mvp 独立工作区，通过 GitHub Desktop 按顺序合入：

| 来源 | 来源提交 | Desktop合并提交 |
|---|---|---|
| W1 | 2e85cd1c69915d651c924d1579470666840a8c2a | 0eb8171 |
| W2 | 4f6c53696cdd1befee05b131c6d51ab3a99098f7 | 472042f |
| W3 | 2839ac206039857585230a85f82e3a8e7a7e227e | e25f936 |

三个合并的冲突均仅为 README/status，由主控保留模块证据与 Data Gate 阻塞事实后重新生成首页。没有合并 main，没有切换或重置其他 work。最终同步提交由交付回复和远端分支给出，不在提交前预填自身SHA。

新增 CoreRegistration：启动时从可信本地登记中读取、审计并快照一个合成输入和冻结配置，每个任务独立复制小型人工输入、调用 W1 execute_run；不复制预处理、模型或评价算法。HTTP仍只接收登记ID，真实执行限制仍由核心 registered_input 强制检查。

核心 execute_run/score_run 增加向后兼容的可选 run_id，CLI增加 --run-id。ID执行前验证、拒绝已有ID和路径穿越；后端传递最初接受的ID，不事后重写产物。RunConfig、HTTP Schema和模型包版本均保持1.0，研究配置未改义。前端可用 TRAFFIC_API_TARGET 选择本work端口；统一TS/MJS/Vue换行为LF，修复Windows检出后的生成检查误报。

## 实际验证

| 检查 | 结果 |
|---|---|
| W1合并后的完整测试 | 73项及7个subtests通过 |
| W2合并后的联合核心/后端测试 | 起初5项收集错误：同名conftest相互覆盖；改成独立测试包及相对导入后110项通过 |
| 新集成测试先失败 | 5项RED：缺少CoreRegistration及显式run_id接口 |
| 新接口完成后 | 5项GREEN；增加失败/冲突/重提检查后6项集成测试通过 |
| 最终核心＋后端＋集成 | 116项通过；Starlette/TestClient弃用警告保留 |
| 前端 | 22项测试、typecheck、build、contracts:check通过；854.70kB入口包提示暂留 |
| 独立代码审查 | 无可复现Critical/Important/Minor；审查独立复跑115项通过，之后新增1项生命周期验证通过 |

联合命令：`python -m pytest tests/core tests/backend tests/integration -q`。集成以三个独立用例验证IF、当前AE和历史增强AE；API受理ID被CLI在独立工作区复用，完整Parquet表、分数/阈值/报警/有效掩码及metrics全部一致，特征134维，重构通道按方法存在或null。服务重启后原成功产物仍可读取。所有拟合仅消费人工生成数据，不代表真实效果。

## 浏览器与下载证据

人工走通HTTP模式数据登记→提交→running→succeeded→完整曲线→无报警→完全漏报片段定位→特征通道→独立评价→三类下载。API端口8102，网页5175，与其他work服务隔离。

本地验证任务 `run-de84bfce56704ee4b91c47c7f9bd8a81`：40个测试分钟、37有效、3预热；正常覆盖31/34、攻击覆盖5/5、仅背景1；TP/FP/TN/FN=0/0/31/5。无报警、5分钟完全漏报片段[02:15,02:20)，precision无分母为null。这是如实保留的合成失败检测例子，不因页面需要演示而修改阈值或输入。

CLI以同一任务ID在另一工作区执行。浏览器实际下载、HTTP导出与保存产物逐字节相同；CLI三个文件也逐字节相同：

| 文件 | 字节 | SHA256 |
|---|---:|---|
| scores.parquet | 2578 | ffb636adcb17b07e39924b6b6979ad0d26130fd16123e72b4abb5af45e4c4ffb |
| metrics.json | 844 | 79d7212ebd756b1294e4d16e2c4d0dafd6343804f9a3b879d504fea6aab0b6ef |
| config.json | 482 | 648b12426d9fb1f85537bb124e3a523178bf42372db438f3a8271622be186c9d |

浏览器还验证有效空范围显示0条、完整5分钟漏报评价仍可定位；倒置范围返回安全错误；恢复范围后仍40条。停止本work API后，在本地SQLite注入一个SYNTHETIC_ONLY遗留running任务，重启后页面显示failed/WORKER_INTERRUPTED；原成功任务重新查询成功，三份下载校验仍通过。自动测试另外覆盖409占用、未完成结果409、缺字段422、未知ID404、执行失败不泄漏内部诊断及失败重提成功。半成品、损坏产物和进程恢复沿用后端回归。

首个HTTP合成IF流水线耗时约1.011秒，未启用tracemalloc的内存字段为0，不将其当有效测量。独立`python -X tracemalloc=1 -m traffic_anomaly.cli run ...`探针耗时约2.728秒、Python追踪分配峰值86,151,500字节；包含解释器/导入开销，且不覆盖全部原生库内存，不能当进程RSS或性能达标证据。性能验收仍NOT_RUN。

初次浏览器下载等待工具超时，但文件确已落盘，经本地字节校验确认；没有把工具超时当成功依据。首个urllib检查被本机代理返回502，显式对本机回环禁用代理后复核通过。运行载荷、下载和页面截图仅保留本地忽略目录，公开仓库只记录摘要。

## 未执行及下一步

真实Data Gate仍BLOCKED。来源/八标签含义已补证，时区仍UNVERIFIED；固定测试载荷全部blacklist>0导致冻结协议下正常候选为0。不得将blacklist整列改为正常、改变测试范围或默认UTC。许可的两份第一方声明存在差异，未公开再分发数据。见[来源与标签核验](../research/2026-10-21-UGR16v3-provenance.md)。

真实IF/AE训练、真实CLI/API/网页联调、窗口/epsilon选择、三种子、容量匹配、正式比较、GPU、性能及异机完整恢复均NOT_RUN。本轮新增合成系统CI；远端执行结果在推送后单独核对，不以旧的仅契约CI替代。

复跑入口：[quickstart](../guides/quickstart.md)。后续各work先同步主控最终集成SHA，保留独立环境/端口/数据库/输出，共同契约仍由W0维护。研究协议调整先形成明确决定及新评价定义，再实施。

## 首次远端集成CI发现的跨平台测试差异

提交81f397f的发布、契约及前端CI通过；合成Python检查115通过、1失败（运行39578207881）。失败位于进程崩溃测试：Windows terminate()强制结束进程，POSIX则发送SIGTERM，Uvicorn进入正常关闭并等待刻意永久阻塞的测试执行器，10秒后超时。根因为故障注入方式不同，不通过延长等待或取消worker所有权等待掩盖。

崩溃注入改用Popen.kill()，在两平台均执行硬终止；正常退出的第二个测试进程仍用terminate()。本地定向回归通过；修复后的Linux实际结果以最终远端CI核验为准。研究协议及业务执行语义不变。
