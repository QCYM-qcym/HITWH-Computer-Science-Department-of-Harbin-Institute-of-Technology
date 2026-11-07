# 准备输入包命令行使用

日期：2026-11-07，Asia/Shanghai。三命令已通过本地人工安装验收，发布PENDING_DESKTOP、新CI NOT_RUN。首轮断管失败保留，第二轮修复后接受，不称自动重试成功。

入口：[接口设计](../design/release-input-cli-v1.md)、[实际验证](../research/2026-11-07-release-input-cli-verification.json)、[准备包说明](release-input-package.md)、[原始分钟包](release-minute-package.md)。

## 三个命令

先由调用者设置人工验收范围内的绝对本机目录变量：$RawPackage为已有raw包，$PreparedPackage为不存在的新输出目录；$AuditEpsilon为显式正有限数，$AuditFitPolicy为P_U/P_B/P_A之一。下面是使用模板，文档维护时没有执行；它们不授权真实输入读取或拟合。使用本项目已验证安装环境的Python。

```powershell
python -m traffic_anomaly.release_input_cli prepare --raw-package "$RawPackage" --output "$PreparedPackage" --epsilon "$AuditEpsilon" --audit-fit-policy "$AuditFitPolicy"
python -m traffic_anomaly.release_input_cli inspect --prepared-package "$PreparedPackage"
python -m traffic_anomaly.release_input_cli verify --raw-package "$RawPackage" --prepared-package "$PreparedPackage"
```

prepare确实拟合预处理并计算当前13与H15/H30残差，保存固定五文件；inspect只读保存包，检查内部一致性；verify使用保存参数及显式raw包重放，不refit。三种行为和许可不能混用。没有默认政策或epsilon，不允许临时改窗口、粒度、切分或容差。

支持-h/--help与正常--name=value；拒重复/缩写/额外位置或跨命令参数、@文件、非法政策及非有限/非正epsilon。inspect/verify不接受output。原上游和输出都不自动改路径或覆盖。

## 看懂输出和失败

成功stdout为唯一JSON加LF，状态依次SAVED、INTERNAL_CONSISTENCY_CHECKED、MATCHED，退出0。身份、配置、分钟有效性、fit人数和三政策资格分别列出。raw fit与common不同；H15/H30各自有效性不合并为单一预热状态。没有分数、阈值或效果指标。

prepare/inspect的replay为null；verify返回实际重放报告。summary.package_checks始终只是内部加载检查，不能据其NOT_REESTIMATED反推prepare没有拟合。重放使用保存mean/scale，不能认证参数的原始拟合过程或来源真实性。

错误退出2，stderr尽力输出固定JSON。例如：

```json
{"error":"OUTPUT_ERROR"}
```

完整编码后才输出，单条stdout/stderr限64KiB，包含末尾LF。不能仅凭main返回2判断解释器退出状态。模块入口在失败后处理可用标准流描述符，避免同一缓冲在退出期再次flush；直接调用main不会改宿主标准流。无法取得/重定向描述符、错误流不可写或其他退出处理不在完整保证内，详见设计。

已有目录也会拒绝；该错误可能发生在prepare已完成计算后。晚期保存或stdout失败可留完整包，不能把包存在或完成标记当作本次成功；不自动清理、重试或改用其他目录。保留失败现场，必要时独立inspect/verify，新的prepare另用新目录。

## 实际安装验收

本节整理既有接受记录，不是本次写文档重新运行。最终源码118项通过；独立修复4项为重叠切片。第一次实际运行S1—S3、N1—N4通过，N5断管实际退出120，stderr109字节含退出flush附加错误；该轮P1/P2及最终成功保持检查未执行，整体失败原样保留。

修复仅改变模块入口失败后的描述符处理；原main宿主行为和包接口保持。新冻结后第二次离线安装wheel为162347字节，68项ZIP成员（64产品＋4元数据），安装64产品文件与冻结源码一致。复用既有锁定环境，不是异机或从零依赖复验。

| 第二轮案例 | 实际退出 | stdout/stderr字节 | 结果 |
| --- | ---: | --- | --- |
| S1 prepare | 0 | 2336/0 | SAVED |
| S2 inspect | 0 | 2359/0 | INTERNAL_CONSISTENCY_CHECKED |
| S3 verify | 0 | 3325/0 | MATCHED |
| N1 缺epsilon | 2 | 0/30 | INVALID_ARGUMENTS |
| N2 已有output | 2 | 0/26 | OUTPUT_EXISTS |
| N3 缺COMPLETE副本 | 2 | 0/28 | INVALID_PACKAGE |
| N4 错绑raw B | 2 | 0/39 | UPSTREAM_IDENTITY_MISMATCH |
| N5 实际断管 | 2 | 不可捕获/25 | OUTPUT_ERROR，无退出期附加错误 |
| P1 受控inspect | 0 | 2359/0 | 独立加载边界通过 |
| P2 受控verify | 0 | 3325/0 | 保存参数重放边界通过 |

N5关闭读端，stdout为设计上不可捕获，未造“0字节成功输出”的占位证据。十例均正常回收，无强制/超时/清理错误；父进程实际退出0。另有4次构建安装启动，不与10例混作单元测试数。最长案例约1.686秒、最终任务2290889字节、最大日志16931字节，属于固定监督范围，不是在线性能指标或OS/RSS硬限。

五份成功summary逐字段相同，新五文件全部保存值与旧人工A投影逐项相同，不只比较人数；没有重新计算独立数值参考。该人工例total/raw/prepared=176、H15=116、H30/common=56、fit=18。三政策train18、calibration10、validation-normal10；test normal/attack/unknown按P_U/P_B/P_A分别15/1/2、16/1/1、15/2/1。这些是人工资格，不是真实研究分母。

普通8次模块命令没有动态动作监测。另2个受控main探针保留至退出后的守卫：P1只prepared_load1；P2为prepared_load/raw_load/verify/upstream_bind/transform各1、history2，均无fit/prepare/save。普通3次prepare尝试中，按固定调用链预期有2次人工fit，不能写成实测profile次数；两个探针fit0也不意味着整个验收无拟合。

原A/B包、新副本、安装、源码/测试及旧A投影保持；缺COMPLETE负例的副本与具名标记单独保留。首次失败目录的149项已观察身份保持。监测限Python事件/冻结函数与受管进程，不认证native I/O、所有文件事件或任意第三方初始化。

## 后续边界

raw包生成CLI正在独立工程任务中，view仅设计/计划接受，均不能借本批宣称已验收。当前新入口未接真实CLI→API→网页→导出链。来源未认证、时间为源钟面完成代理，最终标签/主数据/真实试点/生产迁移仍待具体决定。S2/Data Gate BLOCKED，真实拟合、模型训练/评分/Q99与正式实验NOT_RUN；研究依据见[试点准备复核](../research/2026-11-06-pilot-readiness-review.md)。
