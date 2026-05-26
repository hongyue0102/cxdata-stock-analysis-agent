# 交易所日公开信息明细-通用 (getStatTradeDateSubByCond-G)

**API_ID:** getStatTradeDateSubByCond-G

#### 输入参数

| 参数名 | 参数中文名 | 数据类型 | 是否必填 | 默认值 |
|--------|------------|----------|----------|----------|
| subId | 子表关联标识 | 数值类型 | 否 |  |
| orgChiName | 营业部名称 | 字符类型 | 否 |  |
| pageNum | 页码 | Integer | 是 | 1 |
| pageSize | 每页条数 | Integer | 是 | 20 |

#### 输出参数

| 参数名 | 参数中文名 | 数据类型 |
|--------|------------|----------|
| SUB_ID | 子表关联标识 | 数值类型 |
| TRADE_METH | 营业部交易方式 | 数值类型 |
| TRADE_RANK | 交易金额排名 | 数值类型 |
| ORG_CHI_NAME | 营业部名称 | 字符类型 |
| ACCUM_TRADE | 买卖合计金额 | 数值类型 |
| BUY_AMUT | 买入金额 | 数值类型 |
| SALE_AMUT | 卖出金额 | 数值类型 |

#### 直接前置依赖
以下参数存在可参考的直接前置接口。是否调用前置接口，取决于当前查询目标、已知条件以及当前接口入参是否已满足。
- 参数 `subId`：可通过调用 **交易所股票日交易信息-通用（API_ID:getStatTradeDateMainByCond-G）** 获取

#### 多流程依赖说明
当当前接口的关键入参存在多种补齐方式时，可按以下流程逐级调用，不要预先串行调用所有上游接口。
##### 流程1（补齐参数 `subId`）
1. 调用 **交易所股票日交易信息-通用（API_ID:getStatTradeDateMainByCond-G）**，补齐后续所需参数 `subId`
2. 调用 **交易所日公开信息明细-通用（API_ID:getStatTradeDateSubByCond-G）**，完成当前查询

