# 交易所股票多周期行情-通用 (getStkRoundQuoByCond-G)

**API_ID:** getStkRoundQuoByCond-G

#### 输入参数

| 参数名 | 参数中文名 | 数据类型 | 是否必填 | 默认值 | 示例值 |
|--------|------------|----------|----------|----------|----------|
| stkUniCode | 股票统一编码 | 数值类型 | 否 |  | 101000006 |
| roundEndDate | 周期结束日期 | 日期类型(yyyy-MM-dd) | 否 |  | 1991-04-05 |
| stkCode | 股票代码 | 字符类型 | 否 |  | 600136 |
| stkShortName | 股票简称 | 字符类型 | 否 |  | *ST岩石 |
| roundTypePar | 统计周期参数 | 数值类型 | 否 |  | 7 |
| restTypePar | 复权类型参数 | 数值类型 | 否 |  | 3 |
| roundYear | 年度 | 数值类型 | 否 |  | 2008 |
| pageNum | 页码 | Integer | 是 | 1 |  |
| pageSize | 每页条数 | Integer | 否 |  |  |

#### 输出参数

| 参数名 | 参数中文名 | 数据类型 | 单位 |
|--------|------------|----------|----------|
| STK_UNI_CODE | 股票统一编码 | 数值类型 |  |
| ROUND_TYPE_PAR | 统计周期参数 | 数值类型 |  |
| REST_TYPE_PAR | 复权类型参数 | 数值类型 |  |
| ROUND_START_DATE | 周期开始日期 | 日期类型 |  |
| ROUND_END_DATE | 周期结束日期 | 日期类型 |  |
| ROUND_YEAR | 年度 | 数值类型 |  |
| PRE_CLOSE_PRICE | 昨收盘价 | 数值类型 | 元 |
| OPEN_PRICE | 开盘价 | 数值类型 | 元 |
| HIGH_PRICE | 最高价 | 数值类型 | 元 |
| LOW_PRICE | 最低价 | 数值类型 | 元 |
| CLOSE_PRICE | 收盘价 | 数值类型 | 元 |
| TRADE_VOL | 成交量 | 数值类型 | 股/份 |
| TRADE_AMUT | 成交额 | 数值类型 | 元 |
| PRE_UPDOWN1 | 涨跌额 | 数值类型 | 元 |
| PRE_UPDOWN2 | 涨跌幅 | 数值类型 | % |
| VIBR_RANGE | 振幅 | 数值类型 | % |
| TURNOVER_RATE | 换手率 | 数值类型 | % |
| STK_CODE | 股票代码 | 字符类型 |  |
| STK_SHORT_NAME | 股票简称 | 字符类型 |  |


