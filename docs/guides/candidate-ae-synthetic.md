# 候选当前与历史AE人工运行

## 保存后的独立检查

五JSON可使用[只读验算](candidate-ae-run-verification.md)检查上游身份、结构及保存算术，不重建网络。原本次生成后的参数/模型重放与后来只读复查是两种证据，后者不认证网络产生了保存分数。

用途：离线验证候选13/26维AE的数值、保存和重载接口。日期2026-10-30；身份SYNTHETIC_ONLY / AUDIT_ONLY / ENGINEERING_TOY_ONLY。依据[实施计划](../superpowers/plans/2026-10-30-candidate-ae-synthetic.md)和[V0.40](../reports/开题报告-V0.40-公开文本.md)。本入口与生产134/268、原后端任务及网页分开。

## 输入和固定工程配置

输入须为[人工记录适配](candidate-records.md)和[候选数值处理](candidate-inputs.md)已生成的目录，并提供原人工source-fixture。执行先按[同次读取快照](candidate-snapshots.md)验证原源、标签分离、预处理参数及H15/H30血缘，不重新拟合预处理。没有原源复查不能执行本入口。

| 模式 | 实际输入顺序 | 固定网络 | 参数量 | history-window |
|---|---|---|---:|---|
| current_ae | 13项已变换当前特征，沿上游feature_names | 13→8→3→8→13 | 288 | 必须省略 |
| history_ae | 前13当前，后13对应历史偏离 | 26→8→3→8→26 | 509 | 显式15或30 |

非输出层使用ReLU，输出线性；CPU float32、seed42、Adam学习率0.001、固定5轮，每轮完整训练资格集合一步，无shuffle、早停或参数搜索。两网络参数量不同；正式容量匹配对照仍NOT_RUN。上述数值只用于检查工程接口，未验证收敛或真实适用性。

所有模式均使用H15与H30共同有效分钟，训练和独立校准另要求当前及完整历史正常；不从分散正常行重新拼历史。验证和测试不参与梯度或选参，所有合法共同分钟都可评分，包括未知标签分钟。运行一次只处理一个模型和窗口，不自动挑选结果较好者。

## 运行

使用[锁定开发环境](development.md)内已安装核心包和PyTorch CPU能力。每次提供新run_id和不存在的输出目录，以下目录名是本地示例，命令不负责下载数据：

```text
python -X utf8 -m traffic_anomaly.candidate_ae_cli --records .runtime/toy-records --inputs .runtime/toy-inputs --source-fixture tests/fixtures/g13u-records-v1.json --method current_ae --run-id toy-current-ae-v1 --output .runtime/toy-current-ae-v1
python -X utf8 -m traffic_anomaly.candidate_ae_cli --records .runtime/toy-records --inputs .runtime/toy-inputs --source-fixture tests/fixtures/g13u-records-v1.json --method history_ae --history-window 15 --run-id toy-history-ae-v1 --output .runtime/toy-history-ae-v1
```

没有真实数据、外部checkpoint、设备选择、resume或调参开关。输出拒绝既有目录、与上游重叠和链接/重解析路径；出错返回安全代码，不回显路径或内部堆栈。失败目录保留，修复后另建运行，不覆盖旧证据。

## 评分与指标

网络收到float32输入；评分将该输入和实际重构分别升为float64，再作差、平方和均值。当前模型score=current_reconstruction_mse；历史模型score=0.5×current_reconstruction_mse+0.5×history_deviation_reconstruction_mse，越大越异常。后者是历史偏离输入的重构误差，与上游MAD偏离值含义不同。当前模式后通道为null、不适用。

每模型从独立校准正常共同分钟取自身linear Q99，严格大于才报警；不借用IF或其他AE阈值。全分钟轴无分数处的score、alarm和误差为null，保留H15/H30原因。P_U/P_B/P_A仅对同一预测作审计评价，未知不加入正常/攻击分母；零分母保留null与原因。合成阈值不意味着真实测试误报率1%，也不冻结最终Attempted政策。

float32转换、前向、loss、梯度、参数、优化器状态或float64评分非有限时整次失败；不裁剪、删样本或改epsilon凑通过。线程数只记录；CPU RNG在成功/失败后恢复，不查询GPU。该CPU RNG作用域仅用于独立串行CLI，不承诺共享进程并发安全或跨平台位级复现。

锁定Torch的Adam每步原本会查询加速器；本入口沿用Adam更新，仅以实例局部子类将该健康检查改为参数、梯度及状态全部CPU且capture关闭的断言。全局优化器不变，配置记录guard/API身份；这是对锁定版本私有接口的依赖，接口缺失时安全失败，升级依赖须重验，不能假定任意Torch版本兼容。

## 五产物和安全权重

| 文件 | 内容与关联 |
|---|---|
| weights.json | 固定八组Linear权重/偏置，float32、精确shape和扁平有限数值；完整运行binding |
| model-state.json | 权重实际摘要、训练/校准索引、5轮loss与模型配置 |
| scores.json | 完整时间轴、共同资格、null、两误差通道、分数/报警与独立校准信息 |
| evaluation.json | scores实际摘要及三政策固定预测分母、指标和未定义原因 |
| manifest.json | 其余四文件的摘要/大小、运行和上游身份；当次重放成功后最后写COMPLETE |

所有文件绑定run_id、独立AE profile、字段顺序、配置、预处理状态、上游五摘要及Python/NumPy/Torch版本。权重文档只允许固定schema和八tensor；拒绝多/少键、bool充数、错shape/类型、非有限或不能精确回到float32的值。读取限制1MiB，其他单JSON16MiB，整次五文件32MiB；输入另继承人工快照上限。

重建只创建硬编码CPU网络并复制已验证数组，无pickle/joblib/torch.load/save。检查逐参数位模式，再重放当次分数、通道、阈值、报警和评价；不恢复优化器或继续训练。严格JSON安全并不认证外部作者、研究有效性或跨版本数值兼容。已有[IF只读验算](candidate-run-verification.md)适用于IF五文件，不能用于此AE格式。

导入核心/权重验证模块和CLI帮助不会导入torch、sklearn或joblib；显式AE执行和安全网络重建才加载torch。没有新依赖下载或生产包格式变更。

## 验证范围

[实际证据](../research/2026-10-30-candidate-ae-verification.json)记录三次固定人工运行：当前/H15/H30均144轴、24分数、训练/校准各6；全部无报警、攻击全漏报，precision为null，未调参改变负例。新增138项与完整870项/56subtests通过，2项本机链接权限skip、1既有警告；独立审查PASS。18上游文件及源保持。当前设计不授权真实CSV、真实预处理/模型/评分/Q99、主数据采用、生产迁移或正式研究；Data Gate/S2保持BLOCKED。
