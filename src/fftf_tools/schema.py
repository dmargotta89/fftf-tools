"""Shared machine contract for FFTF agent tools.

Every pipeline command writes this block. ``distro_blocked`` is always true.
These tools never unlock Distro, publish, call YouTube or Spotify, or spend money.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from fftf_tools.machine import (
    BASE_FENCES,
    CHANNEL_NAME,
    CHANNEL_SHORT,
    machine_block,
    write_machine_json,
)

CHANNEL_DISPLAY = CHANNEL_NAME

# These fences describe what the tools themselves refuse to do.
# Claim-gate holds them by policy instead of scanning narration for the words.
TOOL_FENCE_IDS = {
    "no-publish",
    "no-distro",
    "no-platform-api",
    "no-invented-sources",
    "no-invented-urls",
    "distro-blocked",
}

_SCHEMA_NAME = "machine-contract.schema.json"
_SCHEMA_CACHE: dict[str, Any] | None = None


class ContractError(ValueError):
    """Raised when a machine block violates the shared contract."""

    def __init__(self, errors: list[str] | str):
        if isinstance(errors, str):
            errors = [errors]
        self.errors = errors
        super().__init__("; ".join(errors))


def schema_path() -> Path:
    """Locate ``schemas/machine-contract.schema.json`` from the repo or install tree."""
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "schemas" / _SCHEMA_NAME
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(f"schemas/{_SCHEMA_NAME} not found from {here}")


def machine_schema() -> dict[str, Any]:
    global _SCHEMA_CACHE
    if _SCHEMA_CACHE is None:
        _SCHEMA_CACHE = json.loads(schema_path().read_text(encoding="utf-8"))
    return _SCHEMA_CACHE


def _type_ok(instance: Any, types: str | list[str]) -> bool:
    if isinstance(types, str):
        types = [types]
    for kind in types:
        if kind == "object" and isinstance(instance, dict):
            return True
        if kind == "array" and isinstance(instance, list):
            return True
        if kind == "string" and isinstance(instance, str):
            return True
        if kind == "integer" and isinstance(instance, int) and not isinstance(instance, bool):
            return True
        if kind == "number" and isinstance(instance, (int, float)) and not isinstance(instance, bool):
            return True
        if kind == "boolean" and isinstance(instance, bool):
            return True
        if kind == "null" and instance is None:
            return True
    return False


def validate_instance(instance: Any, schema: dict[str, Any], path: str = "$") -> list[str]:
    """Validate ``instance`` against the subset of JSON Schema these contracts use."""
    errors: list[str] = []
    if "const" in schema and instance != schema["const"]:
        errors.append(f"{path}: expected const {schema['const']!r}, got {instance!r}")

    types = schema.get("type")
    if types is not None and not _type_ok(instance, types):
        errors.append(f"{path}: expected type {types}, got {type(instance).__name__}")
        return errors

    if "enum" in schema and instance not in schema["enum"]:
        errors.append(f"{path}: {instance!r} is not one of {schema['enum']}")

    if isinstance(instance, str):
        if "minLength" in schema and len(instance) < schema["minLength"]:
            errors.append(f"{path}: shorter than minLength {schema['minLength']}")
        if "pattern" in schema and re.search(schema["pattern"], instance) is None:
            errors.append(f"{path}: does not match {schema['pattern']}")

    if (
        "minimum" in schema
        and isinstance(instance, (int, float))
        and not isinstance(instance, bool)
        and instance < schema["minimum"]
    ):
        errors.append(f"{path}: below minimum {schema['minimum']}")

    if isinstance(instance, dict) and (types == "object" or (isinstance(types, list) and "object" in types) or "properties" in schema):
        props = schema.get("properties", {})
        for key in schema.get("required", []):
            if key not in instance:
                errors.append(f"{path}.{key}: required")
        additional = schema.get("additionalProperties", True)
        for key, val in instance.items():
            child = f"{path}.{key}"
            if key in props:
                errors.extend(validate_instance(val, props[key], child))
            elif additional is False:
                errors.append(f"{child}: additional property not allowed")

    if isinstance(instance, list) and "items" in schema:
        item_schema = schema["items"]
        for index, item in enumerate(instance):
            errors.extend(validate_instance(item, item_schema, f"{path}[{index}]"))

    return errors


def validate_machine(data: Any) -> list[str]:
    """Return contract errors. An empty list means the block is valid."""
    if not isinstance(data, dict):
        return ["$: machine contract must be a JSON object"]
    return validate_instance(data, machine_schema())


def seal(payload: dict[str, Any]) -> dict[str, Any]:
    """Copy ``payload``, force Distro locked and sources unverified, then validate.

    Callers cannot unlock Distro by passing false, and cannot mark a source
    verified. The written block is rejected if any other contract rule fails.
    """
    if not isinstance(payload, dict):
        raise ContractError("machine contract must be a JSON object")
    data = dict(payload)
    data["distro_blocked"] = True
    sources = data.get("sources")
    if isinstance(sources, list):
        locked_sources = []
        for item in sources:
            if isinstance(item, dict):
                item = dict(item)
                item["verified"] = False
            locked_sources.append(item)
        data["sources"] = locked_sources
    errors = validate_machine(data)
    if errors:
        raise ContractError(errors)
    return data


def write_machine(path: Path | str, payload: dict[str, Any]) -> dict[str, Any]:
    """Validate, then write through ``fftf_tools.machine.write_machine_json``."""
    sealed = seal(payload)
    write_machine_json(path, sealed)
    return sealed


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or "episode"


def normalize_episode_id(raw: str) -> str:
    episode_id = slugify(raw)
    if not episode_id:
        raise ContractError("episode_id is empty")
    return episode_id


def load_json_value(value: str | None) -> Any:
    """Load a JSON object/array from a file path or an inline JSON string."""
    if value is None or value == "":
        return None
    path = Path(value)
    raw = path.read_text(encoding="utf-8") if path.is_file() else value
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ContractError(f"invalid JSON: {exc}") from exc


def find_sibling_machine(path: Path) -> Path | None:
    """Return the only machine block next to ``path``, or the path itself.

    Accepts ``*.machine.json`` (pipeline) and ``machine.json`` (distro-pack /
    shorts-cutter). Two different blocks in the same directory are ambiguous.
    """
    path = Path(path)
    if path.is_file() and (path.name == "machine.json" or path.name.endswith(".machine.json")):
        return path
    named = sorted(path.parent.glob("*.machine.json"))
    plain = path.parent / "machine.json"
    unique: list[Path] = []
    seen: set[Path] = set()
    for candidate in [*named, plain]:
        if not candidate.is_file():
            continue
        key = candidate.resolve()
        if key in seen:
            continue
        seen.add(key)
        unique.append(candidate)
    if len(unique) == 1:
        return unique[0]
    return None


@dataclass
class Source:
    n: int
    url: str
    label: str
    origin: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Emit the pipeline fields and the Wave 2 source fields on one object."""
        data: dict[str, Any] = {
            "id": f"s{self.n}",
            "n": self.n,
            "locator": self.url,
            "url": self.url,
            "label": self.label,
            "verified": False,
        }
        if self.origin:
            data["origin"] = self.origin
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Source:
        url = str(data.get("url") or data.get("locator") or "")
        n_raw = data.get("n")
        if n_raw is None:
            match = re.fullmatch(r"s(\d+)", str(data.get("id", "")).strip())
            n_raw = int(match.group(1)) if match else 0
        if int(n_raw) < 1:
            raise ContractError("source n is required")
        return cls(
            n=int(n_raw),
            url=url,
            label=str(data.get("label", "")),
            origin=str(data.get("origin") or ""),
        )


