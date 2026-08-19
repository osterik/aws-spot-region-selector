# AWS Spot Region Selector

CLI-инструмент выбирает AWS Region и Availability Zone для краткосрочной Spot-нагрузки по задержке, истории цен и Spot Placement Score для заданных географических зон\регионов.

Приложение измеряет RTT до выбранных регионов; затем для тех, которые удовлетворяют условию по максимальному времени доступа, запрашивает Spot Price History и Spot Placement Score а затем покажет рекомендацию и альтернативы.

Полные требования и правила расчёта находятся в [SPECIFICATION_RU.md](SPECIFICATION_RU.md). Английская документация доступна в [README.md](README.md).

## Быстрый старт

Требования: Python 3.10+ и AWS credentials с read-only разрешениями из следующего раздела.

```shell
python3 -m venv .venv
source .venv/bin/activate
python -m pip install .
```

Отредактируйте готовый `config.yml`, как минимум указав типы инстансов и рассматриваемые регионы:

```yaml
workload:
  instance_types: [t4g.medium]

regions:
  included_regions: ["eu-*"]
  excluded_regions: []
```

Основные команды:

```shell
# Проверить конфигурацию ./config.yml (без обращения к AWS):
spot-region-selector validate-config

# Получить список регионов для анализа:
spot-region-selector list-regions

# Измерить RTT до выбранных регионов:
spot-region-selector latency

# Запустить оценку:
spot-region-selector evaluate
```

## IAM-разрешения

Приложение выполняет только read-only запросы и не создаёт, не изменяет и не удаляет AWS-ресурсы. Минимальная IAM policy должна включать:

```text
ec2:DescribeRegions           # Получение регионов, доступных текущему AWS-аккаунту
ec2:DescribeSpotPriceHistory  # Получение текущих и исторических Spot-цен по Region/AZ/type
ec2:GetSpotPlacementScores    # Оценка вероятности получить требуемую Spot-ёмкость
```

`ec2:GetSpotPlacementScores` можно исключить из policy, если в конфигурации задано `placement.enabled=false`

## Включение/исключение регионов

```yaml
regions:
  included_regions:
    - eu-*
    - us-east-*
  excluded_regions:
    - eu-central-*
    - us-east-1

```

Пример разрешает все регионы `eu-*` и регионы `us-east-*`, кроме всех регионов `eu-central-*` и конкретно `us-east-1`.
Исключения всегда имеют приоритет. По умолчанию `included_regions` содержит `"*"`, то есть рассматриваются все регионы, доступные AWS credentials аккаунта.

## Пример

Конфигурация:

```yaml
regions:
  included_regions: ["eu-*", "il-*", "ap-south-*"]
  excluded_regions: []

workload:
  instance_types: [t3.medium, t4g.medium]
  product_descriptions: [Linux/UNIX]
  target_capacity: 1                  # 1 инстанс
  duration_hours: 1                   # на 1 час

latency:
  max_rtt_ms: 1000

output:
  format: table
```

Сокращённый пример вывода (цены иллюстративны и меняются со временем):

