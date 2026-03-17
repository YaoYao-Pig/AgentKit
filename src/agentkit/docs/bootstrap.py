from __future__ import annotations

from pathlib import Path

from .models import DocumentDefinition
from .registry import DocumentRegistry
from .template_loader import MarkdownTemplateLoader


def _is_ignored_template(path: Path) -> bool:
    # Ignore migration sidecars such as decision_log.starter.md
    # to avoid duplicate document ids during bootstrap/adoption flows.
    name = path.name.lower()
    return ".starter." in name


def load_registry_from_templates(
    template_dir: str,
    output_path_overrides: dict[str, str] | None = None,
    loader: MarkdownTemplateLoader | None = None,
) -> DocumentRegistry:
    output_path_overrides = output_path_overrides or {}
    loader = loader or MarkdownTemplateLoader()

    registry = DocumentRegistry()
    for path in sorted(Path(template_dir).glob("*.md")):
        if _is_ignored_template(path):
            continue
        template = loader.load(str(path))
        metadata = template.metadata
        definition = DocumentDefinition(
            id=metadata.id,
            template_path=str(path),
            metadata=metadata,
            output_path_override=output_path_overrides.get(metadata.id),
        )
        registry.register(definition)
    return registry
