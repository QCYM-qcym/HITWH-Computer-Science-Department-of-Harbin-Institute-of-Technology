> 公开归档副本。保留原文版本与当时状态；当前进度以仓库项目规划和最新报告为准。原始附件与个人信息留在本地。

# 数据库 E-R 图：实体、属性与联系

本次按用户提供的参考图重绘第6图，使用矩形实体、椭圆属性、菱形联系与主键下划线。文字、形状及线段均为Visio原生对象。主图为核心属性视图，保留五个实体及原有一对多关系，未将其改写成已经实现的数据库。

## 记号与联系

| 图形或记号 | 含义 |
| --- | --- |
| 矩形 | 实体，以名词命名 |
| 椭圆 | 属性，以连线连接所属实体 |
| 菱形 | 联系，以动词命名 |
| 属性名称下划线 | 主键标识符 |
| 1、0..N | 父实体一条记录可关联零至多条子记录；每个子记录归属一个父记录 |
| 联系上的箭头 | 按用户示例表示父到子的阅读方向，基数由数字决定；不是数据流或UML消息 |

联系依次为：数据版本「划分」数据片段，数据片段「执行」检测任务，检测任务「生成」运行产物，检测任务「汇总」评价记录。主图中外键由这些联系表达，不再重复画成属性。

## 核心属性与字段映射

| 实体（拟议表） | 图中属性 → 拟议字段 |
| --- | --- |
| 数据版本 DatasetVersion | 数据版本编号 → dataset_version_id（PK）；数据集名称 → name；版本号 → version；特征文件路径 → feature_path；标签文件路径 → label_path；校验值 → checksum |
| 数据片段 DataSegment | 片段编号 → segment_id（PK）；开始时间 → start_time；结束时间 → end_time；划分角色 → split_role；边界配置 → boundary_config_json |
| 检测任务 Run | 任务编号 → run_id（PK）；模型名称 → model_name；运行配置 → config_json；任务状态 → status；随机种子 → seed；失败原因 → error_message |
| 运行产物 Artifact | 产物编号 → artifact_id（PK）；产物类型 → kind；文件格式 → format；文件路径 → file_path；校验值 → checksum；创建时间 → created_at |
| 评价记录 Metric | 评价记录编号 → metric_id（PK）；评价范围 → scope；指标名称 → metric_name；指标值 → value；样本数量 → sample_count；说明 → note |

## 完整字段保留与约束

主图为可读性省略的既有字段仍保留在拟议设计中：

- DatasetVersion：source_path、time_metadata_path。
- DataSegment：dataset_version_id（非空FK，关联DatasetVersion）。
- Run：segment_id（非空FK，关联DataSegment）、created_at、finished_at、code_version。
- Artifact：run_id（非空FK，关联Run）。
- Metric：run_id（非空FK，关联Run）。

所有主键拟采用单独标识符；图中不存在必须由父键与局部键共同标识的弱实体，也未引入继承关系。数据版本建议UNIQUE(name,version)；指标建议UNIQUE(run_id,scope,metric_name)。片段需满足end_time > start_time，边界拟采用[start_time,end_time)。任务状态限定排队、运行、成功、失败，失败原因和结束时间按状态校验。

逐分钟特征、独立标签和评分文件不扩展为SQLite大表，按报告采用版本化文件与Parquet保存。Metric仅保存汇总，未定义指标允许NULL，同时记录样本数和说明。JSON配置用于保存运行快照，完整物理类型、长度、约束及模型复用关系在详细设计阶段确定。

## 核验范围

已依据V0.16与前版设计检查实体名称、核心属性、主键、联系动词和基数的一致性。每个图中属性归属一个实体；四条联系与四个非空外键映射一致。此轮未创建或运行实际数据库，不声称已通过样本数据验证或形式化正规化证明。候选关系表的函数依赖、配置拆分需求与完整性约束需在物理设计和数据库测试时继续检查。

## 参考来源

记号与版式参考用户提供的截图及郝老三《E-R图总结规范》：https://blog.csdn.net/hlzdbk/article/details/124804730 。原文声明CC BY-SA 4.0；此处为本项目原创模型重绘，未复制示例图片。项目实体与技术内容依据《开题报告-项目作者-V0.16-研究内容图文重写版.docx》第3.5.2节及既有V4.0拟议逻辑设计。
