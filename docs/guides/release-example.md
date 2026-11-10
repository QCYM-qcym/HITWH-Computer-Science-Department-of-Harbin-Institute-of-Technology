# 从固定人工 CSV 复现 release 工程链

日期：2026-11-11。状态：源码、完整Python回归及14阶段新安装人工链已经独立复核并接受；本批Desktop与准确新CI仍待核。实际范围见[验证记录](../research/2026-11-11-release-example-verification.json)。接口和固定配方见[设计](../design/release-example-v1.md)，任务边界见[实施计划](../superpowers/plans/2026-11-11-release-example.md)。

本入口生成 91 列、176 行人工 CSV，以及可供现有聚合命令直接读取的配置和配方说明。后续每步显式运行已有命令：CSV → 原始分钟包 → 准备输入 → 两个 IF 结果 → 独立核验 → 只读页面。旧的 [candidate demo](candidate-demo.md) 仍有自己的复现入口；本文对应新的 release 包格式。

所有记录均按固定配方人工构造。`create` 不读取外部数据，也不聚合、拟合预处理、训练、评分或启动服务。研究仍处于 S2 / Data Gate `BLOCKED`；真实 C17 训练、评分、阈值校准及正式比较为 `NOT_RUN`。本示例中的 P_U 和 epsilon 只用于人工工程审计。

## 环境和新目录

按[开发环境说明](development.md)准备 Python 3.14 和项目锁定依赖，并安装包含本入口的 core。两条 IF `run` 还需要现有固定 IF 的 `scikit-learn==1.9.1` 及其依赖；最后的页面服务需要 backend。本文不增加依赖、安装器或自动训练脚本。

在 PowerShell 中，把以下两个占位符改成自己的绝对路径。`$exampleParent` 必须是已存在的普通本地目录；下面各个子目录须尚不存在。各目标互为相邻目录，不放进源目录或其他包内部。

```powershell
$python = '<ABSOLUTE_LOCKED_PYTHON>'
$exampleParent = '<EXISTING_ABSOLUTE_PARENT_DIRECTORY>'
$source = Join-Path $exampleParent 'release-artificial-source'
$spec = Join-Path $source 'aggregate-spec.json'
$scratch = Join-Path $exampleParent 'release-artificial-scratch'
$raw = Join-Path $exampleParent 'release-artificial-raw'
$prepared = Join-Path $exampleParent 'release-artificial-prepared'
$current = Join-Path $exampleParent 'release-artificial-current-result'
$h30 = Join-Path $exampleParent 'release-artificial-h30-result'
```

逐步运行。每条命令结束后检查实际退出码和回执；遇到非零退出就停止后续步骤，保留已有文件。一个步骤成功不保证下一个步骤成功。

## 1. 创建人工源与真实摘要配置

```powershell
& $python -m traffic_anomaly.release_example_cli create --output $source
```

成功时退出 0，stderr 为空，stdout 为一份 `status=CREATED` 的 JSON。新目录恰有以下三份文件：

| 成员 | 内容与身份 |
| --- | --- |
| `artificial.csv` | UTF-8、无 BOM、LF；固定表头和 176 条人工流记录 |
| `aggregate-spec.json` | 指向本次实际 CSV 的绝对路径、字节数和 SHA256；含四段源钟面边界及有界聚合预算 |
| `recipe.json` | 人工配方、来源和时间语义说明；CSV 的字节数、SHA256 与行数 |

回执 `files` 中的字节数和 SHA256 来自实际写入后读回的成员。CSV 和 recipe 在不同输出根中保持相同内容；spec 含实际绝对路径，因此可随输出位置改变。移动 CSV 后，旧 spec 的路径也随之失效；不要只移动文件后继续使用旧配置。

配方没有随机数，也不接受外部标签、特征或配置覆盖。每个注册分钟恰有一条人工流，开始于秒 10、持续 1 秒。四段为源钟面半开区间：

| 角色 | 起点 | 终点 | 人工行数 |
| --- | --- | --- | ---: |
| 训练 | `2026-01-01T00:00:00` | `2026-01-01T00:48:00` | 48 |
| 验证 | `2026-01-01T01:00:00` | `2026-01-01T01:40:00` | 40 |
| 独立校准 | `2026-01-01T02:00:00` | `2026-01-01T02:40:00` | 40 |
| 测试 | `2026-01-01T03:00:00` | `2026-01-01T03:48:00` | 48 |

未注册的间隔不会补成正常分钟。Protocol0 保留在独立 U 通道；测试段包含明确攻击、合法 Attempted 和人工未知标签。它们在模型运行前已经固定，不按检测结果修改。未使用字段的 0 是人工占位，不能解释为真实捕获测量值或旧 134 维补零。

