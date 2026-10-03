"""Server-side limits on user-supplied profiles.

A reviewer may submit `profile_yaml`, which names an endpoint, an environment variable for the
bearer token and local files. Without limits that is a way to make the server send its own secrets
to an arbitrary host or read arbitrary files, so the API enforces an allow-list for
`auth_env` and keeps every path inside a configured data root.
"""

from __future__ import annotations

from pathlib import Path

from maat.api.settings import ApiSettings
from maat.schemas.profile import SystemProfile


def _paths(prof: SystemProfile) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    if prof.target.config:
        out.append(("target.config", prof.target.config))
    t = prof.tabular
    if t is not None:
        for name in ("dataset", "model_file", "train_dataset", "reference_dataset"):
            v = getattr(t, name)
            if v:
                out.append((f"tabular.{name}", v))
    a = prof.artifacts
    out += [(f"artifacts.docs[{i}]", d) for i, d in enumerate(a.docs)]
    for name in ("corpus", "logs", "qa_set"):
        v = getattr(a, name)
        if v:
            out.append((f"artifacts.{name}", v))
    if prof.ers:
        out.append(("ers", prof.ers))
    return out


def validate_profile_for_api(prof: SystemProfile, settings: ApiSettings) -> None:
    """Raise ValueError (shown to the client as a 422) if the profile asks for too much."""
    env = prof.target.auth_env
    if env and env not in settings.allowed_auth_env:
        raise ValueError(
            f"target.auth_env {env!r} is not on this server's allow-list "
            "(MAAT_API_ALLOWED_AUTH_ENV)"
        )
    root = Path(settings.data_root).resolve()
    for field, raw in _paths(prof):
        if "://" in raw:
            raise ValueError(f"{field}: URLs are not accepted, use a path under the data root")
        resolved = Path(raw).resolve()  # the loaders resolve relative paths against the cwd
        if not resolved.is_relative_to(root):
            raise ValueError(f"{field}: path is outside the server data root")
