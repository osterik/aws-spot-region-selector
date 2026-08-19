# AWS Spot Region Selector — Product and Development Specification

Status: Draft 1.0
Date: 2026-08-18
Russian version: [SPECIFICATION_RU.md](SPECIFICATION_RU.md)

## 1. Purpose

`aws-spot-price-selector` is a command-line tool that selects a preferred AWS Region for a short-lived EC2 Spot Instance workload. The selection balances network latency from the machine running the tool, Spot cost, price stability, and the likelihood of obtaining the requested capacity.

The tool only analyzes options and returns a recommendation. It does not create EC2 instances, Spot Fleets, Auto Scaling Groups, or any other AWS resources.

## 2. Terminology

- **Region** — an AWS Region ID, such as `eu-west-1`.
- **Availability Zone (AZ)** — an availability zone within a Region, such as `eu-west-1a`.
- **RTT** — total round-trip time for a network request.
- **SPS** — EC2 Spot Placement Score, from 1 to 10.
- **Candidate** — a Region/AZ/instance-type combination that passed all mandatory filters.

## 3. Version 1 goals

Version 1 must:

1. Retrieve the current list of available AWS Regions.
2. Include and exclude Regions by exact Region ID or glob pattern.
3. Measure network latency to the remaining Regions.
4. Reject Regions whose latency exceeds a configured limit.
5. Retrieve Spot Price History for configured instance types.
6. Calculate price statistics for a configured period while accounting for how long each price was active.
7. Use Spot Placement Score when available.
8. Rank eligible candidates and return one primary recommendation plus alternatives.
9. Explain inclusion, exclusion, and final-selection decisions.
10. Support human-readable table output and machine-readable JSON.

## 4. Out of scope for version 1

- Automatically provisioning or terminating resources.
- ML-based price forecasting.
- Actively measuring interruption frequency by launching instances.
- Automatically copying AMIs, data, or secrets between Regions.
- Comparing AWS with other cloud providers.
- Measuring latency from multiple geographic origins in a single run.
- Guaranteeing Spot capacity; SPS is an AWS recommendation, not a guarantee.

## 5. User scenarios

### 5.1 Primary scenario

The user specifies instance types, maximum RTT, analysis period, and expected workload duration. The tool returns the best Region/AZ/type and a ranked list of alternatives.

### 5.2 Restricting geographic groups and individual Regions

The user can restrict the search with patterns, for example by including all `us-*` Regions and `ca-central-1`, while excluding `us-east-1`. By default, every Region available to the account is included with `*`.

### 5.3 Automation

A CI/CD system or scheduler runs the command with `--output json`, checks the exit code, and consumes the structured recommendation in a subsequent step.

## 6. Command-line interface

Primary command:

```shell
spot-region-selector evaluate
```

Additional commands:

```shell
spot-region-selector validate-config --config config.yml
spot-region-selector list-regions --config config.yml
spot-region-selector latency --config config.yml
```

If `--config` is omitted, the command reads `config.yml` from the current working directory. When the application is run without arguments and the default configuration file does not exist, it displays help and exits successfully. An explicitly specified missing configuration file is an error.

The `latency` command performs only Region discovery, filtering, and RTT measurement. It does not call Spot Price History or Spot Placement Score, does not require workload/pricing/placement settings, and does not produce a price recommendation. Results are sorted by median RTT.

CLI flags override configuration values. Precedence is:

1. CLI flag;
2. configuration file;
3. default value.

Minimum required flags for `evaluate`:

```text
--config PATH
--profile NAME
--instance-types TYPE[,TYPE...]
--max-rtt-ms NUMBER
--history-days NUMBER
--duration-hours NUMBER
--output table|json
```

Every runtime option except the path to the configuration file and the service flags `--help` and `--version` must have an equivalent YAML field. The command can also be selected with `run.mode`; an explicit CLI subcommand takes precedence. A normal invocation can therefore consist only of `spot-region-selector`, with all behavior defined in `config.yml`.

