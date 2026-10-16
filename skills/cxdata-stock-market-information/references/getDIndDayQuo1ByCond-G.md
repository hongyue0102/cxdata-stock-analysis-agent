# 股票指数日行情-通用 (getDIndDayQuo1ByCond-G)

**API_ID:** getDIndDayQuo1ByCond-G

#### 输入参数

| 参数名 | 参数中文名 | 数据类型 | 是否必填 | 默认值 | 示例值 |
|--------|------------|----------|----------|----------|----------|
| indUniCode | 指数统一编码 | 数值类型 | 否 |  | 106002041 |
| indCode | 指数代码 | 字符类型 | 否 |  | CN2337 |
| indShortName | 指数简称 | 字符类型 | 否 |  | 深证民营R |
| tradeDate | 交易日期 | 日期类型(yyyy-MM-dd) | 否 |  | 2010-10-18 |
| pageNum | 页码 | Integer | 是 | 1 |  |
| pageSize | 每页条数 | Integer | 否 |  |  |

#### 输出参数

| 参数名 | 参数中文名 | 数据类型 | 单位 |
|--------|------------|----------|----------|
| IND_UNI_CODE | 指数统一编码 | 数值类型 |  |
| IND_CODE | 指数代码 | 字符类型 |  |
| IND_SHORT_NAME | 指数简称 | 字符类型 |  |
| TRADE_DATE | 交易日期 | 日期类型 |  |
| PRE_CLOSE_PRICE | 昨收盘价 | 数值类型 | 点 |
| OPEN_PRICE | 开盘价 | 数值类型 | 点 |
| TRADE_AMUT | 成交金额 | 数值类型 | 元 |
| HIGH_PRICE | 最高价 | 数值类型 | 点 |
| LOW_PRICE | 最低价 | 数值类型 | 点 |
| CLOSE_PRICE | 收盘价 | 数值类型 | 点 |
| TRADE_VOL | 成交数量 | 数值类型 | 股 |
| PRICE_UPDOWN1 | 价格升跌 | 数值类型 |  |
| PRI_LIMIT | 涨跌幅 | 数值类型 | % |


