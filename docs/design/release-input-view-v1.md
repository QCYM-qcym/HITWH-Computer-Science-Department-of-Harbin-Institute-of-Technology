# 准备输入包只读查看协议 V1

日期：2026-11-09。状态：源码与限定范围单元测试已接受；实际安装链验收未完成。范围：一个已保存准备输入包的摘要、固定 HTTP 传输、前台启动命令和独立静态页面。依据：[准备输入包格式](release-input-package-v1.md)、[输入 CLI 协议](release-input-cli-v1.md)、[本批验证记录](../research/2026-11-09-release-input-view-verification.json)。

## 输入与摘要

`summarize_release_inputs` 接收已加载的 `ReleasePreparedInputs`，只投影保存字段并统计保存的布尔 mask。CLI `inspect` 与查看服务共用该投影。摘要包含：

| 字段 | 含义与边界 |
|---|---|
| `identity`、`upstream_identity` | 准备包与上游分钟包的 profile、context SHA256、manifest SHA256 及字节数 |
| `source_authentication`、`time_basis` | 保存的来源声明与时间基础；不因查看而升级 |
| `configuration`、`configuration_sha256` | 数值规则、窗口、拟合窗口、epsilon、审计拟合政策、政策状态、特征数及配置身份 |
| `minute_counts` | 总分钟、raw/prepared/common 有效分钟及 H15/H30 历史有效分钟 |
| `fit` | 保存的预处理拟合人口、拟合 mask 与拟合行摘要；与模型训练资格分别展示 |
| `qualification_counts` | P_U/P_B/P_A 各八类保存资格：训练、独立校准、验证正常/攻击/未知、测试正常/攻击/未知 |
| `package_checks` | 保存结构与字节检查及未执行重放/拟合核验的范围 |

投影不读取文件、不重新聚合 CSV、不重放变换与历史、不估计参数、不运行模型。Python 对象类型也不构成来源认证。

## 启动与传输

独立入口为 `python -m traffic_api.release_input_serve_cli`，必填 `--prepared-package`；目录要求沿用准备包加载器。`--port` 为 0—65535 的十进制整数，默认 0；`--shutdown-after-seconds` 可选，范围 1—3600 秒。`--help`/`-h` 必须单独使用，不读取包。未知、重复、缩写及响应文件形式的参数安全拒绝。

启动顺序为：加载一次准备包→投影并编码一次摘要→预载三个资源并完成端点上下文预热→绑定 `127.0.0.1` 的同一 socket→启动服务。固定路由如下：

| 方法与路径 | 内容 |
|---|---|
| `GET /release/v1/input-summary` | 同包 CLI `inspect` 的完整 JSON 字节，含末尾 LF |
| `GET /release/inputs` | HTML |
| `GET /release/inputs.mjs` | JavaScript 模块 |
| `GET /release/inputs.css` | CSS |

摘要为 UTF-8、键排序、紧凑 JSON，拒绝非有限数；编码后上限 65536 字节。单个资源须为非空有效 UTF-8 且不超过 65536 字节，三个资源总量不超过 196608 字节。资源随后端包发布，缺失或无效时在绑定前拒绝。

请求端点为异步传输，正常请求只返回预先保存的字节。四条路由均拒绝非空原始查询串，返回 422 `INVALID_QUERY`。未知路径返回 404 `NOT_FOUND`，其他方法返回 405 `METHOD_NOT_ALLOWED` 并附 `Allow: GET`；其他异常返回固定 500 `INTERNAL_ERROR`。HEAD 错误体为空。响应包含 `Cache-Control: no-store` 与 `X-Content-Type-Options: nosniff`；无 OpenAPI、文档页或路径重定向。

## 事件与退出

`SERVER_READY` 在服务启动且事件完整写入、刷新后成立，包含本次 host、port、url、进程及父进程 ID；可选关闭计时从此开始。定时器请求优雅关闭，不承诺硬超时。`SERVER_STOPPED` 仅在已就绪、正常关闭完成且未强制退出时发送。

成功要求就绪、停止、关闭完成和非强制状态全部满足，进程退出 0；安全错误退出 2，直接捕获的键盘中断退出 130。事件输出失败会使整次运行失败。模块入口处理失败退出时的流刷新，固定错误内容不暴露路径或堆栈。单条 READY/STOPPED 不能代替实际退出、回收和端口关闭证据。

## 页面

页面仅请求一次固定摘要，不上传或切换输入。实际响应上限 64 KiB，请求及读体总期限 10 秒，失败使用固定说明。DOM 验证响应结构、声明、身份、分钟数与资格字段；整数 0 原样展示。页面保留完整摘要、六类分钟、预处理拟合记录、三政策表与检查范围；窄屏表格可横向滚动并通过键盘聚焦。

校准资格为 0 不等于 FPR 为 0，也不提供可用 Q99。`INTERNAL_CONSISTENCY_CHECKED` 只说明既定结构与字节检查；此次查看的 `replay` 为 `null`。来源保持 `NOT_AUTHENTICATED`，时间保持 `SOURCE_WALL_CLOCK_COMPLETION_PROXY`，政策保持 `AUDIT_ONLY`，不认证 UTC。

## 验收状态

核心切片 118 通过/37 未选；后端最终切片 201 通过/1 警告；前端单文件 DOM 71 通过且类型检查通过。计数分范围保留，后端 201 替代前序 200，不累加；DOM 通过不等于实际浏览器通过。

首次实际构建/安装的四阶段成功，8 个受管直接 Python 子进程退出 0 并回收。整轮仍为 FAIL：在后端安装后检查 Windows 控制台文件的路径/句柄执行位差异时，私有身份比较器报 `PRIVATE_HANDLE_CHANGED`；尚未进入应用案例。应用案例、实际 HTTP、实际浏览器均为 0，完整 after-map 未建立。补充只读安装产物核对及 13 项比较器回归不替代缺失验收；修复后第二轮未启动。

查看页本批 Desktop 发布为 PENDING、新 CI 为 NOT_RUN。前序 raw CLI 的精确提交与 CI 单列于验证记录，不能覆盖本批。S2/Data Gate 保持 BLOCKED；D1—D6 待决、真实预处理/训练/评分/Q99/正式比较继续 NOT_RUN。后继输入与模型成对核验仅有私有设计/计划，无实现。
