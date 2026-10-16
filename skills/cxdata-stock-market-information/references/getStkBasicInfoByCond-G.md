# 股票基本信息-通用 (getStkBasicInfoByCond-G)

**API_ID:** getStkBasicInfoByCond-G

#### 输入参数

| 参数名 | 参数中文名 | 数据类型 | 是否必填 | 默认值 | 示例值 |
|--------|------------|----------|----------|----------|----------|
| stkUniCode | 股票统一编码 | 数值类型 | 否 |  | 101000223 |
| stkCode | 股票代码 | 字符类型 | 否 |  | 000029 |
| stkShortName | 股票简称 | 字符类型 | 否 |  | 深深房A |
| stkTypePar | 股票类型 | 数值类型 | 否 |  | 101 |
| stkUniCode1 | 同公司A/B股统一编码 | 数值类型 | 否 |  | 101002140 |
| comUniCode | 公司统一编码 | 数值类型 | 否 |  | 200013841 |
| listDate | 上市日期 | 日期类型(yyyy-MM-dd) | 否 |  | 1993-09-15 |
| secMarPar | 证券市场 | 数值类型 | 否 |  | 1 |
| listSectPar | 上市板块 | 数值类型 | 否 |  | 1 |
| listStaPar | 上市状态 | 数值类型 | 否 |  | 1 |
| chanDate | 变更日期 | 日期类型(yyyy-MM-dd) | 否 |  | 2020-01-08 |
| delistDate | 退市日期 | 日期类型(yyyy-MM-dd) | 否 |  | 2020-01-08 |
| pageNum | 页码 | Integer | 是 | 1 |  |
| pageSize | 每页条数 | Integer | 否 |  |  |

#### 输出参数

| 参数名 | 参数中文名 | 数据类型 | 单位 |
|--------|------------|----------|----------|
| STK_UNI_CODE | 股票统一编码 | 数值类型 |  |
| STK_CODE | 股票代码 | 字符类型 |  |
| STK_SHORT_NAME | 股票简称 | 字符类型 |  |
| SPE_SHORT_NAME | 股票拼音简称 | 字符类型 |  |
| STK_TYPE_PAR | 股票类型 | 数值类型 |  |
| STK_UNI_CODE1 | 同公司A/B股统一编码 | 数值类型 |  |
| COM_UNI_CODE | 公司统一编码 | 数值类型 |  |
| PAR_VAL | 股票面值 | 数值类型 | 元 |
| LIST_DATE | 上市日期 | 日期类型 |  |
| SEC_MAR_PAR | 证券市场 | 数值类型 |  |
| LIST_SECT_PAR | 上市板块 | 数值类型 |  |
| LIST_STA_PAR | 上市状态 | 数值类型 |  |
| ISIN_CODE | ISIN码 | 字符类型 |  |
| CURY_TYPE_PAR | 货币类型 | 数值类型 |  |
| STK_CODE1 | 变更前或转板前股票代码 | 字符类型 |  |
| CHAN_DATE | 变更日期 | 日期类型 |  |
| CHAN_REAS_PAR | 变更原因 | 数值类型 |  |
| DELIST_DATE | 退市日期 | 日期类型 |  |
| STK_SHORT_NAME_EX | 股票扩位简称 | 字符类型 |  |

#### 直接前置依赖
以下参数存在可参考的直接前置接口。是否调用前置接口，取决于当前查询目标、已知条件以及当前接口入参是否已满足。
- 参数 `stkUniCode1`：可通过调用 **股票基本信息-批量（API_ID:getStkBasicInfoByCond-P）** 获取
- 参数 `stkUniCode1`：可通过调用 **股票基本信息-通用（API_ID:getStkBasicInfoByCond-G）** 获取
- 参数 `comUniCode`：可通过调用 **机构基本信息-ES（API_ID:getPubOrgInfoByCond-ES）** 获取
- 参数 `comUniCode`：可通过调用 **机构基本信息-通用（API_ID:getPubOrgInfoByCond-G）** 获取

#### 多流程依赖说明
当当前接口的关键入参存在多种补齐方式时，可按以下流程逐级调用，不要预先串行调用所有上游接口。
##### 流程1（补齐参数 `stkUniCode1`）
1. 调用 **股票基本信息-批量（API_ID:getStkBasicInfoByCond-P）**，补齐后续所需参数 `stkUniCode1`
2. 调用 **股票基本信息-通用（API_ID:getStkBasicInfoByCond-G）**，完成当前查询

##### 流程2（补齐参数 `comUniCode`）
1. 调用 **机构基本信息-ES（API_ID:getPubOrgInfoByCond-ES）**，补齐后续所需参数 `comUniCode`
2. 调用 **股票基本信息-通用（API_ID:getStkBasicInfoByCond-G）**，完成当前查询

##### 流程3（补齐参数 `comUniCode`）
1. 调用 **机构基本信息-通用（API_ID:getPubOrgInfoByCond-G）**，补齐后续所需参数 `comUniCode`
2. 调用 **股票基本信息-通用（API_ID:getStkBasicInfoByCond-G）**，完成当前查询

