# 证券基本信息-通用 (getPubSecCodeByCond-G)

**API_ID:** getPubSecCodeByCond-G

#### 输入参数

| 参数名 | 参数中文名 | 数据类型 | 是否必填 | 默认值 |
|--------|------------|----------|----------|----------|
| secUniCode | 证券统一编码 | 数值类型 | 否 |  |
| marCode | 证券代码 | 字符类型 | 否 |  |
| secShortName | 证券简称 | 字符类型 | 否 |  |
| secFullName | 证券全称 | 字符类型 | 否 |  |
| engName | 英文名称 | 字符类型 | 否 |  |
| pageNum | 页码 | Integer | 是 | 1 |
| pageSize | 每页条数 | Integer | 是 | 20 |

#### 输出参数

| 参数名 | 参数中文名 | 数据类型 |
|--------|------------|----------|
| MAR_CODE | 证券代码 | 字符类型 |
| SEC_SHORT_NAME | 证券简称 | 字符类型 |
| SPE_SHORT_NAME | 证券拼音简称 | 字符类型 |
| SEC_FULL_NAME | 证券全称 | 字符类型 |
| ENG_NAME | 英文名称 | 字符类型 |
| ENG_SHORT_NAME | 英文名称缩写 | 字符类型 |
| COM_UNI_CODE | 公司代码 | 数值类型 |
| SEC_TYPE_BIG_PAR | 证券大类型 | 数值类型 |
| SEC_TYPE_SUBD_PAR | 证券细分类型 | 数值类型 |
| SEC_MAR_PAR | 证券市场 | 数值类型 |
| AREA_UNI_CODE | 证券市场所属国家/地区 | 数值类型 |
| LIST_DATE | 上市日期 | 日期类型 |
| QUIT_DATE | 退市日期 | 日期类型 |
| LIST_STA_PAR | 上市状态 | 数值类型 |
| LIST_SECT_PAR | 上市板块 | 数值类型 |
| ISIN_CODE | ISIN代码 | 字符类型 |


