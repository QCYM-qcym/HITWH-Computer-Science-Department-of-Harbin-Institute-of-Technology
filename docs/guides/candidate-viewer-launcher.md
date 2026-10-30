# 候选合成结果查看页的本地启动

日期：2026-10-31。状态：本地合成启动、关闭与安装验收通过；提交及CI以实际远端为准。范围：SYNTHETIC_ONLY/AUDIT_ONLY。依据[本批计划](../superpowers/plans/2026-10-31-candidate-viewer-launcher.md)，复用[候选查看页](candidate-viewer.md)及原安全加载器。

先按[开发说明](development.md)安装核心和后端包。命令只消费已存在的人工结果，不生成输入或模型。以下目录为占位，必须换成已经保存且相互匹配的候选包；source必须是生成这些包的同一个人工夹具。

```text
python -X utf8 -m traffic_api.candidate_serve_cli --records .runtime/example-records --inputs .runtime/example-inputs --source-fixture tests/fixtures/g13u-records-v1.json --if-run .runtime/example-if-run --ae-run .runtime/example-current-ae-run --ae-run .runtime/example-history15-ae-run --ae-run .runtime/example-history30-ae-run --port 0
```

`--if-run`和`--ae-run`可以分别重复，总计1–4包；目录顺序固定先IF后AE，各族保留参数内顺序。运行ID从原包读取，重复ID不能启动。族标志错误不会自动换用另一个加载器。所有运行共用records、inputs与可选source；不同输入应单独开命令/端口。缺source时保留NOT_PROVIDED；有source而核验失败时拒绝启动，不降级忽略。

输入快照先加载一次，每个运行仍会由原加载器独立核验上游保存关系；这包括保存的预处理、历史、阈值和评价一致性，不是新的模型训练或评分。全部快照和三静态资源准入后才绑定固定127.0.0.1。默认端口0请求系统分配空闲端口，同一个socket直接交给服务器；显式占用端口报错，不偷偷换端口。单worker、无reload，不自动打开浏览器。就绪JSON行给出实际URL，浏览器打开其中 `/candidate` 入口。

默认前台运行，Ctrl+C请求关闭。无人值守工程核查可增加 `--shutdown-after-seconds 10`：允许1–3600的正整数，从服务器实际就绪开始计时，然后请求优雅关闭。它不是硬墙钟上限；仍需等待已开始的请求结束。不要把强制结束进程当作正常关闭验证。

SERVER_READY只在服务器真正启动后输出，SERVER_STOPPED只在优雅关闭完成后输出。强制退出状态（例如第二次Ctrl+C）不能产生正常停止事件。监听socket在所有退出路径关闭，但单纯关socket不代表成功完成关闭流程。捕获Ctrl+C的退出码为130；Uvicorn在优雅关闭后可能重发SIGTERM/SIGBREAK等系统信号，因此进程退出码与关闭事件需要分别判断。具体信号路径是否实测在验收记录中单列。

标准输出只包含固定字段的就绪/停止JSON事件，help为普通命令帮助。参数、加载、绑定和服务错误通过安全code诊断，不回显本地路径、异常正文或堆栈。命令运行期间只调整Uvicorn命名日志的安全格式，结束后恢复；不全局屏蔽Python warning。输入路径只存在于受信终端参数，网页不接收它们；原HTTP固定错误规则保持。

更换运行包时先停止命令，再重新指定并核验。命令不写数据库、运行产物或新模型，也不监视/热加载文件。原生产任务后端、Vue四页、134/268契约及真实数据配置保持独立。

本批51项新测试、179项相关测试通过（含51项），保留既有TestClient弃用警告。49项初始有效失败后实现；另复现并修复非字符串错误码和强制退出误报正常停止。实际运行4次普通python -m（一次四包服务、三次预期拒绝）及另一个受控main服务，总18次HTTP核对通过。两次服务均定时正常停止、退出0、进程回收、已验证服务句柄结束且端口关闭，39旧文件身份及目录成员保持。未知参数、缺包、占用端口均退出2且无就绪事件。实际wheel安装后模块来源、help和三资源字节验证通过；沿用已有锁定依赖，不能称异机全新环境验证。详见[实际验收](../research/2026-10-31-candidate-viewer-launcher-verification.json)。实际命令、独立守卫探针和既有浏览器验收分开记录；本批不重做全部网页交互，也不新增真实CSV、下载、真实预处理拟合、模型训练评分校准或正式实验。主数据及最终Attempted政策仍待决定，Data Gate仍BLOCKED。


独立守卫只监测另一个IF/no-source受控main，未发现模型导入/执行或生产模块导入；普通四次python -m未插桩，不将该观察外推。弱来源保持NOT_PROVIDED。启动保存关系核验允许，本批没有重新插桩HTTP文件访问，也没有重跑查看CLI、浏览器交互或导出。实际操作系统信号关闭未执行；本轮实际关闭证明来自定时器，强制状态仅单元测试。
