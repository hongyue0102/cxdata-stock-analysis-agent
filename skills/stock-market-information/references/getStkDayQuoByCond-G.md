# 交易所股票日行情-通用 (getStkDayQuoByCond-G)

**API_ID:** getStkDayQuoByCond-G

#### 输入参数

| 参数名 | 参数中文名 | 数据类型 | 是否必填 | 默认值 |
|--------|------------|----------|----------|----------|
| stkCode | 股票代码 | 字符类型 | 否 |  |
| stkShortName | 股票简称 | 字符类型 | 否 |  |
| tradeDate | 交易日期 | 日期类型 | 否 |  |
| pageNum | 页码 | Integer | 是 | 1 |
| pageSize | 每页条数 | Integer | 是 | 10000 |

#### 输出参数

| 参数名 | 参数中文名 | 数据类型 |
|--------|------------|----------|
| STK_CODE | 股票代码 | 字符类型 |
| STK_SHORT_NAME | 股票简称 | 字符类型 |
| TRADE_DATE | 交易日期 | 日期类型 |
| PRE_CLOSE_PRICE | 昨收盘价 | 数值类型 |
| OPEN_PRICE | 开盘价 | 数值类型 |
| TRADE_AMUT | 成交金额 | 数值类型 |
| HIGH_PRICE | 最高价 | 数值类型 |
| LOW_PRICE | 最低价 | 数值类型 |
| CLOSE_PRICE | 收盘价 | 数值类型 |
| TRADE_VOL | 成交数量 | 数值类型 |
| PRICE_LIMIT | 价格涨跌幅 | 数值类型 |


