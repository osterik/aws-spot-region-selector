# AWS Spot Region Selector

CLI-инструмент выбирает AWS Region и Availability Zone для краткосрочной Spot-нагрузки по задержке, истории цен и Spot Placement Score для заданных географических зон\регионов.

Приложение измеряет RTT до выбранных регионов; затем для тех, которые удовлетворяют условию по максимальному времени доступа, запрашивает Spot Price History и Spot Placement Score а затем покажет рекомендацию и альтернативы.

Полные требования и правила расчёта находятся в [SPECIFICATION.md](SPECIFICATION.md).

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
REGION        AZ             TYPE        RTT_MED   LATEST   TREND               AVG        P95      EST_COST   SPS
------------  -------------  ----------  --------  -------  ------------------  ---------  -------  ---------  ---
ap-south-1    ap-south-1b    t4g.medium  954.7 ms  $0.0089  → $0 (0.0%)         $0.008316  $0.0089  $0.008725  3
ap-south-1    ap-south-1c    t4g.medium  954.7 ms  $0.0093  ↑ +$0.0001 (+1.1%)  $0.009352  $0.0099  $0.009435  3
il-central-1  il-central-1c  t4g.medium  427.5 ms  $0.0101  → $0 (0.0%)         $0.010126  $0.0103  $0.010148  -
ap-south-1    ap-south-1a    t4g.medium  954.7 ms  $0.0116  ↑ +$0.0001 (+0.9%)  $0.011093  $0.0115  $0.011428  3
ap-south-2    ap-south-2c    t4g.medium  996.5 ms  $0.0109  → $0 (0.0%)         $0.011044  $0.0113  $0.011023  -
ap-south-2    ap-south-2b    t4g.medium  996.5 ms  $0.0111  → $0 (0.0%)         $0.011328  $0.0114  $0.011228  -
ap-south-2    ap-south-2a    t4g.medium  996.5 ms  $0.0114  ↑ +$0.0001 (+0.9%)  $0.011392  $0.0116  $0.011437  -
eu-south-2    eu-south-2b    t4g.medium  398.5 ms  $0.0118  ↓ -$0.0001 (-0.8%)  $0.01289   $0.0141  $0.012587  -
eu-south-2    eu-south-2c    t3.medium   398.5 ms  $0.0131  ↓ -$0.0001 (-0.8%)  $0.013499  $0.0138  $0.01336   -
eu-south-2    eu-south-2a    t3.medium   398.5 ms  $0.013   ↓ -$0.0002 (-1.5%)  $0.013585  $0.0142  $0.013416  -
eu-south-2    eu-south-2b    t3.medium   398.5 ms  $0.0135  → $0 (0.0%)         $0.013953  $0.0145  $0.013836  -
il-central-1  il-central-1a  t4g.medium  427.5 ms  $0.0132  ↓ -$0.0001 (-0.8%)  $0.013431  $0.0136  $0.013349  -
il-central-1  il-central-1b  t4g.medium  427.5 ms  $0.0135  ↓ -$0.0001 (-0.7%)  $0.013607  $0.0138  $0.013592  -
eu-south-1    eu-south-1c    t3.medium   310.8 ms  $0.0146  ↓ -$0.0001 (-0.7%)  $0.01487   $0.0151  $0.014781  3
eu-west-2     eu-west-2d     t4g.medium  367.0 ms  $0.0146  → $0 (0.0%)         $0.0146    $0.0146  $0.0146    -
ap-south-1    ap-south-1a    t3.medium   954.7 ms  $0.0144  → $0 (0.0%)         $0.01401   $0.0144  $0.014283  3
ap-south-2    ap-south-2c    t3.medium   996.5 ms  $0.0139  → $0 (0.0%)         $0.014207  $0.0147  $0.014152  -
eu-south-1    eu-south-1b    t3.medium   310.8 ms  $0.015   → $0 (0.0%)         $0.015093  $0.0152  $0.015068  3
eu-south-2    eu-south-2a    t4g.medium  398.5 ms  $0.0143  → $0 (0.0%)         $0.015424  $0.0162  $0.015017  -
eu-south-1    eu-south-1a    t4g.medium  310.8 ms  $0.0159  → $0 (0.0%)         $0.015629  $0.0159  $0.015819  3
eu-west-2     eu-west-2a     t3.medium   367.0 ms  $0.0161  → $0 (0.0%)         $0.016414  $0.0167  $0.016314  -