## 2. 用现有命令聚合

```powershell
& $python -m traffic_anomaly.release_minute_cli --spec $spec --scratch $scratch --output $raw
```

成功退出 0 且回执 `status=SAVED` 后，再继续。该步骤独立读取真实 CSV，核对声明的字节数、SHA256 和流末尾，保存五文件原始分钟包。回执还报告实际记录数、分钟数和 scratch 清理状态。正常完成时 scratch 目录已清理；出现失败时保留现场，不自动重试或删除残留。详细边界见[原始分钟 CLI](release-minute-cli.md)。

## 3. 显式拟合人工预处理与历史输入

```powershell
& $python -m traffic_anomaly.release_input_cli prepare --raw-package $raw --output $prepared --epsilon 0.000001 --audit-fit-policy P_U
```

这一步才实际拟合训练正常候选的预处理参数，并生成 H15、H30 和共同有效掩码。每段独立预热，历史不跨分段或缺口。P_U 将合法 Attempted 作为 unknown；三个现有标签映射仍保存用于审计，`policy_status=AUDIT_ONLY`。此处选择不能当作最终研究政策批准。

供给计数应读取本次真实回执或保存输入；不要套用其他人工包的旧计数。prepare 的训练资格和模型的训练人口见[输入 CLI](release-input-cli.md)及[只读输入配对](release-model-input-pair.md)。

## 4. 分别生成两个固定 IF 视图

```powershell
& $python -m traffic_anomaly.release_if_result_cli run --raw-package $raw --prepared-package $prepared --view current13 --output $current
& $python -m traffic_anomaly.release_if_result_cli run --raw-package $raw --prepared-package $prepared --view h30_26 --output $h30
```

两条命令各计算一次对应视图并独立保存结果，成功状态均为 `SAVED`。先确认第一条成功再运行第二条。固定 IF 没有新增调参选项；阈值仅由本次独立校准正常资格计算。每段预热或未知标签的处理不能靠修改测试标签绕过。详细配置及命令说明见[IF 工程接口](release-iforest-engineering.md)和[结果 CLI](release-if-result-cli.md)。

## 5. 在独立进程核验保存结果

```powershell
& $python -m traffic_anomaly.release_if_result_cli inspect --result-package $current
& $python -m traffic_anomaly.release_if_result_cli inspect --result-package $h30
& $python -m traffic_anomaly.release_if_result_cli verify --result-package $current --raw-package $raw --prepared-package $prepared
& $python -m traffic_anomaly.release_if_result_cli verify --result-package $h30 --raw-package $raw --prepared-package $prepared
```

inspect 只需结果包，成功为 `INTERNAL_CONSISTENCY_CHECKED`。verify 额外读取原始和准备包，成功为 `INPUT_BINDING_MATCHED`。二者检查保存分数的阈值一致性，均不重新训练或评分。字节完整性和输入声明绑定只说明内部一致性；来源、真实数值派生及历史模型执行仍不作认证。

## 6. 使用有限前台服务查看

```powershell
& $python -m traffic_api.release_if_result_serve_cli --current-dir $current --h30-dir $h30 --port 8768 --serve-seconds 300
```

服务固定只监听 `127.0.0.1`，在监听前冻结两包的页面数据。用实际 `SERVER_READY` 回执给出的地址打开页面。该命令的服务计时配置为 300 秒；实际进程耗时还包括启动和停机回收，按 `SERVER_READY`／`SERVER_STOPPED` 及实际退出记录核对。网页请求不训练或评分。完整分钟轴中的未评分值保留为空，与未报警的 false 分开显示。分页和双图说明见[结果包与页面](release-if-result-package.md)。

## 失败与证据范围

create 只接受单独的 `--help` 或上述 create 命令。目标已存在时返回 `OUTPUT_EXISTS`；排他创建和成员写入均不覆盖现有内容。中途失败会保留部分或完整成员，回执输出失败也可能留下完整三文件。recipe 只描述配方，不是完成标记；stdout 可能已有部分内容，应结合实际退出和独立文件检查记录失败，不能据此自动续跑。

create 回执不包含绝对路径、CSV 正文或模型指标。人工源的信任与时间说明位于 `recipe.json` 和 create 回执；原始分钟包、准备包及结果包在各自上下文保留 `NOT_AUTHENTICATED` 和 `SOURCE_WALL_CLOCK_COMPLETION_PROXY`。这里的钟面未被认证为官方数据 UTC。人工链可以验证文件格式、窗口、保存身份和服务兼容，不能产生真实网络误报率、漏报率、模型优劣或跨网络泛化结论。