```text
REGION        AZ  TYPE        RTT_MED   LATEST   TREND               AVG      P95      EST_COST  SPS
------------  --  ----------  --------  -------  ------------------  -------  -------  --------  ---
ap-south-1    b   t4g.medium  969.5 ms  $0.0090  ↑ +$0.0001 (+1.1%)  $0.0083  $0.0089  $0.0088   3
ap-south-1    c   t4g.medium  969.5 ms  $0.0093  → $0.0000 (0.0%)    $0.0093  $0.0098  $0.0094   3
il-central-1  c   t4g.medium  428.4 ms  $0.0101  → $0.0000 (0.0%)    $0.0101  $0.0103  $0.0101   3
ap-south-1    a   t4g.medium  969.5 ms  $0.0115  ↓ -$0.0001 (-0.9%)  $0.0111  $0.0115  $0.0114   3
ap-south-2    c   t4g.medium  988.9 ms  $0.0108  ↓ -$0.0001 (-0.9%)  $0.0110  $0.0113  $0.0110   3
ap-south-2    b   t4g.medium  988.9 ms  $0.0111  → $0.0000 (0.0%)    $0.0113  $0.0114  $0.0112   3
ap-south-2    a   t4g.medium  988.9 ms  $0.0114  → $0.0000 (0.0%)    $0.0114  $0.0116  $0.0114   3
eu-south-2    b   t4g.medium  394.6 ms  $0.0118  ↓ -$0.0001 (-0.8%)  $0.0128  $0.0141  $0.0126   3
eu-south-2    c   t3.medium   394.6 ms  $0.0131  → $0.0000 (0.0%)    $0.0135  $0.0138  $0.0134   3
eu-south-2    a   t3.medium   394.6 ms  $0.0130  → $0.0000 (0.0%)    $0.0136  $0.0142  $0.0134   3
eu-south-2    b   t3.medium   394.6 ms  $0.0135  → $0.0000 (0.0%)    $0.0139  $0.0145  $0.0138   3
il-central-1  a   t4g.medium  428.4 ms  $0.0132  → $0.0000 (0.0%)    $0.0134  $0.0136  $0.0133   3
il-central-1  b   t4g.medium  428.4 ms  $0.0135  → $0.0000 (0.0%)    $0.0136  $0.0138  $0.0136   3
eu-south-1    c   t3.medium   305.1 ms  $0.0146  → $0.0000 (0.0%)    $0.0149  $0.0151  $0.0148   -
eu-west-2     d   t4g.medium  312.0 ms  $0.0146  → $0.0000 (0.0%)    $0.0146  $0.0146  $0.0146   3
ap-south-1    a   t3.medium   969.5 ms  $0.0144  → $0.0000 (0.0%)    $0.0140  $0.0144  $0.0143   3
ap-south-2    c   t3.medium   988.9 ms  $0.0139  → $0.0000 (0.0%)    $0.0142  $0.0147  $0.0141   3
eu-south-1    b   t3.medium   305.1 ms  $0.0149  ↓ -$0.0001 (-0.7%)  $0.0151  $0.0152  $0.0150   -
eu-south-2    a   t4g.medium  394.6 ms  $0.0143  → $0.0000 (0.0%)    $0.0154  $0.0162  $0.0150   3
eu-south-1    a   t4g.medium  305.1 ms  $0.0159  → $0.0000 (0.0%)    $0.0156  $0.0159  $0.0158   -
eu-west-2     a   t3.medium   312.0 ms  $0.0161  → $0.0000 (0.0%)    $0.0164  $0.0167  $0.0163   3

Recommended: ap-south-1 / b / t4g.medium
Reason: lowest estimated compute cost within the configured constraints; price ties prefer lower RTT.

Regional averages across Availability Zones:
REGION        TYPE        AZS  RTT_MED   AVG_LATEST  AVG_TREND           AVG_HIST  AVG_P95  AVG_EST  SPS
------------  ----------  ---  --------  ----------  ------------------  --------  -------  -------  ---
ap-south-1    t4g.medium  3    969.5 ms  $0.0099     → $0.0000 (0.0%)    $0.0096   $0.0101  $0.0099  3
ap-south-2    t4g.medium  3    988.9 ms  $0.0111     ↓ -$0.0000 (-0.3%)  $0.0112   $0.0114  $0.0112  3
il-central-1  t4g.medium  3    428.4 ms  $0.0123     → $0.0000 (0.0%)    $0.0124   $0.0126  $0.0124  3
eu-south-2    t3.medium   3    394.6 ms  $0.0132     → $0.0000 (0.0%)    $0.0137   $0.0142  $0.0135  3
eu-south-2    t4g.medium  3    394.6 ms  $0.0147     ↓ -$0.0000 (-0.2%)  $0.0156   $0.0167  $0.0154  3
eu-south-1    t3.medium   3    305.1 ms  $0.0156     ↓ -$0.0000 (-0.2%)  $0.0157   $0.0158  $0.0157  -
il-central-1  t3.medium   3    428.4 ms  $0.0161     ↓ -$0.0001 (-0.4%)  $0.0161   $0.0162  $0.0161  3
ap-south-1    t3.medium   3    969.5 ms  $0.0168     ↑ +$0.0000 (+0.2%)  $0.0161   $0.0168  $0.0166  3
eu-west-2     t3.medium   4    312.0 ms  $0.0172     ↓ -$0.0001 (-0.4%)  $0.0174   $0.0176  $0.0174  3
ap-south-2    t3.medium   3    988.9 ms  $0.0174     ↓ -$0.0001 (-0.4%)  $0.0176   $0.0178  $0.0175  3
eu-north-1    t4g.medium  3    399.1 ms  $0.0162     ↓ -$0.0000 (-0.2%)  $0.0185   $0.0201  $0.0177  -
eu-west-1     t4g.medium  3    373.0 ms  $0.0188     ↑ +$0.0000 (+0.2%)  $0.0193   $0.0203  $0.0192  -
eu-north-1    t3.medium   3    399.1 ms  $0.0176     ↓ -$0.0002 (-1.3%)  $0.0202   $0.0222  $0.0193  -
eu-south-1    t4g.medium  3    305.1 ms  $0.0199     ↓ -$0.0000 (-0.2%)  $0.0197   $0.0200  $0.0199  -
eu-central-2  t3.medium   3    312.5 ms  $0.0200     ↓ -$0.0001 (-0.3%)  $0.0206   $0.0210  $0.0204  -
eu-central-1  t3.medium   3    308.1 ms  $0.0206     ↑ +$0.0000 (+0.2%)  $0.0205   $0.0207  $0.0206  -
eu-west-3     t3.medium   3    336.9 ms  $0.0211     → $0.0000 (0.0%)    $0.0208   $0.0211  $0.0210  -
eu-central-2  t4g.medium  3    312.5 ms  $0.0207     ↓ -$0.0001 (-0.5%)  $0.0216   $0.0223  $0.0213  -
eu-central-1  t4g.medium  3    308.1 ms  $0.0235     ↓ -$0.0001 (-0.6%)  $0.0244   $0.0249  $0.0240  -
eu-west-1     t3.medium   3    373.0 ms  $0.0243     ↓ -$0.0000 (-0.1%)  $0.0246   $0.0248  $0.0245  -
eu-west-3     t4g.medium  3    336.9 ms  $0.0243     ↓ -$0.0003 (-1.1%)  $0.0252   $0.0262  $0.0249  -
eu-west-2     t4g.medium  4    312.0 ms  $0.0249     ↓ -$0.0001 (-0.5%)  $0.0257   $0.0262  $0.0254  3
Excluded:
- ap-northeast-1: not_included (no include rule matched)
...
```

Первая таблица показывает отдельные кандидаты по Availability Zone. Вторая усредняет цены всех прошедших фильтры AZ отдельно для каждой комбинации `Region + instance type + product description`.

## Разработка

Для локальной разработки установите проект в editable-режиме с dev-зависимостями:

```shell
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
pre-commit install
```

### Проверки перед коммитом

После `pre-commit install` каждый ручной коммит запускает:

- проверки YAML/TOML, конфликтов слияния, больших файлов и whitespace;
- Ruff lint с безопасными автоисправлениями;
- Ruff formatter;
- Gitleaks для поиска случайно добавленных credentials, токенов и других секретов;
- полный набор pytest.

Запуск вручную для всего репозитория:

```shell
pre-commit run --all-files
```
