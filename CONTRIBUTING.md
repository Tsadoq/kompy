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
uv run pre-commit install    # optional: run the linters on every commit
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
  you have to change behaviour, deprecate the old way first with a `DeprecationWarning`, and list the change in
  `CHANGELOG.md`.
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
- **Update the docs.** If you change behaviour, update `README.md` and add an entry to the `Unreleased` section of
  `CHANGELOG.md`.

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
2. Add tests, and update the README and CHANGELOG where relevant.
3. Fill in the pull request template.

The "All checks passed" CI job must be green before a pull request is merged.

## Releasing (maintainers)

Releases are automatic. The [publish workflow](.github/workflows/publish.yml) runs on every push to `main` that
changes `kompy/__init__.py`; when `__version__` names a version that has no `vX.Y.Z` tag yet, it runs the tests,
builds the sdist and the wheel, uploads them to PyPI with
[Trusted Publishing](https://docs.pypi.org/trusted-publishers/) (no API token is needed), then creates the tag and a
GitHub release whose notes are the version's section of `CHANGELOG.md`. Merges that do not bump the version publish
nothing.

To release:

1. Pick the version, following [Semantic Versioning](https://semver.org/) (while kompy is below 1.0, a breaking
   change bumps the minor version).
2. In a pull request (on its own or as part of a feature):
   - set `__version__` in `kompy/__init__.py` (the single source of the version; `uv.lock` does not record it, so
     run `uv lock` only if dependencies changed);
   - in `CHANGELOG.md`, rename `Unreleased` to the version and date (`## [0.2.0] - 2026-11-30`), start a new empty
     `## [Unreleased]` section above it, and update the links at the bottom. The workflow refuses to release a
     version without its own changelog section.
3. Merge it once CI is green. The release appears on PyPI and on the GitHub releases page a few minutes later.
4. Check the new version on <https://pypi.org/project/kompy/>, and try `pip install kompy==X.Y.Z` in a clean
   environment.

### One-time repository setup

These settings live on GitHub and PyPI, not in the repository. Check them before the first release:

- **PyPI trusted publisher**: on pypi.org, project `kompy` -> Publishing -> add a GitHub publisher for the
  repository `Tsadoq/kompy`, workflow `publish.yml`, environment `pypi`. Without it the upload step fails.
- **`pypi` environment**: in the repository settings -> Environments, create `pypi` and add protection rules
  (required reviewers, and/or deployment only from the `main` branch). GitHub creates a missing environment automatically
  but without any protection, so the environment is only "protected" once you configure this.
- **`komoot-live` environment**: create it with the secrets `KOMOOT_EMAIL` and `KOMOOT_PASSWORD` of a dedicated
  test account, for the live contract workflow (it fails, by design, while they are missing).
- **Old secret**: delete the repository secret `PYPI_API_TOKEN`, which the previous publish workflow used.

If the workflow fails, fix the problem on `main` and run it again from the Actions tab ("Run workflow"): a version
that is already tagged is skipped, and files already on PyPI are not uploaded twice. A version number that has been uploaded to PyPI cannot be reused, so if a broken version was uploaded, release a
new patch version.

## License

By contributing, you agree that your contributions are released under the [MIT License](LICENSE).
