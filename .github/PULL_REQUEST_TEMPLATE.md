## What does this change?

<!-- A short description of the change and why it is needed. Link related issues, e.g. "Closes #123". -->

## Type of change

<!-- The pull request title and every commit message follow Conventional Commits, which decides the release:
     "fix: ..." (patch), "feat: ..." (minor), "feat!: ..." (breaking), "docs:/ci:/chore:/test: ..." (no release). -->

- [ ] Bug fix (`fix:`)
- [ ] New feature (`feat:`)
- [ ] Breaking change (`!`, with a `BREAKING CHANGE:` footer)
- [ ] Documentation / tooling only (`docs:`, `ci:`, `chore:`, ...)

## Checklist

- [ ] `uv run ruff check .` and `uv run ruff format --check .` pass
- [ ] `uv run mypy` passes
- [ ] `uv run pytest --cov` passes, and new behaviour is covered by tests (mocked with `responses`, no real network)
- [ ] Public functions and classes have docstrings
- [ ] Commit messages and the title follow Conventional Commits (`CHANGELOG.md` is generated from them)
- [ ] No credentials, tokens or personal tour data in code, fixtures or logs
