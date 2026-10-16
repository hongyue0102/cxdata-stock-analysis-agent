# 股票大宗交易统计-通用 (getDStkBlockTradeByCond-G)

**API_ID:** getDStkBlockTradeByCond-G

#### 输入参数

| 参数名 | 参数中文名 | 数据类型 | 是否必填 | 默认值 | 示例值 |
|--------|------------|----------|----------|----------|----------|
| secUniCode | 证券统一编码 | 数值类型 | 否 |  | 101000007 |
| marCode | 股票代码 | 字符类型 | 否 |  | 601988 |
| secShortName | 股票简称 | 字符类型 | 否 |  | 中国银行 |
| tradeDate | 交易日期 | 日期类型(yyyy-MM-dd) | 否 |  | 2009-02-19 |
| pageNum | 页码 | Integer | 是 | 1 |  |
| pageSize | 每页条数 | Integer | 否 |  |  |

#### 输出参数

| 参数名 | 参数中文名 | 数据类型 | 单位 |
|--------|------------|----------|----------|
| SEC_UNI_CODE | 证券统一编码 | 数值类型 |  |
| MAR_CODE | 股票代码 | 字符类型 |  |
| SEC_SHORT_NAME | 股票简称 | 字符类型 |  |
| TRADE_DATE | 交易日期 | 日期类型 |  |
| HIGH_PRICE | 日最高价 | 数值类型 | 元 |
| LOW_PRICE | 日最低价 | 数值类型 | 元 |
| OPEN_PRICE | 开盘价 | 数值类型 | 元 |
| CLOSE_PRICE | 收盘价 | 数值类型 | 元 |
| TRADE_PRI | 大宗交易成交均价 | 数值类型 | 元 |
| TRADE_AMUT | 大宗交易成交金额 | 数值类型 | 万元 |
| TRADE_VOL | 大宗交易成交量 | 数值类型 | 万股/万份 |
| TRADE_NUM | 成交笔数 | 数值类型 | 笔 |


