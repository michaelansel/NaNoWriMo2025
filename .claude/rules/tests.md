---
paths:
  - "tests/**"
---

# Tests

- Plain pytest only: `test_*.py`, `assert`, fixtures in `conftest.py`. No home-made harnesses, no `unittest.TestCase`, no test that swallows exceptions.
- A test that cannot fail is deleted. Every test asserts on a value, an exception, or a file.
- LLM code is tested with `FakeLLM` (scripted responses) and `RecordingLLM` (captures requests); nothing in `tests/` reaches a network.
- `tests/fixtures/eval-story/` is the canonical story. `truth.json` is the ground truth; `test_fixture_integrity.py` proves the story and the truth agree before anything else runs.
- Regression fixtures for known false positives live under `tests/fixtures/` with the original finding as the test name (for example the height-on-four-paths and the sword-on-a-branch cases). They must stay green on every prompt change.
- Eval baselines are committed at `tests/eval/baselines/<profile>.json` and updated only in the same PR as the prompt change that moved them.
- No names, dates, or passage titles from a real writing year. Use eval-story names.
- Tests do not depend on the cwd, tweego, git history, or files outside `tests/`. Build a temp repo with `tmp_path` when git is needed.
- A slow test (over 2 s) is marked `@pytest.mark.slow`; the hook runs `pytest -m "not slow"`, CI runs everything.
- JS tests for the path-id lookup live in `tests/js/` and run through the same CI job.
