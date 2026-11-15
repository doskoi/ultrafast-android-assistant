from __future__ import annotations

import json
import sys

import pytest
from test_jev import click_response
from test_policy import APP_PACKAGE, FakeClient, FakeDevice, snapshot

from jev_android_assistant import cli
from jev_android_assistant.policy import JevPolicy


@pytest.mark.parametrize("option", ["--primary-provider", "--secondary-provider"])
def test_removed_cli_options_exit_before_observation_or_request(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], option: str
) -> None:
    monkeypatch.setattr(sys, "argv", ["assistant", "--package", APP_PACKAGE, option, "laya", "suggest", "goal"])
    with pytest.raises(SystemExit) as exc:
        cli.main()
    assert exc.value.code == 2
    assert "invalid choice: 'laya'" in capsys.readouterr().err


@pytest.mark.parametrize(
    ("options", "environment"),
    [
        (["--model", "/preserved/checkpoint"], {}),
        ([], {"ULTRAFAST_PRIMARY_PROVIDER": "laya", "ULTRAFAST_SECONDARY_PROVIDER": "none"}),
        ([], {"LAYA_MLX_PATH": "/preserved/local/checkout"}),
    ],
)
def test_cli_reports_retired_configuration_before_constructing_device(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    options: list[str],
    environment: dict[str, str],
) -> None:
    for variable, value in environment.items():
        monkeypatch.setenv(variable, value)
    monkeypatch.setattr(sys, "argv", ["assistant", "--package", APP_PACKAGE, *options, "suggest", "goal"])

    def unexpected_device(**kwargs: object) -> None:
        raise AssertionError("Device must not be touched with retired model configuration")

    monkeypatch.setattr(cli, "AdbDevice", unexpected_device)
    with pytest.raises(SystemExit) as exc:
        cli.main()
    assert exc.value.code == 2
    assert "remote Jev" in capsys.readouterr().err


@pytest.mark.parametrize("command", ["inspect", "suggest", "run"])
def test_cli_commands_keep_jev_and_guarded_execution(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], command: str
) -> None:
    device = FakeDevice(snapshot())
    remote = FakeClient(click_response())
    monkeypatch.setattr(cli, "AdbDevice", lambda **kwargs: device)
    monkeypatch.setattr(cli, "JevPolicy", lambda **kwargs: JevPolicy(client=remote, **kwargs))
    arguments = ["assistant", "--package", APP_PACKAGE, "--model", "jev-test-model", command]
    if command != "inspect":
        arguments.append("打开市场情绪")
    if command == "run":
        arguments.extend(["--max-steps", "1"])
    monkeypatch.setattr(sys, "argv", arguments)

    cli.main()

    output = capsys.readouterr().out
    if command == "inspect":
        assert json.loads(output)["package"] == APP_PACKAGE
        assert remote.calls == []
        assert device.executed == []
    elif command == "suggest":
        assert json.loads(output)["decision"]["provider"] == "jev"
        assert device.executed == []
        assert len(remote.calls) == 2
    else:
        results = [json.loads(line) for line in output.splitlines()]
        assert [result["status"] for result in results] == ["executed", "blocked"]
        assert device.executed == [("CLICK", "1")]
        assert len(remote.calls) == 2
    assert all(call["model"] == "jev-test-model" for call in remote.calls)
