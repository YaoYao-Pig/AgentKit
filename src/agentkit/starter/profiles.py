from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class StarterProfile:
    name: str
    description: str
    include_tests: bool
    include_extra_example: bool


PROFILES: dict[str, StarterProfile] = {
    "minimal": StarterProfile(
        name="minimal",
        description="Core runtime scaffold with one runnable example and baseline tests.",
        include_tests=True,
        include_extra_example=False,
    ),
    "extended": StarterProfile(
        name="extended",
        description="Core scaffold plus additional customization example and docs.",
        include_tests=True,
        include_extra_example=True,
    ),
}
