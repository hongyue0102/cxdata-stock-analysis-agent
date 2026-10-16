# 交易所股票日交易信息-通用 (getStatTradeDateMainByCond-G)

**API_ID:** getStatTradeDateMainByCond-G

#### 输入参数

| 参数名 | 参数中文名 | 数据类型 | 是否必填 | 默认值 | 示例值 |
|--------|------------|----------|----------|----------|----------|
| endDate | 截止日期 | 日期类型(yyyy-MM-dd) | 否 |  | 2024-06-14 |
| secUniCode | 证券统一编码 | 数值类型 | 否 |  | 101001478 |
| stkCode | 股票代码 | 字符类型 | 否 |  | 000836 |
| stkShortName | 股票简称 | 字符类型 | 否 |  | ST富通 |
| mainId | 主表关联标识 | 数值类型 | 否 |  | 46578 |
| pageNum | 页码 | Integer | 是 | 1 |  |
| pageSize | 每页条数 | Integer | 否 |  |  |

#### 输出参数

| 参数名 | 参数中文名 | 数据类型 | 单位 |
|--------|------------|----------|----------|
| END_DATE | 截止日期 | 日期类型 |  |
| SEC_UNI_CODE | 证券统一编码 | 数值类型 |  |
| STK_CODE | 股票代码 | 字符类型 |  |
| STK_SHORT_NAME | 股票简称 | 字符类型 |  |
| ABNORM_TYPE_PAR | 异动类型 | 数值类型 |  |
| TRADE_VOL | 成交量 | 数值类型 | 万股/万份 |
| TRADE_AMUT | 成交金额 | 数值类型 | 万元 |
| RISE_DROP_RANGE | 涨跌幅 | 数值类型 | % |
| RANGE_DEVI_VAL | 涨跌幅偏离值 | 数值类型 | % |
| VIBR_RANGE | 振幅 | 数值类型 | % |
| TURNOVER_RATE | 换手率 | 数值类型 | % |
| MAIN_ID | 主表关联标识 | 数值类型 |  |


