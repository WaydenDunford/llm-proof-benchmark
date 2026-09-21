"""Configuration, atomic persistence, prompts and provenance."""
import importlib.metadata
import os
from pathlib import Path
import platform
import subprocess
import tempfile
from typing import TypeVar
import yaml
from jinja2 import Environment, StrictUndefined
from pydantic import BaseModel
from .schemas import Theorem

T = TypeVar("T", bound=BaseModel)


def load_config(path: Path, schema: type[T]) -> T:
    return schema.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))


def load_theorems(root: Path) -> list[Theorem]:
    items = [load_config(p, Theorem) for p in sorted((root / "theorems").iterdir())
             if p.suffix.lower() in {".yaml", ".yml", ".json"}]
    ids = [t.id for t in items]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate theorem IDs")
    return items


def find_theorem(root: Path, name: str) -> Theorem:
    items = load_theorems(root)
    for item in items:
        if item.id == name:
            return item
    for p in (root / "theorems").iterdir():
        if p.stem == name and p.suffix in {".yaml", ".yml", ".json"}:
            return load_config(p, Theorem)
    raise ValueError(f"Unknown theorem: {name}")


def render(template: str, **context) -> str:
    return Environment(undefined=StrictUndefined, autoescape=False).from_string(template).render(**context)


def atomic_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def save_result(path: Path, result: BaseModel) -> None:
    atomic_text(path, result.model_dump_json(indent=2))


def provenance(root: Path) -> dict:
    packages = {}
    for package in ("torch", "transformers", "accelerate", "vllm", "pydantic"):
        try:
            packages[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            packages[package] = None
    result = {"python_version": platform.python_version(), "platform": platform.platform(),
              "packages": packages, "cuda_available": False, "gpu_names": [],
              "git_commit": None, "git_dirty": None}
    try:
        result["git_commit"] = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=root, stderr=subprocess.DEVNULL, text=True).strip()
        result["git_dirty"] = bool(subprocess.check_output(
            ["git", "status", "--porcelain"], cwd=root, text=True).strip())
    except (OSError, subprocess.CalledProcessError):
        pass
    if packages["torch"]:
        try:
            import torch
            result["cuda_available"] = torch.cuda.is_available()
            result["gpu_names"] = [torch.cuda.get_device_name(i) for i in range(torch.cuda.device_count())]
            result["cuda_version"] = torch.version.cuda
        except Exception as exc:
            result["hardware_probe_error"] = str(exc)
    return result
