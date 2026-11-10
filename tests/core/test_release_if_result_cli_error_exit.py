"""In-memory safe error mapping only; no path, save or numerical pipeline."""
from traffic_anomaly import release_if_result_cli as cli


def enter_failing_operation(monkeypatch, error):
    monkeypatch.setattr(cli, '_arguments', lambda argv: ('inspect', {}))
    monkeypatch.setattr(cli, '_paths', lambda command, options: {})
    def fail(*args):
        raise error
    monkeypatch.setattr(cli, '_execute', fail)
    status, escaped = None, None
    try:
        status = cli.main([])
    except BaseException as caught:
        # Observe the bug as an assertion failure, without interrupting pytest.
        escaped = type(caught).__name__
    return status, escaped


def test_unknown_exact_error_type_never_reads_code_getter(monkeypatch, capfdbinary):
    reads = []
    class UnknownError(ValueError):
        @property
        def code(self):
            reads.append(True)
            raise KeyboardInterrupt('private unknown getter')
    status, escaped = enter_failing_operation(monkeypatch, UnknownError('private'))
    captured = capfdbinary.readouterr()
    assert escaped is None
    assert status == 2
    assert reads == []
    assert captured.out == b''
    assert captured.err == b'{"error":"INTERNAL_ERROR"}\n'


def test_known_exact_error_code_getter_interrupt_uses_terminal_outlet(monkeypatch, capfdbinary):
    reads = []
    error = cli._CLIError('INVALID_ARGUMENTS')
    def interrupted_code(self):
        reads.append(True)
        raise KeyboardInterrupt('private known getter')
    monkeypatch.setattr(cli._CLIError, 'code', property(interrupted_code), raising=False)
    status, escaped = enter_failing_operation(monkeypatch, error)
    captured = capfdbinary.readouterr()
    assert escaped is None
    assert status == 2
    assert reads == [True]
    assert captured.out == b''
    assert captured.err == b'{"error":"INTERRUPTED"}\n'
