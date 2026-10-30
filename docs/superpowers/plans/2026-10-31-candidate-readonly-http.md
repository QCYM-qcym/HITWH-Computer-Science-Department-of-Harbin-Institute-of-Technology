# 候选合成结果的隔离只读HTTP

日期：2026-10-31。状态：IMPLEMENTED_SYNTHETIC_ONLY。起点9f0df54。依据[报告V0.40](../../reports/开题报告-V0.40-公开文本.md)的结果回放要求，以及已有[候选查看CLI](../../guides/candidate-view-cli.md)、[分钟详情](../../guides/candidate-minute-details.md)和[范围分页](../../guides/candidate-series-pages.md)。

新增独立 `traffic_api.candidate_app.create_candidate_app`，只消费既有安全加载器产生的冻结运行与输入快照。接受长度1–4的list/tuple，每项为冻结的CandidateRegistration(run, inputs)；先检查全部配对，再复制为内部固定目录。运行ID沿用已验证run_id，拒绝重复、错误类型和不兼容配对，不接收目录路径或生成器。快照类型本身不认证人为构造的对象，真实启动仍须使用既有加载器。

三条GET：`/candidate/v1/runs`、`/candidate/v1/runs/{run_id}/series`、`/candidate/v1/runs/{run_id}/detail?timestamp=...`。目录只返回固定的合成证据/审计政策标记及运行ID、模型profile、method、history_window、selected_policy、原分钟数/有效数与配对来源证明；不返回路径或任意元数据。series/detail原样复用纯查询，不适配生产134/268类型，也不重算评价分母。

目录无查询键；series只接受start/end/page/page_size，detail只接受一个必填timestamp。解码后逐项检查重复/未知参数。page/page_size仅接受ASCII非负十进制数字字符串，再由既有1-based范围规则拒绝0和越界。source_clock整分钟不转换UTC。未知运行、分钟、路由分别404 RUN_NOT_FOUND/MINUTE_NOT_FOUND/NOT_FOUND；请求错误422 INVALID_QUERY；错误方法405 METHOD_NOT_ALLOWED；不可兼容/意外异常/序列化问题500 INTERNAL_ERROR；超长响应500 RESOURCE_LIMIT。公共错误仅固定code，不回显输入、路径或堆栈，405仅允许固定Allow头。

成功响应统一完整序列化为UTF-8紧凑JSON加单LF，含LF最多1MiB，allow_nan=False；检查后才发送这些字节。debug/OpenAPI/docs/redoc/斜杠自动重定向关闭，不加CORS。应用不创建DB、任务、worker、模型、输出或动态重载，不挂入生产app。启动前安全加载仍验算保存关系；请求应用层只查冻结快照，网络传输与服务器日志不包含在“零文件读取/模型执行”证据中。工厂不决定监听地址，受信本地启动必须127.0.0.1、单worker、无reload；实际验证用空闲端口并正常停止回收。

- [x] 新手写或mock测试先RED再最小实现；覆盖注册冻结、路由、null、错误、字节上限、重复键及独立边界，不新增模型训练。
- [x] 独立规格/质量审查。既有backend conftest会导入生产模块，不将测试进程描述为完全未导入；独立启动子进程另核。
- [x] 主控复用四个旧人工包，真实loopback HTTP与CLI逐值一致，记录端口、状态、退出、守卫范围和39原文件身份；不把HTTP客户端验证称网页验收。
- [ ] 更新公开结果、既有知识库和状态；相关检查后Desktop提交推送，核对准确远端与CI。

仅SYNTHETIC_ONLY工程消费接口。生产契约/前端不迁移，最终Attempted政策、主数据采用和真实模型权限不改变。真实CSV读取、下载、训练评分校准和正式实验不启动，Data Gate仍BLOCKED。
