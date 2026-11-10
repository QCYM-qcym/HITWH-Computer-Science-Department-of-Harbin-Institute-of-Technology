# IF 结果命令行：生成、检查与输入绑定

日期：2026-11-11。状态：命令实现、独立源码复核、完整 Python 回归及新安装人工验收已接受。实际 13 个子进程、两条模型 run、独立 inspect/verify 和既有 API 兼容检查见[本阶段验证记录](../research/2026-11-11-release-if-result-cli-verification.json)。接口与范围分别见[冻结协议](../design/release-if-result-cli-v1.md)和[实施计划](../superpowers/plans/2026-11-11-release-if-result-cli.md)。此前结果包/网页及其原控制器失败属于[上一阶段](../research/2026-11-11-release-if-results-verification.json)，原失败保持；其真实发布与 CI 见[前阶段发布回执](../research/2026-11-11-release-if-results-publication.json)。

本入口提供三个命令：`run` 从一对保存输入计算一个视图并保存结果；`inspect` 单独检查结果包；`verify` 再提供原输入核对声明绑定。当前验收只安排已知人工输入。真实数据研究仍处于 S2 / Data Gate `BLOCKED`，真实 C17 拟合、训练、评分、Q99 和正式比较保持 `NOT_RUN`。

## 环境与目录

使用已安装 core 及其锁定依赖的 Python 3.14 环境。`run` 还需要既有固定 IF 所用的 `scikit-learn==1.9.1` 及其依赖；模型按需加载。`help`、`inspect`、`verify` 不要求 sklearn 模型依赖，后两项仍会通过 core 检查保存分数的 Q99 一致性。

下面所有 `ABS_...` 都须替换为本机绝对目录。原始包与准备包须是已经保存、可成对核验的输入。两个输出分别为尚不存在的新目录，其父目录必须已存在且为普通本地目录。输出不能等于任何输入目录，不能位于输入内部，也不能成为输入的祖先；可使用独立输出父目录下的两个相邻子目录。路径不接受相对路径、`..`、链接/reparse 或不受支持的非本地形式。

CLI 的路径预检不提前创建或保留目标；若预检后另一进程抢先创建目标，最终排他保存仍拒绝覆盖，此时模型可能已经计算完成。不要把预检当作目录锁。

## 1. 两条命令分别生成视图

```text
python -m traffic_anomaly.release_if_result_cli run --raw-package ABS_RAW_DIR --prepared-package ABS_PREPARED_DIR --view current13 --output ABS_NEW_CURRENT_RESULT_DIR
python -m traffic_anomaly.release_if_result_cli run --raw-package ABS_RAW_DIR --prepared-package ABS_PREPARED_DIR --view h30_26 --output ABS_NEW_H30_RESULT_DIR
```

每条 `run` 只计算一个视图，具有独立的目标和退出状态；第一条成功不保证第二条成功。固定 IF 配置沿用[内存接口](release-iforest-engineering.md)，不增加调参选项。成功状态为 `SAVED`，其含义是本次调用已执行模型并完成结果保存；结果包自身的模型历史执行仍不作认证。

训练正常资格为零时返回 `NO_TRAINING_NORMAL`，独立校准正常资格为零时返回 `NO_CALIBRATION_NORMAL`。不要通过修改标签、挪分段或把未评分分钟改成正常来绕过这些条件。视图只接受 `current13` 或 `h30_26`，不能用命令参数批准真实数据研究。

## 2. 在新进程中单独检查结果

```text
python -m traffic_anomaly.release_if_result_cli inspect --result-package ABS_CURRENT_RESULT_DIR
python -m traffic_anomaly.release_if_result_cli inspect --result-package ABS_H30_RESULT_DIR
```

此时无需原始包或准备包。成功状态为 `INTERNAL_CONSISTENCY_CHECKED`，表示三个结果文件的字节引用、结构、人口、保存阈值与预测关系符合结果格式。未评分行保留为 `None`，不能当作正常负例。包的具体结构和局限见[结果包指南](release-if-result-package.md)。

## 3. 显式提供输入核对绑定

```text
python -m traffic_anomaly.release_if_result_cli verify --result-package ABS_CURRENT_RESULT_DIR --raw-package ABS_RAW_DIR --prepared-package ABS_PREPARED_DIR
python -m traffic_anomaly.release_if_result_cli verify --result-package ABS_H30_RESULT_DIR --raw-package ABS_RAW_DIR --prepared-package ABS_PREPARED_DIR
```

成功状态为 `INPUT_BINDING_MATCHED`。命令实际加载三个包并核对输入配对，再检查完整身份、配置、分段、共同评分掩码及三个样本索引的声明关系。它不重放预处理、不重新拟合 IF 或重新评分，也不能认证源流量、正常资格、保存数值派生或历史模型执行。一个内部合法结果包单独 `inspect` 成功，与它能否绑定本次显式输入是两个问题。

## 4. 用既有只读服务查看两包

在具备 backend 依赖的环境中，把上述两个结果目录交给现有入口：

```text
python -m traffic_api.release_if_result_serve_cli --current-dir ABS_CURRENT_RESULT_DIR --h30-dir ABS_H30_RESULT_DIR --port 8768 --serve-seconds 300
```

