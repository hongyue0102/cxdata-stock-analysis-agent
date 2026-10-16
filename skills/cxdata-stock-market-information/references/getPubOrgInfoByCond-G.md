# 机构基本信息-通用 (getPubOrgInfoByCond-G)

**API_ID:** getPubOrgInfoByCond-G

#### 输入参数

| 参数名 | 参数中文名 | 数据类型 | 是否必填 | 默认值 | 示例值 |
|--------|------------|----------|----------|----------|----------|
| orgUniCode | 机构统一编码 | 数值类型 | 否 |  | 200000006 |
| orgChiName | 机构中文名称 | 字符类型 | 否 |  | 南京栖霞建设股份有限公司 |
| regAddr | 注册地址 | 字符类型 | 否 |  | 江苏省南京市栖霞区仙林大道99号8幢 |
| areaUniCode | 注册地所属区域 | 数值类型 | 否 |  | 401202235 |
| orgEstDate | 机构成立日期 | 字符类型 | 否 |  | 1999-12-23 |
| uniSocCreCode | 统一社会信用代码 | 字符类型 | 否 |  | 91320100721702184R |
| pareComCode | 母公司码 | 数值类型 | 否 |  | 200037422 |
| topOrgCode | 顶级机构代码 | 数值类型 | 否 |  | 200040425 |
| highLevelOrgCode | 上一级机构代码 | 数值类型 | 否 |  | 200036567 |
| orgDeleCode | 企业代表编码 | 数值类型 | 否 |  | 301068521 |
| induSmaPar | 行业分类 | 字符类型 | 否 |  | 房地产开发经营 |
| induUniCode | 行业统一编码 | 数值类型 | 否 |  | 401308447 |
| pageNum | 页码 | Integer | 是 | 1 |  |
| pageSize | 每页条数 | Integer | 否 |  |  |

#### 输出参数

| 参数名 | 参数中文名 | 数据类型 | 单位 |
|--------|------------|----------|----------|
| ORG_CHI_NAME | 机构中文名称 | 字符类型 |  |
| CHI_SHORT_NAME | 机构中文简称 | 字符类型 |  |
| ORG_ENG_NAME | 机构英文名称 | 字符类型 |  |
| ENG_SHORT_NAME | 机构英文简称 | 字符类型 |  |
| CHI_SPE_SHORT_NAME | 机构拼音简称 | 字符类型 |  |
| ORG_NAME_HIST | 机构曾用名 | 字符类型 |  |
| REG_CAP | 注册资本 | 数值类型 | 万元 |
| CURY_TYPE_PAR | 货币类型 | 数值类型 |  |
| AREA_CHI_SHORT_NAME1 | 注册地所属省/直辖市 | 字符类型 |  |
| AREA_CHI_SHORT_NAME2 | 注册地所在市/区 | 字符类型 |  |
| REG_ADDR | 注册地址 | 字符类型 |  |
| AREA_UNI_CODE | 注册地所属区域 | 数值类型 |  |
| OFFI_ADDR | 办公地址 | 字符类型 |  |
| POST_CODE | 办公地邮政编码 | 字符类型 |  |
| COM_WEB | 公司网址 | 字符类型 |  |
| LEG_PER | 法人代表 | 字符类型 |  |
| GEN_MAN | 总经理 | 字符类型 |  |
| ORG_CON_PER | 机构联系人 | 字符类型 |  |
| ORG_TEL | 机构电话 | 字符类型 |  |
| ORG_FAX | 机构传真 | 字符类型 |  |
| ORG_MAIL_ADDR | 机构电子邮件地址 | 字符类型 |  |
| ORG_EST_DATE | 机构成立日期 | 字符类型 |  |
| CUS_CON_TEL | 客服联系电话 | 字符类型 |  |
| ORG_STA_PAR | 机构存续状态 | 数值类型 |  |
| UNI_SOC_CRE_CODE | 统一社会信用代码 | 字符类型 |  |
| IC_REG_CODE | 工商登记号 | 字符类型 |  |
| ORG_CLA_BIG_PAR | 机构类型大类 | 数值类型 |  |
| ORG_CLA_MID_PAR | 机构类型中类 | 数值类型 |  |
| ORG_CLA_SMA_PAR | 机构类型小类 | 数值类型 |  |
| ORG_ORGA_FORM_PAR | 企业组织形式 | 数值类型 |  |
| PARE_COM_CODE | 母公司码 | 数值类型 |  |
| TOP_ORG_CODE | 顶级机构代码 | 数值类型 |  |
| HIGH_LEVEL_ORG_CODE | 上一级机构代码 | 数值类型 |  |
| ORG_ABBR | 机构简介 | 字符类型 |  |
| ORG_SID_BUSI | 机构兼营业务 | 字符类型 |  |
| DIS_DATE | 解散日期 | 日期类型 |  |
| DIS_REAS | 解散原因 | 字符类型 |  |
| ORG_LIST_PAR | 机构上市状态 | 数值类型 |  |
| IF_ISS_BOND | 是否发行债券 | 数值类型 |  |
| LIST_MKT | 上市地点 | 数值类型 |  |
| ORG_ATTR_PAR | 企业性质参数 | 数值类型 |  |
| TECH_NUM | 技术人员数量 | 数值类型 | 人 |
| STAFF_SUM | 员工总数 | 数值类型 | 人 |
| MAN_NUM | 管理人员数量 | 数值类型 | 人 |
| IF_ISS_PUB_FUND | 是否发行公募基金 | 数值类型 |  |
| PERMIT_DATE | 核准日期 | 字符类型 |  |
| ORG_CLA_PAR | 企业类型 | 字符类型 |  |
| ORG_DELE | 企业代表 | 字符类型 |  |
| ORG_DELE_CODE | 企业代表编码 | 数值类型 |  |
| ORG_DELE_PAR | 企业代表类型参数 | 数值类型 |  |
| OPER_COND | 经营状态 | 字符类型 |  |
| INDU_SMA_PAR | 行业分类 | 字符类型 |  |
| OPER_STA_DATE | 经营期限自 | 字符类型 |  |
| OPER_END_DATE | 经营期限至 | 字符类型 |  |
| REG_AUTH | 登记机关 | 字符类型 |  |
| ORG_CODE | 组织机构代码 | 字符类型 |  |
| INDU_UNI_CODE | 行业统一编码 | 数值类型 |  |
| ORG_UNI_CODE | 机构编码 | 字符类型 |  |


