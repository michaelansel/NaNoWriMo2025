"""Every typed error, including the LLM client's, reaches the user as one line."""

import pytest

import nanoif.cli as cli
from nanoif.errors import NanoifError
from nanoif.llm.errors import LLMError, LLMTransportError


@pytest.mark.intent("ADR-015")
def test_llm_errors_are_nanoif_errors():
    assert issubclass(LLMError, NanoifError)


@pytest.mark.intent("ADR-015")
def test_llm_error_reaching_the_cli_is_one_line_and_exit_1(monkeypatch, tmp_path, capsys):
    def boom(_args):
        raise LLMTransportError("provider returned HTTP 503: overloaded", status=503)

    monkeypatch.setattr(cli, "_intent_check", boom)
    assert cli.main(["intent", "check", "--repo", str(tmp_path)]) == 1
    err = capsys.readouterr().err
    assert err.strip() == "error: provider returned HTTP 503: overloaded"
