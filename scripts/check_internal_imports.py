"""Static repository checks that do not import third-party dependencies."""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INTERNAL_ROOTS = ("AlexaMusic", "config", "strings")


def python_files() -> list[Path]:
    files: list[Path] = []
    for root_name in INTERNAL_ROOTS:
        files.extend((ROOT / root_name).rglob("*.py"))
    files.append(ROOT / "genstring.py")
    return sorted(files)


def module_name(path: Path) -> str:
    relative = path.relative_to(ROOT).with_suffix("")
    parts = list(relative.parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


FILES = python_files()
MODULES = {module_name(path) for path in FILES}


def module_exists(name: str) -> bool:
    return name in MODULES


def resolve_relative(current: str, level: int, module: str | None) -> str:
    path = ROOT.joinpath(*current.split("."))
    is_package = (path / "__init__.py").exists()
    package = current if is_package else current.rpartition(".")[0]
    parts = package.split(".") if package else []
    up = max(level - 1, 0)
    if up > len(parts):
        return ""
    base = parts[: len(parts) - up] if up else parts
    if module:
        base.extend(module.split("."))
    return ".".join(base)


def check_imports() -> list[str]:
    errors: list[str] = []
    for path in FILES:
        current = module_name(path)
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError as error:
            errors.append(f"{path.relative_to(ROOT)}:{error.lineno}: {error.msg}")
            continue

        for node in ast.walk(tree):
            target = None
            if isinstance(node, ast.ImportFrom):
                if node.level:
                    target = resolve_relative(current, node.level, node.module)
                elif node.module and node.module.split(".", 1)[0] in INTERNAL_ROOTS:
                    target = node.module
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.split(".", 1)[0] in INTERNAL_ROOTS and not module_exists(alias.name):
                        errors.append(
                            f"{path.relative_to(ROOT)}:{node.lineno}: missing internal module {alias.name}"
                        )

            if target and target.split(".", 1)[0] in INTERNAL_ROOTS and not module_exists(target):
                errors.append(
                    f"{path.relative_to(ROOT)}:{node.lineno}: missing internal module {target}"
                )
    return errors


def check_plugin_allowlist() -> list[str]:
    path = ROOT / "AlexaMusic/plugins/__init__.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    errors: list[str] = []

    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(target, ast.Name) and target.id == "ALL_MODULES" for target in node.targets):
            continue
        values = ast.literal_eval(node.value)
        for value in values:
            module = "AlexaMusic.plugins" + value
            if not module_exists(module):
                errors.append(f"plugin allowlist references missing module {module}")
        break
    return errors


def main() -> None:
    errors = check_imports() + check_plugin_allowlist()
    if errors:
        print("Repository checks failed:")
        for error in errors:
            print(f" - {error}")
        raise SystemExit(1)
    print(f"Repository checks passed for {len(FILES)} Python files.")


if __name__ == "__main__":
    main()
