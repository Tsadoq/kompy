## What does this change?

<!-- A short description of the change and why it is needed. Link related issues, e.g. "Closes #123". -->

## Type of change

- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change (existing code using kompy may need to change)
- [ ] Documentation / tooling only

## Checklist

- [ ] `uv run ruff check .` and `uv run ruff format --check .` pass
- [ ] `uv run mypy` passes
- [ ] `uv run pytest --cov` passes, and new behaviour is covered by tests (mocked with `responses`, no real network)
- [ ] Public functions and classes have docstrings
- [ ] `CHANGELOG.md` has an entry under "Unreleased" for user-visible changes
- [ ] No credentials, tokens or personal tour data in code, fixtures or logs
