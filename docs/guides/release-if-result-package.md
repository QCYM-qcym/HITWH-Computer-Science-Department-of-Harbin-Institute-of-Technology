# 隔离森林结果保存与只读查看

日期：2026-11-11。当前状态：结果包、独立加载、双视图后端和页面已完成源码实现与复核；已观察的人工安装、保存、独立重载、HTTP 和实际浏览器功能经单独运行后核对及独立复审后接受。原控制器在服务完成后的全局 bind 数断言处退出 1，原整轮仍为 FAIL，并未改成成功或另跑一轮。详见[验证与失败保留记录](../research/2026-11-11-release-if-results-verification.json)。格式见[结果包设计](../design/release-if-result-package-v1.md)，展示接口见[只读展示设计](../design/release-if-result-view-v1.md)，实施范围见[本阶段计划](../superpowers/plans/2026-11-10-release-if-results.md)。

本入口将已产生的 `current13`、`h30_26` 隔离森林结果保存为两个独立结果包，随后可在新进程中加载并查看。查看阶段消费保存分数、阈值、预测和时间轴，不重新训练或评分。当前用途为人工工程验证；S2 / Data Gate 仍为 `BLOCKED`，真实 C17 拟合、训练、评分、Q99 和正式比较仍为 `NOT_RUN`。

当前还可使用新增的[结果 CLI](release-if-result-cli.md)，通过两条单视图 run 生成包，再在独立进程 inspect 或显式 verify，随后接入本页既有服务。新 CLI 的人工安装与 3 次 HTTP 兼容验收见[独立记录](../research/2026-11-11-release-if-result-cli-verification.json)，不重写下方结果包/网页阶段的原控制器失败。结果包阶段 26 文件已由 Desktop 发布并核对准确远端及 CI，见[发布回执](../research/2026-11-11-release-if-results-publication.json)；下文各数量和运行限制保留该阶段原范围。

当前完整 Python 回归为 4,360 通过、23 跳过、1 项既有 TestClient 警告和 56 个子测试；前端 8 个文件共 318 项通过，类型检查与构建通过，保留既有 Vite 分块体积警告。初次完整回归发现资源清单不符合既有显式打包规则，改为逐个列出三个页面资源后重跑通过。各专项计数包含在相应完整范围内，不累加。

## 保存已产生的结果

前置环境与固定 IF 调用见[保存输入到隔离森林](release-iforest-engineering.md)。下面的 `pair` 是已验收原始包与准备包的配对对象，`result` 是由同一 `pair` 产生的某一个视图结果。示例只保存已有对象，不启动模型。

```python
from pathlib import Path
from traffic_anomaly.release_if_result_contract import (
    make_release_if_result_package,
)
from traffic_anomaly.release_if_result_package import (
    save_release_if_result_package,
)

package = make_release_if_result_package(pair, result)
saved_identity = save_release_if_result_package(
    package, Path("ABS_NEW_RESULT_DIR")
)
```

将 `ABS_NEW_RESULT_DIR` 替换为一个尚不存在的绝对目录，其父目录必须已存在。每个目录只保存一个视图；两个视图分别调用一次并保存到不同新目录。函数返回保存包的身份，不写模型权重或原始输入矩阵。已有目录不会覆盖，失败残留不会自动删除或重试。

结果包恰有三个文件：

| 文件 | 内容 | 字节上限（含末尾换行） |
|---|---|---:|
| `result.json` | 全轴分数、预测、共同评分掩码、保存阈值及三类样本索引 | 1,048,576 |
| `manifest.json` | 输入身份、源钟面分段、视图与模型配置、结果字节引用 | 65,536 |
| `COMPLETE.json` | 清单字节引用；最后写入 | 4,096 |

合计上限 1,118,208 字节，轴长为 1—10,000 分钟。完整格式使用规范 UTF-8 JSON、固定字段和 SHA256 引用。`COMPLETE.json` 的存在不单独代表有效，加载时仍须检查全包。写入使用排他创建和读回核对，不提供事务原子性或掉电持久性保证。

## 新进程加载及可选配对核对

只查看结果时，不需要重新打开原始输入包或运行 IF：

