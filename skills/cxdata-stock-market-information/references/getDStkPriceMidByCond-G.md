# 股票复权行情信息-通用 (getDStkPriceMidByCond-G)

**API_ID:** getDStkPriceMidByCond-G

#### 输入参数

| 参数名 | 参数中文名 | 数据类型 | 是否必填 | 默认值 |
|--------|------------|----------|----------|----------|
| stkCode | 股票代码 | 字符类型 | 否 |  |
| stkShortName | 股票简称 | 字符类型 | 否 |  |
| endDate | 交易日期 | 日期类型(yyyy-MM-dd) | 否 |  |
| pageNum | 页码 | Integer | 是 | 1 |
| pageSize | 每页条数 | Integer | 是 | 20 |

#### 输出参数

| 参数名 | 参数中文名 | 数据类型 |
|--------|------------|----------|
| STK_CODE | 股票代码 | 字符类型 |
| STK_SHORT_NAME | 股票简称 | 字符类型 |
| END_DATE | 交易日期 | 日期类型 |
| IS_SUSP_PAR | 是否停牌 | 数值类型 |
| ACTU_DATE | 停牌前一交易日 | 日期类型 |
| CLOSE_PRICE | 收盘价 | 数值类型 |
| PRE_CLOSE_PRICE | 昨收价 | 数值类型 |
| OPEN_PRICE | 开盘价 | 数值类型 |
| HIGH_PRICE | 最高价 | 数值类型 |
| LOW_PRICE | 最低价 | 数值类型 |
| CLOSE_PRICE_RE | 收盘价(后复权) | 数值类型 |
| PRE_CLOSE_PRICE_RE | 昨收价(后复权) | 数值类型 |
| OPEN_PRICE_RE | 开盘价(后复权) | 数值类型 |
| HIGH_PRICE_RE | 最高价(后复权) | 数值类型 |
| LOW_PRICE_RE | 最低价(后复权) | 数值类型 |
| TRADE_VOL | 成交量 | 数值类型 |
| TRADE_AMUT | 成交额 | 数值类型 |
| TRADE_NUM | 成交笔数 | 数值类型 |
| AVE_PRICE | 均价 | 数值类型 |
| AVE_PRICE_RE | 均价(后复权) | 数值类型 |
| VIBR_RANGE | 振幅 | 数值类型 |
| TURNOVER_RATE | 换手率 | 数值类型 |
| RISE_DROP | 涨跌 | 数值类型 |
| RISE_DROP_RANGE | 涨跌幅 | 数值类型 |
| RISE_DROP_RE | 涨跌(后复权) | 数值类型 |
| RISE_DROP_RANGE_RE | 涨跌幅(后复权) | 数值类型 |
| TRADE_VOL_CHAN | 成交量变化 | 数值类型 |
| TRADE_VOL_CHAN_RATE | 成交量变化率 | 数值类型 |
| TRADE_AMUT_CHAN | 成交额变化 | 数值类型 |
| TRADE_AMUT_CHAN_RATE | 成交额变化率 | 数值类型 |


