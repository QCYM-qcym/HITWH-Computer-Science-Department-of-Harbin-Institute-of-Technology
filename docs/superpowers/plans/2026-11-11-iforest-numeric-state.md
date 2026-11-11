# P1 数值森林状态层：实施计划

日期：2026-11-11。状态：W0已采用工程P1；实现、源码测试和新安装实际运行通过；主控后验接受已完成，发布待核。基线`746ad0fc3ef2f3e8ef808d6a553ae479e5d387fb`已Desktop发布且官方ref/README匹配。依据[数值状态设计](../../design/iforest-numeric-state-v1.md)，只新增授权模块与测试，研究S2/Data Gate BLOCKED不变。

目标：一个公开纯API支持固定7字段安全JSON森林状态及NumPy评分，另一个私有文件承载数值算法，返回不可变tuple正异常分数。无raw/prep/result、threshold/Q99/label/policy、fit/export、文件包、CLI、server或模型。旧src/test/docs/configs及E全部冻结文件保护；研究S2/Data Gate BLOCKED不变。

## W0采用与文件ownership

W0已读完整设计并独立builder检查通过，采用整个P1并冻结API、错误域、文件owner及旧材料基线。按实际验证推进，未执行项保持NOT_RUN；不以截止时间代替验收。

| owner | 只能创建的文件 | 责任 |
|---|---|---|
| W1 | src/core/traffic_anomaly/iforest_numeric_state.py；tests/core/iforest_numeric_state_cases.py；tests/core/test_iforest_numeric_state_codec.py | 值对象/验证/canonical codec/有限错误与惰性score转发；无NumPy导入的codec；共享有界人工树构造，不输出数值expected |
| W2 | src/core/traffic_anomaly/_iforest_numeric_score.py；tests/core/test_iforest_numeric_score.py | 接收W1公开转发已验证的精确state，私有_score_validated_state负责矩阵/运行时边界、copy、路由、系数/固定树序/power；不另建状态validator或格式 |
| W3 | tests/integration/test_iforest_numeric_state.py；docs/guides/iforest-numeric-state.md | 内存encode→decode→score的独立手算端到端、无副作用/模型/I/O保护与真实范围指南；不称磁盘或模型集成 |
| W0 | 工程采用记录、公开设计与计划、验收/报告/安装runner及必要项目状态 | 冻结、协调、独立spec+quality review、最终必要回归与可选P1安装、Desktop提交推送；公共状态只由W0维护 |

W1公开module在导入时不导入W2；公开score先以唯一_validate_state验证state，成功后才惰性导入私有_score_validated_state并转发。W2可在自身module导入W1值对象/错误类，NumPy也在私有评分调用内导入；不形成初始化循环，且坏state优先于运行时/矩阵。W0冻结这个方向。W2/W3先写测试与手算expected可并行；实际GREEN依赖W1共享helper与公开seam落地。不得为等依赖临时写同名替身到产品目录、修改W1 helper或加入第三框架。

共享helper候选：`manual_numeric_state(*, width=13, pattern='root_leaf', max_samples=1)`，返回精确IForestNumericState。允许固定模式root_leaf、split2、asymmetric4、three_leaf4、balanced32；函数只构造≤1008节点的literal/明确有界整数树，无导入时计算、I/O、模型或expected评分。各模式/m组合不合法直接测试helper ValueError；产品没有pattern参数。W0可按builder意见缩减helper，但采用后不可并行改签名。

## W1 contract/codec：顺序任务

1. 先写 `test_manual_root_leaf_roundtrip_has_exact_seven_fields_and_canonical_bytes`，首个RED应是新公开module/API缺失，不是坏helper或依赖错误。根叶state共16棵、宽13/m1，明确完整expected canonical结构与LF预算。
2. 实现spec的3个frozen slots值对象、常量、七个安全code构造器；精确参数type；唯一 `_validate_state`。先检查所有容器上限，再验证节点类型、root/count/feature/leaf唯一表示、child范围/顺序/入度/可达、深度与样本守恒。
3. 实现fixed7/1/5字段canonical encoder/decoder；bytes总262144含LF，duplicate/nonfinite/非canonical/长token拒绝；codec只stdlib，模型库与NumPy均无需导入。固定algorithm与feature_order不接受覆盖。构造器不隐藏计算。
4. 增加双宽、m1/2/4/32、63node/5depth有效状态；精确类型、bool/np标量、未初始化对象、字段缺失、graph各类错误与资源先验拒绝。测试JSON恶意改值后重新规范编码，证明抓的是结构而非仅格式。
5. `encode→decode→encode`字节相同，decode返回的tuple/嵌套dataclass不可变；合法float threshold的-0.0保留；类型错误code与版本不兼容code不同。含LF阈值用窄patch本模块限额验证不截断。
6. 共享helper、公开score惰性转发与API可用时通知W2/W3。W1只跑自己的新codec测试，保存真实RED/GREEN日志、执行边界与文件SHA；不跑全套、安装、E模块或模型。

## W2 scorer：与W1分文件并行

