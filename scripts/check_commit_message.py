"""
Check that commit messages follow Conventional Commits (https://www.conventionalcommits.org).

release-please reads the commit history to pick the next version and write the changelog, so every commit that
reaches ``main`` must say what kind of change it is::

    feat: add plan_tour()              -> minor release (0.x: also minor)
    fix(cli): handle empty tour list   -> patch release
    feat!: drop Python 3.11            -> breaking (minor while kompy is below 1.0)
    docs: / ci: / chore: / test: ...   -> no release

Usage::

    python scripts/check_commit_message.py .git/COMMIT_EDITMSG   # commit-msg hook (pre-commit)
    python scripts/check_commit_message.py --range BASE..HEAD    # every non-merge commit of a pull request
    python scripts/check_commit_message.py --message "feat: ..."  # a single message, e.g. a pull request title
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

TYPES = ('build', 'chore', 'ci', 'docs', 'feat', 'fix', 'perf', 'refactor', 'revert', 'style', 'test')
MAX_HEADER_LENGTH = 100
HEADER = re.compile(
    rf'^(?P<type>{"|".join(TYPES)})(?:\((?P<scope>[a-z0-9][a-z0-9._/-]*)\))?(?P<breaking>!)?: (?P<subject>\S.*)$'
)
# Lines git adds itself: merge commits, `git revert`, and `git commit --fixup/--squash` (squashed before merging).
GIT_GENERATED = re.compile(r'^(Merge (branch|pull request|remote-tracking branch) |Revert ")')
AUTOSQUASH = re.compile(r'^(fixup|squash|amend)! ')

HELP = f"""\
Commit messages must follow Conventional Commits: <type>[(scope)][!]: <description>
  types: {', '.join(TYPES)}
  examples: "feat: add plan_tour()", "fix(cli): handle an empty tour list", "feat!: drop Python 3.11"
  feat = new feature (minor release), fix = bug fix (patch release), "!" = breaking change.
See CONTRIBUTING.md, "Commit messages"."""


def header_of(message: str) -> str:
    """Return the first line of a commit message that is not empty and not a git comment."""
    for line in message.splitlines():
        if line.strip() and not line.startswith('#'):
            return line.rstrip()
    return ''


def problem_with(header: str, *, allow_autosquash: bool = False) -> str | None:
    """Return why a commit header is not acceptable, or ``None`` if it is."""
    if not header:
        return 'the message is empty'
    if GIT_GENERATED.match(header) or (allow_autosquash and AUTOSQUASH.match(header)):
        return None
    if AUTOSQUASH.match(header):
        return 'fixup!/squash! commits must be squashed (git rebase --autosquash) before merging'
    if len(header) > MAX_HEADER_LENGTH:
        return f'the first line is {len(header)} characters long (at most {MAX_HEADER_LENGTH})'
    if not HEADER.match(header):
        return 'it does not start with "<type>[(scope)][!]: "'
    return None


def commits_in(revision_range: str) -> list[tuple[str, str]]:
    """Return ``(short sha, header)`` of every non-merge commit in a git revision range."""
    output = subprocess.run(  # noqa: S603 - fixed git command, the range is passed as a single argument
        ['git', 'log', '--no-merges', '--format=%h%x00%s', revision_range],  # noqa: S607 - git from PATH
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return [tuple(line.split('\0', 1)) for line in output.splitlines()]  # type: ignore[misc]


def main(argv: list[str] | None = None) -> int:
    """Check the given commit messages; return 1 (and explain) if any is not acceptable."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('file', nargs='?', type=Path, help='file holding a commit message (commit-msg hook)')
    group.add_argument('--range', dest='revision_range', help='git revision range, e.g. origin/main..HEAD')
    group.add_argument('--message', help='a single message, e.g. a pull request title')
    args = parser.parse_args(argv)

    if args.file is not None:
        checked = [('commit message', header_of(args.file.read_text(encoding='utf-8')), True)]
    elif args.message is not None:
        checked = [('message', header_of(args.message), False)]
    else:
        checked = [(sha, header, False) for sha, header in commits_in(args.revision_range)]

    failures = [
        f'  {name}: {header!r}: {problem}'
        for name, header, autosquash in checked
        if (problem := problem_with(header, allow_autosquash=autosquash)) is not None
    ]
    if failures:
        print('\n'.join(['Not a Conventional Commit:', *failures, '', HELP]), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