## 7. Configuration file

Version 1 uses YAML. Unknown fields are errors so that typographical mistakes cannot silently change behavior.

Complete example:

```yaml
version: 1

run:
  mode: evaluate

aws:
  profile: default
  discovery_region: us-east-1
  include_opt_in_regions: false

workload:
  instance_types:
    - c7a.large
    - c7i.large
    - c7g.large
  product_descriptions:
    - Linux/UNIX
  target_capacity: 10
  duration_hours: 3

regions:
  included_regions:
    - "*"
  excluded_regions:
    - eu-west-1
    - eu-central-*

latency:
  max_rtt_ms: 100
  warmup_attempts: 3
  attempts: 5
  timeout_ms: 1500
  concurrency: 8
  metric: median
  probe: https

pricing:
  history_days: 7
  statistic: time_weighted_average
  currency: USD

placement:
  enabled: true
  min_score: 6
  failure_policy: warn

ranking:
  price_tie_relative_percent: 1.0
  alternatives: 5

output:
  format: table
  explain_exclusions: true
  verbose: false
  log_level: info
```

### 7.1 Configuration reference

| Field | Purpose and non-obvious semantics |
|---|---|
| `version` | Configuration schema version, not application version. Version 1 only accepts `1`. |
| `run.mode` | `evaluate`, `latency`, `list-regions`, or `validate-config`. A CLI subcommand overrides it. |
| `aws.profile` | Profile from the standard AWS credential/config chain. `null` uses normal AWS SDK resolution. |
| `aws.discovery_region` | Region endpoint used for the logically global `DescribeRegions` call. It receives no ranking preference. |
| `aws.include_opt_in_regions` | Allows `not-opted-in` Regions to be considered; it does not opt the account into them. |
| `workload.instance_types` | Interchangeable eligible types. The recommendation selects a concrete type. |
| `workload.product_descriptions` | OS/license variant used by Spot Price History. Values must exactly match the EC2 API values. |
| `workload.target_capacity` | Capacity units requested for SPS. In version 1, one unit corresponds to one instance. |
| `workload.duration_hours` | Expected workload duration used to estimate compute cost. |
| `regions.included_regions` | Allowlist of exact Region IDs or glob patterns. Defaults to `["*"]`. |
| `regions.excluded_regions` | Exact Region IDs or patterns containing `*`, such as `eu-west-*`. |
| `latency.warmup_attempts` | Warm-up requests excluded from statistics. Defaults to `3`. |
| `latency.attempts` | Measured requests after warm-up. Defaults to `5`. |
| `latency.timeout_ms` | Timeout for one attempt, not the entire run. |
| `latency.concurrency` | Maximum number of Regions measured concurrently. |
| `latency.metric` | Threshold metric. `median` is less sensitive to isolated outliers. |
| `latency.probe` | Probe protocol. Version 1 requires `https`; this is not ICMP ping. |
| `pricing.history_days` | Historical window ending at invocation time, including the latest known price. |
| `pricing.statistic` | Version 1 requires `time_weighted_average`. Prices are weighted by active duration. |
| `pricing.currency` | Version 1 requires `USD`; no automatic currency conversion is performed. |
| `placement.min_score` | Minimum SPS. A score of 10 indicates the highest likelihood, not a guarantee. |
| `placement.failure_policy` | Behavior when SPS is unavailable: exclude, warn, or ignore. A successfully retrieved score below the minimum always excludes the Region. |
| `ranking.price_tie_relative_percent` | Relative tolerance within which prices are tied; lower RTT wins a price tie. |
| `ranking.alternatives` | Maximum alternatives after the primary recommendation. |
| `output.explain_exclusions` | Adds exclusion reasons to table output; JSON always retains them. |
| `output.verbose` | Compatibility switch for debug diagnostics; equivalent to `--verbose`. |
| `output.log_level` | Minimum stderr level: `error`, `warning`, `info`, or `debug`. Defaults to `info`; `--verbose` maps to `debug`. |

