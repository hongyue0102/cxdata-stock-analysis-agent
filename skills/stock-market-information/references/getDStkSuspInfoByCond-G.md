# 股票停牌信息-通用 (getDStkSuspInfoByCond-G)

**API_ID:** getDStkSuspInfoByCond-G

#### 输入参数

| 参数名 | 参数中文名 | 数据类型 | 是否必填 | 默认值 |
|--------|------------|----------|----------|----------|
| stkCode | 股票代码 | 字符类型 | 否 |  |
| stkShortName | 股票简称 | 字符类型 | 否 |  |
| pageNum | 页码 | Integer | 是 | 1 |
| pageSize | 每页条数 | Integer | 是 | 20 |

#### 输出参数

| 参数名 | 参数中文名 | 数据类型 |
|--------|------------|----------|
| STK_CODE | 股票代码 | 字符类型 |
| STK_SHORT_NAME | 股票简称 | 字符类型 |
| SUSP_TYPE_PAR | 停牌类型 | 数值类型 |
| EVENT_START_DATE | 停牌日期 | 日期类型 |
| EVENT_START_TIME | 停牌时间 | 字符类型 |
| EVENT_END_DATE | 复牌日期 | 字符类型 |
| EVENT_END_TIME | 复牌时间 | 字符类型 |
| SPE_TIPS_CONTE | 停牌原因 | 字符类型 |
| SUSP_MATU_PAR | 停牌期限 | 数值类型 |
| PUBL_DATE | 发布日期 | 日期类型 |


