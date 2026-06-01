#!/bin/bash
# 获取认证token（可选工具）
# 说明: api_query.py 已自动处理token获取，此脚本仅用于独立查看token
# 用法: ./auth.sh

# 读取.env文件
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "$SCRIPT_DIR/.env" ]; then
    export $(grep -v '^#' "$SCRIPT_DIR/.env" | xargs)
fi

# 获取authtoken
get_authtoken() {
    local token=$(curl -s "${BASE_URL}/webservice/foreign_getAuthtoken.htm?userKey=${CXDA_USER_KEY}" | grep -o '"authtoken":"[^"]*"' | cut -d'"' -f4)
    echo "$token"
}

# 导出authtoken
export AUTHTOKEN=$(get_authtoken)
echo "AuthToken: ${AUTHTOKEN}"
