# 公司信息披露考评-通用 (getDComInfoDiscEvaByCond-G)

**API_ID:** getDComInfoDiscEvaByCond-G

#### 输入参数

| 参数名 | 参数中文名 | 数据类型 | 是否必填 | 默认值 |
|--------|------------|----------|----------|----------|
| stkCode | 股票代码 | 字符类型 | 否 |  |
| stkShortName | 股票简称 | 字符类型 | 否 |  |
| evaYear | 考评年度 | 字符类型 | 否 |  |
| pageNum | 页码 | Integer | 是 | 1 |
| pageSize | 每页条数 | Integer | 是 | 20 |

#### 输出参数

| 参数名 | 参数中文名 | 数据类型 |
|--------|------------|----------|
| STK_CODE | 股票代码 | 字符类型 |
| STK_SHORT_NAME | 股票简称 | 字符类型 |
| EVA_YEAR | 考评年度 | 字符类型 |
| EVA_END_PAR | 考评结果 | 数值类型 |
| EVA_START_DATE | 考评起始日 | 日期类型 |
| EVA_END_DATE | 考评截止日 | 日期类型 |


