"""从结构化验收状态生成或核对 README；仅使用 Python 标准库。"""
from __future__ import annotations

import argparse
from datetime import date
import html
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
START = "<!-- PROJECT-PROGRESS:START -->"
END = "<!-- PROJECT-PROGRESS:END -->"
SOURCE = "docs/project/status.json"
STATES = {
    "COMPLETED": ("已完成", "done", "#d8efdf"),
    "IN_PROGRESS": ("进行中", "active", "#dceafb"),
    "NOT_STARTED": ("待开始", "planned", "#eeeeee"),
    "BLOCKED": ("阻塞", "blocked", "#ffe1d6"),
    "NOT_RUN": ("未运行 NOT_RUN", "notrun", "#f2e7fa"),
}


class Repository:
    def __init__(self, root: Path, staged: bool = False):
        self.root = root.resolve()
        self.staged = staged

    def git(self, *args: str) -> bytes:
        return subprocess.check_output(["git", *args], cwd=self.root, stderr=subprocess.DEVNULL)

    def read(self, name: str) -> str:
        if self.staged:
            return self.git("show", ":" + name).decode("utf-8-sig")
        return (self.root / name).read_text(encoding="utf-8-sig")

    def require_file(self, name: str):
        path = PurePosixPath(name)
        if not name or path.is_absolute() or ".." in path.parts or "\\" in name or ":" in name:
            raise ValueError("证据或入口必须是仓库内相对路径")
        resolved = (self.root / name).resolve()
        if not resolved.is_relative_to(self.root):
            raise ValueError("证据路径越过仓库边界")
        if self.staged:
            self.git("cat-file", "-e", ":" + name)
        elif not resolved.is_file():
            raise ValueError("证据或入口文件不存在")


def validate(source: dict, repo: Repository):
    if source["schema_version"] != 1:
        raise ValueError("不支持的状态源版本")
    date.fromisoformat(source["updated"])
    for key in ("theme", "counting_scope"):
        if not isinstance(source[key], str) or not source[key].strip():
            raise ValueError("缺少状态摘要")
    for key in ("recent_changes", "blockers"):
        if not isinstance(source[key], list) or not source[key] or any(not isinstance(x, str) or not x.strip() for x in source[key]):
            raise ValueError("变更与阻塞必须显式登记；无阻塞时填写无")
    if not 3 <= len(source["recent_changes"]) <= 5:
        raise ValueError("近期变更保留三至五条")
    if len(source["next_tasks"]) != 3:
        raise ValueError("首页必须列出三项下一步任务")
    for entry in [*source["entrypoints"], *source["next_tasks"]]:
        repo.require_file(entry["path"])
    if not source["entrypoints"]:
        raise ValueError("缺少成果入口")
    ids, criteria_ids = set(), set()
    for stage in source["stages"]:
        stage_id = stage["id"]
        if not re.fullmatch(r"[A-Z][A-Z0-9_]*", stage_id) or stage_id in ids:
            raise ValueError("阶段编号非法或重复")
        ids.add(stage_id)
        if stage["status"] not in STATES or not stage["criteria"]:
            raise ValueError("阶段状态非法或验收项为空")
        if not stage["name"].strip() or not stage["next"].strip():
            raise ValueError("缺少阶段名称或下一步")
        repo.require_file(stage["entry"])
        for criterion in stage["criteria"]:
            if criterion["id"] in criteria_ids:
                raise ValueError("验收编号重复")
            criteria_ids.add(criterion["id"])
            if type(criterion["met"]) is not bool or not criterion["text"].strip():
                raise ValueError("验收状态必须是布尔值并注明条件")
            if criterion["met"] and not criterion["evidence"]:
                raise ValueError("已完成验收项必须提供证据")
            for evidence in criterion["evidence"]:
                repo.require_file(evidence)
        met = sum(c["met"] for c in stage["criteria"])
        if stage["status"] == "COMPLETED" and met != len(stage["criteria"]):
            raise ValueError("已完成阶段仍有未通过验收项")
        if stage["status"] in {"NOT_RUN", "NOT_STARTED"} and met:
            raise ValueError("未运行或待开始阶段不能含已完成验收项")
    if source["current_stage"] not in ids:
        raise ValueError("当前阶段不存在")


def cell(text: str) -> str:
    return text.replace("|", "&#124;").replace("\n", " ")


def link(label: str, path: str) -> str:
    return f"[{cell(label)}](<{path}>)"