最终两项源码集成各实际执行 create、CSV 聚合和人工预处理，2 项通过，0.62 秒，无警告；IF 入口和 sklearn/torch/joblib 导入处于禁止守卫下。每个新 CSV 实测 47,631 字节、91 列、176 行，SHA256 均为 `e11538582584118e8d0e94605d8136ee09de9485e5a9420853f1cd9b57af11da`。源配置声明、实际 raw source 身份和包成员摘要分别核对一致，正常 scratch 清理完成。

新配方的实测有效分钟为 176，H15 为 116，H30 和共同有效分钟均为 56；四段共同有效数依次为 18、10、10、18，训练与预处理拟合各 18、独立校准 10。源协议计数为 TCP 59、UDP 57、U 60，无排除记录。测试共同资格的正常/攻击/未知数分别为 P_U 的 15/1/2、P_B 的 16/1/1、P_A 的 15/2/1；它们是标签与供给计数，没有计算误报、漏报或模型效果。

首次联调曾因测试将 eligible 四通道计数误写成 raw 五通道形状而出现 1 通过、1 失败。核对既有契约后只修正本测试期望，原失败保留，未修改生产实现。上述最终源码集成成功记录独立于那次失败。随后的一次新安装完整链已接受，范围如下；本轮浏览器未重验，HTTP与浏览器证据分开。

## 本轮实际新安装验收

新core wheel的78个成员与复用API wheel的35个成员，经CRC、RECORD和产品字节核对后安装到新目录，共120文件。依赖复用既有锁定虚拟环境，本轮未新建虚拟环境或进行异机恢复。

一次实际链包含build／install、普通模块help及11个透明观察下的业务阶段，共14个直接子进程。唯一预期负例是对同一源目录再次create，退出2／OUTPUT_EXISTS且不调用builder；其余13阶段退出0。全部子进程回收，无强制终止或重试，父进程实际退出0。父计时43.742104秒记录到最终收据组装，区别于子进程耗时之和。

| 核对范围 | 实际结果 |
| --- | --- |
| 人工源与供应 | 47,631字节／91列／176行，源摘要、raw身份及前述H15／H30／标签资格一致 |
| 预处理 | prepare及fit统计各1次，transform1次，H15与H30各1次 |
| 两个IF视图 | fit、score、模型阈值Q99各2次，完整返回在make之前落盘，保存与独立重载逐值一致 |
| 保存分数检查 | 另18次Q99：run各4、inspect各1、verify各2、server4；观察器回调的独立重载单列 |
| HTTP与关闭 | summary及两页共3次／49,536字节，覆盖176分钟；服务实际31.116297秒并正常退出、记录端口关闭 |
| 保存及安装保护 | 292项保护和五类正产物的首次成员／字节／SHA／mtime前值均落盘并独立复证 |

模型结果、HTTP及binary64阈值严格核对。独立预处理均值／总体标准差使用1e-12容差，最大差8.88e-16；按保存状态重建变换与median／MAD历史的最大差为0。运行时核对实际float32模型输入行选择，没有另存逐值调用矩阵，独立复核范围据此限定。

资源原观察4,606,604字节，范围是任务递归文件加准备目录顶层，未含准备嵌套归档，非整个工作区、连续峰值或OS硬配额。构建stderr有123字节的两条byte-compiling disabled提示；除它和预期负例外，其他12阶段stderr为空。额外127.0.0.1:0绑定的用途仅为推断。

源码初审的错误码读取中断，以及私有快照只绑定一项已审文件的缺口，均保留原FAIL，失败回归和独立复审后通过。相邻旧结果CLI只修同类安全出口，模型数值、参数及格式未改；原269基线留存，268项未变，唯一旧源码变更单独登记。一次静态harness目录setup错误和一次只读reader的histories格式误读亦保留；后者修工具后未重跑业务。当前一次实际完整链为PASS且没有failure.json，与这些早期失败及旧A父FAIL分开。

源码环境closed-stdout真实退出2且完整三文件保留；安装后physical broken-pipe及另一合法pair绑定负例仍NOT_RUN。UI和后端未改，本轮未重跑前端或浏览器；完整Python4577通过／23跳过／1既有警告／56子测试，范围与局部测试重叠。S2／Data Gate继续BLOCKED，主数据、最终政策及真实试点依原决定处理。

前批IF命令准确Desktop提交和三项成功CI见[发布回执](../research/2026-11-11-release-if-result-cli-publication.json)，不覆盖本批新增代码。本批发布及新CI在当前快照为PENDING_AT_SNAPSHOT。