@dataclass
class Fence:
    id: str
    rule: str
    status: str = "unknown"
    pattern: str | None = None

    def __post_init__(self) -> None:
        if self.status not in {"held", "broken", "unknown"}:
            raise ContractError(
                f"fence {self.id!r} status {self.status!r} must be held, broken, or unknown"
            )
        if not self.id:
            raise ContractError("fence id is required")

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "id": self.id,
            "text": self.rule,
            "rule": self.rule,
            "status": self.status,
            "locked": True,
        }
        if self.pattern:
            data["pattern"] = self.pattern
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Fence:
        if not isinstance(data, dict):
            raise ContractError("fence must be a JSON object")
        status = data.get("status") or "unknown"
        pattern = data.get("pattern")
        rule = str(data.get("rule") or data.get("text") or "").strip()
        return cls(
            id=str(data.get("id", "")).strip(),
            rule=rule,
            status=str(status),
            pattern=str(pattern) if pattern else None,
        )


@dataclass
class Asset:
    path: str
    beat: str = ""
    license: str = ""
    sha256: str = ""
    role: str = ""
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Emit ``role`` always, and beat fields only when a beat is set.

        Wave 2 assets are ``{role, path}``. An empty ``beat`` is omitted so
        that shape still validates against the beat enum.
        """
        role = self.role or self.beat
        data: dict[str, Any] = {"path": self.path}
        if role:
            data["role"] = role
        if self.beat:
            data["beat"] = self.beat
            data["license"] = self.license
            data["sha256"] = self.sha256
        if self.note:
            data["note"] = self.note
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Asset:
        return cls(
            path=str(data.get("path", "")),
            beat=str(data.get("beat") or ""),
            license=str(data.get("license") or ""),
            sha256=str(data.get("sha256") or ""),
            role=str(data.get("role") or ""),
            note=str(data.get("note") or ""),
        )


@dataclass
class MachineContract:
    episode_id: str
    sources: list[Source] = field(default_factory=list)
    fences: list[Fence] = field(default_factory=list)
    asset_index: list[Asset] = field(default_factory=list)
    distro_blocked: bool = True
    extras: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.distro_blocked is not True:
            raise ContractError("distro_blocked must be true; these tools never unlock Distro")

    def to_dict(self) -> dict[str, Any]:
        return contract_payload(
            self.episode_id,
            sources=self.sources,
            fences=self.fences,
            asset_index=self.asset_index,
            **self.extras,
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MachineContract:
        errors = validate_machine(data)
        if errors:
            raise ContractError(errors)
        known = {"episode_id", "sources", "fences", "asset_index", "distro_blocked"}
        extras = {key: value for key, value in data.items() if key not in known}
        return cls(
            episode_id=data["episode_id"],
            sources=[Source.from_dict(item) for item in data["sources"]],
            fences=[Fence.from_dict(item) for item in data["fences"]],
            asset_index=[Asset.from_dict(item) for item in data["asset_index"]],
            distro_blocked=True,
            extras=extras,
        )


def read_machine(path: Path | str) -> MachineContract:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return MachineContract.from_dict(data)


def parse_fences(data: Any) -> list[Fence]:
    if data is None:
        return []
    if isinstance(data, dict) and "fences" in data:
        data = data["fences"]
    if not isinstance(data, list):
        raise ContractError("fences must be a JSON list")
    return [Fence.from_dict(item) for item in data]


def parse_sources(data: Any) -> list[Source]:
    if data is None:
        return []
    if isinstance(data, dict) and "sources" in data:
        data = data["sources"]
    if not isinstance(data, list):
        raise ContractError("sources must be a JSON list")
    sources: list[Source] = []
    for item in data:
        if not isinstance(item, dict):
            raise ContractError("each source must be a JSON object")
        if not any(key in item for key in ("n", "id", "url", "locator")):
            raise ContractError("source n is required")
        sources.append(Source.from_dict(item))
    return sources


def parse_assets(data: Any) -> list[Asset]:
    if data is None:
        return []
    if isinstance(data, dict) and "asset_index" in data:
        data = data["asset_index"]
    if not isinstance(data, list):
        raise ContractError("asset index must be a JSON list")
    return [Asset.from_dict(item) for item in data]


def default_fences() -> list[Fence]:
    """Base tool fences from ``machine.BASE_FENCES``, plus the vocab fence."""
    fences = [Fence.from_dict({**item, "status": "held"}) for item in BASE_FENCES]
    fences.extend(
        [
            Fence(
                id="no-invented-urls",
                rule="Do not invent primary-source URLs.",
                status="held",
            ),
            Fence(
                id="distro-blocked",
                rule="Do not unlock Distro, publish, or call YouTube or Spotify.",
                status="held",
            ),
            Fence(
                id="vocab-cartoon",
                rule="Spoken narration must not contain the word cartoon.",
                status="unknown",
            ),
            Fence(
                id="vocab-spine",
                rule="Spoken narration must not contain the word spine.",
                status="unknown",
            ),
        ]
    )
    return fences


def hold_tool_fences(fences: list[Fence]) -> None:
    """Mark tool-behavior fences held. They are enforced by the tools, not by a token scan."""
    for fence in fences:
        if fence.id in TOOL_FENCE_IDS:
            fence.status = "held"


def merge_fences(*groups: list[Fence]) -> list[Fence]:
    """Later groups override the same fence id."""
    merged: dict[str, Fence] = {}
    for group in groups:
        for fence in group:
            merged[fence.id] = fence
    return list(merged.values())


def channel_line() -> str:
    return f"Channel: {CHANNEL_DISPLAY} ({CHANNEL_SHORT})"


def one_line(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def contract_payload(
    episode_id: str,
    sources: list[Source],
    fences: list[Fence],
    asset_index: list[Asset] | None = None,
    **extras: Any,
) -> dict[str, Any]:
    """Build a contract dict through ``machine_block``.

    ``distro_blocked`` is forced true. Unlock, publish, and upload extras are dropped.
    """
    protected = {"episode_id", "sources", "fences", "asset_index", "distro_blocked"}
    extras_clean = {key: value for key, value in extras.items() if key not in protected}
    try:
        return machine_block(
            episode_id=normalize_episode_id(episode_id),
            sources=[source.to_dict() for source in sources],
            fences=[fence.to_dict() for fence in fences],
            asset_index=[asset.to_dict() for asset in (asset_index or [])],
            **extras_clean,
        )
    except ValueError as exc:
        raise ContractError(str(exc)) from exc
