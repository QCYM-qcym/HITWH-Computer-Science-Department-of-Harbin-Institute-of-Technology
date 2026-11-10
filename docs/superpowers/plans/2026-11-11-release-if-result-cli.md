# Release IF Result CLI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax. W0 handles GitHub Desktop publication; W1/W2/W3 own disjoint files.

**Goal:** 在安装后的 core 中，通过三个公开命令生成、单独检查并显式绑定一个 IF 保存结果包。

**Architecture:** 单一 core 模块解析固定参数、预检路径，调用既有 raw/prepared loader、配对、IF、结果包 API，输出统一有限回执。单个 run 对应单个目标和 view。

**Tech Stack:** 既有 Python 3.14、NumPy、按需加载的锁定 sklearn、pytest。使用现有公开库和包发现配置。

**Spec:** [Release IF结果命令行v1](../../design/release-if-result-cli-v1.md)。W0已采用设计并通过builder check，基线 `bc276bb3ea4ba57f53a773b9bdc14ad72d753d72`；本阶段命令实现、专项与磁盘集成就绪，独立审查及新安装运行待完成。

## Global Constraints

固定 main(argv=None)，run/inspect/verify 参数和 stdout 精确字段见 spec。成功 0，错误/中断 2，UTF-8 单 LF 的业务 JSON ≤65,536 字节。验收只用已知人工磁盘包，S2/Data Gate BLOCKED，真实 C17 fit/score/Q99/正式实验 NOT_RUN。W0 管理共享状态与公开材料，所有 owner 独占下列文件。上一批运行保全窗口已结束，26文件版本已由Desktop推送并核对远端；原控制器FAIL保留，窄人工功能经独立后验对账接受。

## Review Focus

1. 同目录、输出祖先/后代、缺父、链接和现有目标在模型调用前失败；目标预检后的竞争保留赢家。
2. run 只计算一个 view；inspect 和 verify 可以做保存分数 Q99 校验，但不得进入模型计算或预处理重放。
3. 自洽结果和错误输入配对有不同结论；verify 失败不能打印 MATCHED，且不能把结果 Q99 或声明绑定称为来源认证。
4. save 成功后 stdout 失败保留可加载包；短写、flush 失败和中断保持安全错误身份。
5. 模块入口及安装位置必须真实，正向运行从新 wheel 产物开始，测试替身的结果不计为模型运行。

## 任务 1 · W0 冻结设计

- [x] 查上一批完整回归、安装/浏览器/进程保全与发布状态；记录尚待工作，确保下一轮准备不触碰上一批保护闭包。
- [x] 审阅 spec 的五类错误集合、输出路径比较、run/verify 的证据用语及默认顺序；通过后将 spec/plan 放入上述公开路径并保存私有冻结哈希。四小时为目标工期，受总任务截止时间约束。
- [x] W1/W2/W3 可并行做各自文件。测试只读 fixture 的构造/期望属于测试层，禁止提供产品测试钩子或重复旧模型/编解码器算法。

## 任务 2 · W1 实现命令与核心单测

**文件**：新增 `src/core/traffic_anomaly/release_if_result_cli.py` 和 `tests/core/test_release_if_result_cli.py`。模块入口、公开接口、回执和错误定义均取 spec。参考既有 release_model_input_cli 的流所有权与 release_input_cli 的子命令风格。

- [x] 写第一条正常入口的 RED，用保护调用的测试替身记录 run 的 raw load → prepared load → pair → fit(view) → make → save 次序与次数，按手写固定值断言回执字段、身份、operations 和 checks，不发布替身为真实 IF 证据。通过 pytest 明确记录缺少目标功能的失败。
- [x] 实现一个小模块。先完成解析与词法/布局检查，随后执行命令。run 仅接受两个 view，inspect/verify 直接消费已验证包。用模块内小投影共享三命令的回执，仅在需要的分支加载产品依赖。
- [x] 参数表覆盖两种选项写法与顺序、重复/混合 help、@file、错 view 和缺项。help/语法错误时给 loader/model 加禁止调用保护。验证一次 argv=None，避免逐项镜像 argparse。
- [x] 输出负例覆盖真实临时目录的相等、祖先、后代、非目录父、缺父、现有目标、同前缀合法兄弟目录；按平台加一个可实际成立的别名/链接案例或注入已观察到的根文件身份。关键断言是 fit 未调用、输入未改变、错误码匹配。在预检后让目标出现，验证独占保存拒绝并保留目标，无二次模型调用。
- [x] 错误映射测一个同类允许码、一个已知异常的异类码和一个含私有消息的未知异常。覆盖短写、flush、KeyboardInterrupt、stderr 失败与宿主 main 不接管流。合法投影上限含 LF；对限额分支可下调测试预算，避免制造产品不支持的大字段。
- [x] 在 worktree 设置本进程 PYTHONPATH=src/core，运行 `.venv/Scripts/python.exe -X utf8 -B -m pytest tests/core/test_release_if_result_cli.py tests/core/test_release_model_input_cli.py -q --tb=short`。记录结果/耗时/失败和两个文件 SHA。

