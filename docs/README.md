# 文档导航

## 2026-11-11 当前工程：固定人工CSV到保存结果完整复现

[运行入口](guides/release-example.md)、[固定配方设计](design/release-example-v1.md)、[实施计划](superpowers/plans/2026-11-11-release-example.md)及[验证记录](research/2026-11-11-release-example-verification.json)。create生成实际人工源、spec和recipe，后续显式使用既有raw、prepare、两IF、独立核验与只读数据服务。

完整Python4577通过／23跳过／1既有警告／56子测试，源码和实际产物独立复核通过。core/API wheel78／35成员安装120文件；一次14子进程均按预期退出、父进程0。新源47,631字节／176行，共同56、train18／cal10；预处理fit1、两IF fit／score／模型Q99各2与18次保存分数复核分列。3HTTP共49,536字节核176全轴，服务正常结束，292项及首次mtime前值保持。

初始审查失败和工具修正保留。UI未改，本轮前端／浏览器未重验；安装后wrong-valid-pair及physical broken-pipe未执行。前批16文件的准确Desktop发布与三CI成功见[回执](research/2026-11-11-release-if-result-cli-publication.json)，不覆盖本批；本批Desktop／准确新CI为PENDING_AT_SNAPSHOT。

下一只读保存预测评价当前仅私有候选与builder核对，无实现或运行。研究S2／Data Gate BLOCKED、真实C17拟合／评分／Q99及正式比较NOT_RUN，最终政策、主数据和134／268迁移不变。下文“当前／待发布”保留各轮原时点，本轮状态以上述入口为准。


## 2026-11-11 当前工程：IF 结果 CLI

[命令用法](guides/release-if-result-cli.md)、[接口协议](design/release-if-result-cli-v1.md)、[实施计划](superpowers/plans/2026-11-11-release-if-result-cli.md)与[实际验证](research/2026-11-11-release-if-result-cli-verification.json)。两条单视图 run 生成结果，独立 inspect/verify 检查保存内容与输入声明，随后复用双视图只读页面。

103 项新 CLI 单测、6 项磁盘集成与独立源码复核完成；完整 Python 4469 通过/23 跳过/1 旧警告/56 子测试。新 core wheel 76 成员、复用 API wheel 35 成员，在新 target 安装 118 文件；13 子进程实际退出符合预期，父进程 0。两条真实人工 run 的完整模型返回和六个保存文件与旧 A 基准一致，独立 inspect/verify 及 3 次 HTTP/47818 字节全部 176 行核对通过。模型 2fit/2score/2模型Q99 与另 18 次保存分数复核分开记录，受保护文件及正包已落盘初始 mtime 均保持。

前阶段结果包/网页的 26 文件已由 Desktop 发布为 `bc276bb3ea4ba57f53a773b9bdc14ad72d753d72`，准确远端和三项 CI 成功见[发布回执](research/2026-11-11-release-if-results-publication.json)；原控制器 FAIL 未擦除。该 CI 不覆盖新 CLI，本批发布为 `PENDING_AT_SNAPSHOT`。UI 未改、前端/浏览器未重复，其旧 318 项和实际浏览器证据只属于前阶段。S2/Data Gate BLOCKED，真实 C17 及正式实验 NOT_RUN，最终政策、主数据采用与生产 134/268 迁移未完成。

下文保留各轮历史范围与当时状态；新 CLI 当前进度以上述入口为准。

## 2026-11-11 前阶段工程：IF 结果保存、独立重载与只读页面

[运行入口](guides/release-if-result-package.md)、[结果包协议](design/release-if-result-package-v1.md)、[展示协议](design/release-if-result-view-v1.md)、[实施计划](superpowers/plans/2026-11-10-release-if-results.md)及[验证与失败保留记录](research/2026-11-11-release-if-results-verification.json)。两个保存视图可独立重载，固定本地服务展示保存分数、阈值、共同有效分钟和分页全轴；浏览时不训练或评分。

源码独审通过，完整 Python 回归 4360 通过/23 跳过/1 旧警告/56 子测试；前端 318 项、类型检查及构建通过。新安装两个 wheel 为 75/35 成员，安装 117 文件；两个实际人工 IF 结果、独立新进程重建、20 次 HTTP/133690 字节和 W0 实际浏览器均有证据，经单独运行后核对及独立复审接受。原控制器在正常服务完成后的全局 bind 数断言处退出 1，原整轮 FAIL 和缺失的原成功收据保持，没有重跑安装、模型或服务。

