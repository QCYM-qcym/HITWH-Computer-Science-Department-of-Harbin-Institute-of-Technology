# 原始13维分钟包：保存与独立加载

日期：2026-11-07。状态：本地联合测试、第二次安装人工往返及独立运行证据复核已通过；本批Desktop提交、推送与新CI待完成。用途是保存已经聚合完成的分钟结果，保留无效分钟、独立标签和诊断，供另一个进程重开。详见[格式设计](../design/release-minute-package-v1.md)、[实际验证记录](../research/2026-11-07-release-minute-package-verification.json)和[实施计划](../superpowers/plans/2026-11-07-release-minute-package.md)。

## 可以使用的接口

核心包提供两个纯编解码函数和两个文件接口：

```python
from pathlib import Path
from traffic_anomaly.release_minute_contract import (
    encode_release_minute_package,
    decode_release_minute_package,
    ReleaseMinutePackageError,
)
from traffic_anomaly.release_minute_package import (
    save_release_minute_package,
    load_release_minute_package,
)

def persist_completed_result(minutes, segments, output_directory: Path):
    # minutes须为已有完整ReleaseMinuteResult，segments为明确登记的元组。
    # output_directory须是本机绝对路径，其父目录存在，目标目录尚不存在。
    identity = save_release_minute_package(minutes, segments, output_directory)
    reopened = load_release_minute_package(output_directory)
    assert reopened.identity == identity
    return reopened
```

这段示例展示实际函数签名；调用方仍需提供已经完成且获准使用的结果。新包不打开CSV、不重新聚合、不拟合参数、不生成历史输入或调用模型，也没有新增CLI/HTTP命令。既有[文件适配](release-file-adapter.md)的结果可由受控本地程序交给保存函数；当前实际接缝验收只使用当轮新造的人工91列文件。

纯`encode`返回五个固定文件名和bytes组成的元组；`decode`只接受精确的内置dict、固定五个str键及bytes值。返回`ReleaseMinutePackage`包含identity、minutes、segments、scope；内部为冻结值和元组。加载后读取属性不再打开路径，普通复制包或加载后移动专用副本不会改变已返回值。

## 五个成员与保证范围

| 成员 | 内容 |
|---|---|
| minutes.json | 完整登记分钟轴、段序号、有效掩码与原始13维值；不含标签 |
| labels.json | P_U/P_B/P_A三政策标签、计数与原始标志的分钟级描述 |
| diagnostics.json | 全局和逐桶记录、排除原因、协议通道及计数 |
| manifest.json | 固定协议、特征顺序、来源声明、分段及前三成员实际大小/SHA-256 |
| COMPLETE.json | 最后写入的完成标记，绑定manifest实际大小/SHA-256 |

profile固定`c17-release-minute-package-v1`，范围为`PACKAGE_INTERNAL_CONSISTENCY_ONLY`。来源始终`NOT_AUTHENTICATED`，时间始终`SOURCE_WALL_CLOCK_COMPLETION_PROXY`：无时区源钟面及流完成代理，不认证UTC、真实导出时刻或完整网络采集。

三项数据文件各不超过8MiB，manifest不超过64KiB，完成标记不超过4KiB，全包不超过20MiB；最多10000个登记分钟、7段、5个声明来源。源字节/记录数的结构上限只定义能表达的结果，不授权读取这些规模的数据。文件按规范UTF-8紧凑排序JSON编码、末尾一个LF；重复键、未知字段、非有限值、错误维度、额外成员和不一致身份均拒绝。

无效分钟的13值全为null，不是正常零向量；仍可保留eligible记录数。例如无法定位的坏时间记录会使所有登记分钟无效，已有合格记录不因此清零。空桶只能表示采集情况未确认，不能当作已确认无流量的正常分钟。Protocol0仍是未解析源协议记录，不能称合法物理协议；其他非法或不支持码按原规则排除。标签与特征分离，三种Attempted政策只是审计对照，没有最终标签决定。

同一来源声明和内容的内部关系可校验；完全自洽重写会得到另一身份并仍可加载。这不认证作者、源解析实际执行、物理记录真实性或研究批准，也不能把新包传入旧SYNTHETIC_ONLY记录、输入或模型入口。

## 路径、失败和残留

保存先完整校验和编码，再独占新目录；已有空目录也拒绝，不覆盖。五文件逐个独占写入、回读核字节，COMPLETE最后写。加载先核本机绝对路径和普通祖先，拒绝链接/reparse、非普通或多硬链接成员，核精确成员集合、实际大小与读取前后身份；解码使用本次取得的同一bytes。

