# 股票指数市场表现-通用 (getIndMarPerf1ByCond-G)

**API_ID:** getIndMarPerf1ByCond-G

#### 输入参数

| 参数名 | 参数中文名 | 数据类型 | 是否必填 | 默认值 |
|--------|------------|----------|----------|----------|
| tradeDate | 交易日期 | 日期类型(yyyy-MM-dd) | 否 |  |
| indCode | 股票指数代码 | 字符类型 | 否 |  |
| indShortName | 股票指数简称 | 字符类型 | 否 |  |
| pageNum | 页码 | Integer | 是 | 1 |
| pageSize | 每页条数 | Integer | 是 | 20 |

#### 输出参数

| 参数名 | 参数中文名 | 数据类型 |
|--------|------------|----------|
| TRADE_DATE | 交易日期 | 日期类型 |
| IND_CODE | 股票指数代码 | 字符类型 |
| IND_SHORT_NAME | 股票指数简称 | 字符类型 |
| IND_TYPE_PAR | 指数类别 | 数值类型 |
| CLOSE_PRICE | 收盘价 | 数值类型 |
| OPEN_PRICE | 开盘价 | 数值类型 |
| HIGH_PRICE | 最高价 | 数值类型 |
| LOW_PRICE | 最低价 | 数值类型 |
| PRE_CLOSE_PRICE | 昨收价 | 数值类型 |
| VIBR_RANGE | 振幅 | 数值类型 |
| AVE_PRICE | 均价 | 数值类型 |
| RISE_DROP | 涨跌 | 数值类型 |
| CHANGE_PCT | 涨跌幅 | 数值类型 |
| TRADE_VOL | 成交量 | 数值类型 |
| TRADE_VOL_CHAN | 成交量变化 | 数值类型 |
| TRADE_VOL_CHAN_RATE | 成交量变化率 | 数值类型 |
| TRADE_AMUT | 成交额 | 数值类型 |
| TRADE_AMUT_CHAN | 成交额变化 | 数值类型 |
| TRADE_AMUT_CHAN_RATE | 成交额变化率 | 数值类型 |
| D_TRADE_AMUT_1M | 近1月日均成交额 | 数值类型 |
| TURNOVER_RATE | 换手率 | 数值类型 |
| D_TURNOVER_RATE_1M | 近1月日均换手率 | 数值类型 |
| HIGH_PRICE_52W | 52周最高价 | 数值类型 |
| LOW_PRICE_52W | 52周最低价 | 数值类型 |
| RISE_DROP_1W | 近1周涨跌 | 数值类型 |
| RISE_DROP_1M | 近1月涨跌 | 数值类型 |
| RISE_DROP_3M | 近3月涨跌 | 数值类型 |
| RISE_DROP_6M | 近6月涨跌 | 数值类型 |
| RISE_DROP_1Y | 近1年涨跌 | 数值类型 |
| RISE_DROP_2Y | 近2年涨跌 | 数值类型 |
| RISE_DROP_3Y | 近3年涨跌 | 数值类型 |
| RISE_DROP_5Y | 近5年涨跌 | 数值类型 |
| RISE_DROP_TW | 本周涨跌 | 数值类型 |
| RISE_DROP_TM | 本月涨跌 | 数值类型 |
| RISE_DROP_TY | 本年涨跌 | 数值类型 |
| RISE_DROP_RANGE_1W | 近1周涨跌幅 | 数值类型 |
| RISE_DROP_RANGE_1M | 近1月涨跌幅 | 数值类型 |
| RISE_DROP_RANGE_3M | 近3月涨跌幅 | 数值类型 |
| RISE_DROP_RANGE_6M | 近6月涨跌幅 | 数值类型 |
| RISE_DROP_RANGE_1Y | 近1年涨跌幅 | 数值类型 |
| RISE_DROP_RANGE_3Y | 近3年涨跌幅 | 数值类型 |
| RISE_DROP_RANGE_5Y | 近5年涨跌幅 | 数值类型 |
| RISE_DROP_RANGE_TW | 本周涨跌幅 | 数值类型 |
| RISE_DROP_RANGE_TM | 本月涨跌幅 | 数值类型 |
| RISE_DROP_RANGE_TY | 本年涨跌幅 | 数值类型 |
| D_RISE_DROP_3M | 近3月日均涨跌幅 | 数值类型 |
| ACCU_RISE_DROP | 累计涨跌(基期) | 数值类型 |
| ACCU_RISE_DROP_RANGE | 累计涨跌幅(基期) | 数值类型 |
| LOG_YIELD | 对数收益率 | 数值类型 |
| ANNA_YIELD_1W | 年化收益率(近1周) | 数值类型 |
| ANNA_YIELD_1M | 年化收益率(近1月) | 数值类型 |
| ANNA_YIELD_3M | 年化收益率(近3月) | 数值类型 |
| ANNA_YIELD_6M | 年化收益率(近6月) | 数值类型 |
| ANNA_YIELD_1Y | 年化收益率(近1年) | 数值类型 |
| ANNA_YIELD_3Y | 年化收益率(近3年) | 数值类型 |
| ANNA_YIELD_5Y | 年化收益率(近5年) | 数值类型 |
| ANNA_YIELD_TW | 年化收益率(本周) | 数值类型 |
| ANNA_YIELD_TM | 年化收益率(本月) | 数值类型 |
| ANNA_VOLA_20D | 年化波动率(近20日) | 数值类型 |
| ANNA_VOLA_60D | 年化波动率(近60日) | 数值类型 |
| ANNA_VOLA_120D | 年化波动率(近120日) | 数值类型 |
| ANNA_VOLA_250D | 年化波动率(近250日) | 数值类型 |
| ANNA_VOLA_RANGE_3M | 近3月波动幅度 | 数值类型 |
| ANNA_YIELD_10Y | 年化收益率(近10年) | 数值类型 |


