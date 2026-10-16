# 股票复权因子-通用 (getDStkReweighFactByCond-G)

**API_ID:** getDStkReweighFactByCond-G

#### 输入参数

| 参数名 | 参数中文名 | 数据类型 | 是否必填 | 默认值 | 示例值 |
|--------|------------|----------|----------|----------|----------|
| stkUniCode | 股票统一编码 | 数值类型 | 否 |  | 101000020 |
| stkCode | 股票代码 | 字符类型 | 否 |  | 002070 |
| stkShortName | 股票简称 | 字符类型 | 否 |  | 智度股份 |
| exrightDate | 除权除息日 | 日期类型(yyyy-MM-dd) | 否 |  | 1998-04-23 |
| pageNum | 页码 | Integer | 是 | 1 |  |
| pageSize | 每页条数 | Integer | 否 |  |  |

#### 输出参数

| 参数名 | 参数中文名 | 数据类型 | 单位 |
|--------|------------|----------|----------|
| STK_UNI_CODE | 股票统一编码 | 数值类型 |  |
| STK_CODE | 股票代码 | 字符类型 |  |
| STK_SHORT_NAME | 股票简称 | 字符类型 |  |
| EXRIGHT_DATE | 除权除息日 | 日期类型 |  |
| THIS_REWEIGH_FACT | 本次复权因子 | 数值类型 |  |
| CUML_REWEIGH_FACT | 累计复权因子 | 数值类型 |  |