这不承诺跨文件原子快照、断电耐久或恶意并发不可规避。失败保留现场、不自动重试或清理；标记写入后的晚期失败可能留下能够独立加载的一致包。应分别记录“保存调用成功返回”和“后来加载成功”，不能仅凭COMPLETE存在宣称前者成功。

安装后实际拒绝结果为：缺完成标记`INVALID_PACKAGE`、成员字节变更但未重签`INTEGRITY_MISMATCH`、多出成员`INVALID_PACKAGE`、输入为普通文件`INVALID_PACKAGE_PATH`、已有空输出目录`OUTPUT_EXISTS`。库异常消息只含固定code；调用方应将code投影为对外错误，未捕获的Python堆栈不保证脱敏。

## 实际验证与限制

最终联合切片收集715项，705通过、10跳过，耗时10.74秒，覆盖本批纯契约、存取、独立手算和既有解析/聚合相关检查；不与各work此前局部计数相加。保留两次联合runner准备失败（长参数ID、仓库导入根）及修正记录。文件测试中原“ancestor”误把目录自身链接当中间祖先，已改名并补真正祖先分支；本机三种真实符号链接创建均因权限不足跳过，不能称链接拒绝断言已实际通过。10项联合跳过不全是这三项，新CI须按实际平台再看。

最大结构实测：10000分钟、7个最长Unicode段名及5个声明源的有效构造为4791175字节；全域污染无效构造为3881186字节。两者均逐成员往返一致，未生成250万CSV行。这些是人工结构观测，不是内存硬配额或所有合法形状均可保存的证明。

第二次验收在源码外新目录离线构建147364字节wheel，61个包成员与冻结源码字节一致；源清单另含pyproject，共62项。使用既有锁定依赖环境，不是全新依赖安装或异机复验。5个人工CSV共17条记录、11164字节，四例各完成一次显式聚合与保存，另进程加载原包和普通复制包，完整字段与保存前独立dataclass投影比较，另核W3手算字段；五个负例分别执行。四个load进程的人工CSV打开次数均为0，返回值在专用副本移动后保持。

| 人工例 | 原始记录/eligible/排除 | 登记分钟/有效分钟 | 覆盖内容 |
|---|---|---|---|
| A | 6/6/0 | 4/3 | 变值分位、三政策、未知及空桶 |
| B | 2/1/1 | 4/0 | 无法落桶记录的全域污染，eligible保留 |
| C | 5/1/4 | 4/1 | 跨源重复、未支持协议及区间外记录 |
| D | 4/2/2 | 6/1 | 相邻分段边界、跨段记录与登记缺口 |

首次构建因pip子进程尝试未授权派生进程而`FAILED_GUARD`；虽已产生wheel，安装和人工案例均未执行。原失败、冻结和脚本保留。源码路径与pip可选rustc版本探测吻合，但首次未捕获运行时调用栈，不写成已观察到完整调用链。

后续只在离线pip进程中进行两项明确适配：导入时暂跳urllib3 IPv6探测并恢复socket标志；暂跳一次可选rustc元数据查找并恢复模块绑定。普通进程缓存保留该离线结果，网络/派生进程拒绝守卫不放宽，未修改第三方安装文件。构建后端仍由父进程逐个登记、限时和回收。因此这里是经过适配的离线pip验收，不能描述为未改运行行为的pip。

联合测试守卫仅覆盖pytest当前进程，记录的3次子进程不自动继承它。安装与13个人工案例/负例进程另有实际守卫和退出收据；所观察范围是Python打开、SQLite连接、导入、网络与派生进程事件，不认证native I/O、所有文件系统事件或操作系统隔离。独立复核的17个受控子进程均退出0、回收、无强停和违规事件；最终任务目录1907904字节。源、原包、安装及夹具的前后身份保持；未打开旧模型包或真实数据。

本批raw13验收快照没有接入预处理、13/26历史准备、模型或网页。收口时，主控已接受下一批prepared-input精确设计和实施计划，W1/W2/W3开始有界人工工程实现；其安装、A9/A10实际验收尚未放行，不列入本批通过结果。真实预处理拟合、模型训练/评分/Q99校准、正式比较和生产134/268迁移仍NOT_RUN；S2 Data Gate BLOCKED。Desktop提交、远端同步与新CI分别核对，不以基点CI替代本批发布结果。

主控已接受冻结的raw13本地字节。下一批已接受的prepared-input设计与实施计划依该本地基点推进；Desktop交互恢复前发布继续PENDING_DESKTOP，不替代提交方式。该顺序调整仅针对本地工程，研究批准不变，见[工程决定](../project/DECISIONS.md)。
