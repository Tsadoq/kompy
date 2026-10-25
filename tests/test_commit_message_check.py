"""Tests for ``scripts/check_commit_message.py``, the Conventional Commits check used by pre-commit and CI."""

from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path
from types import ModuleType

import pytest

SCRIPT = Path(__file__).parent.parent / 'scripts' / 'check_commit_message.py'


@pytest.fixture(scope='module')
def check() -> ModuleType:
    spec = importlib.util.spec_from_file_location('check_commit_message', SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    'header',
    [
        'feat: add plan_tour()',
        'fix(cli): handle an empty tour list',
        'feat!: drop Python 3.11',
        'refactor(http)!: rename the retry option',
        'chore(deps): bump requests from 2.32.0 to 2.33.0',
        'chore(main): release 0.2.0',
        'ci: pin actions',
        'docs: fix a typo',
        'Merge pull request #31 from Tsadoq/feature/plan-tour',
        "Merge branch 'main' into feature/plan-tour",
        'Revert "feat: add plan_tour()"',
    ],
)
def test_accepted(check: ModuleType, header: str) -> None:
    assert check.problem_with(header) is None


@pytest.mark.parametrize(
    ('header', 'problem'),
    [
        ('Add plan_tour()', 'does not start with'),
        ('feature: add plan_tour()', 'does not start with'),
        ('Feat: add plan_tour()', 'does not start with'),
        ('feat:add plan_tour()', 'does not start with'),
        ('feat:  ', 'does not start with'),
        ('feat(): add plan_tour()', 'does not start with'),
        ('feat(CLI): add plan_tour()', 'does not start with'),
        ('', 'empty'),
        ('feat: ' + 'x' * 100, 'characters long'),
        ('fixup! feat: add plan_tour()', 'must be squashed'),
    ],
)
def test_rejected(check: ModuleType, header: str, problem: str) -> None:
    assert problem in check.problem_with(header)


def test_autosquash_commits_are_allowed_locally(check: ModuleType) -> None:
    assert check.problem_with('fixup! feat: add plan_tour()', allow_autosquash=True) is None


def test_header_skips_blank_and_comment_lines(check: ModuleType) -> None:
    assert check.header_of('\n# Please enter the commit message\n\nfeat: x\n\nbody\n') == 'feat: x'
    assert check.header_of('# only comments\n') == ''


def test_commit_msg_hook(check: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    good, bad = tmp_path / 'good', tmp_path / 'bad'
    good.write_text('feat: add plan_tour()\n\nLonger explanation.\n', encoding='utf-8')
    bad.write_text('Add plan_tour()\n', encoding='utf-8')

    assert check.main([str(good)]) == 0
    assert check.main([str(bad)]) == 1
    err = capsys.readouterr().err
    assert "commit message: 'Add plan_tour()'" in err
    assert 'CONTRIBUTING.md' in err


def test_single_message(check: ModuleType) -> None:
    assert check.main(['--message', 'fix: handle 429']) == 0
    assert check.main(['--message', 'Fix the thing']) == 1


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ['git', '-c', 'user.name=t', '-c', 'user.email=t@example.com', '-c', 'commit.gpgsign=false', *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def test_range_checks_every_non_merge_commit(
    check: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _git(tmp_path, 'init', '-q', '-b', 'main')
    _git(tmp_path, 'commit', '-q', '--allow-empty', '-m', 'initial commit, before the convention')
    base = _git(tmp_path, 'rev-parse', 'HEAD')
    _git(tmp_path, 'switch', '-q', '-c', 'topic')
    _git(tmp_path, 'commit', '-q', '--allow-empty', '-m', 'feat: one')
    _git(tmp_path, 'switch', '-q', 'main')
    _git(tmp_path, 'commit', '-q', '--allow-empty', '-m', 'fix: on main')
    _git(tmp_path, 'switch', '-q', 'topic')
    _git(tmp_path, 'merge', '-q', '--no-edit', 'main')  # a merge commit, skipped
    monkeypatch.chdir(tmp_path)

    assert check.main(['--range', f'{base}..HEAD']) == 0

    _git(tmp_path, 'commit', '-q', '--allow-empty', '-m', 'wip')
    assert check.main(['--range', f'{base}..HEAD']) == 1
    assert "'wip'" in capsys.readouterr().err
