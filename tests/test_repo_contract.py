"""Repository contract tests (offline; stdlib + pytest). Run: python -m pytest -q tests

They replace #8's placeholder tests/test_smoke.py, which no workflow ran. Its compile test wrote the
__pycache__/*.pyc files that #8 then committed, and its import test always skipped ("repository declares no
importable package").

Each test checks one coupling between files that would otherwise drift apart silently:
  * pyproject.toml ships tools/compass/szl_frontier_compass.py, and its console script is that module's CLI;
  * the module imports only the standard library, which is what `dependencies = []` and the README claim;
  * every argv the scheduled / dispatched workflow passes is accepted by the real CLI parser;
  * CI runs every test module, and pull requests that touch a tested file trigger it;
  * no bytecode is tracked, and .gitignore keeps the files tests and builds generate out of git.
"""
from __future__ import annotations

import argparse
import ast
import fnmatch
import importlib
import re
import shlex
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if not (ROOT / ".git").exists():
    pytest.skip("repository contract tests need a git checkout (an sdist has no .github/ or requirements/)",
                allow_module_level=True)

PYPROJECT = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
SETUPTOOLS = PYPROJECT["tool"]["setuptools"]
WORKFLOW = (ROOT / ".github" / "workflows" / "frontier-compass.yml").read_text(encoding="utf-8")
TOOL = ROOT / "tools" / "compass" / "szl_frontier_compass.py"


def _git(*args):
    return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True, timeout=60)


def _tracked():
    p = _git("ls-files", "-z")
    assert p.returncode == 0, p.stderr
    return [f for f in p.stdout.split("\0") if f]


def _test_modules():
    patterns = PYPROJECT["tool"]["pytest"]["ini_options"].get("python_files", ["test_*.py", "*_test.py"])
    return sorted(f for f in _tracked() if any(fnmatch.fnmatchcase(Path(f).name, p) for p in patterns))


def _covers(target, path):
    return Path(target) == Path(path) or Path(target) in Path(path).parents


class _ParsedArgs(Exception):
    def __init__(self, namespace):
        super().__init__("parsed")
        self.namespace = namespace


def _entry_point():
    """Import the console-script target the way an install does: from the package-dir that pyproject.toml declares."""
    mod_name, _, func_name = PYPROJECT["project"]["scripts"]["szl-frontier-compass"].partition(":")
    sys.path.insert(0, str(ROOT / SETUPTOOLS["package-dir"][""]))
    try:
        module = importlib.import_module(mod_name)
    finally:
        sys.path.pop(0)
    return module, getattr(module, func_name)


def _cli_parse(argv, monkeypatch):
    """Run the console-script target on argv, but stop right after its own parser accepted the arguments."""
    _, main = _entry_point()
    real_parse = argparse.ArgumentParser.parse_args

    def parse_then_stop(self, args=None, namespace=None):
        raise _ParsedArgs(real_parse(self, args, namespace))

    monkeypatch.setattr(argparse.ArgumentParser, "parse_args", parse_then_stop)
    try:
        main(argv)
    except _ParsedArgs as done:
        return done.namespace
    except SystemExit as exc:  # argparse rejected argv (exit 2) or printed --help (exit 0)
        return exc
    raise AssertionError("main() returned without parsing its arguments")


def test_distribution_ships_the_compass_module_and_nothing_else():
    assert SETUPTOOLS["py-modules"] == ["szl_frontier_compass"]
    assert (ROOT / SETUPTOOLS["package-dir"][""] / "szl_frontier_compass.py").resolve() == TOOL.resolve()
    assert "packages" not in SETUPTOOLS  # #8 declared packages = [], which built a wheel with no module in it


