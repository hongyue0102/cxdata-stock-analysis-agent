# 股票行情技术指标表-通用 (getStkDayQuoTrendByCond-G)

**API_ID:** getStkDayQuoTrendByCond-G

#### 输入参数

| 参数名 | 参数中文名 | 数据类型 | 是否必填 | 默认值 | 示例值 |
|--------|------------|----------|----------|----------|----------|
| stkUniCode | 股票统一编码 | 数值类型 | 否 |  | 101000364 |
| stkCode | 股票代码 | 字符类型 | 否 |  | 002221 |
| stkShortName | 股票简称 | 字符类型 | 否 |  | 东华能源 |
| tradeDate | 交易日期 | 日期类型(yyyy-MM-dd) | 否 |  | 2026-09-28 |
| restTypePar | 复权类型参数 | 数值类型 | 否 |  | 1 |
| isTradeHalt | 是否计算停牌 | 数值类型 | 否 |  | 1 |
| rvol | 量比 | 数值类型 | 否 |  | 1.1020 |
| limitUpDays | 连续涨停次数 | 数值类型 | 否 |  | 0 |
| upDays | 连续上涨天数 | 数值类型 | 否 |  | 0 |
| pageNum | 页码 | Integer | 是 | 1 |  |
| pageSize | 每页条数 | Integer | 否 |  |  |

#### 输出参数

| 参数名 | 参数中文名 | 数据类型 | 单位 |
|--------|------------|----------|----------|
| STK_UNI_CODE | 股票统一编码 | 数值类型 |  |
| STK_CODE | 股票代码 | 字符类型 |  |
| STK_SHORT_NAME | 股票简称 | 字符类型 |  |
| TRADE_DATE | 数据日期 | 日期类型 |  |
| REST_TYPE_PAR | 复权类型参数 | 数值类型 | 元 |
| IS_TRADE_HALT | 是否计算停牌 | 数值类型 | 元 |
| RVOL | 量比 | 数值类型 | 元 |
| RETURN_1W | 近一周涨幅 | 数值类型 | 元 |
| UP_DAYS | 连续上涨天数 | 数值类型 | 元 |
| LIMIT_UP_DAYS_1W | 近一周涨停次数 | 数值类型 | 元 |
| LIMIT_UP_DAYS | 连续涨停次数 | 数值类型 | 股/份 |
| PSY_12 | PSY_12 | 数值类型 | % |
| MA_5 | MA_5 | 数值类型 |  |
| MA_6 | 	MA_6 | 数值类型 | 股/份 |
| MA_10 | MA_10 | 数值类型 | 元 |
| MA_12 | MA_12 | 数值类型 |  |
| MA_20 | MA_20 | 数值类型 |  |
| MA_24 | MA_24 | 数值类型 |  |
| MA_60 | MA_60 | 数值类型 |  |
| MA_120 | MA_120 | 数值类型 |  |
| MA_250 | MA_250 | 数值类型 |  |
| MTM_6 | MTM_6 | 数值类型 |  |
| MTMMA_12 | MTMMA_12 | 数值类型 |  |
| KDJ_RSV | KDJ_RSV | 数值类型 |  |
| KDJ_K | KDJ_K | 数值类型 |  |
| KDJ_D | KDJ_D | 数值类型 |  |
| KDJ_J | KDJ_J | 数值类型 |  |
| BIAS_6 | BIAS_6 | 数值类型 |  |
| BIAS_12 | BIAS_12 | 数值类型 |  |
| BIAS_24 | BIAS_24 | 数值类型 |  |
| EMA_12 | EMA_12 | 数值类型 |  |
| EMA_26 | EMA_26 | 数值类型 |  |
| DIF | DIF | 数值类型 |  |
| DEA | DEA | 数值类型 |  |
| MACD_PRE | MACD_PRE | 数值类型 |  |
| RSI_6 | RSI_6 | 数值类型 |  |
| RSI_12 | RSI_12 | 数值类型 |  |
| RSI_24 | RSI_24 | 数值类型 |  |
| EMA_UP_6 | EMA_UP_6 | 数值类型 |  |
| EMA_DOWN_6 | EMA_DOWN_6 | 数值类型 |  |
| EMA_UP_12 | EMA_UP_12 | 数值类型 |  |
| EMA_DOWN_12 | EMA_DOWN_12 | 数值类型 |  |
| EMA_UP_24 | EMA_UP_24 | 数值类型 |  |
| EMA_DOWN_24 | EMA_DOWN_24 | 数值类型 |  |
| BOLL_MD | BOLL标准差 | 数值类型 |  |
| BOLL_UP | BOLL上轨 | 数值类型 |  |
| BOLL_MB | BOLL中轨 | 数值类型 |  |
| BOLL_DN | BOLL下轨 | 数值类型 |  |
| BOLL_BAND | BOLL带宽 | 数值类型 |  |


