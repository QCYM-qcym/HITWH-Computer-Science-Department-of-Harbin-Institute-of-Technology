# 原始分钟包 CLI 使用与验收边界

日期：2026-11-07。状态：**固定人工安装链已本地接受，Desktop发布待完成**。示例未在本次文档维护中执行；下面的已运行结果来自单独冻结的实际验收。完整格式见[设计](../design/release-minute-cli-v1.md)，事实记录见[验证JSON](../research/2026-11-07-release-minute-cli-verification.json)。

## 准备输入

使用项目锁定的Python3.14环境和包含本CLI的核心包。提供已获准使用的人工CSV及其已登记字节数/SHA，不用占位值运行。spec须UTF-8无BOM；其中source路径、spec路径、scratch和output均为绝对本机路径，两个输出位置不能已存在或互相嵌套，父目录必须已存在。

下面仅表示格式，尖括号占位需替换，bytes须改为实际整数；它不是可直接执行的配置，也不授权读取真实CSV：

```json
{
  "version": 1,
  "sources": [{
    "path": "<ABSOLUTE_ARTIFICIAL_CSV_PATH>",
    "bytes": "<REPLACE_WITH_REGISTERED_INTEGER_BYTE_COUNT>",
    "sha256": "<REPLACE_WITH_REGISTERED_LOWERCASE_SHA256>"
  }],
  "segments": [{
    "id": "artificial-train",
    "role": "train",
    "start": "2026-01-01T00:00:00",
    "end": "2026-01-01T00:32:00"
  }],
  "budget": {
    "max_total_source_bytes": 1048576,
    "max_rows": 512,
    "max_database_bytes": 8388608,
    "max_elapsed_seconds": 30,
    "max_minutes": 240
  }
}
```

源内容SHA在reader一次消费时校验；CLI没有额外预哈希。来源身份仍NOT_AUTHENTICATED，时间仍是SOURCE_WALL_CLOCK_COMPLETION_PROXY。三种Attempted映射均仅作审计对照，spec不能选择最终政策或改变特征维度。

## 命令与后续输入准备

在既有获准运行目录中设置下列变量，确认三个目标路径与运行相符后调用；以下仅为文档示例：

```powershell
$python = '<ABSOLUTE_LOCKED_PYTHON>'
$spec = '<ABSOLUTE_SPEC_JSON>'
$scratch = '<NEW_ABSOLUTE_SCRATCH_DIRECTORY>'
$raw = '<NEW_ABSOLUTE_RAW_PACKAGE_DIRECTORY>'
& $python -m traffic_anomaly.release_minute_cli --spec $spec --scratch $scratch --output $raw
```

只有实际进程成功退出0且stdout为SAVED才把该命令记为成功。返回的manifest身份、实际源身份及计数应进入独立运行记录，完整结果在五文件包中。scratch须已清理；失败时保留现场，不手动以同一路径自动重试。

raw成功后可以显式串联已接受的[输入CLI](release-input-cli.md)，它才承担人工预处理与历史计算：

```powershell
$prepared = '<NEW_ABSOLUTE_PREPARED_PACKAGE_DIRECTORY>'
& $python -m traffic_anomaly.release_input_cli prepare --raw-package $raw --output $prepared --epsilon 0.000001 --audit-fit-policy P_U
& $python -m traffic_anomaly.release_input_cli inspect --prepared-package $prepared
& $python -m traffic_anomaly.release_input_cli verify --prepared-package $prepared --raw-package $raw
```

P_U、epsilon1e-6及上述32分钟分段是已登记人工验收方案，不是最终真实研究政策或最优参数。inspect只加载检查；verify显式重放保存参数，不重新fit。不要把人工示例改指真实CSV后启动模型或拟合。

## 故障解释

