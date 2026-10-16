"""Conservative, durable request and message caps from an explicit human approval."""

import hashlib
import json
import os
import re
from pathlib import Path


class GpuBudget:
    def __init__(
        self, approval_file=Path("HUMAN_TODO.md"), state_dir=Path("data/private/gpu_budget")
    ):
        text = approval_file.read_text(encoding="utf-8")
        lines = re.findall(r"^approved: gpu calls ([1-9]\d*)\s*$", text, re.M)
        if len(lines) != 1:
            raise PermissionError("NOT RUN (needs exactly one explicit GPU approval line)")
        self.cap = int(lines[0])
        self.identity = hashlib.sha256(f"approved: gpu calls {self.cap}".encode()).hexdigest()
        self.directory = state_dir
        self.path = state_dir / f"{self.identity}.json"

    def reserve(self, messages):
        if messages < 1:
            raise ValueError("A request must contain a positive number of messages")
        self.directory.mkdir(parents=True, exist_ok=True)
        lock = self.directory / "budget.lock"
        # An interrupted reservation fails closed until the owner reviews the lock.
        descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        try:
            state = (
                json.loads(self.path.read_text())
                if self.path.exists()
                else {"http_requests": 0, "messages": 0}
            )
            if state["http_requests"] + 1 > self.cap or state["messages"] + messages > self.cap:
                raise PermissionError("GPU approval cap exhausted")
            state["http_requests"] += 1
            state["messages"] += messages
            self.path.write_text(json.dumps(state) + "\n", encoding="utf-8")
        finally:
            os.close(descriptor)
            lock.unlink()


def require_training_approval(path=Path("HUMAN_TODO.md")):
    if not re.search(r"^approved: train\s*$", path.read_text(encoding="utf-8"), re.M):
        raise PermissionError("NOT RUN (needs explicit training approval)")
