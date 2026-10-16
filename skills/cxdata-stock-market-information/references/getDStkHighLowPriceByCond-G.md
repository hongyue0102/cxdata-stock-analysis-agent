# 股票最高最低价信息-通用 (getDStkHighLowPriceByCond-G)

**API_ID:** getDStkHighLowPriceByCond-G

#### 输入参数

| 参数名 | 参数中文名 | 数据类型 | 是否必填 | 默认值 | 示例值 |
|--------|------------|----------|----------|----------|----------|
| stkUniCode | 股票统一编码 | 数值类型 | 否 |  | 101000006 |
| stkCode | 股票代码 | 字符类型 | 否 |  | 000003 |
| stkShortName | 股票简称 | 字符类型 | 否 |  | PT金田A |
| endDate | 截止日期 | 日期类型(yyyy-MM-dd) | 否 |  | 1991-04-03 |
| pageNum | 页码 | Integer | 是 | 1 |  |
| pageSize | 每页条数 | Integer | 否 |  |  |

#### 输出参数

| 参数名 | 参数中文名 | 数据类型 | 单位 |
|--------|------------|----------|----------|
| STK_UNI_CODE | 股票统一编码 | 数值类型 |  |
| STK_CODE | 股票代码 | 字符类型 |  |
| STK_SHORT_NAME | 股票简称 | 字符类型 |  |
| END_DATE | 截止日期 | 日期类型 |  |
| HIGH_PRICE_52W | 52周最高价 | 数值类型 | 元 |
| LOW_PRICE_52W | 52周最低价 | 数值类型 | 元 |
| HIGH_PRICE_52W_RE | 52周最高价(后复权) | 数值类型 | 元 |
| LOW_PRICE_52W_RE | 52周最低价(后复权) | 数值类型 | 元 |
| HIGH_PRICE_TW | 本周以来最高价 | 数值类型 | 元 |
| LOW_PRICE_TW | 本周以来最低价 | 数值类型 | 元 |
| HIGH_PRICE_TW_RE | 本周以来最高价(后复权) | 数值类型 | 元 |
| LOW_PRICE_TW_RE | 本周以来最低价(后复权) | 数值类型 | 元 |
| HIGH_PRICE_TM | 本月以来最高价 | 数值类型 | 元 |
| LOW_PRICE_TM | 本月以来最低价 | 数值类型 | 元 |
| HIGH_PRICE_TM_RE | 本月以来最高价(后复权) | 数值类型 | 元 |
| LOW_PRICE_TM_RE | 本月以来最低价(后复权) | 数值类型 | 元 |
| HIGH_PRICE_TY | 本年以来最高价 | 数值类型 | 元 |
| LOW_PRICE_TY | 本年以来最低价 | 数值类型 | 元 |
| HIGH_PRICE_TY_RE | 本年以来最高价(后复权) | 数值类型 | 元 |
| LOW_PRICE_TY_RE | 本年以来最低价(后复权) | 数值类型 | 元 |
| HIGH_PRICE_FL | 上市以来最高价 | 数值类型 | 元 |
| LOW_PRICE_FL | 上市以来最低价 | 数值类型 | 元 |
| HIGH_PRICE_FL_RE | 上市以来最高价(后复权) | 数值类型 | 元 |
| LOW_PRICE_FL_RE | 上市以来最低价(后复权) | 数值类型 | 元 |


