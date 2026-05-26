import os
import base64
import gzip
import json
import sys
import requests
from pathlib import Path
from datetime import datetime, timedelta

OUTPUT_ENCODING = sys.getfilesystemencoding()

os.environ['PYTHONIOENCODING'] = 'utf-8'

ENV_PATH = Path(__file__).parent / '.env'
TOKEN_VALID_SECONDS = 60  # token缓存60秒
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

def load_env():
    """加载 .env 配置文件"""
    env = {}
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text(encoding='utf-8').splitlines():
            if '=' in line and not line.strip().startswith('#'):
                k, v = line.split('=', 1)
                env[k.strip()] = v.strip()
    return env

def save_env(env):
    """保存 .env 配置文件"""
    lines = []
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text(encoding='utf-8').splitlines():
            if not any(line.strip().startswith(k) for k in ['AUTH_TOKEN', '# === Token']):
                lines.append(line)

    lines.extend([
        '',
        '# === Token缓存（自动管理，请勿手动修改）===',
        f'AUTH_TOKEN={env.get("AUTH_TOKEN", "")}',
        f'AUTH_TOKEN_EXPIRE={env.get("AUTH_TOKEN_EXPIRE", "")}',
    ])

    ENV_PATH.write_text('\n'.join(lines) + '\n', encoding='utf-8')

def get_cached_token():
    """获取缓存的有效 token，返回 (token, need_refresh)"""
    env = load_env()

    try:
        expire = datetime.strptime(env.get('AUTH_TOKEN_EXPIRE', ''), '%Y-%m-%d %H:%M:%S')
        token = env.get('AUTH_TOKEN')
        if not token:
            return None, True

        remaining = expire - datetime.now()
        if remaining <= timedelta(0):
            return None, True  # 已过期
        else:
            return token, False  # 有效
    except:
        return None, True

def cache_token(token):
    """缓存 token"""
    env = load_env()
    env.update({
        'AUTH_TOKEN': token,
        'AUTH_TOKEN_EXPIRE': (datetime.now() + timedelta(seconds=TOKEN_VALID_SECONDS)).strftime('%Y-%m-%d %H:%M:%S'),
    })
    save_env(env)

def fetch_new_token(base_url, user_key):
    """获取新 token"""
    resp = requests.get(
        f"{base_url}/webservice/foreign_getAuthtoken.htm",
        params={"userKey": user_key},
        headers=HEADERS
    )
    token = json.loads(resp.text).get("result")
    if token:
        cache_token(token)
    return token

def parse_params(args):
    """解析命令行参数，支持 key=value 格式"""
    params = {}
    for arg in args:
        if '=' in arg:
            k, v = arg.split('=', 1)
            params[k.strip()] = v.strip()
    return params

def run_query(api_id, params):
    """执行API查询"""
    config = load_env()
    base_url = config.get('BASE_URL', '').rstrip('/')
    # 优先读取环境变量，再读取 .env
    user_key = os.environ.get('CXDA_USER_KEY') or config.get('CXDA_USER_KEY')

    if not base_url or not user_key:
        print(json.dumps({"error": "未在 .env 或环境变量中找到 BASE_URL 或 USER_KEY"}, ensure_ascii=False))
        return

    try:
        # 获取 token（优先缓存，自动刷新）
        token, need_refresh = get_cached_token()
        if need_refresh:
            new_token = fetch_new_token(base_url, user_key)
            if not new_token:
                print(json.dumps({"error": "获取 authToken 失败"}, ensure_ascii=False))
                return
            token = new_token

        # 构建请求参数，添加 authtoken
        request_params = {"authtoken": token}
        request_params.update(params)

        # 发送业务请求
        resp = requests.get(
            f"{base_url}/webservice/cxdata/{api_id}.htm",
            params=request_params,
            headers=HEADERS
        )

        # 解码解压
        data = json.loads(gzip.decompress(base64.b64decode(resp.text.strip())).decode('utf-8'))
        print(json.dumps(data, indent=4, ensure_ascii=False))

    except Exception as e:
        print(json.dumps({"error": str(e), "status": "failed"}, ensure_ascii=False))

if __name__ == "__main__":
    sys.stdout = open(sys.stdout.fileno(), mode='w', encoding=OUTPUT_ENCODING, closefd=False)
    if len(sys.argv) < 3:
        print("Usage: python api_query.py <API_ID> <key=value> [key=value] ...")
        print("Examples:")
        print("  python api_query.py getStkBasicInfoByCond-K stkCode=600519")
        print("  python api_query.py getCooWineCateDailQuoByWineName wineName=飞天茅台")
        print("  python api_query.py getCooWineCateDailQuoByWineName wineName=飞天茅台 pageNum=1 pageSize=10")
    else:
        api_id = sys.argv[1]
        params = parse_params(sys.argv[2:])
        run_query(api_id, params)
