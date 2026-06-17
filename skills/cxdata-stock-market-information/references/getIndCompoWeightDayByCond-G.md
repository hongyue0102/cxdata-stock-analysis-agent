# 股票指数成分股每日权重-通用 (getIndCompoWeightDayByCond-G)

**API_ID:** getIndCompoWeightDayByCond-G

#### 输入参数

| 参数名 | 参数中文名 | 数据类型 | 是否必填 | 默认值 |
|--------|------------|----------|----------|----------|
| indId | 指数标识 | 数值类型 | 否 |  |
| secUniCode | 证券统一编码 | 数值类型 | 否 |  |
| tradeDate | 交易日 | 日期类型(yyyy-MM-dd) | 否 |  |
| pageNum | 页码 | Integer | 是 | 1 |
| pageSize | 每页条数 | Integer | 是 | 20 |

#### 输出参数

| 参数名 | 参数中文名 | 数据类型 |
|--------|------------|----------|
| IND_ID | 指数标识 | 数值类型 |
| SEC_UNI_CODE | 证券统一编码 | 数值类型 |
| TRADE_DATE | 交易日 | 日期类型 |
| WEIGHT_DAY | 每日权重 | 数值类型 |

#### 直接前置依赖
以下参数存在可参考的直接前置接口。是否调用前置接口，取决于当前查询目标、已知条件以及当前接口入参是否已满足。
- 参数 `indId`：可通过调用 **指数信息表-通用（API_ID:getDIndInfoByCond-G）** 获取
- 参数 `secUniCode`：可通过调用 **证券基本信息-通用（API_ID:getPubSecCodeByCond-G）** 获取

#### 多流程依赖说明
当当前接口的关键入参存在多种补齐方式时，可按以下流程逐级调用，不要预先串行调用所有上游接口。
##### 流程1（补齐参数 `indId`）
1. 调用 **指数信息表-通用（API_ID:getDIndInfoByCond-G）**，补齐后续所需参数 `indId`
2. 调用 **股票指数成分股每日权重-通用（API_ID:getIndCompoWeightDayByCond-G）**，完成当前查询

##### 流程2（补齐参数 `secUniCode`）
1. 调用 **证券基本信息-通用（API_ID:getPubSecCodeByCond-G）**，补齐后续所需参数 `secUniCode`
2. 调用 **股票指数成分股每日权重-通用（API_ID:getIndCompoWeightDayByCond-G）**，完成当前查询

