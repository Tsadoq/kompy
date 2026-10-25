# Contributing to kompy

Thanks for your interest in kompy! Bug reports, fixes, new endpoints and documentation improvements are all welcome.

- **Questions and ideas:** open an [issue](https://github.com/Tsadoq/kompy/issues) (there are templates for bugs
  and feature requests).
- **Security problems:** do not open a public issue; follow [SECURITY.md](SECURITY.md).
- **Code:** fork the repository, create a branch, and open a pull request against `main`. For larger changes,
  open an issue first so we can agree on the approach.

kompy wraps Komoot's unofficial API. Never commit real credentials, tokens, or API responses that contain
personal data (see [Test fixtures](#test-fixtures)).

## Development setup

kompy uses [uv](https://docs.astral.sh/uv/) to manage the development environment. Install uv, then:

```bash
git clone https://github.com/<you>/kompy.git
cd kompy
uv sync                      # creates .venv with kompy (editable) and the dev tools
uv run pre-commit install    # linters before each commit, and the commit message check
```

`uv sync` installs the `dev` dependency group from `pyproject.toml`: pytest, responses, ruff, mypy and pre-commit.
The `docs` group adds pdoc (`uv sync --group docs`). `uv.lock` pins every version, so your environment matches CI.
If you change the dependencies in `pyproject.toml`, run `uv lock` and commit the updated `uv.lock`.

The supported Python versions are 3.11 to 3.14. To test with a specific one, run `uv run --python 3.13 pytest`.

## Running the tests

```bash
uv run pytest                        # the whole suite
uv run pytest tests/connector -k gpx # a subset
uv run pytest --cov                  # with coverage, as CI does (90% branch coverage required)
```

Unit tests never touch the network. HTTP calls are mocked with [responses](https://github.com/getsentry/responses),
and `tests/conftest.py` makes any real request fail. Useful fixtures and helpers in `tests/conftest.py` include
`connector` (a connector with a mocked login), `mocked_responses`, `load_api_fixture` and `make_tour`. pytest runs
with `filterwarnings = error`, so a test that triggers a warning fails. Check expected warnings with
`pytest.warns(...)` or `pytest.deprecated_call()`.

The scripts in `examples/` are exercised by `tests/test_examples.py` against the same mocks. If you change an
example, update its test.

### Live tests

Tests marked `live` (in `tests/live/`) talk to the real Komoot API. They are excluded from the default run by
`addopts = ["-m", "not live"]` in `pyproject.toml`, and they are skipped unless `KOMOOT_EMAIL` and
`KOMOOT_PASSWORD` are set. Use a dedicated test account.

```bash
export KOMOOT_EMAIL='you@example.com'
export KOMOOT_PASSWORD='...'
uv run pytest -m live                       # read-only: about 40 requests
KOMOOT_LIVE_WRITE=1 uv run pytest -m live   # also upload, change and delete a private test tour
```

The tests that create, change or delete tours run only with `KOMOOT_LIVE_WRITE=1`. They name their tour
`kompy-live-test-<random>`, delete it at the end, and `test_no_live_test_tours_left` removes any leftovers of an
earlier interrupted run. Set `KOMOOT_LIVE_REQUIRED=1` to make missing credentials fail the run instead of skipping
every test.

On GitHub, the [Live API contract tests](.github/workflows/live.yml) workflow runs them weekly and on demand, with
the credentials stored as secrets of the `komoot-live` environment. It sets `KOMOOT_LIVE_REQUIRED=1`, so a run
without credentials fails instead of passing with every test skipped. The weekly run is read-only; the write tests
run only when you start the workflow by hand and tick "write". Keep the request rate low in live tests.

Unit tests have a 60-second timeout (pytest-timeout), so a pagination bug that loops forever against `responses`
fails instead of hanging.

### Test fixtures

`tests/resources/api/` contains real API responses that have been anonymized: names, emails, usernames and ids are
replaced, and coordinates are moved. If you add a fixture, anonymize it the same way, and check that it contains no
email address other than `user@example.com` and no real token.

## Linting, formatting and type checking

```bash
uv run ruff check .          # lint (add --fix to apply the automatic fixes)
uv run ruff format .         # format (single quotes, 120 columns)
uv run mypy                  # strict type checking of kompy/
uv run pre-commit run --all-files
```

CI runs all of these and fails on any finding.

## Coding guidelines

- **Keep backward compatibility.** kompy is on PyPI, so public names, method names and keyword arguments stay. If
  you have to change behaviour, deprecate the old way first with a `DeprecationWarning`, and mark the commit as
  breaking (`feat!:`) with a `BREAKING CHANGE:` footer that says what users must do.
- **Type everything.** The package ships `py.typed`, and mypy runs in strict mode. Use modern syntax (`list[str]`,
  `X | None`).
- **Document everything public** with reStructuredText docstrings (`:param x:`, `:return:`, `:raises:`). The API
  reference is generated from them with pdoc.
- **Parse leniently.** The API is unofficial and changes. Models accept unknown enum values as plain strings, and
  missing optional fields are `None`. Only truly essential fields (such as `id`) may raise.
- **Raise kompy exceptions.** Use the classes in `kompy.exceptions` for errors from Komoot. Do all HTTP through
  `kompy._http.HttpClient`, which handles timeouts, retries and status codes.
- **Log, don't print.** Use `logging.getLogger(__name__)`, never add handlers in library code, and never log
  secrets. Only `kompy/cli.py` prints.
- **Import fit_tool lazily**, inside functions, because importing it configures the root logger.
- **Test every change.** Bug fixes come with a regression test.
- **Update the docs.** If you change behaviour, update `README.md`. Do not edit `CHANGELOG.md` by hand: release-please
  writes it from the commit messages.

## API documentation

The API reference at <https://tsadoq.github.io/kompy/> is built with pdoc from the docstrings. Its landing page is
the docstring of `kompy/__init__.py`. To preview it:

```bash
uv run --group docs pdoc -d restructuredtext kompy            # live preview in the browser
uv run --group docs pdoc -d restructuredtext kompy -o site/   # static HTML, as CI builds it
```

The `Docs` workflow builds the reference for every pull request and deploys it to GitHub Pages on every push to
`main`.

## Pull requests

Before you open a pull request:

1. Run `uv run pytest --cov`, `uv run ruff check .`, `uv run ruff format --check .` and `uv run mypy`.
2. Add tests, and update the README where relevant.
3. Check that every commit message, and the pull request title, follows [Conventional Commits](#commit-messages).
4. Fill in the pull request template.

The "All checks passed" and "Conventional commits" checks must be green before a pull request is merged.

## Commit messages

kompy uses [Conventional Commits](https://www.conventionalcommits.org): release-please reads the commit messages to
pick the next version and to write the changelog. The first line of every commit is
`<type>[(scope)][!]: <description>`, at most 100 characters:

| Type | Use it for | Release |
|---|---|---|
| `feat` | a new feature | minor (`0.2.0` -> `0.3.0`) |
| `fix` | a bug fix | patch (`0.2.0` -> `0.2.1`) |
| `perf` | a performance improvement | patch |
| `docs` | documentation only | none, but listed in the changelog |
| `refactor`, `test`, `build`, `ci`, `chore`, `style` | everything else | none |

Add `!` after the type (`feat!: ...`) or a `BREAKING CHANGE: ...` footer for a breaking change; while kompy is below
1.0 it bumps the minor version. The scope is optional and lowercase, for example `fix(cli): ...`. Write the
description for users, since it ends up in the changelog: `feat: add plan_tour() to create planned tours`.

`uv run pre-commit install` installs a commit-msg hook that rejects other messages before the commit is made. CI
checks every commit of a pull request and its title (which becomes the message of a squash merge) with the same
script, `scripts/check_commit_message.py`. To fix a message: `git commit --amend` for the last commit, or
`git rebase -i` for older ones.

## Releasing (maintainers)

Releases are automatic, driven by [release-please](https://github.com/googleapis/release-please) in the
[publish workflow](.github/workflows/publish.yml):

1. On every push to `main`, release-please opens or updates a pull request titled `chore(main): release X.Y.Z`. It
   bumps `__version__` in `kompy/__init__.py` and adds the changelog entry, both computed from the commit messages
   since the last release. Commits that do not trigger a release (`docs`, `ci`, `chore`, ...) do not open one.
2. When you want to release, merge that pull request (review the version and the changelog first; edit the pull
   request branch if you want to reword an entry).
3. release-please then creates the `vX.Y.Z` tag and the GitHub release, and the workflow tests and builds the
   package, uploads it to PyPI with [Trusted Publishing](https://docs.pypi.org/trusted-publishers/) (no API token
   is needed) and attaches the files to the release.
4. Check the new version on <https://pypi.org/project/kompy/>, and try `pip install kompy==X.Y.Z` in a clean
   environment.

To force a specific version, add a commit with a `Release-As: X.Y.Z` footer, for example
`git commit --allow-empty -m "chore: release 1.0.0" -m "Release-As: 1.0.0"`.

### One-time repository setup

These settings live on GitHub and PyPI, not in the repository. Check them before the first release:

- **PyPI trusted publisher**: on pypi.org, project `kompy` -> Publishing -> add a GitHub publisher for the
  repository `Tsadoq/kompy`, workflow `publish.yml`, environment `pypi`. Without it the upload step fails.
- **`pypi` environment**: in the repository settings -> Environments, create `pypi` and add protection rules
  (required reviewers, and/or deployment only from the `main` branch). GitHub creates a missing environment automatically
  but without any protection, so the environment is only "protected" once you configure this.
- **`komoot-live` environment**: create it with the secrets `KOMOOT_EMAIL` and `KOMOOT_PASSWORD` of a dedicated
  test account, for the live contract workflow (it fails, by design, while they are missing).
- **Release pull requests and CI**: pull requests opened with the default `GITHUB_TOKEN` do not trigger workflows,
  so the required checks never run on the release pull request and it has to be merged by an admin. To run CI on
  it, add a fine-grained personal access token (this repository only; contents and pull requests: read and write)
  as the repository secret `RELEASE_PLEASE_TOKEN`; the workflow uses it when it exists.

If a job fails after the release was created, fix the cause (for example the PyPI setup) and use "Re-run failed
jobs" on that workflow run: files already on PyPI are not uploaded twice. A version number that has been uploaded to
PyPI cannot be reused, so if a broken version was uploaded, merge a `fix:` and release a new patch version.

## License

By contributing, you agree that your contributions are released under the [MIT License](LICENSE).
