# AWS Spot Region Selector

CLI-инструмент выбирает AWS Region и Availability Zone для краткосрочной Spot-нагрузки по задержке, истории цен и Spot Placement Score.

Полные требования и правила расчёта находятся в [SPECIFICATION.md](SPECIFICATION.md).

## Установка

```shell
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[dev]'
```

Настройте стандартные AWS credentials/profile, отредактируйте `config.yml` и запустите:

```shell
spot-region-selector
```

Только измерение RTT:

```shell
spot-region-selector latency
```

Другой конфигурационный файл и JSON-вывод:

```shell
spot-region-selector evaluate --config my-config.yml --output json
```

Сообщения о прогрессе пишутся в stderr и не портят табличный или JSON-результат в stdout. Уровень детализации настраивается в YAML:

```yaml
output:
  log_level: info  # error, warning, info или debug
```

или через CLI:

```shell
spot-region-selector evaluate --log-level debug
```

Устаревающий флаг `--verbose` сохраняется как короткий эквивалент уровня `debug`.

Проверка без обращения к AWS:

```shell
spot-region-selector validate-config
```

Минимальные IAM actions:

```text
ec2:DescribeRegions
ec2:DescribeSpotPriceHistory
ec2:GetSpotPlacementScores
```

## Исключение регионов

```yaml
regions:
  included_regions:
    - eu-*
    - us-east-*
  excluded_regions:
    - eu-west-1
    - eu-central-*
```

Пример разрешает все регионы `eu-*` и регионы `us-east-*`. Исключения всегда имеют приоритет. По умолчанию `included_regions` содержит `"*"`, то есть рассматриваются все регионы, доступные AWS credentials аккаунта.

Маска `*` сопоставляется со всем Region ID. Другие glob-операторы в первой версии не поддерживаются.
