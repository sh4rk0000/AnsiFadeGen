import io

import pytest

from ansifadegen import cli
from ansifadegen.engine import strip_ansi


class FakeStdin(io.StringIO):
    def isatty(self):
        return False


def run(monkeypatch, capsys, argv, stdin="hi\nthere\n"):
    monkeypatch.setattr("sys.stdin", FakeStdin(stdin))
    code = cli.main(argv)
    return code, capsys.readouterr()


def test_stdout_pipeline(monkeypatch, capsys):
    code, cap = run(monkeypatch, capsys, ["-c", "red,blue", "-d", "horizontal"])
    assert code == 0 and strip_ansi(cap.out) == "hi\nthere\n"


def test_file_output(tmp_path, monkeypatch, capsys):
    src, dst = tmp_path / "in.txt", tmp_path / "out.html"
    src.write_text("abc", encoding="utf-8")
    code, _ = run(monkeypatch, capsys, [str(src), "-p", "Neon", "-f", "html", "-o", str(dst)])
    assert code == 0 and "<pre>" in dst.read_text(encoding="utf-8")


def test_bad_colour_reports_error(monkeypatch, capsys):
    code, cap = run(monkeypatch, capsys, ["-c", "red,nope"])
    assert code == 1 and "Invalid colour" in cap.err


def test_missing_file(monkeypatch, capsys):
    code, cap = run(monkeypatch, capsys, ["/no/such/file"])
    assert code == 1 and cap.err


def test_help_exits_cleanly(capsys):
    with pytest.raises(SystemExit) as e:
        cli.main(["--help"])
    assert e.value.code == 0