## 任务 3 · W2 独立磁盘集成

**文件**：仅新增 `tests/integration/test_release_if_result_cli.py`。依赖 W1 的公开 main 与现有结果包 API。先写用例并明确合法 RED，待 W1 有入口后接入。

- [x] 参考 tests/core/release_input_cases.py 的人工 raw/prepared 构造，用其实际保存/加载身份建立 pair；用可手算的有限分数、预测和索引形成结果后通过既有 API 写盘。所有预处理构造只发生在测试准备中。避免直接复用声明 identity 未绑定磁盘 bytes 的 hand_pair 作为成功的磁盘输入。
- [x] 对搬迁后的独立结果包运行 inspect（仅 result 路径），再对真实磁盘输入运行 verify。逐项比较实际 result identity、读入的 input references、总数、阈值、预处理人数、checks 和 operations。冻结测试准备之后，在两条 CLI 执行期间禁止模型 fit/score、prepare、derivation replay，允许既有 saved-score Q99 校验。期望来自手工设定和独立包身份。
- [x] 用另一个内部合法且可成对的人工输入调用 verify，期望 INPUT_BINDING_MISMATCH、stdout 空；同一结果包独立 inspect 仍成功。另选一种破坏结果字节的情况，断言底层 INTEGRITY_MISMATCH 在 CLI 保留。确认成功/失败前后的源包与结果成员字节一致。
- [x] 测一次落盘后的输出故障，通过 W1 的受控计算边界或从单测接收这一用例，明确测试产生的是人工手写结果。实际 save 后使 stdout flush 失败，退出 2、错误为 OUTPUT_ERROR，再用真实 load/inspect 取得该包。W1 只测流协议，W2 负责此跨磁盘断言。W2 不以 stub 作为模型真实性证据。
- [x] 运行 `.venv/Scripts/python.exe -X utf8 -B -m pytest tests/integration/test_release_if_result_cli.py -q --tb=short`，使用现有仓库测试导入约定。保留每次实际结果，无需重跑完整旧模型套件。

## 任务 4 · W3 指南和有限安装验收准备

**文件**：编写 `docs/guides/release-if-result-cli.md`，私有目录下编写 `installed-acceptance-proposal.md`。本任务不启动安装、模型、服务或浏览器。

- [x] 指南提供可复制的模块命令，使用本地绝对路径占位符，分别给出两个 run、独立 inspect 和带显式输入的 verify，再链接既有双包 serve 用法。说明模型额外依赖、空校准错误、相邻目录约束、保存失败残留与 stdout 故障后先 inspect。示例输出只展示已冻结协议，不填虚构实测身份或研究结果。
- [x] 为 W0 列出离线 wheel 安装与来源检查、新进程 help、两个 run、两个 inspect/verify 和负例的确切 argv 模板。负例优先选择 output 已存在及能证明与另一合法输入不符的 verify。核对新产物与上一轮相同人工输入的可比条件。记录父子进程、实际 exit、每项输入结果字节摘要、已执行请求和操作真实数量。准备好验收后即交 W0，不操作 W1/W2 文件。

## 任务 5 · W0 整合、独审和执行

- [x] 冻结 CLI、核心单测、集成测试和指南。独立核对全部公共命令、父子/别名关系、压缩后的安全码、可加载残留与证据用语，集中处理实际发现后审修复差异。
- [x] 在最终源码运行专项合测和适当全套 Python 回归。W0 归并重叠覆盖，记录跳过和旧警告；UI 无改动，无需机械重跑浏览器全套。若有跨模块回归，先定位、修复、复核再打开安装验收。
- [x] 运行前冻结实际输入与源码/环境哈希、离线 wheel 来源、唯一新 target、新输出名、负例输入、具体命令/期望 status、墙钟与文件预算、停止条件。默认最多两条人工 run，各一个视图；只读命令在新进程调用。失败不自动重试。只读 codec 的保存分数 Q99 与两次模型阈值计算分别记账。
- [x] 从安装 target 运行实际命令。对两个结果各自对照独立新进程的 inspect/verify 与存盘 identity；有可比较的既有人工基准时核对分数/预测/阈值与包身份。确认两包可被既有结果 app 接纳，按冻结预算做最小 actual HTTP 兼容检查。如果已有源阶段或史料只能证明某项部分完成，按实际标注。
- [ ] 将实际结果、命令退出和证据限制加入新验证摘要与指南，W0 按维护约定更新索引/状态及 Vault，使用 GitHub Desktop 提交、推送并核对远端。如果截止时间先到，交接已完成阶段和待验证项。源码、人工实际模型、发布和真实研究各依其证据记录。

建议时间为 W0 冻结 0–25 分钟，W1/W2/W3 分工 25–110 分钟，整合与审查 110–160 分钟，实际安装验收与归档 160–240 分钟。实际工期和接受结论由执行收据确定。