保存包成员与字节独立一致，正包初始 mtime 基线未落盘，故其独立 mtime 验证为 null；父进程精确总耗时为 null。额外 loopback 端口 0 的用途仅为来源支持的推断。完整限制见验证记录，不将人工工程接受当作真实效果通过。当前发布快照 `PENDING_AFTER_PUSH`，准确 Desktop 提交与远端 CI 另核；S2/Data Gate BLOCKED，真实 C17 fit/train/score/Q99 和正式比较 NOT_RUN，生产 134/268 未迁移。

下文为各日期历史交付范围与当时状态；当前结果保存和页面进度以上述入口为准。

## 2026-11-10 下一阶段工程：安装、浏览器与候选IF

本轮按[开发计划](superpowers/plans/2026-11-10-release-if-engineering.md)完成三项工程：新core安装后的四例配对CLI、两例输入页实际浏览器、13/26维保存输入到隔离森林的内存消费者。新IF源码独审通过，最终117专项包含在281相关中；最终源完整本地回归4067通过、20跳过、1既有TestClient警告、56子测试，范围不累加。

配对四例在新安装target退出0/0/2/2；浏览器两例及窄屏/零校准提示完成，两服务正常退出，旧失败和原INCOMPLETE_BROWSER保留。新IF在另一个新安装target对已有人工A包运行两视图，透明observer实际记录2fit/2score/2Q99，训练18、独立校准10、共同56，原输入与安装保持。详见[配对安装](research/2026-11-10-release-pair-installed-verification.json)、[浏览器补验](research/2026-11-10-release-input-browser-verification.json)、[IF工程入口](guides/release-iforest-engineering.md)及[实际验证](research/2026-11-10-release-iforest-engineering-verification.json)。

新模块的两个入口函数只给分数、报警、阈值和身份，未增加模型持久化、任务API或结果网页。后续工程先保存并独立加载新结果，再接后端只读接口与页面。真实C17数据训练、评分、阈值和正式比较仍NOT_RUN，S2/Data Gate BLOCKED；固定工程参数不代表最终研究选择或性能优势，生产134/268未迁移。

整体源码、三项修订及最终安装运行的独立复核均为spec/quality PASS。最终源修后首次私有比较器失败保留，V3仅修正比较表示并完整验收通过。本轮Desktop提交/推送和实际CI在发布快照时尚待执行；旧已发布fa6cd63不覆盖新改动。下文保留先前时点，提交自身的准确远端与CI由最终交付及工作流核对，不循环回填。

## 2026-11-10 发布补记

13文件业务提交已通过GitHub Desktop提交推送，官方远端、跟踪分支与已冻结Git字节核对一致，旧10月31日草稿未纳入。实际CI与精确提交见[发布回执](research/2026-11-10-release-model-input-pair-publication.json)；三项精确提交CI已完成并成功。下方PENDING_DESKTOP和CI NOT_RUN保留为提交前时点，不代表当前未推送；输入配对独立安装、查看页浏览器及真实模型实验仍未完成。未合并main，研究Gate保持BLOCKED。

## 2026-11-10 保存输入成对核对源码完成，查看页浏览器仍未验收

[配对入口](guides/release-model-input-pair.md)、[协议](design/release-model-input-pair-v1.md)、[验证记录](research/2026-11-10-release-model-input-pair-verification.json)。raw/prepared只读配对和薄CLI已实现，核心45与CLI100组成最终合跑145通过，两项独审PASS；两例joint使用加载器替身及真实pair/summary，追加独审PASS。源码环境四例实际人工双包CLI与97源/测试、20个原包JSON成员保全通过；独立构建安装及四例安装后CLI仍NOT_RUN，新IF未实现。

查看页新完整轮10应用、24HTTP/49912字节、3受控guard PASS/0尝试及完整保全通过，但浏览器0，原收据INCOMPLETE_BROWSER不改。旧Windows比较与今日N6插件扫描失败保留；BA/BZ补充启动被时间门拒绝，0应用/0浏览器。本批Desktop PENDING、CI NOT_RUN；S2/Gate及研究清单保持。下文为历史时点。