Fields irrelevant to the selected `run.mode` may be present and are ignored. In `latency` mode, the `workload`, `pricing`, `placement`, and `ranking` sections may be omitted.

### 7.2 Region inclusion and exclusion rules

Filtering occurs before latency and pricing requests. The allowlist is evaluated first, then exclusions.

- `included_regions` contains full Region IDs or glob patterns. `*` matches every discovered Region.
- A Region is considered only if it matches at least one `included_regions` rule.
- The default `["*"]` includes all Regions available to the current credentials, including newly discovered AWS Regions.
- `included_regions` cannot be empty. Use a pattern such as `eu-*` for a geographic group.
- `excluded_regions` contains full Region IDs or glob patterns normalized to lowercase.
- Only the `*` metacharacter is supported. Matching covers the entire Region ID: `eu-west-*` matches `eu-west-1` but not `x-eu-west-1`.
- Other glob metacharacters (`?`, `[]`, `{}`) are forbidden in version 1.
- Matching is case-insensitive after normalization to lowercase.
- Duplicate rules are allowed and removed during normalization.
- If multiple rules match, all matching reasons and patterns are reported.
- Exclusions unconditionally take precedence over inclusions and other settings.
- GovCloud and China partitions are not queried by default unless the active credentials/partition and implementation explicitly support them.

Example:

```yaml
regions:
  included_regions: [us-*, eu-central-*, ca-central-1]
  excluded_regions: [us-east-1]
```

The allowlist admits all `us-*` Regions, discovered `eu-central-*` Regions, and `ca-central-1`; the exclusion then removes `us-east-1`.

Empty lists are allowed:

```yaml
regions:
  included_regions: ["*"]
  excluded_regions: []
```

## 8. Data sources and AWS APIs

### 8.1 Region list

Use EC2 `DescribeRegions(AllRegions=true)`. By default, only Regions with `opt-in-not-required` or `opted-in` status participate. `not-opted-in` Regions are included only when `include_opt_in_regions: true` and must be marked as potentially unavailable.

### 8.2 Spot price history

For each Region that passes the latency filter, call `DescribeSpotPriceHistory` with:

- `StartTime = now - history_days`;
- `EndTime = now`;
- `InstanceTypes` from configuration;
- `ProductDescriptions` from configuration;
- complete pagination handling.

Analyze prices independently for each Region/AZ/instance-type/product-description combination. Represent monetary values with a decimal type, not binary floating point.

### 8.3 Spot Placement Score

When `placement.enabled: true`, use `GetSpotPlacementScores` for the configured instance types and `target_capacity`. The score applies to a Region and does not replace statistics for a specific AZ.

Handle AWS API limits and throttling with bounded concurrency, exponential backoff with jitter, and SDK retries.

### 8.4 IAM permissions

Minimum read-only actions:

```text
ec2:DescribeRegions
ec2:DescribeSpotPriceHistory
ec2:GetSpotPlacementScores
```

If instance-type availability is later checked through another API, document the additional read-only permission and include it in diagnostics.

## 9. Latency measurement

### 9.1 Version 1 method

The default method is an HTTPS request to a stable regional AWS endpoint. ICMP is not the default because it can be blocked and may not represent the application route.

For every Region:

1. Resolve DNS outside the measured interval when the implementation permits.
2. Perform `warmup_attempts` warm-up requests and exclude them from statistics.
3. Perform `attempts` measurements with an individual `timeout_ms`.
4. Record TCP/TLS/HTTP round-trip duration or total request duration, according to the implementation.
5. Calculate median and p95 from successful measured attempts.

The threshold uses `latency.metric`, which defaults to median. A Region passes when the selected metric is `<= max_rtt_ms`.

