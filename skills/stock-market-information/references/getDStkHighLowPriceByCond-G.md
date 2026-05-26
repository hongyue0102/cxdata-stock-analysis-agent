# 股票最高最低价信息-通用 (getDStkHighLowPriceByCond-G)

**API_ID:** getDStkHighLowPriceByCond-G

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
| HIGH_PRICE_52W | 52周最高价 | 数值类型 |
| LOW_PRICE_52W | 52周最低价 | 数值类型 |
| HIGH_PRICE_52W_RE | 52周最高价(后复权) | 数值类型 |
| LOW_PRICE_52W_RE | 52周最低价(后复权) | 数值类型 |
| HIGH_PRICE_TW | 本周以来最高价 | 数值类型 |
| LOW_PRICE_TW | 本周以来最低价 | 数值类型 |
| HIGH_PRICE_TW_RE | 本周以来最高价(后复权) | 数值类型 |
| LOW_PRICE_TW_RE | 本周以来最低价(后复权) | 数值类型 |
| HIGH_PRICE_TM | 本月以来最高价 | 数值类型 |
| LOW_PRICE_TM | 本月以来最低价 | 数值类型 |
| HIGH_PRICE_TM_RE | 本月以来最高价(后复权) | 数值类型 |
| LOW_PRICE_TM_RE | 本月以来最低价(后复权) | 数值类型 |
| HIGH_PRICE_TY | 本年以来最高价 | 数值类型 |
| LOW_PRICE_TY | 本年以来最低价 | 数值类型 |
| HIGH_PRICE_TY_RE | 本年以来最高价(后复权) | 数值类型 |
| LOW_PRICE_TY_RE | 本年以来最低价(后复权) | 数值类型 |
| HIGH_PRICE_FL | 上市以来最高价 | 数值类型 |
| LOW_PRICE_FL | 上市以来最低价 | 数值类型 |
| HIGH_PRICE_FL_RE | 上市以来最高价(后复权) | 数值类型 |
| LOW_PRICE_FL_RE | 上市以来最低价(后复权) | 数值类型 |