## 2026-11-09 输入包检查页：源码接受，实际运行验收未完成

[运行入口与限制](guides/release-input-viewer.md)、[接口协议](design/release-input-view-v1.md)、[源码与首轮失败记录](research/2026-11-09-release-input-view-verification.json)。核心118通过/37未选、后端最终201通过/1警告、前端DOM71及类型检查通过，分范围保留。首轮四个构建/安装阶段成功、8个直接Python子进程退出0并回收；整轮FAIL停于安装后Windows控制台路径/句柄执行位比较，应用案例、实际HTTP和浏览器均0，完整after-map未建立。13项窄范围比较器回归及独立审查不替代实际验收，修复后第二轮NOT_STARTED。

raw CLI已由Desktop提交推送`0f030142735028aaf27f4bc56501d8dfc1a4d0b4`，精确CI三工作流成功；仓库13、契约21、Python3517通过/70跳过/1警告/56子测试、前端147及类型/构建按job分列，不相加，也不覆盖本页。本页本批Desktop仍PENDING、新CI NOT_RUN。下方旧记录保留当时状态；研究S2/Data Gate BLOCKED、D1—D6待决，真实拟合/训练/评分/Q99/正式比较NOT_RUN。后继输入与模型成对核验仅有私有设计/计划，无实现。

## 2026-11-07 原始分钟包CLI：人工安装链本地接受

[运行指南](guides/release-minute-cli.md)、[接口与边界](design/release-minute-cli-v1.md)、[实际验证](research/2026-11-07-release-minute-cli-verification.json)。源码377通过/4跳过、独审56重叠；新安装固定八例一次通过，5普通/3受控与4安装启动分列。N3断管exit2、stderr25B且无附加诊断，stdout不可捕获；L1独立重开残留包通过。普通动作次数仅预期，受控动作格另列。

前序raw包/prepared包/input CLI共39文件已由Desktop发布`35461b9ccb964297a4a52a38dc37515c667ec237`，三项CI实际SUCCESS；该提交不包含当前raw CLI两文件。本批仍PENDING_DESKTOP，新CI NOT_RUN。view另批并行实现，尚无整批接受或页面验收。下方旧时点记录保留；真实S2/Data Gate BLOCKED、真实拟合/模型/正式实验NOT_RUN不变。

## 2026-11-07 准备输入包与三命令本地接受

[准备包指南](guides/release-input-package.md)、[精确格式](design/release-input-package-v1.md)、[包验收记录](research/2026-11-07-release-input-package-verification.json)；[CLI用法](guides/release-input-cli.md)、[CLI设计](design/release-input-cli-v1.md)、[实际退出与首轮失败](research/2026-11-07-release-input-cli-verification.json)、[实施记录](superpowers/plans/2026-11-07-release-input-cli.md)。raw/prepared及输入CLI均获本地人工工程接受，发布仍PENDING_DESKTOP、新CI NOT_RUN。

CLI最终源码118项及第二轮10个实际案例通过；首轮断管exit120保留，修复后实际exit2且错误流无附加诊断。普通8次模块命令与2个受控main探针分列，不把main返回值或旧包测试代替实际进程证据。raw CLI继续分项开发、尚未整批接受；只读view仅设计/计划接受、实现未放行。下方各日期记录保留当时状态，S2/Data Gate BLOCKED及真实拟合/模型/正式实验NOT_RUN不变。

## 2026-11-07 原始13维分钟包

[保存与独立加载](guides/release-minute-package.md)、[五文件格式](design/release-minute-package-v1.md)、[实际验收记录](research/2026-11-07-release-minute-package-verification.json)。本地人工安装往返及独立复核通过；Desktop发布待实际完成，真实数据与模型阶段不升级。

## 2026-11-07 AE容量对照页面

[运行与限制](guides/candidate-capacity-viewer.md)、[实际验证记录](research/2026-11-07-candidate-capacity-viewer-verification.json)。固定四槽和三政策保存结果；完整组与子集实际验收通过，不产生新模型或研究效果结论。

## 2026-10-31 候选查看页的前台启动命令