```python
from pathlib import Path
from traffic_anomaly.release_if_result_package import (
    load_release_if_result_package,
)

loaded = load_release_if_result_package(Path("ABS_EXISTING_RESULT_DIR"))
identity = loaded.identity
context = loaded.context
result = loaded.result
checks = loaded.load_report
```

`result.scores`、`result.predictions`、`result.scored_mask` 保留全轴顺序；未评分行的分数和预测均为 `None`，分数 `0.0` 与预测 `False` 则保留原值。`train_indices`、`calibration_indices`、`preprocessing_fit_indices` 分别记录模型训练、独立校准和预处理拟合人口；三者不能互换，`role=train` 也不表示该分区每行都参与模型训练。

加载器检查三个实际文件的完整成员集合、有限读取、字节引用和结果内部关系，并按保存校准分数复核固定线性 Q99。复核阈值算术与重新选择阈值、训练模型、重新评分分别记录。报警规则保持保存分数严格大于阈值；等于阈值不报警。

若调用方还持有一个经过现有入口核验的输入配对，可显式核对其声明：

```python
from traffic_anomaly.release_if_result_contract import verify_release_if_result_pair

verify_release_if_result_pair(loaded, pair)  # 成功返回 None
```

该函数对照完整输入身份、配置、分段、共同评分掩码和三类索引，不隐式读取外部原包。独立加载只证明保存字节与内部关系符合本格式；不能证明源数据真实、正常资格真实、分数确由 IF 产生或输入数值推导正确。自洽改写内容与哈希仍可形成另一个合法包。来源与模型执行认证继续为 `NOT_AUTHENTICATED`。

## 启动双视图结果页

在同时具备 core、backend 及其锁定依赖的环境中运行：

```text
python -m traffic_api.release_if_result_serve_cli --current-dir ABS_CURRENT_RESULT_DIR --h30-dir ABS_H30_RESULT_DIR --port 8768 --serve-seconds 300
```

两个目录参数必填并须替换为绝对目录；`--current-dir` 对应 `current13`，`--h30-dir` 对应 `h30_26`。两包必须具有相同的完整输入身份、配置身份、源语义、全轴分段、共同评分掩码和三类索引，不能仅凭相同长度或人数配对。视图、输入宽度、各自分数及阈值可以不同。

`--port` 可省略，默认 8768，允许 1—65535；`--serve-seconds` 可省略，默认 300，允许 1—300 秒。固定监听 `127.0.0.1`，前台运行；不会自动打开浏览器。启动前各加载一个结果包，完成包检查、两视图核对及所有响应编码后才监听。单独运行 `--help` 不加载结果。

启动后使用 `SERVER_READY` JSON 中的 `url`，默认地址为 `http://127.0.0.1:8768/release/results`。正常计时停止输出 `SERVER_STOPPED` 并退出 0；错误通常输出固定 JSON 错误码并退出 2。应同时核对实际进程退出与端口关闭，不能仅凭启动事件认定整次成功。

页面显示两张摘要卡、各自使用独立纵轴的分数图与保存 Q99 线，以及共用的 100 行分页表。表格保留原全轴索引、源钟面、分区、未评分行和两个视图的保存预测。相等和严格超过阈值的摘要计数仅统计校准分钟，不是全轴或当前页报警数。未评分原因未随结果保存，页面据实显示“未评分，包内未保存具体原因”。

时间轴采用 `SOURCE_WALL_CLOCK_COMPLETION_PROXY`，不自动转换为已认证 UTC；政策保持 `AUDIT_ONLY`。未报警不等于正常标签，保存报警也不是误报或漏报判定。页面不提供标签指标、训练、参数搜索或政策选择。

## API 与限制

| Python 入口 | 返回值 / 用途 |
|---|---|
| `make_release_if_result_package(pair, result)` | `ReleaseIFResultPackage`；核对显式配对声明并构造结果包 |
| `save_release_if_result_package(package, output_directory: Path)` | `ReleaseIFResultIdentity`；排他保存到新目录 |
| `load_release_if_result_package(directory: Path)` | `ReleaseIFResultPackage`；独立读取三个文件并核验 |
| `verify_release_if_result_pair(package, pair)` | `None`；显式核对与输入配对的一致性 |
| `create_release_if_result_view_app(current13, h30_26)` | `FastAPI`；模块 `traffic_api.release_if_result_view`，接纳两个包对象，启动前冻结只读响应 |

