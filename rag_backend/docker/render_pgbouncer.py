#!/usr/bin/env python3
"""从 .template 渲染 pgbouncer 配置文件，替换 ${VAR} 占位符。

用法（在 rag_backend 目录下执行）：
    python docker/render_pgbouncer.py

读取 rag_backend/.env 中的环境变量，将同目录下所有 *.template 渲染为去掉
.template 后缀的实际配置文件（如 pgbouncer_transaction_mode.ini）。
渲染产物被 .gitignore 排除，不会进入 git。

跨平台（Windows / macOS / Linux）。无外部依赖。
"""
import os
import re
import sys
from pathlib import Path


def load_env(env_path: Path) -> dict:
    env: dict = {}
    if not env_path.exists():
        return env
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        env[key.strip()] = value.strip().strip('"').strip("'")
    return env


def render(text: str, env: dict) -> str:
    def replace(match: re.Match) -> str:
        name = match.group(1)
        if name not in env and name not in os.environ:
            raise KeyError(name)
        return env.get(name, os.environ.get(name, ""))

    return re.sub(r"\$\{([A-Z0-9_]+)\}", replace, text)


def main() -> int:
    docker_dir = Path(__file__).resolve().parent
    env_path = docker_dir.parent / ".env"
    env = load_env(env_path)

    templates = sorted(docker_dir.glob("*.template"))
    if not templates:
        print("未找到任何 .template 文件，无事可做。")
        return 0

    rendered_count = 0
    for tmpl in templates:
        out_path = tmpl.with_suffix("")  # 去掉 .template
        try:
            rendered = render(tmpl.read_text(encoding="utf-8"), env)
        except KeyError as missing:
            print(f"❌ {tmpl.name}: 缺少环境变量 {missing.args[0]}，"
                  f"请在 {env_path} 中设置后重试。")
            return 1
        out_path.write_text(rendered, encoding="utf-8")
        print(f"✅ 渲染 {tmpl.name} → {out_path.name}")
        rendered_count += 1

    print(f"\n完成：共渲染 {rendered_count} 个文件。")
    print("接下来重启 pgbouncer 容器：docker compose restart pgbouncer")
    return 0


if __name__ == "__main__":
    sys.exit(main())