def test_compass_imports_only_the_standard_library():
    roots = set()
    for node in ast.walk(ast.parse(TOOL.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            roots |= {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.level == 0:
            roots.add(node.module.split(".")[0])
    assert roots and not roots - set(sys.stdlib_module_names), "declare third-party imports in pyproject.toml"
    assert PYPROJECT["project"]["dependencies"] == []


def test_console_script_is_the_compass_cli(monkeypatch, capsys):
    module, _ = _entry_point()
    assert Path(module.__file__).resolve() == TOOL.resolve()
    exc = _cli_parse(["--help"], monkeypatch)
    assert isinstance(exc, SystemExit) and exc.code == 0
    out = capsys.readouterr().out
    assert module.VERSION in out and "--fail-on" in out


def test_every_fail_on_value_the_workflow_can_pass_is_accepted(monkeypatch):
    run = re.search(r"python -X utf8 tools/compass/szl_frontier_compass\.py((?:[^\n]*\\\n)*[^\n]*)", WORKFLOW)
    assert run, "the scheduled step no longer runs tools/compass/szl_frontier_compass.py"
    argv = shlex.split(run.group(1).replace("\\\n", " "))
    assert "$FAIL_ON" in argv and "--file-issues" not in argv  # tools/compass/README.md: "CI never files"
    dispatch = re.search(r"\n      fail_on:\n((?:        .*\n)+)", WORKFLOW)
    assert dispatch, "workflow_dispatch input fail_on not found"
    options = re.findall(r'"([^"]+)"', re.search(r"options:\s*\[([^\]]*)\]", dispatch.group(1)).group(1))
    default = re.search(r'default:\s*"([^"]+)"', dispatch.group(1)).group(1)
    scheduled = re.search(r"inputs\.fail_on \|\| '([^']+)'", WORKFLOW).group(1)  # schedule runs have no inputs
    assert default in options and scheduled in options
    for value in options:
        parsed = _cli_parse([value if a == "$FAIL_ON" else a for a in argv], monkeypatch)
        assert isinstance(parsed, argparse.Namespace), f"the CLI rejects the workflow's argv with --fail-on {value}"
        assert parsed.fail_on == value and parsed.receipts == "" and parsed.file_issues is False  # read-only CI


def test_ci_and_plain_pytest_run_every_test_module():
    modules = _test_modules()
    assert "tests/test_repo_contract.py" in modules and "tools/compass/test_szl_frontier_compass.py" in modules
    command = re.search(r"python -m pytest([^\n]*)", WORKFLOW)
    assert command, "the workflow no longer runs pytest"
    ci_targets = [t for t in shlex.split(command.group(1)) if (ROOT / t).exists()]
    testpaths = PYPROJECT["tool"]["pytest"]["ini_options"]["testpaths"]
    assert [m for m in modules if not any(_covers(t, m) for t in ci_targets)] == [], "add it to the CI pytest step"
    assert [m for m in modules if not any(_covers(t, m) for t in testpaths)] == [], "add it to pytest testpaths"


def test_pull_requests_that_touch_tested_files_trigger_ci():
    block = re.search(r"\n  pull_request:\n    paths:\n((?:      - .*\n)+)", WORKFLOW)
    assert block, "pull_request paths filter not found"
    patterns = re.findall(r'- "([^"]+)"', block.group(1))
    watched = [*_test_modules(), str(TOOL.relative_to(ROOT)), "pyproject.toml", ".gitignore",
               "requirements/frontier-observer-tests.lock", ".github/workflows/frontier-compass.yml"]
    assert [f for f in watched if not any(fnmatch.fnmatchcase(f, p) for p in patterns)] == []


def test_no_bytecode_is_tracked():
    assert [f for f in _tracked() if f.endswith((".pyc", ".pyo")) or "__pycache__/" in f] == []


@pytest.mark.parametrize("generated", [
    "tools/compass/__pycache__/szl_frontier_compass.cpython-314.pyc",  # what #8 committed
    "tests/__pycache__/test_repo_contract.cpython-313-pytest-9.0.3.pyc",  # pytest assertion rewriting
    ".pytest_cache/v/cache/nodeids",
    "tools/compass/frontier_compass.egg-info/PKG-INFO",  # pip install -e . / python -m build
    "compass-out/compass_report.json",  # --out used by CI and tools/compass/README.md
    "szl-compass-out/compass_report.json",  # the CLI's default --out
])
def test_generated_files_are_ignored(generated):
    assert _git("check-ignore", "-q", "--no-index", generated).returncode == 0, f"{generated} is not git-ignored"
