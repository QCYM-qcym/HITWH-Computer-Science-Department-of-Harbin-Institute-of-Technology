# 时间语义与连续性复核

访问/核查日期：2026-10-21。Work B与主控只读既有载荷。**绝对时区、DST规则和v3专用分钟桶端点仍UNVERIFIED**；未添加Z或用本机时区解释真实时钟。

## 证据层次

| 项目 | 已有证据 | 限制 |
|---|---|---|
| obs_l/obs_lt、CSV Row | 全量为12位YYYYMMDDHHmm字符串，日历往返一致 | 不是epoch；没有偏移或时区 |
| 分钟粒度 | [正式派生论文§2.2](https://digibug.ugr.es/bitstream/10481/102834/1/data-10-00033.pdf)与[DMP §2.1](https://codas.ugr.es/animalicos/doc/deliverable3.pdf#page=3)说明一分钟聚合 | 不足以证明本次生成链的时区/端点 |
| classM/classMt | 全量等于hour×100+minute，即HHMM整数编码 | **不是午夜后累计分钟数**；01:00为100不是60，不用于间隔计算 |
| classD/classDt、classWD/classWDt | 与源字符串日期YYYYMMDD、工作日1/周末2逐行一致 | 是相同钟面的派生字段，不是独立时区证明 |
| X/Y的时间基准 | 两CSV时间键及MAT轴逐行相同 | 文件连接可信；上游是否用相同flow时间字段/桶端点仍缺生成配置 |
| 通用FCParser | [固定源码normalize_timestamps](https://github.com/josecamachop/FCParser/blob/959c10679eefcd9479aa8522b63dc054ac5e05cd/bin/fcparser.py)在window=1时将second置0并输出12位标签 | 该通用实现对应分钟桶起点；未证明此提交及配置生成了当前v3，不能升级为v3起点已确认 |
| 原始流时间字段 | [原始论文§IV-D](https://nesg.ugr.es/nesg-ugr16/dataset_AuthorVersionFinal.pdf)描述公开流CSV的te为流结束时刻 | 原始流字段不能自动继承为v3聚合字段 |

官方固定树未包含v3专用nfdump命令、FCParser配置、时区环境或删行表。[通用TimeVariable](https://github.com/josecamachop/FCParser/blob/959c10679eefcd9479aa8522b63dc054ac5e05cd/bin/faac.py)及[示例配置](https://github.com/josecamachop/FCParser/blob/959c10679eefcd9479aa8522b63dc054ac5e05cd/example/config/netflow.yaml)不带时区，不能据此认定UTC或Europe/Madrid。原站/PDF部分访问403、MDPI429；原论文时间说明采用同一第一方URL索引，通用源码与DMP已直接读取；派生论文机构PDF由Work C直接核对。

## 原始钟面连续性

| 项目 | 作者训练范围 | 作者测试范围 |
|---|---:|---:|
| 唯一保留分钟 | 72,644 | 27,697 |
| 首尾含端点钟面分钟 | 106,560 | 43,154 |
| 间断/缺少钟面分钟 | 850 / 33,916 | 1,354 / 15,457 |
| 连续钟面区段 | 851 | 1,355 |
| 最长连续区段 | 4,855 | 3,337 |
| 重复/原序逆序 | 0 / 0 | 0 / 0 |
| H15/H30纯连续性位置，不看标签 | 65,192 / 62,569 | 22,512 / 20,679 |

训练/测试时间键交集为0，两范围之间相隔82,127钟面分钟，不连接历史。2016-03-27 01:59下一条为03:00，与某些DST跳变兼容，也与删行兼容；**不能据此选时区或扣除60个缺测分钟**。所有数量均为钟面差，不冒充实际UTC经过时间。缺口不填零，不声称每个缺口都是采集失败或无流量。

## 代码复现与修复

- 原始`...00.000000001Z`被datetime丢失精度后误收为整分钟。现在解析前检查非零小数，拒绝1ns等输入；不静默取整。
- 同一瞬时的Z与+01:00写法、其余字段相同，旧实现按原始dict比较而误判冲突。现在按统一时间键与其余载荷判重复，保留原始时间文本；真正不同特征/标签仍拒绝。
- NumPy ns可对公元2500回绕。该读取样例原先被后续整分钟检查拒绝，不能称已绕过审计；但旧split_minutes确实静默转换越界边界。新增共享显式UTC/范围/往返检查，在读取分组和切分前拒绝越界。
- 规范CSV排序原先丢失“原序逆序”事实。现审计保留原始轴并报告original_reverse_steps；排序、去重和历史重置规则保持。

当前未发现使用机器本地时区的隐式转换。真实provider审计仍保留原钟面并报告source_timezone=null。Windows验证环境没有IANA tzdata，未声称已实测民用时区DST动态路径；若后续证据指定IANA时区，应锁定对应依赖并补gap/fold测试，不能先给真实数据选择Madrid。

## 可做与仍阻塞

原始文件时间键连接、钟面排序、格式及保守缺口重置可核查。绝对UTC瞬时、DST附近实际间隔、UTC四段切分、真实H分钟认证及按UTC日/ISP民用时段解释仍受阻。源字符串工作日只能称源钟面日历，不能当独立业务日证据。未将未知钟面注册进真实pipeline。见[统一判定](../project/DATA-GATE-2026-10-21.md)。
