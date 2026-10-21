# W3-01 前端与结果展示

用途：本地分钟流量回放、任务操作和评价查看。日期：2026-10-21。程序版本：0.1.0。状态：`SYNTHETIC_ONLY`，真实联调 `NOT_RUN`。

依赖基点：`codex/integration-mvp` 的 `74f163bf69559f02ad70ae1d5bb730e1f10d15bf`。本工作分支为 `codex/frontend-replay`，不合并 main。依据：[实施计划 W3-01](../../docs/superpowers/plans/2026-10-21-parallel-development.md)、[契约 v1](../../docs/design/contracts-v1.md)、[开发环境](../../docs/guides/development.md)。本模块只修改前端及本分支首页进度；W0 的 Schema、OpenAPI 和统一合成样例保持原样。

## 安装与运行

已在 Node **24.18.0**、npm **11.16.0** 实测安装与 `npm ci` 恢复。Vue 3、TypeScript、Pinia、ECharts 及开发工具的确切版本见 `package.json` / `package-lock.json`；TypeScript 保留 5.x，以满足 OpenAPI 类型生成器的 peer 依赖。

从仓库根目录执行：

```powershell
npm --prefix src/frontend ci
npm --prefix src/frontend run dev
```

访问 <http://127.0.0.1:5173/>。仅绑定本机，端口被占用时直接失败，不静默换端口。需要独立备用端口时执行 `npm --prefix src/frontend run dev -- --port 5175`，并将实际分配记入忽略的本地配置。集成页面保留 5174；本工作不写任务数据库或运行产物。

默认使用统一合成样例。顶部核查场景可选择任务失败、空查询结果与标签缺失。合成分数为 W0 手工指定，不是检测器预测；合成模式只允许隔离森林，AE 与历史增强 AE 的真实产物仍待 W1 提供。没有的历史/重构通道保留 null，不造零值或移用其他通道。

真实接入入口已提供，但未联调：在模块内建立被仓库忽略的 `.env`，内容写为 `VITE_API_MODE=http` 后重启。删除该行或设为 `mock` 可恢复合成模式。开发代理把 `/api` 转到本机 8101；具体 API 就绪及产物兼容由 W2/W1 验证。生产构建使用同源 `/api`，不包含独立后端部署。构建产物写入现有规则已忽略的 `dist.local/`；模块不新增根级发布规则。

## 页面与数据边界

| 页面 | 已实现操作 |
|---|---|
| 数据查看 | 读取登记表、数据身份、时间范围、134 维及配置/划分 ID，不接受服务器文件路径 |
| 检测任务 | 提交固定四字段请求，查询已有 run_id；排队/运行/完成/失败状态，失败原因与重新提交；停止追踪仅停止轮询，不取消后台任务 |
| 异常分析 | 同一 UTC 时间轴的流量/分数/阈值/报警；范围与分页、预热断点、报警和完全漏报片段定位；当前特征、历史偏离、两组重构误差各列独立展示 |
| 实验对比 | 并列已完成任务的后端评价、混淆计数、覆盖分母、排除攻击和高负载不可用原因；导出评价/配置 JSON |

接口 v1 没有全量任务列表，所以任务页仅列本会话查看过的记录，旧任务通过编号查询。数据范围为 `[start,end)`，使用 UTC 整分钟；状态时间保留服务返回的秒精度。分页/范围只影响回放与报警列表，评价始终取完整任务 `/evaluation`。比较页不判断共同分钟是否相同、不计算新的研究指标或模型排名，正式同条件比较等待 W1 验证。

图表密度仅影响当前页绘图，保留报警、无效点及真实缺口两侧；表格仍可访问服务器当前页全部分钟。未知流量、无效分数或缺通道显示未提供；无分母指标显示不可评价。事后标签不进入模型请求；解释通道仅是排查线索。

模拟接口与测试直接导入仓库 `tests/fixtures/contracts-v1.json`，未维护另一份数值样例。`scripts/contracts.mjs` 从 W0 OpenAPI 生成前端类型与运行时 JSON Schema；HTTP 响应经 AJV 校验。契约变更须先由 W0 发布新版本，再运行：

```powershell
npm --prefix src/frontend run contracts:generate
npm --prefix src/frontend run contracts:check
```

## 验证记录

```powershell
npm --prefix src/frontend run test -- --run
npm --prefix src/frontend run typecheck
npm --prefix src/frontend run build
```

已观察首次测试因前端模块不存在而失败，随后实现通过。补充回归先复现模拟方法误标和切换任务遗留加载状态，再修复通过。测试核对 W0 全部 HTTP 样例、请求四字段、半开时间范围、分页、任务终态停止轮询、网络失败、取消订阅后的迟到结果、预热/缺口、无报警正常分钟、完全漏报定位、独立解释通道、长字段名、空查询及标签缺失。最终 22 项前端测试、typecheck、build 及生成契约漂移检查通过；13 项仓库维护测试在提交前复跑。独立审查的导出名称错配、首次状态失败丢失任务编号、页大小跳页和数据卡片选择四项均先复现再修复，22 项全套回归通过。

浏览器核查：默认桌面宽度、390px 窄屏（可用宽度375px）均已检查；修复窄屏网格和导航溢出，复查页面宽度与视口一致。走通提交→排队→完成→曲线→漏报详情；失败场景显示 `WORKER_INTERRUPTED`，空查询显示空曲线/无报警，正常分钟可单独查看，评价 JSON 实际下载并核对。长字段与四通道的数值展示由组件测试验证，统一 IF 样例不伪造 AE 通道。

构建成功；ECharts/校验器使入口压缩后约854KB（gzip约280KB），Vite 提示大于500KB；本机功能验收通过，首屏分包优化留作后续工作。

| 未执行项 | 状态与依赖 |
|---|---|
| W2 HTTP 服务联调、真实提交与持久化恢复 | `NOT_RUN`，等待 W2 |
| W1 实际数据、IF/AE/历史增强模型产物及效果比较 | `NOT_RUN`，等待 Data Gate / W1 |
| CLI/API/网页逐分钟一致性及完整 Parquet 导出 | `NOT_RUN`，等待 W0-02/W2-02；模拟模式明确拒绝假 Parquet |
| GPU、真实研究实验、资源与性能达标 | `NOT_RUN`，前端模拟验收不升级研究 Gate |
| 前端远端自动测试 | `NOT_RUN`，现有 CI 只覆盖仓库维护及 W0 契约；本模块命令为本地验证 |

Desktop 提交、推送和远端 CI 状态由本次实际交付核对，不因本说明存在而视为已同步。后续合入及公共进度冲突由 W0 逐项整合。
