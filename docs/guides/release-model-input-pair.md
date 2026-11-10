# 保存输入成对核对入口

2026-11-10 安装验收补记：独立 core wheel 构建、新目标安装及四例安装后人工双包 CLI 均 PASS；独立审查的 spec 与 quality 均 PASS，主控已接受这项工程验收。源码与源码环境证据见[原验证记录](../research/2026-11-10-release-model-input-pair-verification.json)，本次安装事实及限制见[安装验证记录](../research/2026-11-10-release-pair-installed-verification.json)。

新 wheel 实测72成员、新安装75成员，其中产品 Python 文件68个；RECORD、产品源字节、安装元数据和新目标导入来源均已核对。构建、安装、来源探针与四例共7个进程自然退出并回收，实际退出码依次为0/0/0/0/0/2/2。A/Z成功输出与旧独立期望逐字节相等；身份错配及缺COMPLETE两例的安全错误字节与退出码亦相符。97份受保护源/测试、20个原人工JSON及既有负例保持；这不表示核对了全仓库所有测试。

本次复用既有pip、setuptools和运行依赖，只独立安装core，不能作为全新依赖环境证明。普通CLI无动态动作监控；不调用prepare/replay/fit/聚合/模型是已审调用链结论。整轮收据记录4.8059563秒，最终新增文件观察为3,314,603字节，后者不是连续峰值。复制源初态mtime仅在运行器内存中，未独立落盘；源、副本、wheel及安装产品的实际字节核对成立，但不能事后用两份持久快照独立比较副本初态mtime。页面浏览器验收另项记录，本安装验收不提升其状态；S2/Data Gate仍BLOCKED，真实处理/拟合、训练/评分、Q99及正式实验仍NOT_RUN。下列午前记录及当时NOT_RUN状态原样保留；本次安装结果不覆盖历史失败或收据。

**午前历史记录（以下为安装验收前快照）：**

日期：2026-11-10。状态：源码与限定单测完成；核心与CLI及两例joint追加独审均PASS，主控已接受源码，安装配对验收待完成。源码环境四例实际人工双包CLI已通过；独立构建安装及四例安装后CLI仍NOT_RUN。详见[协议](../design/release-model-input-pair-v1.md)与[验证记录](../research/2026-11-10-release-model-input-pair-verification.json)。

模块入口如下，两个参数填写既有原始分钟包和对应准备包的绝对目录；此处是用法，不是本轮实际执行记录：

```text
python -m traffic_anomaly.release_model_input_cli --raw-package ABS_RAW_DIR --prepared-package ABS_PREPARED_DIR
python -m traffic_anomaly.release_model_input_cli --help
```

两个参数支持空格或等号形式，不接受未知、重复、缩写参数或响应文件形式。`run=@daily`作为普通目录值保留。help必须独立使用。加载要求由既有包加载器执行，CLI不扫描来源或解析CSV。

成功输出一行`INPUTS_PAIRED`摘要，包含两包身份、配置身份、13/26列序、六类有效分钟计数及攻击存在计数、预处理fit人口、模型训练/校准人口、三政策八类资格和未执行声明。零校准人口不等于已经校准；内部对齐不认证来源或真实模型执行。错误仅输出安全代码，返回2；输出失败不重试。

最终源码合跑145项通过/0.23秒，核心45（含两例加载器替身、真实pair/summary联合测试）与CLI100为组成分项，旧143不累计。源码环境四例实际人工双包CLI已通过：A/Z完整输出与旧独立保存期望逐字节相等，人口分别为176/56/18/18/10及32/2/2/2/0（总/common/fit/train/校准）；身份错配与缺COMPLETE分别安全退出2。97源/测试和20个既有人工JSON成员及负例副本前后保持。普通命令未动态插桩，禁动作未调用仅按已审调用链预期。

另有help、未知参数、help破管3个源码环境smoke进程，实际退出0/2/2并自然回收。它们与四个双包数据例、145单测及完整合成回归分别记录，不相加；数据载荷输出破管、独立构建安装及四例安装后CLI仍NOT_RUN。

输入查看页另有一次完整安装运行：10应用、24HTTP与完整保全通过，但实际浏览器0，收据保持`INCOMPLETE_BROWSER`。两个900秒浏览器补充服务只准备和短审，启动尝试因时间门拒绝，无新目录、应用或页面观察。旧Windows句柄比较失败和今日N6插件扫描失败均保留。它们与本成对核对模块的源码测试分开登记。

本批发布PENDING_DESKTOP，CI NOT_RUN。主控已接受源码环境四例；下一步为独立构建安装、四例安装后CLI及页面验收，本轮尚未完成。S2/Data Gate BLOCKED，真实fit/train/score/Q99及正式实验NOT_RUN；新IF尚未实现。

发布补记：13文件业务提交已通过Desktop推送并核对官方远端；最新实际CI及提交见[发布回执](../research/2026-11-10-release-model-input-pair-publication.json)。上段PENDING_DESKTOP/CI NOT_RUN保留提交前时点，不将发布视为安装、页面或研究验收通过。
