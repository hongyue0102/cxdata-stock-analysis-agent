# 股票特别提示主表-通用 (getStkSpeTipsMainByCond-G)

**API_ID:** getStkSpeTipsMainByCond-G

#### 输入参数

| 参数名 | 参数中文名 | 数据类型 | 是否必填 | 默认值 |
|--------|------------|----------|----------|----------|
| secUniCode | 证券统一编码 | 数值类型 | 否 |  |
| pageNum | 页码 | Integer | 是 | 1 |
| pageSize | 每页条数 | Integer | 是 | 20 |

#### 输出参数

| 参数名 | 参数中文名 | 数据类型 |
|--------|------------|----------|
| SEC_UNI_CODE | 证券统一编码 | 数值类型 |
| PUBL_DATE | 发布日期 | 日期类型 |
| SPE_TIPS_CONTE | 特别提示内容 | 字符类型 |
| EVENT_START_DATE | 事件起始日期 | 日期类型 |
| EVENT_END_DATE | 事件截止日期 | 日期类型 |
| SUSP_MATU_PAR | 停牌期限 | 数值类型 |
| SPE_TIPS_CLASS_CODE | 特别提示分类代码 | 数值类型 |

#### 直接前置依赖
以下参数存在可参考的直接前置接口。是否调用前置接口，取决于当前查询目标、已知条件以及当前接口入参是否已满足。
- 参数 `secUniCode`：可通过调用 **股票基本信息-通用（API_ID:getStkBasicInfoByCond-G）** 获取

#### 多流程依赖说明
当当前接口的关键入参存在多种补齐方式时，可按以下流程逐级调用，不要预先串行调用所有上游接口。
##### 流程1（补齐参数 `secUniCode`）
1. 调用 **股票基本信息-通用（API_ID:getStkBasicInfoByCond-G）**，补齐后续所需参数 `secUniCode`
2. 调用 **股票特别提示主表-通用（API_ID:getStkSpeTipsMainByCond-G）**，完成当前查询

