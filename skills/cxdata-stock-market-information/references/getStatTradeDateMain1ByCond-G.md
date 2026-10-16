# 交易所基金日交易信息-通用 (getStatTradeDateMain1ByCond-G)

**API_ID:** getStatTradeDateMain1ByCond-G

#### 输入参数

| 参数名 | 参数中文名 | 数据类型 | 是否必填 | 默认值 | 示例值 |
|--------|------------|----------|----------|----------|----------|
| endDate | 截止日期 | 日期类型(yyyy-MM-dd) | 否 |  | 2010-10-21 |
| secUniCode | 证券统一编码 | 数值类型 | 否 |  | 102000035 |
| fundCode | 基金代码 | 字符类型 | 否 |  | 150013 |
| fundShortName | 基金简称 | 字符类型 | 否 |  | 中证100B |
| pageNum | 页码 | Integer | 是 | 1 |  |
| pageSize | 每页条数 | Integer | 否 |  |  |

#### 输出参数

| 参数名 | 参数中文名 | 数据类型 | 单位 |
|--------|------------|----------|----------|
| END_DATE | 截止日期 | 日期类型 |  |
| SEC_UNI_CODE | 证券统一编码 | 数值类型 |  |
| FUND_CODE | 基金代码 | 字符类型 |  |
| FUND_SHORT_NAME | 基金简称 | 字符类型 |  |
| ABNORM_TYPE_PAR | 异动类型 | 数值类型 |  |
| TRADE_VOL | 成交量 | 数值类型 | 万份 |
| TRADE_AMUT | 成交金额 | 数值类型 | 万元 |
| RISE_DROP_RANGE | 涨跌幅 | 数值类型 | % |
| RANGE_DEVI_VAL | 涨跌幅偏离值 | 数值类型 | % |
| VIBR_RANGE | 振幅 | 数值类型 | % |
| TURNOVER_RATE | 换手率 | 数值类型 | % |
| MAIN_ID | 主表关联标识 | 数值类型 |  |