[本地启动说明](guides/candidate-viewer-launcher.md)、[真实启停与安装验收](research/2026-10-31-candidate-viewer-launcher-verification.json)。复用原人工包，一条命令启动独立候选查看页。

## 2026-10-31 候选合成结果的独立查看页

[候选合成结果查看页](guides/candidate-viewer.md)、[安装与浏览器验证](research/2026-10-31-candidate-viewer-verification.json)。固定候选目录、分页、曲线和13通道详情，独立于原Vue四页。

## 2026-10-31 候选合成结果的隔离只读HTTP

[候选只读HTTP](guides/candidate-readonly-http.md)、[实际HTTP/CLI验证](research/2026-10-31-candidate-readonly-http-verification.json)。固定人工结果目录、曲线和分钟详情，独立于原任务后端与Vue。

## 2026-10-31 候选结果只读查看CLI

[只读查看命令](guides/candidate-view-cli.md)、[实际验证](research/2026-10-31-candidate-view-cli-verification.json)。无需新模型运行即可查看候选人工包的分钟详情和曲线页。

## 2026-10-31 候选曲线范围分页

[范围分页接口](guides/candidate-series-pages.md)、[实际验证](research/2026-10-31-candidate-series-page-verification.json)。页面保留原无效分钟和分区断点，完整评价身份不随筛选变化。

## 2026-10-31 候选单分钟详情

[接口与限制](guides/candidate-minute-details.md)、[实际验证](research/2026-10-31-candidate-minute-detail-verification.json)。候选分钟的分数、输入、历史和标签可从同一人口的快照读取。

## 2026-10-31 候选已验证运行结果快照

[接口与限制](guides/candidate-run-snapshots.md)、[实际验证](research/2026-10-31-candidate-run-snapshot-verification.json)。已验证的候选分数文档可供分钟级消费者直接读取。

## 2026-10-30 JSON解析的单文件身份

[保证及限制](guides/json-byte-consistency.md)、[实际验证](research/2026-10-30-json-byte-verification.json)、[实施记录](superpowers/plans/2026-10-30-json-byte-consistency.md)。五类后端JSON先核取得字节再解析同对象，根manifest不作来源认证。

## 2026-10-30 Parquet解析的单文件身份

[保证及内存成本](guides/parquet-byte-consistency.md)、[实际验证](research/2026-10-30-parquet-byte-verification.json)、[实施记录](superpowers/plans/2026-10-30-parquet-byte-consistency.md)。后端三类Parquet先核取得的字节再解析同buffer。

## 最终导出字节完整性

[导出字节绑定及限制](guides/export-byte-consistency.md)、[实际验证](research/2026-10-30-export-byte-verification.json)、[实施记录](superpowers/plans/2026-10-30-export-byte-consistency.md)。三个白名单产物保留原字节，后读变化安全拒绝。

## 保存评价区间核验

[兼容边界及口径](guides/backend-interval-consistency.md)、[实际验证](research/2026-10-30-backend-interval-verification.json)、[实施记录](superpowers/plans/2026-10-30-backend-interval-consistency.md)。同一次评价核对汇总和区间，错误包安全拒绝，历史文件保持。

## 合成解释通道修复

[时间与字段绑定指南](guides/fake-channel-mapping.md)、[实际验证](research/2026-10-30-fake-channel-verification.json)、[实施记录](superpowers/plans/2026-10-30-fake-channel-mapping.md)。新合成包按显式详情匹配，旧产物不重写。

## 未报警攻击片段示例修正

[片段与FN的区别](guides/episode-display.md)、[实际验证](research/2026-10-30-episode-example-verification.json)、[实施记录](superpowers/plans/2026-10-30-episode-example-alignment.md)。仅纠正旧例子，保留原始规则与研究阻塞。

## 后端保存评价汇总修复

[核验范围与已知限制](guides/backend-evaluation-consistency.md)、[76项相关测试及三场景证据](research/2026-10-30-backend-evaluation-verification.json)、[实施记录](superpowers/plans/2026-10-30-backend-evaluation-consistency.md)。只核六项汇总，原片段差异另行追查。

## 候选IF/AE已存结果共同条件

