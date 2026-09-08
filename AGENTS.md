# Development guidelines

These instructions apply to the entire repository. Follow the user's current request when it changes these defaults.

## Working principles

- Build a small, understandable utility with minimal dependencies and a clear execution path.
- Start with the happy path. Add retries, persistence, locking, extensive validation, or abstractions only when required by the specification or observed failure modes.
- Preserve existing configuration, credentials, and generated or downloaded data during routine initialization and upgrades.
- Before changing code, inspect the current implementation, tests, specification, README, configuration example, and working-tree status relevant to the request.
- Do not overwrite, delete, stage, commit, or reformat unrelated user changes. Treat untracked files as user-owned unless their purpose is established.
- Complete a functional change as one coherent unit: implementation, focused tests, configuration/help text, specification, and user documentation when affected.
- Prefer stable machine-readable interfaces and keep presentation-only changes out of internal models and JSON unless the contract explicitly changes.

## Specification first

- For a new utility, write a short specification before implementation. Cover the goal, non-goals, configuration, execution modes, main algorithm, external APIs, output formats, error behavior, and a few acceptance checks.
- Keep the specification proportional to the utility. Avoid large requirement matrices and exhaustive edge-case catalogs.
- For changes, update the existing specification instead of creating a separate design document for every feature.
- Resolve ambiguous terms in the contract with concrete examples, especially glob matching, thresholds, aggregation, rounding, tie-breaking, and displayed identifiers.
- Record defaults in one authoritative place and keep code, example configuration, CLI help, README, and specification synchronized.

## Configuration and command-line interface

- Store every normal runtime option in the configuration file; CLI options override configuration values rather than defining a separate behavior set.
- Provide `-c, --config CONFIG`, `-l, --log-level LEVEL`, and `-h, --help`. Add distinct one-letter aliases for other frequently used long options when practical.
- In help output, display a shared metavar only once, for example `-c, --config CONFIG`, not `-c CONFIG, --config CONFIG`.
- Default to `config.yaml` beside the application entry point, regardless of the current working directory.
- Resolve relative paths in configuration against the configuration file's directory.
- Default logging to `INFO`. Accept the standard `ERROR`, `WARNING`, `INFO`, and `DEBUG` levels case-insensitively.
- If invoked without arguments and the default configuration file is absent, print the missing path and full help, then exit with a nonzero status.
- Comment non-obvious settings immediately above them in `config.yaml` and the example configuration. Explain units, matching rules, precedence, statistical meaning, and failure policies.
- Never overwrite an existing user configuration during initialization or upgrades.

## Execution modes and filtering

- Keep independently useful phases available as explicit modes when practical. A diagnostic mode must avoid unrelated API calls; for example, latency-only mode must not request pricing or placement data.
- Inclusion and exclusion rules use one simple mechanism: complete names or shell-style masks such as `eu-west-1` and `eu-west-*`.
- Do not introduce a separate prefix syntax. Inclusion defaults to `['*']`, meaning all regions available to the account. Explicit exclusions take precedence over inclusions.
- Discover available resources from the account or upstream API instead of maintaining a stale hard-coded list.
- Make thresholds, metrics, history windows, workload assumptions, and tie-breaking rules configurable and document their units.

## Logging and progress

- Use standard logging with timestamps and levels, written to stderr. Reserve stdout for the requested result format so JSON remains pipe-friendly.
- Log the effective startup parameters after configuration and CLI overrides are merged. Avoid secrets and redact sensitive values.
- Use `INFO` for major phases and bounded progress counters, such as discovery, RTT measurement, per-region pricing progress, aggregation, and completion.
- Use `DEBUG` for endpoint selection, detailed checks, metadata requests, and troubleshooting information; `WARNING` for recoverable degradation; `ERROR` for failures.
- Long-running operations must make progress visible without logging every request or downloaded chunk.
- When comparing API variants, log the effective variant and save each result and its logs separately so the experiment is reproducible.

## Output contracts

- Offer a concise human-readable table and a stable JSON representation when the utility is intended for both interactive and automated use.
- Apply cosmetic shortening and rounding only to table output. Preserve complete identifiers and full numeric precision in JSON and internal calculations.
- Keep column names compact but unambiguous, and update examples and tests whenever table headers or formatting change.
- Show the latest value, historical aggregate, trend direction, and decision-relevant measurements when they are part of selection logic.
- Explain exclusions when enabled. If a threshold excludes an item, include its measured value, configured limit, unit, and selected metric.
- Define deterministic ordering and tie-breaking in the specification and tests.

## Tests and verification

