# 股票指数成分股每日权重-通用 (getIndCompoWeightDayByCond-G)

**API_ID:** getIndCompoWeightDayByCond-G

#### 输入参数

| 参数名 | 参数中文名 | 数据类型 | 是否必填 | 默认值 | 示例值 |
|--------|------------|----------|----------|----------|----------|
| indUniCode | 指数统一编码 | 数值类型 | 否 |  | 106003560 |
| indCode | 指数代码 | 数值类型 | 否 |  | 000001 |
| indShortName | 指数简称 | 字符类型 | 否 |  | 上证指数 |
| secUniCode | 证券统一编码 | 数值类型 | 否 |  | 101000460 |
| marCode | 证券代码 | 数值类型 | 否 |  | 600000 |
| secShortName | 证券简称 | 字符类型 | 否 |  | 浦发银行 |
| tradeDate | 交易日 | 日期类型(yyyy-MM-dd) | 否 |  | 2026-07-01 |
| pageNum | 页码 | Integer | 是 | 1 |  |
| pageSize | 每页条数 | Integer | 否 |  |  |

#### 输出参数

| 参数名 | 参数中文名 | 数据类型 | 单位 |
|--------|------------|----------|----------|
| IND_CODE | 指数代码 | 数值类型 |  |
| IND_SHORT_NAME | 指数简称 | 字符类型 |  |
| IND_UNI_CODE | 指数统一编码 | 数值类型 |  |
| TRADE_DATE | 交易日 | 日期类型 |  |
| MAR_CODE | 证券代码 | 数值类型 |  |
| SEC_SHORT_NAME | 证券简称 | 字符类型 |  |
| SEC_UNI_CODE | 证券统一编码 | 数值类型 |  |
| WEIGHT_DAY | 每日权重 | 数值类型 | % |


