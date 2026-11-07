from squidz.infra import etw_helper


def test_etw_helper_starts_and_stops_its_trace(monkeypatch, tmp_path):
    session = "SquidzDebugTest"
    providers = tmp_path / "providers.txt"
    etl = tmp_path / "events.etl"
    ready = tmp_path / "ready.txt"
    stop = tmp_path / "stop.txt"
    result = tmp_path / "result.txt"
    providers.write_text("{provider-guid} 0xFFFFFFFFFFFFFFFF 5\n")
    commands = []

    def run(command):
        commands.append(command)
        if command[1:3] == ["start", session]:
            stop.touch()

    monkeypatch.setattr(etw_helper, "_run", run)
    monkeypatch.setattr(etw_helper.psutil, "pid_exists", lambda _pid: True)

    exit_code = etw_helper.run_etw_helper(
        session, str(providers), str(etl), str(ready), str(stop), str(result), 1234)

    assert exit_code == 0
    assert [command[1] for command in commands] == ["create", "start", "stop", "delete"]
    assert ready.read_text() == "READY"
    assert result.read_text() == ""


def test_etw_helper_reports_session_creation_errors(monkeypatch, tmp_path):
    ready = tmp_path / "ready.txt"
    result = tmp_path / "result.txt"

    def fail(_command):
        raise RuntimeError("access denied")

    monkeypatch.setattr(etw_helper, "_run", fail)

    exit_code = etw_helper.run_etw_helper(
        "SquidzDebugTest", "providers.txt", "events.etl",
        str(ready), str(tmp_path / "stop.txt"), str(result), 1234)

    assert exit_code == 1
    assert ready.read_text() == "ERROR\naccess denied"
    assert result.read_text() == "access denied"