1. 先用手写root leaf写 `test_single_sample_state_scores_exact_half_in_both_widths`，RED应指新seam尚未实现/私有scorer缺失。共享构造若未落地，可测试文件先落地不执行；不从其他测试import数值expected。
2. 公开转发先以W1唯一helper验证state，私有scorer不重复验证；在私有评分调用内导入NumPy并核精确2.5.4版本，然后严格native float32/64、二维、width匹配、N0..10000、全有限。输入独立C序f32copy与转换后有限检查；原readonly/非连续/F序数组不改变。dtype转换局部errstate不泄露警告。
3. 固定tree顺序路由。x32比较前显式double提升，threshold原binary64；leaf索引有界。c表按spec NumPy公式；根depth1、每树 `depth+c-1`后depths+=；normalizer/power/outones-where0严格按spec。输出tuple精确Pythonfloat/有限/(0,1]；无math.log、树并行、reduction或任何模型入口。
4. literal手算测试覆盖m1=0.5、m2=0.5、asymmetric4路径/c校正、three_leaf4深度、balanced32满树与双宽feature26末列。m2不能充当NEP50错误路由检测器；用m4叶count1/3与t=1-2^-26，错误float32阈值会给不同score。
5. 覆盖原f64→f32舍入后路由、等阈值左分支、f32scalar与Pythonfloat比较陷阱、threshold不能转f32；m1分母0；几何可分人工满树，冻结已独立核算的binary64 literal/路径表。不得用产品score或内部c函数生成自己的expected。
6. matrix错误族、上限、0行、source nonfinite、cast overflow、非法dtype与子类、state优先/运行时优先、浮点环境恢复、输入bytes/flags不变；在setup后禁止文件open/路径访问及sklearn/joblib/torch导入，确保被测评分真纯。
7. 只跑自己新scorer测试并保留RED/GREEN/实际NumPy版本/哈希。无fit/score_samples/tree.apply/prepare，不能把数学树路由次数写成模型执行。

## W3 数值端到端与指南

1. 在新integration测试先写 `test_canonical_manual_forest_roundtrips_then_scores_without_model_or_io`，缺新接口应形成有效RED；不制造测试临时包或源文件来暗示I/O产品能力。
2. 手写canonical bytes经真实decode后以完整双宽输入调用真实publicscore；核immutable tuple与独立literal/路径表，encode回字节完全相同。多个state与多树不同结构确保不是只测16份同树。
3. 在操作期保护builtins/io/Path/os文件/目录入口、producer/模型导入；人工setup只构造小数组和值对象，无prepare。验证输入/decoded对象不被修改，坏bytes/坏矩阵/错误state不返回部分tuple。对zero-row与max-row边界作必要覆盖，不引入大规模性能测试。
4. 指南仅给in-memory API与人工scope、精确格式/错误/NumPy2.5.4依赖、float32路由/正分数、可接受矩阵与零行；无生产CLI命令、无save/checkpoint示例、无raw/prep/result或Q99/policy声明。明确无export/模型/来源认证，P2仍NOT_RUN。
5. 只跑新integration文件，留真实日志、手算核算表、哈希与执行边界；输出小P1安装提案但不build/install。与W1/W2依赖未就绪时等待，不重写公共helper或补全产品。

## W0整合、审查及验收

- [x] 在采用前核builder-check-list所有设计阻断项；冻结API及文件owner，保存旧src/tests/docs/configs与E冻结文件完整bytes/SHA清单。当前私有草稿不需要Git写入。
- [x] 收齐owner原始RED/GREEN与准确SHA，确认不偷用产品作数值oracle，codec不导NumPy、scorer不导模型/做I/O，错误safe且父文件未改。独立Spec与Quality从冻结文件审，不由实施者自称独立PASS。
- [x] 必要联合新文件测试只在真实新改动/集成风险下执行。最终完整回归由W0统一决定一次，记录覆盖重叠，不机械重跑E已过模块、不复用E旧回归冒充新增代码通过。
- [x] 若采用P1安装：新taskroot、core wheel与新target、显式锁定解释器/NumPy、wheel每member/RECORD与target origin。没有产品CLI或help步骤；普通child中的独立小runner读人工canonical bytes并调用安装后的public API评分，guard模型/业务I/O，核literal tuple与物理exit。测试runner读取自己的固定人工bytes与Python导入代码另计，不能把保护期纯调用夸成进程从启动起零文件读取。
- [x] 安装最小候选为4个direct child：offline build、no-deps install、合法双宽手写state评分、坏matrix/state负例；无模型export、无服务/HTTP/浏览器。总180s/child45s/task64MiB/日志1MiB可作预算起点，实际argv/cwd/env/每预期exit与停止规则须另冻。源码/包/输入前后hash、自然退出/reap及import origin都留证据。
- [x] 无论是否安装，P1的模型fit/score_samples/tree.apply、prepare、CSV/source内容访问、checkpoint导出均0/NOT_RUN。NumPy手写树路由与数学score操作可运行并如实计，不说“零数值计算”。
- [ ] 所有实现/测试/安装状态分别更新；公开资料与Desktop提交推送只W0在实际采用/完成后按项目规则办理，核远端SHA与CI。指南不因源码测试通过就预填安装通过。

P1若只完成codec或源码层，就按实际界限交付，不自动推进P2。下一次人工fit/export和release绑定必须单独设计/采用；本计划没有批准真实模型、真实流量或外部pickle加载，也没有承诺剩余时间内完成。

## 执行结果快照

完整新full为5112通过/23跳过/1既有警告/56子测试，295.46秒；原41个setup失败保留，sentinel回归与共享模块差量修复另记。一次四阶段安装运行已实际完成，独立后验复核后主控已实际接受；不以当前内部PASS替代公开提交或准确CI。详见[验证](../../research/2026-11-11-iforest-numeric-state-verification.json)。G仅私有候选，未采用或执行。