该服务在监听前重新检查两包及其共同输入关系，固定只监听 `127.0.0.1`，使用实际 `SERVER_READY` 输出的地址打开页面。浏览期间不训练或评分。服务的独立双图、全轴分页、时间语义和有限前台运行限制见[结果查看指南](release-if-result-package.md)。本阶段没有修改网页，旧网页成功不计作新 CLI 运行成功。

## 回执与失败处理

三条业务命令成功时退出 0，只向 stdout 写一份规范 UTF-8 JSON，末尾一个 LF，含换行不超过 65,536 字节，stderr 为空。完整顶层字段如下；此表是协议说明，没有填写虚构的实测身份或阈值。

| 字段 | 含义 |
|---|---|
| `version`、`command`、`status` | 版本 1、所执行命令及其固定成功状态 |
| `result_identity`、`input_references` | 结果与原始/准备输入的完整四字段身份 |
| `view`、`threshold`、`configuration_sha256` | 保存视图、原有限阈值与准备配置摘要 |
| `counts` | `total`、`scored`、`training`、`calibration`、`preprocessing_fit` 五类整数人口 |
| `checks` | 内部一致性、保存分数 Q99、显式输入绑定、来源与模型执行认证范围 |
| `operations` | `model_fit_score`：run 为 `PERFORMED`，inspect/verify 为 `NOT_PERFORMED`，仅描述本次调用 |

`input_pair_binding` 在 run/verify 为 `MATCHED`，在 inspect 为 `NOT_PERFORMED`。来源和模型执行认证均保持 `NOT_AUTHENTICATED`。保存分数 Q99 算术复核与模型阶段阈值计算分别记账，不能把只读复核说成新训练。

失败或中断退出 2，stderr 尽力写固定 `{"error":"CODE"}` 加一个 LF，不回显本机路径、异常原文或 traceback。单独运行 `python -m traffic_anomaly.release_if_result_cli --help` 可查看帮助，不加载输入或模型；混用子命令与 help、重复选项、未知参数及非法 view 均被拒绝。

输出已存在时为 `OUTPUT_EXISTS`，与输入重叠时为 `INVALID_PATH_LAYOUT`。保存中途失败会保留已创建的残留，不自动清理、覆盖、重试或续跑。save 成功之后也可能因回执编码、stdout 短写或 flush 失败返回错误；stdout 可能已有部分甚至完整内容，它不是提交标记。先对目标运行独立 `inspect`，再区分有效包与不完整残留，不要直接重跑同一个输出目录。

本命令不输出逐分钟数组、标签、源路径或权重，也不提供最终政策、主数据采用或生产 134/268 迁移。未报警不等于正常标签；通过内部核验和输入声明绑定不构成误报率、漏报率或模型有效性结论。

## 本阶段实际验证

103 项新 CLI 单测与 100 项既有相邻单测合跑 203 项通过；另有 6 项真实磁盘集成通过，其中两项在数值计算边界使用手工分数替身，不能计作真实模型运行。最终完整 Python 回归为 4,469 通过、23 跳过、1 项既有 TestClient 警告、56 个子测试，277.00 秒。各切片包含在完整范围内，不相加。

新 core wheel 为 76 个成员，复用经逐成员核对的 35 成员 API wheel，安装到一个新 target 共 118 文件；依赖复用已有锁定环境。两条实际 run 各使用同一已接受人工 A 输入，完整模型返回在 make 前留存；两个新包的全部六个文件字节、身份及完整结果与旧 A 基准一致。两视图各 176 分钟、共同评分 56、未评分 120、训练 18、独立校准 10、预处理拟合 18。

真实模型阶段合计 2 次 fit、2 次 score_samples、2 次模型阈值 Q99。另有 18 次保存分数 Q99 复核：run 4+4、inspect 1+1、verify 2+2、服务启动前 4；三个负例均为 0。这些复核与模型阈值计算分开记账。两项 inspect 和两项 verify 分别在新进程执行，完整回执与保存身份一致。

13 个直接子进程退出依次为 0/0/0/0/0/0/0/0/0/2/2/2/0，全部回收且无强制、重试。help 是普通模块命令；其他产品命令通过透明观察器执行实际公开模块，物理退出独立记录，不把受控 runpy 调用冒称普通 shell 模块启动。父进程实际退出 0，单独 caller 回执绑定本轮 acceptance 摘要；父进程记录的 40.0882121 秒截止到最终收据组装，不是外层退出总时长。

既有 API 的 30 秒服务正常 READY→STOPPED、退出 0，3 次 HTTP 共 47,818 字节，摘要及全部 176 行与新保存包一致，端口关闭已记录。观察到配置端口 8769 和 loopback 端口 0 两次 bind，后者用途仍只作来源支持的推断。前端与浏览器本阶段没有改动或重复运行，原 318 项前端及实际浏览器证据单列保留。306 个受保护项及新正包的成员、字节、哈希和已落盘初始 mtime 均核对保持。

实际安装的错误合法输入绑定反例未执行：既有另一组 Z 校准为 0，不能充作合法 IF 输入；精确反例由源码手工磁盘集成覆盖。安装后物理断管同样 `NOT_RUN`，源码 main 的流故障与可重载残留测试不替代它。本 CLI 批次的 Desktop/准确远端 CI 为 `PENDING_AT_SNAPSHOT`，不使用前阶段提交的 CI 代替，也不循环回填当前尚未产生的提交号。
