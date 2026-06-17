# 股票指数成分-通用 (getDIndCompo1ByCond-G)

**API_ID:** getDIndCompo1ByCond-G

#### 输入参数

| 参数名 | 参数中文名 | 数据类型 | 是否必填 | 默认值 |
|--------|------------|----------|----------|----------|
| indCode | 指数代码 | 字符类型 | 否 |  |
| indShortName | 指数简称 | 字符类型 | 否 |  |
| marCode | 证券代码 | 字符类型 | 否 |  |
| secShortName | 证券简称 | 字符类型 | 否 |  |
| pageNum | 页码 | Integer | 是 | 1 |
| pageSize | 每页条数 | Integer | 是 | 20 |

#### 输出参数

| 参数名 | 参数中文名 | 数据类型 |
|--------|------------|----------|
| IND_CODE | 指数代码 | 字符类型 |
| IND_SHORT_NAME | 指数简称 | 字符类型 |
| MAR_CODE | 证券代码 | 字符类型 |
| SEC_SHORT_NAME | 证券简称 | 字符类型 |
| IN_DATE | 调入日期 | 日期类型 |
| OUT_DATE | 调出日期 | 日期类型 |
| IS_COMPO_PAR | 是否最新成分股 | 数值类型 |


