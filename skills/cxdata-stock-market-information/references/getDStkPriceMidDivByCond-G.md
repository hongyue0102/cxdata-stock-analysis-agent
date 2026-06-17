# 股票前复权行情-通用 (getDStkPriceMidDivByCond-G)

**API_ID:** getDStkPriceMidDivByCond-G

#### 输入参数

| 参数名 | 参数中文名 | 数据类型 | 是否必填 | 默认值 |
|--------|------------|----------|----------|----------|
| endDate | 截止日期 | 日期类型(yyyy-MM-dd) | 否 |  |
| stkCode | 股票代码 | 字符类型 | 否 |  |
| stkShortName | 股票简称 | 字符类型 | 否 |  |
| pageNum | 页码 | Integer | 是 | 1 |
| pageSize | 每页条数 | Integer | 是 | 20 |

#### 输出参数

| 参数名 | 参数中文名 | 数据类型 |
|--------|------------|----------|
| END_DATE | 截止日期 | 日期类型 |
| ACTU_DATE | 实际行情数据日期 | 日期类型 |
| CLOSE_PRICE_BRE | 收盘价(前复权) | 数值类型 |
| PRE_CLOSE_PRICE_BRE | 昨收价(前复权) | 数值类型 |
| OPEN_PRICE_BRE | 开盘价（前复权） | 数值类型 |
| HIGH_PRICE_BRE | 最高价（前复权） | 数值类型 |
| LOW_PRICE_BRE | 最低价（前复权） | 数值类型 |
| AVE_PRICE_BRE | 均价（前复权） | 数值类型 |
| RISE_DROP_BRE | 涨跌（前复权） | 数值类型 |
| RISE_DROP_RANGE_RE | 涨跌幅（前复权） | 数值类型 |