[核对指南](guides/candidate-comparison.md)、[四包实际证据](research/2026-10-30-candidate-comparison-verification.json)、[实施记录](superpowers/plans/2026-10-30-candidate-comparison.md)。共同数据与评价人口可并列，不认证模型或判优。

## 候选AE只读结果检查

[五JSON验算入口](guides/candidate-ae-run-verification.md)、[六次实际证据](research/2026-10-30-candidate-ae-run-verification.json)、[实施记录](superpowers/plans/2026-10-30-candidate-ae-run-verifier.md)。只核存储一致性，不执行或认证模型。

## 候选AE人工链路

[当前/历史AE与JSON权重运行](guides/candidate-ae-synthetic.md)、[三次实际证据](research/2026-10-30-candidate-ae-verification.json)和[实施记录](superpowers/plans/2026-10-30-candidate-ae-synthetic.md)。仅SYNTHETIC_ONLY，原研究和生产接口不变。

## 候选IF运行只读复查

[不加载模型的五产物验算](guides/candidate-run-verification.md)、[实际证据](research/2026-10-30-candidate-run-verification.json)及[实施记录](superpowers/plans/2026-10-30-candidate-run-verifier.md)。成功仅表示存储分数/产物一致，模型来源和真实研究不因此认证。

## 候选13维IF合成运行

[运行与五产物](guides/candidate-if-synthetic.md)、[实际阈值/分母/漏报与测试记录](research/2026-10-30-candidate-if-verification.json)。当前只有SYNTHETIC_ONLY工程演练，真实模型/正式实验NOT_RUN，Data Gate BLOCKED。

## 候选产物消费接缝

[不可变快照接口](guides/candidate-snapshots.md)、[实际验证](research/2026-10-30-candidate-snapshots-verification.json)及[第三批计划](superpowers/plans/2026-10-30-candidate-verified-snapshot.md)。同次读取、实际值保留、数组和元数据隔离已经验证；独立候选13维IF尚未实现，真实Gate仍BLOCKED。

## 自主开发第二批入口

[候选产物只读复查](guides/candidate-artifacts.md)、[实际验证](research/2026-10-30-candidate-artifacts-verification.json)及[实施记录](superpowers/plans/2026-10-30-candidate-artifact-verifier.md)。人工产物三政策有/无源6次复查通过；保存参数不重新拟合，缺源不冒称核验。真实Gate仍BLOCKED。

当前自主迭代：[源记录到分钟整链](guides/candidate-records.md)、[具体有限试点建议](research/2026-10-30-limited-pilot-proposal.md)、[10月30日合成证据](research/2026-10-30-candidate-records-verification.json)。仅工程SYNTHETIC_ONLY，真实Gate仍BLOCKED；下方保留前批与真实审计入口。

最近开发：[候选13/26输入计算](guides/candidate-inputs.md)、[自主实施计划](superpowers/plans/2026-10-29-candidate-inputs.md)、[合成数值证据](research/2026-10-29-candidate-inputs-verification.json)。10月29日程序与人工验证完成；真实审计结果及其研究边界见下方，Data Gate仍BLOCKED。

最近真实审计入口：[G13U获准发布记录供应复算](research/2026-10-24-c17-g13u-audit.md)、[完整聚合](research/2026-10-24-c17-g13u-audit.json)、[获准审计与历史交接](guides/c17-g13u-supply.md)。10月28日已完成本地真实复算：共同开发资格150/88/148、测试1831分钟，供应仍有限；最终标签政策、主数据采用和生产迁移未批准，真实模型及正式实验NOT_RUN。原G12失败证据逐字保留。

修订2026-10-30；用途：当前公开材料与版本对应。报告/答辩均为草稿，待审阅；没有最新稿确认记录。公开文本对应同版本本地原稿，私人路径映射保留本地。

## 当前材料

历史设计记录：[CICIDS2017候选与论文要求对照](research/2026-10-23-cicids-suitability-analysis.md)。当时给出150/90/150理想上界；现已由G12失败证据和本轮G13U实际150/88/148供应补充，未替代数据采用决定。

历史来源记录：[GitHub数据检索与镜像元信息](research/2026-10-23-github-dataset-search.md)。该次只核元信息；随后C17-I1获准获取作者修订版，本轮只复用本地载荷，未改变正式选型或Gate。

