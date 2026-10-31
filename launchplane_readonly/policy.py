import hashlib
import json
import re
from collections.abc import Mapping
from typing import Any

RUNTIME_ENV = "LAUNCHPLANE_RUNTIME_IDENTITY_JSON"
COPY_PARAMETER = "launchplane.testing_copy.restore_complete"
GROUP = "launchplane_readonly.group_user"


def canonical_identity(identity: Mapping[str, Any]) -> dict[str, Any]:
    result = dict(identity)
    revision = result.pop("source_revision", None)
    if revision is not None:
        if result.get("source_git_ref", revision) != revision:
            raise ValueError("Conflicting source identity")
        result["source_git_ref"] = revision
    result.pop("deployed_at", None)
    return result


def product_login(product: str) -> str:
    encoded = json.dumps(product, ensure_ascii=True, allow_nan=False, sort_keys=True, separators=(",", ":")).encode()
    return "lp_walk_" + hashlib.sha256(encoded).hexdigest()[:32]


def qualify_runtime(
    identity: object, runtime: str, platform_instance: str, database: str, database_uuid: str, copy_witness: str
) -> dict[str, str]:
    if not isinstance(identity, dict):
        raise ValueError("Missing runtime identity")
    observed = json.loads(runtime)
    if not isinstance(observed, dict) or canonical_identity(identity) != canonical_identity(observed):
        raise ValueError("Runtime identity changed")
    for name in ("product", "context", "instance", "deployment_record_id", "artifact_id", "source_git_ref"):
        value = canonical_identity(identity).get(name)
        if not isinstance(value, str) or not value.strip():
            raise ValueError("Incomplete runtime identity")
    if identity.get("schema_version") != 1 or not database or not database_uuid:
        raise ValueError("Unknown runtime or database")
    if identity.get("database_uuid") and identity["database_uuid"] != database_uuid:
        raise ValueError("Database identity changed")
    kind = identity.get("environment_kind")
    instance = identity["instance"]
    if kind == "stable" and instance == "testing" and platform_instance == "testing":
        if not re.fullmatch(r"[a-f0-9]{64}", copy_witness):
            raise ValueError("Missing testing copy witness")
        if identity.get("preview_id") or identity.get("preview_generation_id"):
            raise ValueError("Unexpected preview identity")
    elif kind == "preview" and platform_instance == "preview" and instance.lower() not in {"prod", "production", "testing"}:
        if not all(isinstance(identity.get(key), str) and identity[key].strip() for key in ("preview_id", "preview_generation_id")):
            raise ValueError("Missing preview identity")
        copy_witness = ""
    else:
        raise ValueError("Read-only QA requires a testing or preview target")
    return {
        "product": identity["product"],
        "context": identity["context"],
        "instance": instance,
        "environment_kind": kind,
        "preview_id": identity.get("preview_id", ""),
        "database": database,
        "database_uuid": database_uuid,
        "testing_copy": copy_witness,
    }
