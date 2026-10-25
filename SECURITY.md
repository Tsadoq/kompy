# Security policy

## Supported versions

Only the latest release of kompy gets security fixes. Please upgrade before reporting a problem.

| Version | Supported |
| --- | --- |
| 0.1.x | Yes |
| 0.0.x and earlier | No |

## Reporting a vulnerability

**Do not open a public issue for a security problem.** Report it privately through GitHub instead: on the
[Security tab](https://github.com/Tsadoq/kompy/security), choose
[Report a vulnerability](https://github.com/Tsadoq/kompy/security/advisories/new).

Please include:

- a description of the problem and its impact;
- the kompy version, the Python version and the operating system;
- steps or a minimal script to reproduce it, **without real credentials or tokens**.

You should get a first answer within a week. Once the problem is confirmed, we prepare a fix and a release, and
then publish an advisory. Tell us if you would like to be credited.

Problems in Komoot's own service or API are out of scope: report those to Komoot. kompy is an unofficial client
and is not affiliated with Komoot.

## Handling your Komoot credentials safely

kompy needs your Komoot credentials, so treat them with care:

- **The API token is equivalent to your password.** `connector.token`, `KOMOOT_TOKEN` and the output of
  `kompy token` give full access to your account: anyone who has them can read, change and delete your tours. In
  our tests the token did not expire and stayed valid after new logins. Store it in a password manager or a
  secret store, never in source code, notebooks, logs or version control.
- Prefer environment variables (`KomootConnector.from_env()`) or your platform's secret store to hard-coded
  credentials. In CI, use encrypted secrets.
- kompy sends the password only once, to log in over HTTPS, and uses the token for every later request. It never
  logs the password or the token, and `str()`/`repr()` of `Authentication` and `KomootConnector` do not reveal
  them. Share tokens and the login email address are redacted (`***`) from log and exception messages.
- If you think a token or password has leaked, change your Komoot password right away. This probably revokes the
  token too, but that has not been verified.