Recommended: ap-south-1 / ap-south-1b / t4g.medium
Reason: lowest estimated compute cost within the configured constraints; price ties prefer lower RTT.

Regional averages across Availability Zones:
REGION        TYPE        AZS  RTT_MED   AVG_LATEST  AVG_TREND             AVG_HISTORY  AVG_P95    AVG_EST_COST  SPS
------------  ----------  ---  --------  ----------  --------------------  -----------  ---------  ------------  ---
ap-south-1    t4g.medium  3    954.7 ms  $0.009933   ↑ +$0.000067 (+0.7%)  $0.009587    $0.0101    $0.009863     3
ap-south-2    t4g.medium  3    996.5 ms  $0.011133   ↑ +$0.000033 (+0.3%)  $0.011255    $0.011433  $0.01123      -
il-central-1  t4g.medium  3    427.5 ms  $0.012267   ↓ -$0.000067 (-0.5%)  $0.012388    $0.012567  $0.012363     -
eu-south-2    t3.medium   3    398.5 ms  $0.0132     ↓ -$0.0001 (-0.8%)    $0.013679    $0.014167  $0.013537     -
eu-south-2    t4g.medium  3    398.5 ms  $0.014733   ↓ -$0.000033 (-0.2%)  $0.015587    $0.016667  $0.015376     -
eu-south-1    t3.medium   3    310.8 ms  $0.0156     ↓ -$0.000033 (-0.2%)  $0.015671    $0.015833  $0.015668     3
il-central-1  t3.medium   3    427.5 ms  $0.0161     ↓ -$0.0001 (-0.6%)    $0.016104    $0.016233  $0.016128     -
ap-south-1    t3.medium   3    954.7 ms  $0.016833   ↑ +$0.000033 (+0.2%)  $0.016114    $0.0168    $0.016611     3
eu-west-2     t3.medium   4    367.0 ms  $0.017225   ↓ -$0.000075 (-0.4%)  $0.017393    $0.01765   $0.01736      -
ap-south-2    t3.medium   3    996.5 ms  $0.017367   ↓ -$0.000067 (-0.4%)  $0.017632    $0.017833  $0.01754      -
eu-north-1    t4g.medium  3    401.2 ms  $0.016233   ↓ -$0.000067 (-0.4%)  $0.018528    $0.020067  $0.017689     -
eu-west-1     t4g.medium  3    376.6 ms  $0.018767   ↑ +$0.000033 (+0.2%)  $0.01933     $0.020367  $0.019256     3
eu-north-1    t3.medium   3    401.2 ms  $0.017767   ↓ -$0.000167 (-0.9%)  $0.020264    $0.022167  $0.019396     -
eu-south-1    t4g.medium  3    310.8 ms  $0.019967   → $0 (0.0%)           $0.019724    $0.02      $0.0199       3
eu-central-2  t3.medium   3    351.5 ms  $0.020033   ↓ -$0.000067 (-0.3%)  $0.020662    $0.021     $0.020415     -
eu-central-1  t3.medium   3    343.9 ms  $0.020533   ↑ +$0.000033 (+0.2%)  $0.020494    $0.020667  $0.020548     3
eu-west-3     t3.medium   3    352.9 ms  $0.021133   → $0 (0.0%)           $0.02078     $0.021133  $0.021027     -
eu-central-2  t4g.medium  3    351.5 ms  $0.020767   ↓ -$0.000067 (-0.3%)  $0.021656    $0.022267  $0.021334     -
eu-central-1  t4g.medium  3    343.9 ms  $0.0235     ↓ -$0.0001 (-0.4%)    $0.024381    $0.024967  $0.024058     3
eu-west-1     t3.medium   3    376.6 ms  $0.024333   ↓ -$0.000067 (-0.3%)  $0.024576    $0.024767  $0.024493     3
eu-west-3     t4g.medium  3    352.9 ms  $0.024367   ↓ -$0.000233 (-0.9%)  $0.025193    $0.0262    $0.024981     -
eu-west-2     t4g.medium  4    367.0 ms  $0.024875   ↓ -$0.000125 (-0.5%)  $0.025717    $0.026175  $0.025388     -
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