def render(source: dict) -> str:
    stages = source["stages"]
    current = next(s for s in stages if s["id"] == source["current_stage"])
    lines = ["## 项目当前进度", "", f"最近更新：**{source['updated']}**。当前阶段：**{current['name']}**；本轮主题：{source['theme']}。", "",
             "```mermaid", "flowchart TB"]
    groups = [("范围与基础", stages[:4]), ("方法与展示", stages[4:7]), ("验收与交付", stages[7:])]
    group_ids = []
    for index, (title, members) in enumerate(groups):
        if not members:
            continue
        group_ids.append(f"G{index}")
        lines += [f'  subgraph G{index}["{title}"]', "    direction LR"]
        for stage in members:
            label, style, _ = STATES[stage["status"]]
            name = html.escape(stage["name"], quote=True).replace("\n", " ")
            lines.append(f'    {stage["id"]}["{name}<br/>{label}"]:::{style}')
        if len(members) > 1:
            lines.append("    " + " --> ".join(s["id"] for s in members))
        lines.append("  end")
    if len(group_ids) > 1:
        lines.append("  " + " --> ".join(group_ids))
    for _, (label, style, color) in STATES.items():
        lines.append(f"  classDef {style} fill:{color},stroke:#555,color:#111")
    lines += ["```", "", "文字与颜色共同表示状态：已完成、进行中、待开始、阻塞、未运行。流程表示依赖顺序，部分文档与测试工作可交叉推进。", "",
              "| 阶段 | 状态 | 已完成/总验收项 | 证据入口 | 下一步 |", "|---|---|---|---|---|"]
    for stage in stages:
        count = sum(c["met"] for c in stage["criteria"])
        lines.append(f"| {cell(stage['name'])} | {STATES[stage['status']][0]} | {count}/{len(stage['criteria'])} | {link('清单与证据', stage['entry'])} | {cell(stage['next'])} |")
    lines += ["", f"计数口径：{source['counting_scope']}。各项条件与证据见[状态源](docs/project/status.json)；文档存在不等于实现或实验通过。不合并为总体百分比；范围变化须登记新分母及原因。", "",
              "**本次完成事项**", ""]
    lines += [f"- {x}" for x in source["recent_changes"]]
    lines += ["", "**当前阻塞或待验证事项**", ""]
    lines += [f"- {x}" for x in source["blockers"]]
    lines += ["", "**接下来最重要的三项任务**", ""]
    lines += [f"{i}. {link(t['id'], t['path'])}：{t['text']}" for i, t in enumerate(source["next_tasks"], 1)]
    lines += ["", "**最新成果入口**", ""]
    lines += [f"- {link(e['label'], e['path'])}" for e in source["entrypoints"]]
    lines += ["", "业务可运行版本与演示：**尚无，NOT_RUN**。仓库维护工具的可运行入口见[工具说明](tools/README.md)。远端自动检查以工作流徽章和实际运行记录为准；本轮提交前为**待远端检查**。"]
    return "\n".join(lines)


def progress_block(readme: str) -> str:
    if readme.count(START) != 1 or readme.count(END) != 1 or readme.index(START) >= readme.index(END):
        raise ValueError("README 必须包含唯一且顺序正确的进度标记")
    return readme.split(START, 1)[1].split(END, 1)[0]


def check_submission(repo: Repository, readme: str):
    changed = repo.git("diff", "--cached", "--name-only", "-z").decode("utf-8").split("\0")
    if not any(changed):
        return
    if "README.md" not in changed:
        raise ValueError("每次提交必须同时更新 README 进度区")
    try:
        previous = repo.git("show", "HEAD:README.md").decode("utf-8-sig")
    except subprocess.CalledProcessError:
        return  # 首次提交没有 HEAD。
    if START in previous and progress_block(previous) == progress_block(readme):
        raise ValueError("README 正文改动不能替代本轮进度区更新")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--staged", action="store_true", help="读取 Git 索引并核对本次提交的进度更新")
    args = parser.parse_args()
    try:
        if args.staged and args.write:
            raise ValueError("暂存区只允许核对")
        repo = Repository(args.root, args.staged)
        source = json.loads(repo.read(SOURCE))
        validate(source, repo)
        readme = repo.read("README.md")
        actual = progress_block(readme)
        expected = "\n" + render(source) + "\n"
        if args.write:
            prefix, tail = readme.split(START, 1)
            suffix = tail.split(END, 1)[1]
            (repo.root / "README.md").write_text(prefix + START + expected + END + suffix, encoding="utf-8", newline="\n")
            print("README 进度区已生成。")
        elif actual != expected:
            raise ValueError("README 与状态源不一致；请运行 --write 后复核")
        else:
            if args.staged:
                check_submission(repo, readme)
            print("README 阶段图、状态表与结构化验收项一致。")
    except (ValueError, KeyError, TypeError, OSError, subprocess.CalledProcessError):
        # 不输出配置或输入值，避免将未审查内容复制到检查日志。
        print("FAIL 进度检查：状态结构、证据、README 或本次提交更新不满足约定。", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
