# 后端 JSON 的校验与解析

状态：SYNTHETIC_ONLY。本文对应[实际验证记录](../research/2026-10-30-json-byte-verification.json)与[实施计划](../superpowers/plans/2026-10-30-json-byte-consistency.md)。

SavedArtifacts 原来先核对 manifest 摘要，再重新按路径读取 JSON。两次读取之间文件变化时，后一次内容仍可能通过类型检查。例如只改变 metrics.reason，旧 API 会返回未被原摘要验证的说明文字。

本批让 summary.json、config.json、metrics.json、model/metadata.json 和 model/preprocess.json 的五处正式调用传入本次 manifest 中的原 SHA-256。read_json 取得 bytes 后先核摘要，再将同一对象交给类型解析器。不刷新摘要，也不重新序列化内容代替核验；即使仅增添合法空白、解析值不变，字节与登记摘要不符仍会拒绝。

根 manifest 没有上级摘要，仍使用原两参调用；这不是来源认证。helper 的可选摘要参数也保留直接调用兼容，五处正式受 manifest 管理的调用均显式提供摘要。初始摘要循环、顺序、类型及业务一致性规则不变。整个目录不因此成为原子快照；metrics.reason 和高负载说明的业务语义没有新增校验政策。core 的独立读取入口不在本批范围。

JSON 原实现已将整个文件读为 bytes；本批只命名并复用该对象进行摘要和解析，不另建完整文件副本或长期缓存，不增加公开大小上限。此前的[Parquet 字节绑定](parquet-byte-consistency.md)和[最终导出字节绑定](export-byte-consistency.md)各自保持原范围。

11 项新回归先得到 6 失败、5 通过：五个新临时包在原摘要验证后物理替换目标 JSON，旧接口返回 200；截短内容会进入旧解析器。缺失及系统读取错误、两参兼容正例单独记录。修复后完整后端 134 项通过，仅保留既有 TestClient 弃用警告。

主控另实际执行六个独立 Fake 任务与数据库：正常任务验证完整分数、报警、评价、四个分钟详情和三种原字节导出；五个新目标分别作合法说明文字或空白变更。每例原摘要通过一次、实际改写一次、后续 payload 读取一次、目标解析次数零，返回安全 500 / ARTIFACT_INVALID；任务状态保留 succeeded，其他九个文件及 manifest 不变。五种正常 helper 均验证解析器收到取得的同一 bytes 对象，无额外路径打开。原第十至十四批目录 SHA、大小、修改时间保持；新替换样本留在各自私有验收目录。

人工验证使用进程内 TestClient，无监听服务器、网页或真实模型调用，不等同于浏览器联调。未重复本地无关全套、前端构建或真实模型集成；远端 CI 以提交后实际结果为准。生产契约、前端、共享样例、研究配置与历史审计未改。真实 CSV 读取和新增下载均为零，真实训练、评分、校准及正式实验仍为 NOT_RUN，Data Gate 为 BLOCKED。
