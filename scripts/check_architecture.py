"""Dependency and source-size guardrails; runs without third-party packages."""

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAX_LINES = 350
MAX_BYTES = 16_000


def check():
    sources = [
        file
        for folder in ("backend", "web", "scripts")
        for file in (ROOT / folder).rglob("*")
        if file.suffix in {".py", ".js", ".css", ".html"}
    ]
    for file in sources:
        text = file.read_text(encoding="utf-8-sig")
        assert len(text.splitlines()) <= MAX_LINES, f"Split oversized file: {file}"
        assert file.stat().st_size <= MAX_BYTES, f"Split oversized file: {file}"
        if file.suffix == ".py":
            ast.parse(text, filename=str(file))

    graph = {}
    for file in (ROOT / "web").rglob("*.js"):
        imports = re.findall(r"\bfrom\s+['\"]([^'\"]+)['\"]", file.read_text(encoding="utf-8"))
        dependencies = [(file.parent / path).resolve() for path in imports]
        for dependency in dependencies:
            assert dependency.is_file(), f"Missing module: {file} -> {dependency}"
            assert dependency.is_relative_to(ROOT / "web"), f"Import outside frontend: {file}"
            if file.parent.name == "core":
                assert dependency.parent.name == "core" or dependency.name == "icons.js", (
                    f"Core must not depend on application/pages/features: {file} -> {dependency}"
                )
            if (
                file.parent.name == "pages"
                or "features" in file.parts
                or file.parent.name == "components"
            ):
                assert "application" not in dependency.parts, f"Use runtime commands: {file}"
        graph[file.resolve()] = dependencies

    def visit(file, stack, complete):
        assert file not in stack, "Circular imports: " + " -> ".join(p.name for p in [*stack, file])
        if file in complete:
            return
        for dependency in graph[file]:
            visit(dependency, [*stack, file], complete)
        complete.add(file)

    complete = set()
    for file in graph:
        visit(file, [], complete)
    print(
        f"Architecture passed: {len(sources)} source files, no frontend import cycles; "
        f"limits {MAX_LINES} lines / {MAX_BYTES} bytes."
    )


if __name__ == "__main__":
    check()
