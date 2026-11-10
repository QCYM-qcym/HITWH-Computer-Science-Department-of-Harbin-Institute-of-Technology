# Release IF 保存结果只读展示 v1

日期：2026-11-10；状态补记：2026-11-11。源码实现与独立复核完成；已观察的人工安装、HTTP及实际浏览器功能经单独运行后核对接受，原控制器整轮FAIL/退出1保持。详见[运行指南](../guides/release-if-result-package.md)与[验证及失败保留记录](../research/2026-11-11-release-if-results-verification.json)。依赖[结果包v1](release-if-result-package-v1.md)。本次只补状态与链接，不改变下述契约；旧release输入页、candidate及生产OpenAPI/134/268不变。研究S2/Data Gate BLOCKED，真实C17训练、评分、Q99、正式实验NOT_RUN。

## 设计选择

采用独立app/static/前台CLI：接纳已保存的两个固定view，用双卡、双图和一个共用分页表查看。沿既有release输入页的启动前冻结和有限流读取模式，不导入旧candidate app（其四模型/合成授信/评价协议不同）。不添加分钟详情钻取、标签指标、时间筛选、排序、政策切换、目录选择或模型运行按钮。结果格式没有保存无效具体原因，页面明确“未评分，包内未保存具体原因”，不猜warmup/数据缺失/模型故障。

页面可用原生details/summary仅披露已保存的完整身份、配置与检查范围，不触发额外请求；这不属于被排除的分钟详情钻取。

所有JSON、静态资源及错误体在返回app前已有限编码；启动前只核保存内容关系，不重fit或重新评分。请求只发送冻结bytes。模型源码不变；依赖锁不变，无新增依赖。

## W1/W2接口边界

新增 `traffic_api.release_if_result_view.create_release_if_result_view_app(current13: ReleaseIFResultPackage, h30_26: ReleaseIFResultPackage) -> FastAPI`。参数必须精确新package，factory用结果codec重验内部一致性、声明identity及保存分数Q99后冻结；CLI才负责磁盘load。factory不能把手构对象校验称实际读了原包字节。

恰一current13和一h30_26且顺序明确。两包精确比较：raw与prepared完整四字段identity、准备configuration_sha256、source schema/auth/time/policy状态/audit政策、minute_count、每个segment全部字段/顺序、展开timestamps/roles、逐位scored_mask、train/calibration/preprocessing-fit全部索引。同长度/同计数不足以准入。view、input_width、各自分数/阈值允许不同；其余固定IF配置按包契约核对。

错参数→安全 `ReleaseIFResultViewError` 的INVALID_VIEW_ARGUMENTS，非法单包或跨包不符→INCOMPATIBLE_RESULT_PAIR，预算→RESOURCE_LIMIT，资源不可读/意外启动错误→VIEW_UNAVAILABLE。code/str相同，未知消息不泄漏。不要吞BaseException。

## 固定只读HTTP协议

唯一5条GET：`/release/results`、`/release/results/results.mjs`、`/release/results/results.css`、`/release-if/v1/summary`、`/release-if/v1/series`。不生成docs/OpenAPI，无目录/文件路径路由；其他path404、其他method405。前三及summary不允许任何query；series以percent-decoded query multi-items判定，解码后只允许唯一page，缺省0，恰ASCII `0|[1-9][0-9]{0,1}`且0<=page<page_count，不接受+、空、空格、负数、小数、前导零、重复或额外键。非法query422，页越界422。%70age=%30与page=0语义等价并接纳；page=0&%70age=0解码后重复仍拒绝，不能只按原始query bytes收窄合法编码。错误body精确 `{"error":"NOT_FOUND|METHOD_NOT_ALLOWED|INVALID_QUERY|VIEW_UNAVAILABLE"}`，按状态选择，有限预编码，不回显请求。

所有响应Cache-Control:no-store、X-Content-Type-Options:nosniff；HTML另CSP `default-src 'self'; script-src 'self'; style-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'`。无外部资源、CORS、cookie或上传。

固定API profile Q=`c17-release-iforest-view-v1`，scope=`SAVED_RESULT_INTERNAL_CONSISTENCY_ONLY`。summary恰下列键：

- `version:1, profile_id:Q, scope, snapshot_sha256`。
- `source:{schema_id,authentication,time_basis,policy_status,audit_fit_policy}`，均沿包context。
- `input_references:{raw:raw_identity,prepared:prepared_identity,configuration_sha256}`。
- `result_references:{current13:result_identity,h30_26:result_identity}`。
- `axis:{minute_count,scored_count,unscored_count,page_size:100,page_count,segments:[Segment...]}`。Segment恰ordinal/id/role/start/end/minute_count/scored_count。页数ceil(N/100)，N1..10000，1..100页。
- `views:{current13:View,h30_26:View}`。View恰configuration（既有8字段）、threshold、training_count、calibration_count、preprocessing_fit_count、equal_threshold_count、above_threshold_count。阈值/人口读取保存结果；equal_threshold_count与above_threshold_count仅遍历保存calibration_indices，相等与严格超过分别计数、合计不超过calibration_count，不是全轴报警数。校准外报警只在series出现，不能增加摘要两计数。它们均不是页内新计算阈值或评价率。
- `checks:{internal_consistency:MATCHED,saved_score_q99:MATCHED,cross_view_binding:MATCHED,input_pair_binding:NOT_PERFORMED,source_authentication:NOT_AUTHENTICATED,model_execution:NOT_AUTHENTICATED}`。

snapshot_sha256 = SHA256(C({profile_id:Q,current13:完整结果identity,h30_26:完整结果identity}))，C同包的canonical规则。只绑定两已接纳包身份，不是执行或来源认证。