- Add focused pytest coverage alongside functional changes.
- Cover the main workflow, configuration/CLI precedence, explicit execution modes, filtering precedence, output contracts, repeat runs without changes, preservation of existing data, and failures explicitly included in the specification.
- Mock network and AWS responses and use temporary directories for automated tests. Tests must not depend on live credentials, current AWS prices, current regions, or upstream availability.
- Use live AWS calls only when the user explicitly requests an integration check. Keep generated JSON and logs out of version control unless they are intentional fixtures with sanitized content.
- Do not add tests that merely duplicate trivial implementation details or exhaustive cases outside the agreed scope.
- Before reporting a code change complete, run the relevant tests, Ruff linting, Ruff formatting checks, and `git diff --check`. Distinguish new failures from pre-existing issues in unrelated user files.
- Documentation-only edits need link, command, and consistency checks rather than a full test run.

## Quality and public-repository hygiene

- Configure pre-commit to run the formatter, linter, focused test suite, and Gitleaks. Keep local commands equivalent to CI checks.
- Keep `.gitignore` current for virtual environments, caches, local configuration, credentials, logs, and experimental API output.
- Never commit AWS credentials, account identifiers, tokens, private endpoints, or sensitive logs. Use placeholders in examples and sanitized fixtures.
- Before public release, provide a license, security-reporting guidance, contribution guidance when useful, supported Python version, dependency metadata, and a minimal CI workflow.
- Prefer least-privilege IAM permissions. Document the exact read-only actions required, why each is needed, and which feature can be disabled to avoid an optional permission.
- Pin or constrain development tooling enough to make checks reproducible, and review dependency updates deliberately.

## Makefile, installation, and scheduled execution

- For utilities that need repeatable local setup, provide `init`, `test`, and `run` targets. Add `install`, `uninstall`, `help`, `status`, and `logs` only when installation or service operation applies.
- `init` creates `.venv`, installs runtime and test dependencies, and prepares configuration from an example without overwriting an existing file.
- `test` runs pytest; `run` invokes the application using the virtual environment.
- Keep the user installation path short and separate it from the developer setup. A cloned repository should have an obvious quickest path to the first successful run.
- For scheduled utilities, prefer a systemd oneshot service and timer. `install` may install and enable the timer; `uninstall` must stop and remove units while preserving configuration, data, and `.venv`.
- Preparing installation commands does not authorize running them on the host. Test generation and installation behavior in isolation when possible.

## Documentation and language

- Use English for primary documentation, specifications, code comments, CLI help, logs, tests, and configuration comments.
- When preserving Russian documentation, use `_RU` before the extension, for example `README_RU.md` and `SPECIFICATION_RU.md`. Keep links and examples synchronized between languages.
- Make README user-oriented: prerequisites, least-privilege IAM permissions, quick start after cloning, configuration, execution modes, example table and JSON output, troubleshooting, and a separate development section.
- Explain environment activation and PATH changes explicitly; do not rely on an editor- or session-specific `.venv/bin` PATH modification.
- Keep README and specification synchronized with CLI options, defaults, configuration comments, logging behavior, output columns, tests, and installation targets.

## Git handoff and completion reports

- Do not create a commit unless the user explicitly requests it.
- When asked for a commit message, inspect only the staged diff and propose a message that describes exactly those changes. Use a concise Conventional Commit subject and an optional bullet body.
- Report completion briefly: what changed, which checks passed, any pre-existing unrelated failures, and any material behavior not verified against live services.
- Distinguish files prepared from commands, services, releases, or external changes actually executed.

## Repository-specific behavior

- In this repository, the default configuration is `./config.yaml` in the current working directory. This intentionally overrides the general beside-entry-point default above.
- In this repository, invocation without arguments and without `./config.yaml` prints help and exits successfully. An explicitly requested missing configuration remains an error.
- RTT probing performs three warm-up requests followed by five measured requests by default. Warm-ups are excluded from statistics.
- Support an RTT-only mode that performs no Spot pricing or Spot Placement Score calls.
- AWS region rules accept full region names or masks. `included_regions: ['*']` includes all regions visible to the account; exclusions win.
- In table output, show only the Availability Zone suffix (`a` for `eu-west-1a`), while JSON retains the full Availability Zone.
- Format all table monetary values with exactly four digits after the decimal point. Do not reduce calculation or JSON precision.
- Use `AVG_HIST` and `AVG_EST` as the regional-summary table headings.
- For `above_limit` exclusions, show the measured RTT, configured RTT limit, and whether `median` or `p95` was used.
- Keep regional averages across Availability Zones separate from per-AZ rows. Do not replace the per-AZ data with aggregates.
- If prices tie according to the configured tolerance, prefer the candidate with lower RTT.
- Keep product-description comparisons reproducible; do not assume similarly named AWS product descriptions return identical history without evidence.
