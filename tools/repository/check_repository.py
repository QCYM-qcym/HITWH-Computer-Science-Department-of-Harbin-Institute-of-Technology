"""检查 Git 索引或公开工作区；仅依赖标准库。"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import posixpath
import re
import subprocess
import sys
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[2]
TOP_FILES = {"README.md", "CONTRIBUTING.md", "CHANGELOG.md", ".gitignore", ".gitattributes"}
TOP_DIRS = {"docs", "src", "tests", "configs", "experiments", "data", "tools", ".github", ".githooks"}
TEXT_EXTENSIONS = {".md", ".py", ".json", ".yaml", ".yml", ".toml", ".txt", ".svg", ".ps1", ".sh", ".mjs", ".js", ".ts", ".tsx", ".vue", ".css", ".html", ".sql"}
PUBLIC_REPOSITORY_URL = "https://github.com/QCYM-qcym/HITWH-Computer-Science-Department-of-Harbin-Institute-of-Technology"
RULES = {
    "个人目录": re.compile(r"(?i)[A-Z]:[\\/](?:Users|obsdian|Study|BaiduNetdiskDownload)[\\/]"),
    "联系方式": re.compile(r"(?<![\w])1[3-9]\d{9}(?!\d)|[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}"),
    "个人编号": re.compile(r"(?:学\s*号|身份证|student[_ -]?id)\s*[:：]?\s*\d{6,}", re.I),
    "凭据": re.compile(r"(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|sk-[A-Za-z0-9]{24,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)"),
}


def git(*args: str) -> bytes:
    return subprocess.check_output(["git", *args], cwd=ROOT)


def inspect(name: str, content: bytes, terms: list[str]) -> list[str]:
    reasons = []
    path = Path(name)
    if path.parts[0] not in TOP_DIRS and name not in TOP_FILES:
        reasons.append("未规划的顶层路径")
    if any(part in {"node_modules", "__pycache__", ".venv"} for part in path.parts):
        reasons.append("缓存或依赖目录")
    if path.name.startswith(".env") and path.name != ".env.example":
        reasons.append("本地环境配置")
    if "local" in path.name.lower():
        reasons.append("本地配置")
    if (name.startswith(("data/raw/", "data/processed/", "experiments/runs/"))
            and path.name != "README.md"):
        reasons.append("原始数据或运行产物")
    if path.suffix.lower() not in TEXT_EXTENSIONS and name not in TOP_FILES and name != ".githooks/pre-commit":
        reasons.append("未支持的文件格式，需专项审查")
    try:
        content_text = content.decode("utf-8")
    except UnicodeDecodeError:
        return reasons + ["非UTF-8文本"]
    if "\x00" in content_text:
        reasons.append("二进制内容")
    combined = (name + "\n" + content_text).replace("project-maintainer@users.noreply.github.com", "[通用维护邮箱]")
    for label, pattern in RULES.items():
        if pattern.search(combined):
            reasons.append(label)
    # 用户指定的公开仓库地址属于发布目标；仅豁免完整地址，禁止项本身仍保留。
    public_link = re.compile(re.escape(PUBLIC_REPOSITORY_URL) + r"(?=/|[\s\"'<>)]|$)", re.I)
    term_text = public_link.sub("[公开仓库地址]", combined)
    if any(term and term.casefold() in term_text.casefold() for term in terms):
        reasons.append("本地禁止项")
    if len(content) > 5 * 1024 * 1024:
        reasons.append("超出文本大小限额")
    return reasons


def check_links(name: str, content: str, files: set[str]) -> list[str]:
    """核对当前入口的行内Markdown文件目标；不请求网络或解释Wiki。"""
    content = re.sub(r"(?ms)^\s*```.*?^\s*```[^\n]*", "", content)
    reasons = []
    for match in re.finditer(r"\[[^\]\n]*\]\((<[^>]+>|[^\s)]+)(?:\s+[^)]*)?\)", content):
        target = match.group(1).strip("<>")
        parsed = urlsplit(target)
        if parsed.scheme or parsed.netloc or not parsed.path:
            continue
        resolved = posixpath.normpath(posixpath.join(posixpath.dirname(name), unquote(parsed.path)))
        if resolved.startswith("../") or resolved.startswith("/") or resolved not in files:
            reasons.append("当前入口链接缺失或越界")
    return sorted(set(reasons))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--staged", action="store_true")
    group.add_argument("--worktree", action="store_true")
    parser.add_argument("--check-author", action="store_true")
    args = parser.parse_args()
    local = ROOT / "privacy.local.json"
    terms = json.loads(local.read_text(encoding="utf-8")).get("deny_terms", []) if local.exists() else []
    if args.staged:
        names = git("ls-files", "-z").decode("utf-8").split("\0")
        reader = lambda name: git("show", ":" + name)
    else:
        names = [p.relative_to(ROOT).as_posix() for d in TOP_DIRS if (ROOT / d).exists()
                 for p in (ROOT / d).rglob("*") if p.is_file()
                 and not any(x in {"node_modules", "__pycache__", ".venv"} for x in p.parts)]
        names += [n for n in TOP_FILES if (ROOT / n).exists()]
        reader = lambda name: (ROOT / name).read_bytes()
    failures = []
    files = set(filter(None, names))
    for name in sorted(set(filter(None, names))):
        content = reader(name)
        reasons = inspect(name, content, terms)
        active = (name in TOP_FILES or name.startswith("docs/project/")
                  or (Path(name).name == "README.md" and not name.startswith("docs/baseline/")))
        if active and name.endswith(".md"):
            try:
                reasons += check_links(name, content.decode("utf-8"), files)
            except (UnicodeDecodeError, ValueError):
                reasons.append("入口文本或链接无法解析")
        if reasons:
            # 只打印类别，避免把发现的敏感内容复制到日志。
            failures.append((name if not any(t.casefold() in name.casefold() for t in terms) else "[受保护文件名]", reasons))
    if args.check_author:
        if git("config", "user.name").decode().strip() != "Project Maintainer":
            failures.append(("提交作者", ["请配置通用维护身份"]))
        email = git("config", "user.email").decode().strip()
        if email != "project-maintainer@users.noreply.github.com":
            failures.append(("提交邮箱", ["请配置约定的非个人邮箱"]))
    for name, reasons in failures:
        print(f"FAIL {name}: {', '.join(reasons)}")
    print(f"检查 {len(set(filter(None, names)))} 个文件，问题 {len(failures)} 项。")
    progress = [sys.executable, "-X", "utf8", str(ROOT / "tools/repository/update_progress.py"), "--check"]
    if args.staged:
        progress.append("--staged")
    result = subprocess.run(progress, cwd=ROOT)
    return 1 if failures or result.returncode else 0


if __name__ == "__main__":
    sys.exit(main())

