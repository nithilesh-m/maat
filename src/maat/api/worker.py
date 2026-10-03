from __future__ import annotations

import json
import shutil
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

from maat import service
from maat.api.events import EventLog
from maat.config import load_config
from maat.evidence.signing import RunKey
from maat.profile.loader import load_profile
from maat.runner import RunConfig


class Worker:
    """Runs audits on a small thread pool (one by default: a single GPU runs audits in turn)."""

    def __init__(self, settings, store, max_workers: int = 1) -> None:
        self.settings, self.store = settings, store
        self.pool = ThreadPoolExecutor(max_workers=max_workers)

    def events_dir(self, run_id: str) -> Path:
        return self.settings.runs_dir / "_events" / run_id

    def approval_file(self, run_id: str) -> Path:
        return self.settings.runs_dir / "_events" / f"{run_id}.approval.json"

    def replay_file(self, run_id: str) -> Path:
        return self.settings.runs_dir / "_events" / f"{run_id}.replay.json"

    def submit(
        self,
        run_id: str,
        profile_path: Path,
        planner: str,
        auto_approve: bool,
        resume_answer: dict | None = None,
        resume_existing: bool = False,
    ) -> None:
        self.store.set_status(run_id, "queued")
        self.pool.submit(
            self._run, run_id, profile_path, planner, auto_approve, resume_answer, resume_existing
        )

    def remediation_file(self, run_id: str) -> Path:
        return self.settings.runs_dir / "_events" / f"{run_id}.remediation.json"

    def submit_remediation(self, run_id: str, mitigation_ids: list[str], signer) -> None:
        self.pool.submit(self._remediate, run_id, mitigation_ids, signer)

    def submit_replay(self, run_id: str) -> None:
        self.pool.submit(self._replay, run_id)

    def _run(self, run_id, profile_path, planner, auto_approve, resume_answer, resume_existing):
        s = self.settings
        events = EventLog(self.events_dir(run_id))
        self.store.set_status(run_id, "running")
        run_dir = s.runs_dir / run_id
        try:
            prof = load_profile(profile_path)
            maat_cfg = None
            if planner == "agents" or Path(s.maat_config).exists():
                maat_cfg = load_config(s.maat_config)
            now = datetime.now(UTC)
            cfg = RunConfig(
                run_id=run_id,
                run_dir=run_dir,
                signer=RunKey.generate(),
                as_of=now,
                on_event=events.append,
                resume_existing=resume_existing,
                meta={
                    "run_id": run_id,
                    "planner": planner,
                    "options": {"planner": planner},
                    "as_of": now.isoformat(),
                    "auto_approve": auto_approve,
                    "allow_same_family": False,
                    "llm_mode": maat_cfg.llm_mode if maat_cfg else None,
                },
            )
            resume = (lambda q: resume_answer) if resume_answer is not None else None
            service.execute_audit(
                prof,
                service.build_target(prof),
                cfg,
                maat_cfg,
                service.AuditOptions(
                    planner=planner, allow_same_family_judges=s.allow_same_family_judges
                ),
                service.make_screen(s.screen),
                resume,
                auto_approve=auto_approve,
            )
            shutil.copy2(profile_path, run_dir / "profile.yaml")
            if planner == "agents" and Path(s.maat_config).exists():
                shutil.copy2(s.maat_config, run_dir / "maat.toml")
            self.approval_file(run_id).unlink(missing_ok=True)
            self.store.set_status(run_id, "complete")
        except service.ApprovalNeeded as e:
            self.approval_file(run_id).parent.mkdir(parents=True, exist_ok=True)
            self.approval_file(run_id).write_text(json.dumps(e.question, default=str))
            events.append("approval_needed", {"question": e.question})
            self.store.set_status(run_id, "paused")
        except Exception as e:  # noqa: BLE001 - surfaced to the client, never a traceback
            events.append("run_failed", {"error": f"{type(e).__name__}: {e}"})
            self.store.set_status(run_id, "failed", f"{type(e).__name__}: {e}")

    def _replay(self, run_id: str) -> None:
        run_dir = self.settings.runs_dir / run_id
        try:
            matched, message = service.replay_audit(
                run_dir, self.settings.runs_dir / "_replays", service.build_target
            )
        except ValueError as e:
            matched, message = False, str(e)
        self.replay_file(run_id).parent.mkdir(parents=True, exist_ok=True)
        self.replay_file(run_id).write_text(json.dumps({"matched": matched, "message": message}))

    def _remediate(self, run_id: str, mitigation_ids: list[str], signer) -> None:
        run_dir = self.settings.runs_dir / run_id
        events = EventLog(self.events_dir(run_id))
        out = self.remediation_file(run_id)
        out.parent.mkdir(parents=True, exist_ok=True)
        try:
            prof = load_profile(run_dir / "profile.yaml")
            result = service.remediate_run(
                run_dir,
                prof,
                apply=True,
                signer=signer,
                config=self.settings.maat_config,
                target_builder=service.build_target,
                mitigation_ids=mitigation_ids,
                allow_same_family_judges=self.settings.allow_same_family_judges,
            )
            summary = {
                "child": result.child_dir.name if result.child_dir else None,
                "summary": result.summary,
                "notes": result.notes,
            }
            events.append("remediation_finished", summary)
            out.write_text(json.dumps({"ok": True, **summary}, default=str))
        except Exception as e:  # noqa: BLE001 - surfaced to the client
            msg = f"{type(e).__name__}: {e}"
            events.append("remediation_failed", {"error": msg})
            out.write_text(json.dumps({"ok": False, "error": msg}))
