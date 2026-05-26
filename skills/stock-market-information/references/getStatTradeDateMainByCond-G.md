# 交易所股票日交易信息-通用 (getStatTradeDateMainByCond-G)

**API_ID:** getStatTradeDateMainByCond-G

#### 输入参数

| 参数名 | 参数中文名 | 数据类型 | 是否必填 | 默认值 |
|--------|------------|----------|----------|----------|
| endDate | 截止日期 | 日期类型 | 否 |  |
| stkCode | 股票代码 | 字符类型 | 否 |  |
| stkShortName | 股票简称 | 字符类型 | 否 |  |
| pageNum | 页码 | Integer | 是 | 1 |
| pageSize | 每页条数 | Integer | 是 | 20 |

#### 输出参数

| 参数名 | 参数中文名 | 数据类型 |
|--------|------------|----------|
| END_DATE | 截止日期 | 日期类型 |
| STK_CODE | 股票代码 | 字符类型 |
| STK_SHORT_NAME | 股票简称 | 字符类型 |
| ABNORM_TYPE_PAR | 异动类型 | 数值类型 |
| TRADE_VOL | 成交量 | 数值类型 |
| TRADE_AMUT | 成交金额 | 数值类型 |
| RISE_DROP_RANGE | 涨跌幅 | 数值类型 |
| RANGE_DEVI_VAL | 涨跌幅偏离值 | 数值类型 |
| VIBR_RANGE | 振幅 | 数值类型 |
| TURNOVER_RATE | 换手率 | 数值类型 |
| MAIN_ID | 主表关联标识 | 数值类型 |


