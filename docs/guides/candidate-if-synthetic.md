# 候选13维IF：人工输入到评分与评价

## 已有产物的只读复查

已有五文件可使用[独立只读验算](candidate-run-verification.md)检查身份、摘要、存储分数Q99和评价；不重跑或反序列化IF，也不认证分数来自模型。原自产保存/当次重载与此后的只读复查是不同证据。

日期2026-10-30；身份**SYNTHETIC_ONLY / ENGINEERING_TOY_ONLY**。用途：在[候选不可变快照](candidate-snapshots.md)上演练当前13维IF、自产模型保存/当次重载、独立Q99和三政策固定预测评价。范围见[开发计划](../superpowers/plans/2026-10-30-candidate-if-synthetic.md)。既有生产134/268模型与HTTP/网页不改变，本入口不连接真实数据。

## 运行

使用[既有开发环境](development.md)和backend锁定的CPU依赖，无新增依赖。先确保`.runtime`父目录存在，以下三个输出目录均须全新；重复执行请选择新目录和run_id：

```powershell
python -X utf8 -m traffic_anomaly.candidate_record_cli --fixture tests/fixtures/g13u-records-v1.json --policy P_U --output .runtime/toy-if-records
python -X utf8 -m traffic_anomaly.candidate_cli --fixture .runtime/toy-if-records/minute-fixture.json --output .runtime/toy-if-inputs
python -X utf8 -m traffic_anomaly.candidate_if_cli --records .runtime/toy-if-records --inputs .runtime/toy-if-inputs --source-fixture tests/fixtures/g13u-records-v1.json --run-id toy-if-v1 --output .runtime/toy-if-run
```

run_id为1—64字符ASCII标识符，首字符字母或数字，后续允许字母、数字、下划线和短横线。CLI必需原人工source，先完整验证输入再执行；不接受CSV、外部model/resume、policy覆盖或调参参数。成功exit0返回run_id/COMPLETE/SYNTHETIC_ONLY；失败exit2返回安全错误码，公共错误无私人路径或堆栈。

[candidate_iforest.py](../../src/core/traffic_anomaly/candidate_iforest.py)负责模型计算；[candidate_evaluation.py](../../src/core/traffic_anomaly/candidate_evaluation.py)负责三政策评价；[candidate_if_cli.py](../../src/core/traffic_anomaly/candidate_if_cli.py)负责有界产物。没有放宽原生产IF宽度、伪造UGR八标签或注册旧worker。

## 固定工程配置与时间资格

| 项目 | 本入口规定 |
|---|---|
| 输入 | prepared当前13项，固定特征顺序；不把标签作为特征 |
| 模型 | 16棵Isolation Forest，max_samples=min(32,N_train)，max_features=1，bootstrap=false，seed42，n_jobs=1 |
| 拟合 | 只取train全历史正常且H15/H30共同有效分钟，不重新拟合保存的预处理参数 |
| 评分 | 对所有共同有效分钟计算−score_samples，越大越异常；不因当前未知/攻击标签删除输入 |
| 阈值 | 只取独立calibration全历史正常共同分数，linear Q99，严格大于才报警 |
| 无效 | 完整轴保留，score/alarm均null；H15/H30理由分别保留；模型无法计算则整体失败，不删行凑成功 |

这些参数仅用于小规模接口演练，未验证最优，也没有最低32条训练样本要求。IF只使用当前13项，采用共同分钟资格是为了衔接既有评价集合，不能据此称IF使用历史26项。validation/test不参与IF拟合，测试值不参与阈值选择。

进入sklearn前，对实际选择的矩阵转float32并再次检查有限性；转换溢出会失败。整轴无效NaN不是有效零分。输入资格来自已验证快照，并在计算入口复核分区、共同掩码及正常历史资格。

## 固定预测的三政策评价

同一选中政策模型只拟合一次、校准一次。P_U/P_B/P_A在相同分数、阈值与报警上替换已审计标签映射；不重新训练或重新选阈值。score_origin_policy保留选中政策身份，所有政策仍为AUDIT_ONLY。

评价单位为test共同且有分数的分钟：normal+attack+unknown等于scored_test_minutes。unknown退出正常/攻击混淆分母，单列计数及其中原明确攻击存在数。未评分分钟与标签未知分钟分别统计，内部False报警占位不当作已评分阴性。

- FPR=FP/(TN+FP)，分母是有分数的当前正常分钟。
- FNR=FN/(TP+FN)，分母是有分数的当前攻击分钟。
- precision/recall/F1及上述比率分母为零时，值为null并给具体原因。

完整评价不做point-adjust，不抽样评价分钟，不根据三政策效果择优。不同选中政策如果改变开发段拟合资格，另一次运行可能得到不同模型；本入口不把这些独立运行冒称同一固定预测。

## 五个产物与失败处理

| 文件 | 内容与关系 |
|---|---|
| model-state.json | run_id、模型profile、13项顺序、toy配置/库版本、预处理状态、上游五摘要、训练/校准索引及weights摘要 |
| weights.bin | 本次进程自产模型；仅在本次调用中保存后重读相同已知bytes并验证重载分数 |
| scores.json | 完整分钟轴、有效性、H15/H30原因、分数/报警、阈值及校准N/分位位置/并列数 |
| evaluation.json | 同run_id与模型来源、实际scores文件摘要、同一阈值及三政策分母/混淆/空值原因 |
| manifest.json | 其余四文件SHA256/字节数；全部写出并完成自产模型重放后才标COMPLETE |

五项JSON共同身份与配置绑定，输出新目录与两个输入目录及源路径不重叠。先检查各层符号链接/重解析点，再规范化路径比较；含`..`的别名也不能进入输入目录。输入内容只读，禁止覆盖已有输出。

单weights最多8MiB、单JSON最多16MiB、含manifest总输出最多32MiB，buffer按实际字节数在写入前限制。失败保留本次其他partial供核查，不标COMPLETE；只可移除本次独占创建且写入失败的manifest，不删除碰撞时他人的文件。

本入口没有外部模型加载参数。joblib只接收本次进程刚产生、保存并比对为相同字节的权重；读取任意外来pickle不会因SHA存在而安全。原预处理来源仍NOT_REESTIMATED，模型产物也不认证作者或研究准入。

## 验证记录与研究边界

实际运行toy-if-20261030-v1：144分钟/24有分数、训练/校准各6，阈值0.5531029014846093。P_U正常/攻击/未知为4/1/1，P_B为5/1/0，P_A为4/2/0；本次没有报警，三政策FNR均1、precision均null。它是保留的人工漏报例子，没有为演示改输入或阈值。

本批实际测试、人工CLI运行、分母和输出摘要见[验证记录](../research/2026-10-30-candidate-if-verification.json)。运行时间只记录工程实况，不作为性能达标或检测有效性证据。

本批只人工样例，无新增数据下载、真实CSV读取、真实变换拟合或真实IF/AE训练/评分/Q99。最终标签政策、主数据采用和134/268迁移仍待明确决定；旧G12/G13U审计及V0.40保留，Data Gate/S2 BLOCKED，真实联调与正式实验NOT_RUN。
