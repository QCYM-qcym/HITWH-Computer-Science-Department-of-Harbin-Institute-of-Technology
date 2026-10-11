# 开发与提交规范

## 开始工作

1. 在 GitHub Desktop 选择本仓库，先 Fetch origin，存在远端更新时 Pull origin。
2. 修改前阅读 [项目规划](docs/project/ROADMAP.md) 和对应分区 README。历史方案与当前提案有差异时，先登记差异再修改。
3. 文档修改直接在对应分区进行；业务开发使用 `feat/<主题>`，修复使用 `fix/<主题>`，文档使用 `docs/<主题>`。

## 文件与实验

文件名使用清楚的主题，历史稿保留版本号；新结果注明数据版本、配置、随机种子、时间划分和运行状态。依赖在对应模块锁定，源码使用相对路径或环境变量。学校正式模板优先，图形沿用 [项目作图规范](docs/baseline/00-规范与模板/项目作图规范.md)。

同一实验协议下比较方法，保持标签独立、时间顺序和阈值校准边界。未执行的验收项写 `NOT_RUN`；失败和负结果也登记。

## 使用 GitHub Desktop 提交

1. 仅勾选本次相关文件，逐项检查 diff，运行 `python tools/repository/check_repository.py --worktree`。
2. 检查提交作者：使用本仓库约定的通用维护身份和非个人邮箱。真实姓名或个人邮箱出现时先修正本仓库配置。
3. 填写中文 Summary，如 `docs: 补充数据审计计划`；Description 写变化原因与验证结果。
4. 点击 Commit，再点击 Push origin。遇到冲突先解决并检查，保持正常快进推送。
5. 确认 GitHub Desktop 显示无待推送提交，远端页面可见新文件。每项已完成的相关工作按此流程同步；推送失败时记录原因和未同步状态。

本地 hook 位于 `.githooks/pre-commit`。新克隆仓库执行 `git config core.hooksPath .githooks` 启用；GitHub Desktop 会调用该检查。安装 Python 后需确保 Desktop 的环境可以找到 `python` 或 `py`。hook 和 CI 是辅助检查，正文、图像及元数据仍需人工复核。

## 文档发布

旧原稿保留本地，只将脱敏版本加入仓库。Office/PDF/图片需要检查正文、页眉页脚、讲者备注、隐藏页、批注、修订、作者属性、嵌入文件和图像，再新增明确发布规则与检查支持。当前默认阻止这些二进制文件提交。

