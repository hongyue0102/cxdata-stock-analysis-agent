# 股票市场热度-通用 (getStkHotMarketByCond-G)

**API_ID:** getStkHotMarketByCond-G

#### 输入参数

| 参数名 | 参数中文名 | 数据类型 | 是否必填 | 默认值 |
|--------|------------|----------|----------|----------|
| endDate | 截止日期 | 日期类型(yyyy-MM-dd) | 否 |  |
| pageNum | 页码 | Integer | 是 | 1 |
| pageSize | 每页条数 | Integer | 是 | 20 |

#### 输出参数

| 参数名 | 参数中文名 | 数据类型 |
|--------|------------|----------|
| END_DATE | 截止日期 | 日期类型 |
| PE_MID | 市盈率中位值 | 数值类型 |
| PE_NUM | 市盈率中位值历史排序 | 数值类型 |
| PE_PER | 市盈率中位值历史百分位 | 数值类型 |
| PE_INDEX | 估值温度参数 | 数值类型 |
| UP_NUM_PER | 上涨家数占比 | 数值类型 |
| UP_PER | 上涨家数占比历史排序 | 数值类型 |
| UP_DOWN_PER | 上涨家数历史百分位 | 数值类型 |
| UP_DOWN_INDEX | 情绪温度参数 | 数值类型 |
| HOT_INDEX | 市场温度指数 | 数值类型 |
| HOT_INDEX_COS | 市场温度评语 | 数值类型 |


