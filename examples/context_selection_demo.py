from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from agentkit.runtime.context_selector import ContextSelectionRequest, ContextSelector


def main() -> None:
    selector = ContextSelector(max_chars_per_file=1200)
    result = selector.select(
        ContextSelectionRequest(
            base_dir=".",
            task_type="feature",
            goal="update runtime adapters",
            module_hints=["runtime", "skills_index"],
            max_chars=5000,
            include_generated_docs=True,
        )
    )

    print(f"Selected contexts: {len(result.selected)}")
    print(f"Total chars: {result.total_chars}")
    for item in result.selected:
        print(f"- {item.path} ({item.chars} chars) | reason: {item.reason}")

    if result.omitted:
        print("Omitted due to budget:")
        for path in result.omitted:
            print(f"- {path}")


if __name__ == "__main__":
    main()
