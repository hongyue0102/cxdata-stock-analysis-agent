# 股票复权因子-通用 (getDStkReweighFactByCond-G)

**API_ID:** getDStkReweighFactByCond-G

#### 输入参数

| 参数名 | 参数中文名 | 数据类型 | 是否必填 | 默认值 |
|--------|------------|----------|----------|----------|
| stkCode | 股票代码 | 字符类型 | 否 |  |
| stkShortName | 股票简称 | 字符类型 | 否 |  |
| exrightDate | 除权除息日 | 日期类型 | 否 |  |
| pageNum | 页码 | Integer | 是 | 1 |
| pageSize | 每页条数 | Integer | 是 | 20 |

#### 输出参数

| 参数名 | 参数中文名 | 数据类型 |
|--------|------------|----------|
| STK_CODE | 股票代码 | 字符类型 |
| STK_SHORT_NAME | 股票简称 | 字符类型 |
| EXRIGHT_DATE | 除权除息日 | 日期类型 |
| RIGHT_REG_DATE | 股权登记日 | 日期类型 |
| CLOSE_PRICE | 股权登记日收盘价 | 数值类型 |
| DIV_TAX | 每股/份派现 | 数值类型 |
| BONUS_RATIO | 每股/份送红股 | 数值类型 |
| TRAN_ADD_RATI | 每股/份转增股 | 数值类型 |
| ATCU_PLACE_RATIO | 每股/份配股 | 数值类型 |
| PLACE_PRICE | 每股配股价格 | 数值类型 |
| THIS_REWEIGH_FACT | 本次复权因子 | 数值类型 |
| CUML_REWEIGH_FACT | 累计复权因子 | 数值类型 |