The endpoint must permit a safe, non-mutating request. Endpoint construction must be centralized and testable. Failure to construct or call an endpoint is a measurement error, not infinite latency.

### 9.2 Measurement errors

- If fewer than half of the measured `attempts` succeed, exclude the Region with `latency_unavailable`.
- One timeout does not terminate the entire run.
- Every result contains successful and unsuccessful attempt counts.
- The report must state that measurements represent the route from the machine running the tool.

## 10. Price metrics

Spot Price History contains price-change events. Averaging records by count is forbidden. The primary statistic is a time-weighted average:

```text
TWA = sum(price_i * active_duration_i) / total_observed_duration
```

For every Candidate, calculate:

- `latest_price` and the time it became active;
- `previous_price` immediately preceding the latest price;
- `price_trend`, including direction and magnitude;
- `time_weighted_average_price`;
- `time_weighted_p50_price`;
- `time_weighted_p95_price`;
- `max_price`;
- `price_change_count`;
- `observed_duration`;
- `estimated_compute_cost = duration_hours * ranking_price`.

Version 1 uses:

```text
ranking_price = 0.5 * latest_price
              + 0.3 * time_weighted_average_price
              + 0.2 * time_weighted_p95_price
```

These coefficients are fixed in version 1 and recorded in JSON. A future version may make them configurable.

If history covers less than 90% of the requested period, retain the Candidate with an `incomplete_price_history` warning. Exclude a Candidate when the latest price cannot be determined.

### 10.1 Latest price and trend

The trend represents the most recently observed Spot price change, like a market ticker. Sort records chronologically and calculate:

```text
delta = latest_price - previous_price
delta_percent = delta / previous_price * 100
```

Display rules:

| Condition | JSON value | Symbol |
|---|---|---|
| `delta > 0` | `up` | `↑` |
| `delta < 0` | `down` | `↓` |
| `delta = 0` | `flat` | `→` |
| no previous price | `unknown` | `?` |

The table shows absolute and percentage change after the arrow, for example `↑ +$0.003 (+7.7%)`. Color may be supplementary, but meaning must not depend on ANSI support. JSON stores `direction`, `symbol`, `absolute_change`, `percent_change`, `latest_price_at`, and `previous_price_at`.

This trend describes only the latest observed change. It is neither a forecast nor a trend over the entire historical window. Time-weighted average and p95 remain separate stability indicators.

## 11. Filtering and ranking

Required processing order:

```text
discover regions
-> normalize and apply inclusion/exclusion rules
-> measure latency
-> apply max RTT
-> retrieve and validate prices
-> retrieve/apply placement score
-> rank candidates
-> render result
```

Exclude a Candidate when:

- its Region matches no inclusion rule;
- its Region matches an exact exclusion or glob pattern;
- RTT measurement is unavailable;
- RTT exceeds the limit;
- the instance type or product description has no Spot price;
- SPS is below `min_score`;
- a mandatory AWS API returns an unrecoverable error for the Candidate.

### 11.1 Placement Score semantics

- `failure_policy: exclude` — missing SPS excludes the Region.
- `failure_policy: warn` — missing SPS retains the Region and adds a warning.
- `failure_policy: ignore` — SPS errors do not affect selection but remain in verbose/JSON diagnostics.
- A successfully retrieved SPS below `min_score` always excludes the Region.

### 11.2 Final ordering

The primary objective is the lowest expected compute cost among candidates that satisfy mandatory constraints.

Two prices are tied when their relative difference does not exceed `ranking.price_tie_relative_percent` of the lower price. Within a tied group, order by:

1. lower median RTT;
2. higher SPS, when known;
3. lower time-weighted p95;
4. lexicographically lower Region, AZ, and instance type for deterministic output.

Outside the tie tolerance, sort by ascending `estimated_compute_cost`.

Version 1 does not numerically model data transfer, EBS, or losses caused by interruption. The report must disclose this limitation.

## 12. Output

