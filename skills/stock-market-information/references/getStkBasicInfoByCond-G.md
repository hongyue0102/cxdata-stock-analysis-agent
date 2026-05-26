# 股票基本信息-通用 (getStkBasicInfoByCond-G)

**API_ID:** getStkBasicInfoByCond-G

#### 输入参数

| 参数名 | 参数中文名 | 数据类型 | 是否必填 | 默认值 |
|--------|------------|----------|----------|----------|
| stkCode | 股票代码 | 字符类型 | 否 |  |
| stkShortName | 股票简称 | 字符类型 | 否 |  |
| stkTypePar | 股票类型 | 数值类型 | 否 |  |
| stkUniCode1 | 同公司A/B股统一编码 | 数值类型 | 否 |  |
| listDate | 上市日期 | 日期类型 | 否 |  |
| secMarPar | 证券市场 | 数值类型 | 否 |  |
| listSectPar | 上市板块 | 数值类型 | 否 |  |
| listStaPar | 上市状态 | 数值类型 | 否 |  |
| chanDate | 变更日期 | 日期类型 | 否 |  |
| delistDate | 退市日期 | 日期类型 | 否 |  |
| pageNum | 页码 | Integer | 是 | 1 |
| pageSize | 每页条数 | Integer | 是 | 20 |

#### 输出参数

| 参数名 | 参数中文名 | 数据类型 |
|--------|------------|----------|
| STK_CODE | 股票代码 | 字符类型 |
| STK_SHORT_NAME | 股票简称 | 字符类型 |
| SPE_SHORT_NAME | 股票拼音简称 | 字符类型 |
| STK_TYPE_PAR | 股票类型 | 数值类型 |
| STK_UNI_CODE1 | 同公司A/B股统一编码 | 数值类型 |
| COM_UNI_CODE | 公司统一编码 | 数值类型 |
| PAR_VAL | 股票面值 | 数值类型 |
| LIST_DATE | 上市日期 | 日期类型 |
| SEC_MAR_PAR | 证券市场 | 数值类型 |
| LIST_SECT_PAR | 上市板块 | 数值类型 |
| LIST_STA_PAR | 上市状态 | 数值类型 |
| ISIN_CODE | ISIN码 | 字符类型 |
| CURY_TYPE_PAR | 货币类型 | 数值类型 |
| STK_CODE1 | 变更前或转板前股票代码 | 字符类型 |
| CHAN_DATE | 变更日期 | 日期类型 |
| CHAN_REAS_PAR | 变更原因 | 数值类型 |
| DELIST_DATE | 退市日期 | 日期类型 |

#### 直接前置依赖
以下参数存在可参考的直接前置接口。是否调用前置接口，取决于当前查询目标、已知条件以及当前接口入参是否已满足。
- 参数 `stkUniCode1`：可通过调用 **股票基本信息-通用（API_ID:getStkBasicInfoByCond-G）** 获取