series恰 `version:1,profile_id:Q,scope,snapshot_sha256,page,page_size:100,total:N,returned,items`。page从0开始；items是连续全轴索引[100*page,min(N,100*(page+1)))，不删未评分行。每项恰 `index,timestamp,segment_id,role,break_before,scored,current13,h30_26,reason`。两个view子对象各恰`score,prediction`，直接复制保存结果，scored共同逐位相同；false时两项均null。reason在scored时null，其他恰NOT_SCORED_CAUSE_NOT_SAVED。源钟面timestamp规范字符串，不加Z、不自动转UTC。

break_before按完整轴计算：i==0、segment变化、相邻非60秒、当前或前一行未评分任一成立为true，否则false。分页不改变全轴断点；页首可false但新图无前一页线段。原始index、segment和role不按页重新编号。

硬限：summary UTF8含LF<=16384B；每series页<=131072B；每静态成员<=65536B，预冻结总bytes（summary+最多100页+三资源+固定错误体）<=16777216B。先有限编码后bind，超限不返回部分app。验证N10000/100页、128码点四字节Unicode segment-id和极端有限float下的真实编码边界，不能靠估算宣布上限成立。FastAPI冷请求处理沿锁版本检查，首请求与重复请求均禁止包load/编码/prepare/replay/fit/score/calibrate或文件访问；在factory阶段的Q99复核单列。

## 前台CLI

新增 `traffic_api.release_if_result_serve_cli`，模块命令必需 `--current-dir ABS --h30-dir ABS`，可选`--port`（默认8768，精确十进制1..65535）、`--serve-seconds`（默认300，精确十进制1..300）。固定host127.0.0.1，无任意host、不后台启动、不自动打开浏览器。使用已锁uvicorn，包各load一次、factory接纳/静态预载/全页预编码均在bind前。既有目录只读不改，CLI不写结果或模型。

成功前台服务普通计时退出0，SIGINT按既有serve CLI约定处理；非法参数、load/factory/bind错误退出2，stdout为空或仅已实际打印的有限启动信息，stderr只固定安全码+LF，无路径/异常原文。help不加载包或模型。编码/包未接纳不得监听。沿既有有限启动与无泄漏server-close/finally规则；实际进程exit/回收/端口核验归后续有界运行，不把main返回值当物理exit。

## W3页面契约

新增独立results.html/results.mjs/results.css，不改变旧页面。HTML标注人工工程示例、打开页面仅查看、真实研究Gate仍阻塞；这是页面用途说明，不在保存包中增造REAL/SYNTHETIC授信。清楚显示NOT_AUTHENTICATED、AUDIT_ONLY和源钟面未认证UTC；保存报警不是标签。

固定双摘要卡与两张小图，current13/H30_26各自纵轴与保存Q99线，图的横轴明确“本页源分钟顺序”，不能把源时间gap画成连续，single-point仍可见。图和共用分钟表保留全部未评分行、原源分钟/分区、两个保存分数与报警。null显示未评分、false显示未报警，不显示“正常”或FP/FN/准确率。role=train不等于实际模型训练行；摘要预处理拟合/模型训练/独立校准人数分别命名，相等与严格超过计数均标明“校准分钟中”，人口不随翻页变化。首末按钮disabled，键盘与手机横滚区域具可访问标签，状态不只靠颜色。

只请求summary一次后series?page=0，再以原生上一页/下一页固定100行翻页；无自动重试或预抓全轴。summary失败清空全页并显示安全错误和重试加载按钮；series失败清空该页旧图表、保留全轴summary、显示重试本页按钮。summary/series独立AbortController+generation，总deadline均10秒贯穿fetch/body，真实Uint8Array流字节上限分别16384/131072，UTF8 fatal、JSON媒体类型、精确shape/标量/枚举/有限数与守恒及snapshot一致性验证。segment_id上限按Unicode码点（如Array.from）计128，不用UTF16 string.length；字符规则与包一致。JSON解码后检查精确字段集合；本服务冻结编码保证唯一键，前端不另造通用JSON语法解析器。不能把Response.json无界读取当流限额。

所有文本用textContent，无innerHTML/eval/内联handler/外部URL；chart几何对空、单点、常数、极大有限值无NaN/Infinity。图以保存prediction显示报警，不重新生成预测。late success/error/finally（fetch或body不合作也一样）不得覆盖当前请求；pagehide/destroy取消reader/timer/listener，不再写DOM；同root重挂不叠加监听。

JS导出 `mountReleaseIFResultView(root, options={})`，默认fetch/timeout/monotonic clock可按现有输入页测试模式注入，返回带destroy的handle。可另导出纯validator/geometry用于测试，精确名字由W3选定并写实现报告，不需要扩大网络接口。

## 验收与范围

后端用独立手写双包，测试错轴/同数不同mask/错完整身份、页0/末页/越界/重复query、五routes与安全头、首个冷请求和所有重复请求零I/O/模型数值调用、有限全页编码及源码无改写。CLI通过受控假server检错不代替真实前台进程。

前端手写符合冻结接口的期望，不借产品投影生成断言。覆盖identity/snapshot错、0/false/null、分区边界和未评分断线、singleton/extreme、分页失败/旧响应/不合作fetch-body/总deadline/stream界限/UTF8/注入/destroy/键盘/移动结构。真实浏览器与安装资源验收另由单一UI owner执行，DOM通过不冒称视觉通过。

最后安装后人工链路：实际core结果保存→独立新进程加载两包→backend前台serve→实际HTTP/浏览器→退出/端口关闭/输入保全；仅获冻结方案和资源预算后执行，失败保留并标未到项NOT_RUN。结果包内部自洽、纯pair绑定、实际模型运行及真实研究效果四种证据分开。
