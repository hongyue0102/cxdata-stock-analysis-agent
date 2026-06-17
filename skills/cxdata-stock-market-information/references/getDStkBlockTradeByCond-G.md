# 股票大宗交易统计-通用 (getDStkBlockTradeByCond-G)

**API_ID:** getDStkBlockTradeByCond-G

#### 输入参数

| 参数名 | 参数中文名 | 数据类型 | 是否必填 | 默认值 |
|--------|------------|----------|----------|----------|
| marCode | 股票代码 | 字符类型 | 否 |  |
| secShortName | 股票简称 | 字符类型 | 否 |  |
| tradeDate | 交易日期 | 日期类型(yyyy-MM-dd) | 否 |  |
| pageNum | 页码 | Integer | 是 | 1 |
| pageSize | 每页条数 | Integer | 是 | 20 |

#### 输出参数

| 参数名 | 参数中文名 | 数据类型 |
|--------|------------|----------|
| MAR_CODE | 股票代码 | 字符类型 |
| SEC_SHORT_NAME | 股票简称 | 字符类型 |
| TRADE_DATE | 交易日期 | 日期类型 |
| HIGH_PRICE | 日最高价 | 数值类型 |
| LOW_PRICE | 日最低价 | 数值类型 |
| OPEN_PRICE | 开盘价 | 数值类型 |
| CLOSE_PRICE | 收盘价 | 数值类型 |
| TRADE_PRI | 大宗交易成交均价 | 数值类型 |
| TRADE_AMUT | 大宗交易成交金额 | 数值类型 |
| TRADE_VOL | 大宗交易成交量 | 数值类型 |
| TRADE_NUM | 成交笔数 | 数值类型 |


