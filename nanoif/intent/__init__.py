"""Intent traceability: feature acceptance criteria, ADRs, and the commit gate.

Three layers of intent live in the repo: why (``VISION.md``, ``PRINCIPLES.md``,
``PRIORITIES.md``), what (``features/*.md`` acceptance criteria with stable ids)
and how (``ARCHITECTURE.md`` and ``architecture/NNN-*.md`` ADRs). This package
keeps them honest:

* :func:`check_repo` verifies every criterion id is well formed and unique, every
  ``verify: test`` criterion is cited by at least one test through
  ``@pytest.mark.intent(...)``, every citation resolves, and every ADR has a status.
* :func:`check_commit` refuses a commit that changes governed code without either
  touching an intent document or carrying an ``Intent: unchanged (<reason>)``
  trailer, so behaviour cannot drift from documented intent silently.
"""

from nanoif.intent.check import Finding, check_repo
from nanoif.intent.docs import Adr, Citation, Criterion, IntentIndex, load_index, scan_citations
from nanoif.intent.gate import CommitResult, check_commit, check_range, classify_paths

__all__ = [
    "Adr",
    "Citation",
    "CommitResult",
    "Criterion",
    "Finding",
    "IntentIndex",
    "check_commit",
    "check_range",
    "check_repo",
    "classify_paths",
    "load_index",
    "scan_citations",
]
