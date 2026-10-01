# <OBJECT NAME>: Z-code brief

Analysis only: read as source, not run in an SAP system.

| field | value |
|---|---|
| object | `<path>` |
| type | report / class / function group |
| lines read | <n> |
| ticket | <Jira key> |
| purpose | <one sentence, in business terms> |

## Dependency map

| kind | object | used for |
|---|---|---|
| custom class | | |
| function module | | |
| SAP class | | |
| DDIC table | | |

FI/CO, MM, SD tables touched: <list or "none">

## S/4HANA risk

| axis | rating | reason |
|---|---|---|
| simplification items | low / medium / high | |
| clean core | low / medium / high | <unreleased APIs called> |

## Defects found by reading

| id | location | defect | trigger | impact |
|---|---|---|---|---|
| D1 | `file:line` | | | |

## ABAP Unit test designs

Designed to run on a GSK system; not executed here.

| id | covers | given | when | expect |
|---|---|---|---|---|
| T1 | D1 | | | |

## Recommended next step

<fix PR, retire, replace with released API, or leave>
