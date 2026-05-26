# 股票市值信息-通用 (getDStkValueMidByCond-G)

**API_ID:** getDStkValueMidByCond-G

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
| TOT_VALUE_RATE | 公司总市值(考虑汇率,A股/B股/H股) | 数值类型 |
| FLOAT_VALUE_RATE | 公司流通市值(考虑汇率,A股/B股) | 数值类型 |
| FLOAT_VALUE_S_RATE | 个股流通市值(考虑汇率) | 数值类型 |
| TOT_VALUE_S_RATE | 个股总市值(考虑汇率) | 数值类型 |
| FLOAT_VALUE_S | 个股流通市值(不考虑汇率) | 数值类型 |
| TOT_VALUE_S | 个股总市值(不考虑汇率) | 数值类型 |
| TOT_VALUE_SHARE | 公司总市值(不考虑汇率，总股本算) | 数值类型 |
| TOT_VALUE_SHARE_S | 公司流通市值(不考虑汇率，流通股本算) | 数值类型 |


