from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(slots=True)
class ContextSelectionRequest:
    base_dir: str
    task_type: str
    goal: str
    module_hints: list[str] = field(default_factory=list)
    max_chars: int = 12000
    include_generated_docs: bool = True


@dataclass(slots=True)
class SelectedContext:
    path: str
    reason: str
    chars: int
    excerpt: str


@dataclass(slots=True)
class ContextSelectionResult:
    selected: list[SelectedContext]
    omitted: list[str]
    total_chars: int


class ContextSelector:
    def __init__(self, max_chars_per_file: int = 2500) -> None:
        self.max_chars_per_file = max_chars_per_file

    def select(self, request: ContextSelectionRequest) -> ContextSelectionResult:
        base = Path(request.base_dir).resolve()
        queue: list[tuple[Path, str]] = []

        queue.extend(
            [
                (base / "AGENTS.md", "global protocol and constraints"),
                (base / "configs" / "policy_rules.yaml", "policy constraints"),
                (base / "configs" / "module_rules.yaml", "module boundaries"),
                (base / "configs" / "skills_index.yaml", "skill and adapter mapping"),
                (base / "configs" / "runtime.yaml", "runtime behavior defaults"),
            ]
        )
        queue.extend(
            [
                (base / "docs" / "generated" / "task_model.md", "latest task state"),
                (base / "docs" / "generated" / "decision_log.md", "recent decisions"),
                (base / "docs" / "generated" / "handoff_note.md", "handoff context"),
            ]
        )

        for hint in sorted(set(request.module_hints)):
            queue.extend(self._hint_files(base, hint))

        seen: set[Path] = set()
        selected: list[SelectedContext] = []
        omitted: list[str] = []
        used = 0

        for path, reason in queue:
            if path in seen:
                continue
            seen.add(path)

            if not path.exists() or not path.is_file():
                continue
            if self._is_ignored(path):
                continue
            if not request.include_generated_docs and "docs" in path.parts and "generated" in path.parts:
                continue

            excerpt = self._excerpt(path)
            size = len(excerpt)
            if used + size > request.max_chars:
                omitted.append(str(path))
                continue

            selected.append(SelectedContext(path=str(path), reason=reason, chars=size, excerpt=excerpt))
            used += size

        return ContextSelectionResult(selected=selected, omitted=omitted, total_chars=used)

    def _hint_files(self, base: Path, hint: str) -> list[tuple[Path, str]]:
        hint_path = base / hint
        if hint_path.exists() and hint_path.is_file() and not self._is_ignored(hint_path):
            return [(hint_path, f"explicit module hint: {hint}")]

        candidates: list[tuple[Path, str]] = []
        for root in [base / "src", base / "docs" / "templates", base / "configs"]:
            if not root.exists():
                continue
            for path in sorted(root.rglob("*")):
                if not path.is_file() or self._is_ignored(path):
                    continue
                rel = str(path.relative_to(base)).replace("\\", "/")
                if hint.lower() in rel.lower():
                    candidates.append((path, f"matched module hint '{hint}'"))
                    if len(candidates) >= 8:
                        return candidates
        return candidates

    def _excerpt(self, path: Path) -> str:
        text = path.read_text(encoding="utf-8", errors="ignore")
        if len(text) <= self.max_chars_per_file:
            return text

        head_budget = self.max_chars_per_file // 2
        tail_budget = self.max_chars_per_file - head_budget - len("\n...\n")
        return f"{text[:head_budget]}\n...\n{text[-tail_budget:]}"

    @staticmethod
    def _is_ignored(path: Path) -> bool:
        if "__pycache__" in path.parts:
            return True
        if path.suffix.lower() in {".pyc", ".pyo"}:
            return True
        return False
