# 行业市值权重-通用 (getInduValueWeightByCond-G)

**API_ID:** getInduValueWeightByCond-G

#### 输入参数

| 参数名 | 参数中文名 | 数据类型 | 是否必填 | 默认值 | 示例值 |
|--------|------------|----------|----------|----------|----------|
| induUniCode | 行业统一编码 | 数值类型 | 否 |  | 401309642 |
| induClassName | 行业分类名称 | 字符类型 | 否 |  | 消费电子 |
| endDate | 截止日期 | 日期类型(yyyy-MM-dd) | 否 |  | 2026-04-09 |
| pageNum | 页码 | Integer | 是 | 1 |  |
| pageSize | 每页条数 | Integer | 否 |  |  |

#### 输出参数

| 参数名 | 参数中文名 | 数据类型 | 单位 |
|--------|------------|----------|----------|
| INDU_UNI_CODE | 行业统一编码 | 数值类型 |  |
| INDU_CLASS_NAME | 行业分类名称 | 字符类型 |  |
| INDU_SYS_PAR | 行业分类体系参数 | 数值类型 |  |
| INDU_LEVEL | 行业级别 | 字符类型 |  |
| END_DATE | 截止日期 | 日期类型 |  |
| INDU_VALUE | 行业总市值 | 数值类型 | 元 |
| INDU_WEIGHT | 行业权重 | 数值类型 | % |


