"""Standard model and the on-disk store.

A standard lives as one YAML file under <profile>/standards/<id>.yaml:

    id: py-naming-functions
    title: Function names are snake_case
    category: naming
    critical: false
    status: approved            # candidate | approved | rejected
    tags: [python, naming, functions]
    evidence:
        observed: 47
        followed: 44
        consistency: 0.936
        sample_files: [src/a.py, src/b.py]
    body: |
        Public functions use snake_case ...

The store reads a base profile (e.g. ~/.agent-standards) and a project profile
(.agent-standards) with simple id-based override inheritance.
"""

from __future__ import annotations

import dataclasses
import os
from typing import Optional

import yaml


class _LiteralStr(str):
    """str subclass rendered as a YAML literal block (body: |)."""


def _represent_literal(dumper, data):
    return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")


yaml.add_representer(_LiteralStr, _represent_literal, Dumper=yaml.SafeDumper)


@dataclasses.dataclass
class Evidence:
    observed: int = 0
    followed: int = 0
    sample_files: Optional[list] = None

    @property
    def consistency(self) -> float:
        return round(self.followed / self.observed, 3) if self.observed else 0.0

    def as_dict(self) -> dict:
        return {
            "observed": self.observed,
            "followed": self.followed,
            "consistency": self.consistency,
            "sample_files": self.sample_files or [],
        }


@dataclasses.dataclass
class Standard:
    id: str
    title: str
    body: str
    category: str = "general"
    critical: bool = False
    status: str = "candidate"
    tags: Optional[list] = None
    evidence: Optional[Evidence] = None
    source: str = "manual"  # discovered | manual

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "body": self.body,
            "category": self.category,
            "critical": self.critical,
            "status": self.status,
            "tags": self.tags or [],
            "source": self.source,
            "evidence": (self.evidence.as_dict() if self.evidence else None),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Standard":
        ev = d.get("evidence")
        return cls(
            id=d["id"],
            title=d["title"],
            body=d.get("body", ""),
            category=d.get("category", "general"),
            critical=bool(d.get("critical", False)),
            status=d.get("status", "candidate"),
            tags=d.get("tags") or [],
            source=d.get("source", "manual"),
            evidence=Evidence(
                observed=ev.get("observed", 0),
                followed=ev.get("followed", 0),
                sample_files=ev.get("sample_files") or [],
            ) if ev else None,
        )


class Store:
    """Reads/writes standards for a base profile + project profile."""

    def __init__(self, project_dir: str = ".agent-standards",
                 base_dir: Optional[str] = None):
        self.project_dir = project_dir
        self.base_dir = base_dir
        self._ensure_dirs()

    def _ensure_dirs(self) -> None:
        os.makedirs(os.path.join(self.project_dir, "standards"), exist_ok=True)
        if self.base_dir:
            os.makedirs(os.path.join(self.base_dir, "standards"), exist_ok=True)

    def _paths(self) -> list:
        paths = []
        if self.base_dir:
            paths.append(os.path.join(self.base_dir, "standards"))
        paths.append(os.path.join(self.project_dir, "standards"))
        return paths

    def save(self, std: Standard) -> str:
        d = std.to_dict()
        if d.get("body"):
            d["body"] = _LiteralStr(d["body"].rstrip("\n") + "\n")
        target = os.path.join(self.project_dir, "standards", f"{std.id}.yaml")
        with open(target, "w", encoding="utf-8") as fh:
            yaml.safe_dump(d, fh, sort_keys=False, allow_unicode=True)
        return target

    def load_all(self, statuses=("approved",), include_critical_only: bool = False) -> list:
        """Project standards override base standards with the same id."""
        merged: dict = {}
        for std_dir in self._paths():
            if not os.path.isdir(std_dir):
                continue
            for fname in sorted(os.listdir(std_dir)):
                if not fname.endswith(".yaml"):
                    continue
                with open(os.path.join(std_dir, fname), encoding="utf-8") as fh:
                    d = yaml.safe_load(fh)
                if not d or not d.get("id"):
                    continue
                merged[d["id"]] = Standard.from_dict(d)
        out = []
        for std in merged.values():
            if std.status not in statuses:
                continue
            if include_critical_only and not std.critical:
                continue
            out.append(std)
        return sorted(out, key=lambda s: s.id)

    def sync_to_base(self) -> int:
        """Copy approved project standards into the base profile (merge by id)."""
        if not self.base_dir:
            return 0
        moved = 0
        for std in self.load_all(statuses=("approved", "candidate")):
            d = std.to_dict()
            if d.get("body"):
                d["body"] = _LiteralStr(d["body"].rstrip("\n") + "\n")
            target = os.path.join(self.base_dir, "standards", f"{std.id}.yaml")
            with open(target, "w", encoding="utf-8") as fh:
                yaml.safe_dump(d, fh, sort_keys=False, allow_unicode=True)
            moved += 1
        return moved
