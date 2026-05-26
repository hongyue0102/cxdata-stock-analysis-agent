# 股票涨跌幅信息-通用 (getDStkRiseDropByCond-G)

**API_ID:** getDStkRiseDropByCond-G

#### 输入参数

| 参数名 | 参数中文名 | 数据类型 | 是否必填 | 默认值 |
|--------|------------|----------|----------|----------|
| stkCode | 股票代码 | 字符类型 | 否 |  |
| stkShortName | 股票简称 | 字符类型 | 否 |  |
| endDate | 截止日期 | 日期类型 | 否 |  |
| pageNum | 页码 | Integer | 是 | 1 |
| pageSize | 每页条数 | Integer | 是 | 20 |

#### 输出参数

| 参数名 | 参数中文名 | 数据类型 |
|--------|------------|----------|
| STK_CODE | 股票代码 | 字符类型 |
| STK_SHORT_NAME | 股票简称 | 字符类型 |
| END_DATE | 截止日期 | 日期类型 |
| RISE_DROP | 涨跌（不复权） | 数值类型 |
| RISE_DROP_RANGE | 涨跌幅（不复权） | 数值类型 |
| RISE_DROP_RE | 涨跌（后复权） | 数值类型 |
| RISE_DROP_RANGE_RE | 涨跌幅（后复权） | 数值类型 |
| RISE_DROP_RANGE_1W | 近1周涨跌幅（后复权） | 数值类型 |
| RISE_DROP_RANGE_1M | 近1月涨跌幅（后复权） | 数值类型 |
| RISE_DROP_RANGE_3M | 近3月涨跌幅（后复权） | 数值类型 |
| RISE_DROP_RANGE_6M | 近6月涨跌幅（后复权） | 数值类型 |
| RISE_DROP_RANGE_1Y | 近1年涨跌幅（后复权） | 数值类型 |
| RISE_DROP_RANGE_3Y | 近3年涨跌幅（后复权） | 数值类型 |
| RISE_DROP_RANGE_5Y | 近5年涨跌幅（后复权） | 数值类型 |
| RISE_DROP_RANGE_TY | 今年以来涨跌幅（后复权） | 数值类型 |
| RISE_DROP_RANGE_FL | 上市至今涨跌幅（后复权） | 数值类型 |
| D_RISE_DROP_3M | 近3月日均涨跌幅（后复权） | 数值类型 |
| RISE_DROP_RANGE_TW | 本周以来涨跌幅（后复权） | 数值类型 |
| RISE_DROP_RANGE_TM | 本月以来涨跌幅（后复权） | 数值类型 |
| RISE_DROP_ISS | 相对发行价涨跌（不复权） | 数值类型 |
| RISE_DROP_RANGE_ISS | 相对发行价涨跌幅（不复权） | 数值类型 |
| RISE_DROP_ISS_RE | 相对发行价涨跌（后复权） | 数值类型 |
| RISE_RANGE_ISS_RE | 相对发行价涨跌幅（后复权） | 数值类型 |
| ANNA_YIELD_24M | 年化收益率(近2年) | 数值类型 |
| ANNA_YIELD_60M | 年化收益率(近5年) | 数值类型 |
| ANNA_YIELD_100W | 年化收益率(近100周) | 数值类型 |
| RISE_DROP_RANGE_1W_NRE | 近1周涨跌幅（不复权） | 数值类型 |
| RISE_DROP_RANGE_1M_NRE | 近1月涨跌幅（不复权） | 数值类型 |
| RISE_DROP_RANGE_3M_NRE | 近3月涨跌幅（不复权） | 数值类型 |
| RISE_DROP_RANGE_6M_NRE | 近6月涨跌幅（不复权） | 数值类型 |
| RISE_DROP_RANGE_1Y_NRE | 近1年涨跌幅（不复权） | 数值类型 |
| RISE_DROP_RANGE_3Y_NRE | 近3年涨跌幅（不复权） | 数值类型 |
| RISE_DROP_RANGE_5Y_NRE | 近5年涨跌幅（不复权） | 数值类型 |
| RISE_DROP_RANGE_TY_NRE | 今年以来涨跌幅（不复权） | 数值类型 |
| RISE_DROP_RANGE_FL_NRE | 上市至今涨跌幅（不复权） | 数值类型 |
| D_RISE_DROP_3M_NRE | 近3月日均涨跌幅（不复权） | 数值类型 |
| RISE_DROP_RANGE_TW_NRE | 本周以来涨跌幅（不复权） | 数值类型 |
| RISE_DROP_RANGE_TM_NRE | 本月以来涨跌幅（不复权） | 数值类型 |
| ANNA_YIELD_3Y | 年化收益率(近3年) | 数值类型 |
| ANNA_YIELD_10Y | 年化收益率(近10年) | 数值类型 |