历史入口核查：[C17官方入口、生成版本及既有C18-S一致性](research/2026-10-23-c17-source-metadata.md)。原官方归档身份待确认，不与后续实际获取的作者修订版混同；该次无新增载荷或Gate升级。

设计与获取历史：[C17-G12决定包](project/CANDIDATE-DATA-DECISION-2026-10-23.md)、[C18-S四前缀16MiB核查](research/2026-10-23-c18-structure-sample.md)。当前[文件与资源清单](research/2026-10-23-candidate-manifest.json)已登记C17-I1获取及G13U复算，供应审计完成；主数据采用、最终标签和生产迁移仍待决定。

方向选择历史：[协议三路径与决定](project/RESEARCH-PROTOCOL-OPTIONS.md)、[增量证据与候选筛选](research/2026-10-22-data-gate-evidence-update.md)。C方向与G13U审计设计已获准，具体主数据/表示正式采用仍待决定。

Data Gate当前判定见[Gate记录](project/DATA-GATE-2026-10-21.md)的2026-10-28 G13U条目及[决定记录](project/DECISIONS.md)的2026-11-06补录；下一步研究决定见[试点就绪复核](research/2026-11-06-pilot-readiness-review.md)D1—D6与[有限试点建议](research/2026-10-30-limited-pilot-proposal.md)。[G13U指南](guides/c17-g13u-supply.md)保留获准审计方法和10月28日交接；[早期preflight](guides/real-validation-preflight.md)仅作历史准备记录，不恢复旧下载、原UGR或G12阻塞为当前G13U结论。

当前程序见[合成快速运行](guides/quickstart.md)、[W0联调记录](project/W0-SYNTHETIC-INTEGRATION-2026-10-21.md)和[UGR16v3证据核验](research/2026-10-21-UGR16v3-provenance.md)。

| 用途 | 入口 | 状态 |
|---|---|---|
| 开发执行 | [并行开发计划V1.0](superpowers/plans/2026-10-21-parallel-development.md) | 依据V0.40；主控＋三个worktree已交付并顺序合成集成；真实Gate仍阻塞 |
| 开题报告 | [报告V0.40](reports/开题报告-V0.40-公开文本.md) | 公开正文抽取版；草稿，待评审 |
| 报告学习 | [V0.40学习与答辩准备手册](reports/开题报告-V0.40-学习与答辩准备手册.md) | 对应54页Word V1.1，保留原基础内容，新增十图深讲与80项追问 |
| 简短文献综述 | [综述V1.0](reports/时间感知网络流量异常检测文献综述-V1.0.md) | 约千字正文，6篇参考文献 |
| 答辩内容 | [答辩V0.24](reports/开题答辩-V0.24-公开文本.md) | HIT模板；16页主讲＋9页隐藏备用；实际排练待开展 |
| 讲述准备 | [V0.24逐页讲述](reports/开题答辩-V0.24-公开文本.md) | 包含逐页讲稿；实际时长另行登记 |
| 后续工作 | [项目规划](project/ROADMAP.md) | 真实数据Gate阻塞；合成系统已联调，真实训练与实验NOT_RUN |
| 当前进度 | [状态源](project/status.json) | 验收及证据；README由此生成 |
| 范围/风险 | [差异](project/DECISIONS.md) · [风险](project/RISKS.md) | 待对齐不当作已确认 |
| 维护证据 | [复核日志](project/MAINTENANCE_LOG.md) | 本地与远端检查分开 |
| 配图规范 | [项目作图规范](baseline/00-规范与模板/项目作图规范.md) | 沿用项目配色、字体、层级及导出检查 |
| 文字规范 | [报告与 PPT 文字规范](project/WRITING_STYLE.md) | 默认成稿检查，保留事实和学校模板 |
| 当前图形源 | [图集说明](figures/README.md) | V4.0/V5.0保留，新增V6.0技术架构与流程八图 |

## 前期设计基线

以下材料保留当时版本和状态，不自动覆盖最新报告中的方案。后续实现前应核对新报告与旧需求、HLD和验收矩阵的差异。