### 12.1 Table output

```text
REGION        AZ          TYPE        RTT_MED  LATEST   TREND              AVG_7D  P95_7D  EST_COST  SPS
eu-north-1    eun1-az2    c7g.large    62 ms    $0.029   ↓ -$0.002 (-6.5%)  $0.029  $0.031  $0.089    9
eu-central-1  euc1-az2    c7a.large    31 ms    $0.042   ↑ +$0.003 (+7.7%)  $0.041  $0.044  $0.126    8

Recommended: eu-north-1 / eun1-az2 / c7g.large
Reason: lowest estimated cost among candidates with RTT <= 100 ms and SPS >= 6.
```

Display the AZ name and, when the API provides a stable AZ ID, retain that ID in JSON. AZ names can map to different physical zones in different AWS accounts.

The `latency` command uses abbreviated output without pricing columns:

```text
REGION         RTT_MED  RTT_P95  SUCCESS  STATUS
eu-central-1    31 ms    39 ms    7/7      eligible
eu-west-1       48 ms    61 ms    6/7      eligible
eu-north-1     112 ms   130 ms    7/7      above_limit
```

Latency mode returns every measured Region, including those above the threshold. Configuration-excluded Regions appear only when `output.explain_exclusions: true`.

### 12.2 JSON

JSON is versioned and contains at least:

```json
{
  "schema_version": 1,
  "generated_at": "2026-08-18T12:00:00Z",
  "measurement_origin": "local",
  "criteria": {},
  "mode": "evaluate",
  "recommendation": {},
  "alternatives": [],
  "regional_summaries": [],
  "excluded_regions": [],
  "warnings": [],
  "diagnostics": {}
}
```

Every excluded Region includes a machine-readable reason code and human-readable explanation. Never output secrets, access keys, or session tokens.

### 12.3 Region-level averages

After the detailed Region/AZ/type table, output a separate summary without AZ detail. Group Candidates by `Region + instance type + product description` so different instance types and license variants are never mixed.

For each group, calculate the arithmetic mean across Availability Zones for:

- latest price;
- time-weighted historical average;
- p95;
- estimated compute cost;
- latest and previous prices used to determine aggregate trend direction.

The summary also contains the number of included AZs, Region RTT, and SPS. JSON stores it in `regional_summaries`. `average_p95_price` is the mean of AZ-level p95 values, not the p95 of a combined Region-wide time series.

## 13. Errors and exit codes

### 13.1 Progress messages

Write progress and diagnostics to stderr and the final table or JSON to stdout. This allows JSON to be redirected or piped safely.

- `error` — errors that make an operation wholly or partially impossible;
- `warning` — recoverable per-Region/API errors and incomplete data;
- `info` — current stage, discovered/filtered counts, RTT progress `N/M`, per-Region history requests, and completion;
- `debug` — endpoints, individual RTT results, time intervals, and read-only AWS request details without secrets.

Every message contains a UTC timestamp and level. Credentials, tokens, and authorization headers are forbidden at every level.

### 13.2 Exit codes

```text
0  recommendation built successfully, or help/validation completed successfully
2  configuration or CLI argument error
3  AWS authentication/authorization error
4  no Region passed mandatory filters
5  insufficient data for a recommendation
10 internal application error
```

A partial failure in one Region must not terminate analysis while valid Candidates remain. `--verbose` diagnostics must not expose sensitive data.

## 14. Non-functional requirements

- Support Linux and macOS; Windows support is desirable but not mandatory for version 1.
- Support Python 3.10+ and use the official AWS SDK for Python (`boto3`).
- Produce repeatable JSON for identical inputs and frozen time.
- Run network operations concurrently with a configurable safe limit.
- One stalled endpoint must not delay the entire run beyond its timeout/retry budget.
- Logs must not contain AWS credentials, authorization headers, or credential-file contents.
- Store and output timestamps as UTC ISO 8601.
- Use `Decimal` for monetary calculations.