| 返回情况 | 处理与证据边界 |
| --- | --- |
| INVALID_ARGUMENTS / INVALID_SPEC | 校对显式参数、字段、类型和预算；不接受缩写或未知字段 |
| OUTPUT_EXISTS | 输出必须全新，空目录也不能接管；保留已有包 |
| INVALID_PATH_LAYOUT | 核同父实体别名、嵌套及源/spec布局，不只比较字符串 |
| SOURCE_SIZE_MISMATCH / SOURCE_HASH_MISMATCH | 声明与实际输入不一致，保留失败并核对象身份；不自动换源 |
| SCRATCH_CLEANUP_FAILED | 聚合未满足正常关闭/清理门槛，不继续save，CLI不删除残留 |
| OUTPUT_ERROR | 输出失败，可能已经保存完整包或发送部分字节；不能当成功或自动覆盖 |
| INTERRUPTED / INTERNAL_ERROR | 中断/未知错误以安全码返回，不公开内部堆栈 |

实际返回码、完整stderr、目录成员及独立加载是不同证据。源码中已实现有限退出期描述符处理，本轮raw CLI已另行新安装验证N3实际exit2；它不是任意资源/第三方退出路径的保证，也不能因input CLI历史通过而省略独立证据。

## 当前完成和实际运行

源码最终377通过/4跳过；独审56项与其重叠。两项实际8.3别名通过，四项symlink创建不可用而跳过；reparse注入不等于真实reparse实体。首次DB下限测试错误及修正保留：实际数据库12288字节合法，预算最小可声明65536不是实际占用下限。

两次人工CSV聚合共64行/两次save；另12次人工值对象保存加载独立计数，无CSV/聚合。它们是源码接缝测试；下列为另外一次新安装的八例实际验收，无补跑：

| 例 | 已登记目标 | 实际状态 |
| --- | --- | --- |
| R1 | 普通模块聚合保存 | PASS；exit0，stdout902B |
| N3 | 普通模块无读端管道，保留完整raw包 | PASS；exit2，stdout不可捕获，stderr25B |
| L1 | 独立受控加载R1及N3残留，核手算值/身份 | PASS；exit0，raw_load=2 |
| P1 | 普通输入CLI prepare | PASS；exit0，stdout2317B |
| I1 | 受控输入CLI inspect，仅加载 | PASS；exit0，stdout2340B |
| V1 | 受控输入CLI verify，保存参数重放、无refit | PASS；exit0，stdout3304B |
| N1 | 普通raw CLI拒绝已有输出 | PASS；exit2，stderr26B |
| N2 | 普通raw CLI拒绝缺少必填参数 | PASS；exit2，stderr30B |

实际为5个普通模块进程、3个受控leaf，加4次构建安装启动；父进程exit0，12子进程自然回收，无强停/超时/清理错误。普通5例未profile；两次聚合/64行/raw save2次/人工fit1次仍按固定调用链预期记录。R1实际reader打开1次，N3打开1次仅为预期，不能从不可捕获stdout推断已观测。

L1实际raw_load=2；I1仅prepared_load=1；V1 prepared_load/raw_load/verify/upstream_bind/transform各1、history=2，三个探针fit均0，不能推广为整个含P1 prepare的运行没有拟合。三个探针的文件读/写分别159/2、163/2、171/2，不是零I/O。

实际保存值与预登记手算一致：32个有效raw分钟、H15为17、H30/common为2、fit索引30/31及人口2；三政策训练资格各2，其余校准/验证/测试资格均0，预热保留null/warmup。该包只有人工训练段，没有阈值校准或效果评价，不能把零校准写作FPR=0。

安装65产品文件与66复制源前后保持，7份生成metadata仅核当前集合；20个旧JSON包保持。验收观察任务目录2216896B、最大日志17157B、R1数据库12288B均在固定监督预算内；属于此次人工观察，不是OS/RSS硬限或在线性能证据。

前序raw包、prepared包和input CLI共39文件已由Desktop发布至35461b9ccb964297a4a52a38dc37515c667ec237，三项CI实际成功；该提交排除了当前raw CLI两文件，不覆盖本批安装验收。本批提交、推送和新CI均待实际完成。Data Gate仍BLOCKED，真实模型与正式实验NOT_RUN。
