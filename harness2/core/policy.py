# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""A deployer's pinned policy: always-on text the proposer never sees as an editable file.

The policy lives on `BenchSpec.pinned_policy`, outside the editable tree, so Propose-Probe-Compose
can add rules around it but cannot trim or delete it. It is injected into the staged always-on
file at materialise time and read back before the run; a mismatch raises rather than runs.
With no policy configured every function here is a no-op.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from .tree import SurfaceSpec

BEGIN = "PINNED POLICY (fixed by the deployer; do not override)"
END = "END PINNED POLICY"


def block(policy: str) -> str:
    """The text injected at the head of the first always-on file; empty for no policy.

    Plain text on purpose: JobBench strips HTML comments and the head survives codex's
    tail truncation of AGENTS.md.
    """
    body = policy.strip()
    return f"{BEGIN}\n{body}\n{END}\n\n" if body else ""


def digest(policy: str) -> str:
    """A short identity for the policy; "" when there is none, so fingerprints stay unchanged."""
    b = block(policy)
    return hashlib.sha256(b.encode("utf-8")).hexdigest()[:16] if b else ""


def reserved_chars(policy: str) -> int:
    """How much of the always-on cap the policy consumes."""
    return len(block(policy))


def inject(surface: SurfaceSpec, staged: Path, policy: str) -> None:
    """Prepend the policy block to the staged first always-on file, then verify it."""
    b = block(policy)
    if not b:
        return
    target = Path(staged) / surface.always_on[0]
    target.parent.mkdir(parents=True, exist_ok=True)
    existing = target.read_text(encoding="utf-8") if target.is_file() else ""
    target.write_text(b + existing, encoding="utf-8")
    verify(surface, staged, policy)


def verify(surface: SurfaceSpec, staged: Path, policy: str) -> None:
    """Fail closed unless the staged always-on file still opens with the exact policy block."""
    b = block(policy)
    if not b:
        return
    target = Path(staged) / surface.always_on[0]
    head = target.read_text(encoding="utf-8")[: len(b)] if target.is_file() else ""
    if hashlib.sha256(head.encode("utf-8")).hexdigest()[:16] != digest(policy):
        raise ValueError(
            f"pinned policy missing or altered in staged {surface.always_on[0]}; "
            f"refusing to run without it"
        )