固定 GET 入口如下；没有目录浏览、任意文件路径或 OpenAPI 页面：

| 路径 | 内容 |
|---|---|
| `/release/results` | 结果页面 |
| `/release/results/results.mjs` | 本地脚本 |
| `/release/results/results.css` | 本地样式 |
| `/release-if/v1/summary` | 全轴身份、人口、阈值、分段与检查范围 |
| `/release-if/v1/series?page=0` | 从 0 开始、固定每页 100 行的全轴结果 |

页号范围为 `0` 至 `page_count-1`；省略 `page` 等价于 0。只接受唯一的规范十进制页号，拒绝重复或额外查询键。其他四个入口不接受非空查询。summary 上限为 16,384 字节，每页上限为 131,072 字节，三个静态资源各上限 65,536 字节；启动前全部冻结内容上限为 16 MiB。这些是应用级边界，不是 OS 配额或连续峰值测量。

正常 HTTP 请求只发送启动前保存的响应字节，不加载包、校准、拟合或评分。页面用同一 10 秒期限限制请求和响应读体，核对结构、身份快照与分页关系；失败时提供显式重试。身份快照 SHA256 绑定两个结果包声明身份，不能认证来源或模型执行。

## 本轮实际验收与保留限制

本轮在新 target 安装了新 core/API wheel，分别为 75/35 个成员，安装共 117 个文件；依赖复用已有锁定环境。两个实际人工 IF 视图各保留 176 分钟、共同评分 56、未评分 120、模型训练 18、独立校准 10、预处理拟合 18。模型返回的全部结果字段在打包前留存，再与保存包及独立新进程重建结果按规范字节核对一致。两阈值为 0.5634703452851734 和 0.5734566900037，均通过保存校准分数与严格预测关系核验。

模型阶段实际观察到 2 次 fit、2 次 score_samples 和 2 次模型阈值 Q99。producer 的 8 次保存分数 Q99 复核、reader 的 2 次复核，以及 CLI 启动前的复核另计，不能写成整轮总共只有 2 次 Q99。20 次手工 HTTP 请求共 133,690 字节，摘要、全部 176 行及三个静态资源与保存包/安装字节一致；浏览器请求未计量，单独记录。实际浏览器核对双卡、独立图尺度、分页 0→1→0、原索引 100、未评分断点、元信息与 390×844 窄屏键盘横滚，未据此声称命中 BFcache。

九个直接子进程实际退出依次为 0/0/0/0/0/0/2/2/0，全部回收且未强制终止。两负例在监听前拒绝；正向服务正常输出 READY→STOPPED，实际运行约 300.737 秒、退出 0，原控制器记录退出后端口关闭。观察到配置服务端口 8768 的一次 bind 和另一次 loopback 端口 0 bind，后者与锁定 Windows asyncio 自管道实现相容的解释仅属来源支持的推断，没有运行时调用栈认证。原控制器因要求全局只有一次 bind 而失败；独立复审接受已取得的有限功能证据，原 FAIL、退出 1 和缺失的原整轮成功收据均保留。运行后核对没有重复安装、模型、服务器、HTTP 或浏览器。

受保护源码、原输入、复制源、wheel 和安装文件的字节与保留时间基线均独立核对。正向结果包的成员、字节和哈希也独立一致；其初始 mtime 树仅在原控制器内存中，原 guard 为 true，但留存材料不能独立重验该时间对照，故独立 mtime 验证为 null。原父进程精确总耗时同样为 null，不由子进程耗时相加推算。限额与观测不代表 OS 配额或连续峰值监控。

本结果包阶段的原发布快照为 `PENDING_AFTER_PUSH`；后续已完成 Desktop 提交/推送及准确远端 CI，详见上述发布回执。新增 CLI 的本批发布仍另行核对，不用旧提交 CI 替代。真实研究准入仍以[统一 Data Gate](../project/DATA-GATE-2026-10-21.md)和当前协议决定为准，生产 134/268 维契约未迁移。
