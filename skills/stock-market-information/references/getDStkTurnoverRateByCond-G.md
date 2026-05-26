# 股票换手率信息-通用 (getDStkTurnoverRateByCond-G)

**API_ID:** getDStkTurnoverRateByCond-G

#### 输入参数

| 参数名 | 参数中文名 | 数据类型 | 是否必填 | 默认值 |
|--------|------------|----------|----------|----------|
| stkCode | 股票代码 | 字符类型 | 否 |  |
| stkShortName | 股票简称 | 字符类型 | 否 |  |
| endDate | 截止日期 | 日期类型 | 否 |  |
| pageNum | 页码 | Integer | 是 | 1 |
| pageSize | 每页条数 | Integer | 是 | 20 |

#### 输出参数

| 参数名 | 参数中文名 | 数据类型 |
|--------|------------|----------|
| STK_CODE | 股票代码 | 字符类型 |
| STK_SHORT_NAME | 股票简称 | 字符类型 |
| END_DATE | 截止日期 | 日期类型 |
| TURNOVER_RATE | 换手率 | 数值类型 |
| TURNOVER_RATE_1W | 近1周平均换手率 | 数值类型 |
| TURNOVER_RATE_1M | 近1月平均换手率 | 数值类型 |
| TURNOVER_RATE_3M | 近3月平均换手率 | 数值类型 |
| TURNOVER_RATE_6M | 近6月平均换手率 | 数值类型 |
| TURNOVER_RATE_1Y | 近1年平均换手率 | 数值类型 |
| TURNOVER_RATE_TW | 本周以来平均换手率 | 数值类型 |
| TURNOVER_RATE_TM | 本月以来平均换手率 | 数值类型 |
| TURNOVER_RATE_TY | 今年以来平均换手率 | 数值类型 |
| TURNOVER_RATE_FL | 上市至今平均换手率 | 数值类型 |
| TRADE_DAY | 上市以来的交易天数 | 数值类型 |
| TOT_VALUE_RATE | 公司总市值(考虑汇率,A股/B股) | 数值类型 |
| FLOAT_VALUE_RATE | 公司流通市值(考虑汇率，A股/B股) | 数值类型 |
| FLOAT_VALUE_S_RATE | 个股流通市值(考虑汇率) | 数值类型 |
| TOT_VALUE_S_RATE | 个股总市值(考虑汇率) | 数值类型 |
| FLOAT_VALUE_S | 个股流通市值(不考虑汇率) | 数值类型 |
| TOT_VALUE_S | 个股总市值(不考虑汇率) | 数值类型 |