- [项目立项与需求分析V0.1](baseline/01-项目立项与需求分析/01-项目立项与需求分析-V0.1.md)
- [研究内容与技术方案V0.1](baseline/02-研究与技术方案/02-研究内容与技术方案-V0.1.md)
- [系统概要设计V0.2](baseline/03-系统概要设计/03-系统概要设计-HLD-V0.2.md)
- [实验设计与验收V0.2](baseline/04-实验与验收/04-实验设计与验收方案-V0.2.md)
- [数据需求与数据集设计V0.1](baseline/05-数据设计/05-数据需求与数据集设计-V0.1.md)
- [项目计划与风险V0.2](baseline/06-项目计划与风险/06-项目计划与风险管理-V0.2.md)
- [需求追踪矩阵V0.2](baseline/02-需求分析/D02A-需求追踪矩阵-V0.2.md)

## 研究资料

- [文献与项目调研](research/2026-10-08-毕设相关开源项目与论文调研.md)
- [网络AI与概念漂移文献](research/2026-10-08-literature-network-ai.md)
- [数据集与综述资料](research/2026-10-08-literature-data-surveys.md)
- [时间序列方法资料](research/2026-10-08-literature-foundations-ts.md)

归档文档中的Wiki Links属于本地知识库引用，未在此复制个人知识库。Office/PDF及未审查图片的链接改为文字说明；正文抽取版的图号应配合独立图集阅读。


- [答辩V0.11：15页，恢复V0.32完整配图](reports/开题答辩-V0.11-公开文本.md)

- [开题报告V0.35：恢复V0.32完整配图](reports/开题报告-V0.35-公开文本.md)

- [开题报告V0.36：收缩研究范围与技术细节](reports/开题报告-V0.36-公开文本.md)

- [开题报告V0.37：保留原图与正文简化](reports/开题报告-V0.37-公开文本.md)

- [答辩V0.12：HIT模板与V0.38报告同步](reports/开题答辩-V0.12-公开文本.md)

- [答辩V0.13：开发方案占70%的三分钟版](reports/开题答辩-V0.13-公开文本.md)
- [图集V8.0：结构与视觉优化](figures/V8.0/README.md)

- [答辩V0.14：从需求到联调的开发说明](reports/开题答辩-V0.14-公开文本.md)

- [答辩V0.15：十分钟开题版与计算机专业答疑](reports/开题答辩-V0.15-公开文本.md)

- [答辩V0.16：三分钟八页主讲与六页备用](reports/开题答辩-V0.16-公开文本.md)

- [答辩V0.17：观点与方法版，8页主讲与6页备用](reports/开题答辩-V0.17-公开文本.md)

- [答辩V0.18：本科目录、研究基础与答疑准备](reports/开题答辩-V0.18-公开文本.md)

- [答辩V0.19：场景需求、方法选择与研究论证](reports/开题答辩-V0.19-公开文本.md)

- 上一轮同步材料：[开题报告V0.40](reports/开题报告-V0.40-公开文本.md)、[答辩V0.20与讲稿](reports/开题答辩-V0.20-公开文本.md)、[最小修改记录](reports/开题材料-V0.40-V0.20-最小修改记录.md)。

- 当前答辩版本：[V0.21一图一页版及讲稿](reports/开题答辩-V0.21-公开文本.md)、[拆页记录](reports/开题答辩-V0.21-拆页记录.md)；配套[报告V0.40](reports/开题报告-V0.40-公开文本.md)。

- 当前答辩版本：[V0.22长版分项汇报与讲稿](reports/开题答辩-V0.22-公开文本.md)、[结构与版本记录](reports/开题答辩-V0.22-结构与版本记录.md)；配套报告仍为V0.40。

- 当前答辩版本：[V0.23业务问题与研究主线与讲稿](reports/开题答辩-V0.23-公开文本.md)、[结构与版本记录](reports/开题答辩-V0.23-结构与版本记录.md)；配套报告仍为V0.40。

- 当前答辩：[V0.24公开文本](reports/开题答辩-V0.24-公开文本.md)、[版本记录](reports/开题答辩-V0.24-结构与版本记录.md)。

## 最新有界载荷核查

- [C18-S四前缀16MiB：实际获取、字段、时间与标签](research/2026-10-23-c18-structure-sample.md)：仅结构样本，不认证四段供应，不采用2018为主数据。
