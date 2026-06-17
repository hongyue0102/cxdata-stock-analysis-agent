# 指数多周期行情-通用 (getIndRoundQuoByCond-G)

**API_ID:** getIndRoundQuoByCond-G

#### 输入参数

| 参数名 | 参数中文名 | 数据类型 | 是否必填 | 默认值 |
|--------|------------|----------|----------|----------|
| roundEndDate | 周期结束日期 | 日期类型(yyyy-MM-dd) | 否 |  |
| indCode | 指数代码 | 字符类型 | 否 |  |
| indShortName | 指数简称 | 字符类型 | 否 |  |
| pageNum | 页码 | Integer | 是 | 1 |
| pageSize | 每页条数 | Integer | 是 | 20 |

#### 输出参数

| 参数名 | 参数中文名 | 数据类型 |
|--------|------------|----------|
| ROUND_TYPE_PAR | 统计周期参数 | 数值类型 |
| ROUND_START_DATE | 周期开始日期 | 日期类型 |
| ROUND_END_DATE | 周期结束日期 | 日期类型 |
| ROUND_YEAR | 年度 | 数值类型 |
| PRE_CLOSE_PRICE | 昨收盘价 | 数值类型 |
| OPEN_PRICE | 开盘价 | 数值类型 |
| HIGH_PRICE | 最高价 | 数值类型 |
| LOW_PRICE | 最低价 | 数值类型 |
| CLOSE_PRICE | 收盘价 | 数值类型 |
| TRADE_VOL | 成交量 | 数值类型 |
| TRADE_AMUT | 成交额 | 数值类型 |
| PRE_UPDOWN1 | 涨跌额 | 数值类型 |
| PRE_UPDOWN2 | 涨跌幅 | 数值类型 |
| IND_CODE | 指数代码 | 字符类型 |
| IND_SHORT_NAME | 指数简称 | 字符类型 |


