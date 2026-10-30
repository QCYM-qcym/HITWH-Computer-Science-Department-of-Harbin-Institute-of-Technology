# 候选合成结果的独立查看页

日期：2026-10-31。状态：IMPLEMENTED_SYNTHETIC_ONLY。起点df6a7d2。依据[报告V0.40](../../reports/开题报告-V0.40-公开文本.md)的保存结果回放要求及[候选只读HTTP](../../guides/candidate-readonly-http.md)。本批只为已有人工结果增加一页查看入口，不决定主数据或研究协议。

采用可选 `traffic_api.candidate_viewer.create_candidate_viewer_app(registrations)` 包装既有工厂；基础三条GET和生产Vue保持。启动时通过包资源读取并固定index.html、viewer.css、viewer.mjs三文件，单文件有界，缺失时安全拒绝。只增加固定GET `/candidate`、`/candidate/viewer.css`、`/candidate/viewer.mjs`；不挂任意目录，禁路径参数、未知查询键和自动斜杠重定向。HTML及模块使用固定 `/candidate/...` 同源URL，避免无尾斜杠入口的相对路径歧义。无CDN、新依赖、CORS或第二任务后台。

页面固定显示SYNTHETIC_ONLY/AUDIT_ONLY，运行选择使用目录原run_id。源钟面字符串不作Date/UTC转换。当前页SVG按记录顺序显示原分数与阈值，null及break_before断线；完整表保留无效行和原因，0分与null、false报警与正常标签分开。不抽样、不插值、不自动取全页、不计算评价指标。空页清除旧阈值，展示原评价身份引用；不制造导出链接或模型排名。

详情按原13特征顺序分别展示raw/prepared/H15/H30及各自有效原因；原三政策分类仅作审计元信息。AE仅显示保存的组标量MSE，APPLICABLE+null、NOT_APPLICABLE、NOT_STORED含义分开，不把标量分摊到特征。运行、范围、页或选中分钟改变时立即清除过期视图。表单草稿与已应用查询分离，Apply回第1页；请求用Abort加代次及身份检查，旧成功、失败、finally均不能覆盖新状态。目录重试也必须防重叠。动态文本通过textContent或文本节点显示，错误只翻译固定code或通用失败。

只进行两项必要配置维护：后端声明三个精确package-data文件；现有Vitest增加独立JS测试的精确发现入口。不放宽TS检查、不改原Vue业务/锁文件。静态模块不属于原Vue构建，分别报告其DOM测试和真实浏览器结果。包资源须用无网络构建wheel、安装到私有隔离目标并核对模块来源与实际资源读取，不能用editable或ZIP清单代替安装证据。

- [x] 静态页面/模块及DOM测试覆盖选择ID、输入状态、null/通道、断点、常量轴、错误/空页和故意乱序完成。初始测试加载偏差单列，不称全部功能先RED；实际浏览器发现单点阈值缺失后追加有效RED并修复。
- [x] 可选wrapper与测试先RED；固定资源路由、内容类型、无请求文件读取、基础API不变；安装资源验证后补精确package-data。
- [x] 主控相关测试、实际wheel安装、旧四包同源浏览器操作与39原文件身份检查；HTTP/DOM/浏览器证据分开，服务正常收尾。
- [ ] 独立审查、公开说明与既有知识库同步、仓库检查、Desktop提交推送和准确远端CI核验。

根主控独占公共记录和两项配置；页面代理仅三静态文件与独立JS测试，后端代理仅wrapper与独立测试，审查代理只读。无真实CSV、下载、训练评分校准或正式实验；最终Attempted、主数据采用、生产134/268迁移仍待决定，Data Gate保持BLOCKED。