## 15. Proposed architecture

```text
CLI
├── Config loader + validator
├── Region discovery/filter
├── Latency probe
├── AWS pricing client
├── AWS placement client
├── Price time-series calculator
├── Candidate ranker
└── Table/JSON renderer
```

External dependencies must be isolated behind interfaces so unit tests never call AWS or the public network.

## 16. Testing

### 16.1 Unit tests

Required cases:

- `eu-*` excludes `eu-west-1` and `eu-central-1`, but not `us-east-1`.
- Default inclusion `*` admits any discovered Region.
- Include patterns combine correctly.
- A Region outside the allowlist receives `not_included` and never reaches latency/pricing clients.
- Exclusion takes precedence over inclusion.
- Exact exclusion `eu-west-1` does not exclude `eu-west-2`.
- `eu-west-*` excludes every discovered `eu-west-N` but not `eu-central-1`.
- Patterns match the entire Region ID; unsupported metacharacters are rejected.
- Region IDs and patterns are normalized by case.
- Empty patterns are rejected.
- Exclusions are applied before latency/pricing calls.
- Three warm-up requests are excluded from five measured RTT requests.
- Time-weighted average is correct for unequal intervals.
- A price effective at the history-window boundary is handled correctly.
- Spot Price History pagination is complete.
- RTT exactly equal to `max_rtt_ms` is eligible.
- Lower RTT resolves a price tie.
- Latest price and trend arrows correctly represent up, down, flat, and unknown states.
- Complete ties are deterministic.
- A failure in one Region does not destroy results from others.
- Region summaries average AZ-level values without mixing instance types.
- JSON conforms to schema version 1.

### 16.2 Integration tests

- Test AWS clients with Botocore Stubber or equivalent.
- Test the latency probe against a local HTTP(S) server with controlled delay and timeout.
- Test one opt-in and one excluded Region through the complete pipeline.
- Verify that `latency` mode never calls pricing or placement clients.

### 16.3 Live smoke test

An optional test using real AWS credentials must require explicit opt-in and must never run automatically in normal CI.

## 17. Version 1 acceptance criteria

Version 1 is complete when:

1. A valid `config.yml` is loaded automatically without `--config`, and normal runtime parameters can be configured through it.
2. Exact Region and glob inclusion/exclusion rules work as defined in section 7.2; all account-visible Regions are considered by default.
3. Median RTT is measured and displayed for multiple Regions using three warm-ups and five measured requests.
4. Regions above `max_rtt_ms` do not participate in price ranking.
5. Spot history is fully paginated and converted to time-weighted metrics.
6. Cost determines the selection, and lower RTT resolves a price tie.
7. SPS is used or its absence is handled according to `failure_policy`.
8. Table output contains the latest price, its timestamp/details, and an arrow trend.
9. The `latency` command or `run.mode: latency` produces an independent RTT report without price/SPS calls.
10. Table output explains the recommendation and includes Region-level averages.
11. JSON contains the recommendation, alternatives, regional summaries, latest price, structured trend, exclusions, and warnings.
12. All required unit and integration tests pass without network access.

## 18. Development stages

1. CLI scaffold, YAML schema, and validator.
2. Region discovery, allowlist, and exclusions.
3. Concurrent HTTPS latency probe.
4. Spot Price History client and time-weighted calculations.
5. Spot Placement Score.
6. Filtering, ranking, and decision explanation.
7. Table and JSON output.
8. Integration tests, IAM documentation, and examples.

## 19. Open questions for future versions

- Include inter-Region transfer cost for input data?
- Estimate expected interruption loss from checkpoint interval?
- Support vCPU/RAM requirements instead of fixed instance-type lists?
- Run probes from multiple agents and aggregate user-facing RTT?
- Store local history beyond the AWS API window for availability and trend analysis?
- Support multiple currencies with an explicit exchange-rate source?
