import requests
import argparse
import sys
import os
import uuid
import hashlib
import time
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm

# --- 全局默认配置 ---
DEFAULT_DICT = "dict.txt"
DEFAULT_THREADS = 10  # 建议降低默认线程以提高隐蔽性
DEFAULT_TIMEOUT = 5
UA_LIST = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:102.0) Gecko/20100101 Firefox/102.0",
]

# 用于存储404页面的特征
fingerprint = {
    "status_code": 404,
    "content_length": -1,
    "content_hash": "",
    "is_soft_404": False
}

# 熔断器计数
error_counter = 0
MAX_ALLOWED_ERRORS = 20 # 连续出现20次拦截则停止

def get_content_hash(content):
    return hashlib.md5(content).hexdigest()

def get_404_fingerprint(url_base, headers, timeout, proxies=None):
    random_path = "/" + str(uuid.uuid4()) + ".html"
    url = url_base + random_path
    try:
        r = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True, proxies=proxies, verify=False)
        fingerprint["status_code"] = r.status_code
        fingerprint["content_length"] = len(r.content)
        fingerprint["content_hash"] = get_content_hash(r.content)
        
        if r.status_code == 200:
            print(f"[*] 检测到 Soft 404 (伪造404)。特征: 状态码 200, 长度 {len(r.content)}")
            fingerprint["is_soft_404"] = True
        else:
            print(f"[*] 站点使用标准响应码: {r.status_code}")
    except Exception as e:
        print(f"[-] 无法获取404特征: {e}")

def scan_path(url_base, path, timeout, headers, proxies=None, delay=0, random_ua=False):
    global error_counter
    
    if error_counter >= MAX_ALLOWED_ERRORS:
        return None

    # 随机延时逻辑
    if delay > 0:
        time.sleep(delay + random.uniform(0, 0.5))

    if not path.startswith("/"):
        path = "/" + path
    url = url_base + path
    
    current_headers = headers.copy()
    if random_ua:
        current_headers["User-Agent"] = random.choice(UA_LIST)

    try:
        # 禁用 SSL 警告
        requests.packages.urllib3.disable_warnings()
        r = requests.get(url, headers=current_headers, timeout=timeout, allow_redirects=True, proxies=proxies, verify=False)
        
        # 检查是否被封锁 (403 Forbidden 或 429 Too Many Requests)
        if r.status_code in [403, 429]:
            error_counter += 1
        else:
            error_counter = 0 # 只要有一个正常响应就重置计数

        # 过滤逻辑
        if r.status_code == 404:
            return None
        
        current_hash = get_content_hash(r.content)
        current_len = len(r.content)
        
        if current_hash == fingerprint["content_hash"] or current_len == fingerprint["content_length"]:
            return None

        return f"[{r.status_code}] {url} - Size: {current_len}"
    except Exception:
        error_counter += 0.5 # 网络超时等异常也计入熔断权重
        pass
    return None

def main():
    parser = argparse.ArgumentParser(description="Advanced Directory Scanner with Anti-Blocking.")
    parser.add_argument("-u", "--url", help="Target URL")
    parser.add_argument("-w", "--wordlist", help="Path to dictionary file")
    parser.add_argument("-t", "--threads", type=int, default=DEFAULT_THREADS, help=f"Threads (default: {DEFAULT_THREADS})")
    parser.add_argument("-x", "--timeout", type=int, default=DEFAULT_TIMEOUT, help=f"Timeout (default: {DEFAULT_TIMEOUT})")
    parser.add_argument("-d", "--delay", type=float, default=0, help="Delay between requests in seconds (e.g. 0.5)")
    parser.add_argument("-p", "--proxy", help="Proxy URL (e.g. http://127.0.0.1:8080)")
    parser.add_argument("--random-agent", action="store_true", help="Use random User-Agent for each request")
    parser.add_argument("-o", "--output", help="Save results to a file")

    args = parser.parse_args()

    # --- 参数预处理 ---
    if not args.url:
        target_url = input("请输入目标 URL: ").strip()
    else:
        target_url = args.url
    
    target_url = target_url.rstrip("/")
    proxies = {"http": args.proxy, "https": args.proxy} if args.proxy else None
    
    # 字典读取
    dict_path = args.wordlist or (DEFAULT_DICT if os.path.exists(DEFAULT_DICT) else None)
    if not dict_path:
        print("[-] 错误: 请指定字典文件")
        sys.exit(1)

    try:
        with open(dict_path, "r", encoding="utf-8", errors="ignore") as f:
            paths = [line.strip() for line in f if line.strip()]
    except Exception as e:
        print(f"[-] 错误: {e}")
        sys.exit(1)

    headers = {"User-Agent": UA_LIST[0]}

    # --- 准备扫描 ---
    print(f"[*] 正在识别 404 特征...")
    get_404_fingerprint(target_url, headers, args.timeout, proxies)

    print("\n" + "="*60)
    print(f" 目标: {target_url}")
    print(f" 线程: {args.threads} | 延时: {args.delay}s | 代理: {args.proxy}")
    print(f" 随机UA: {args.random_agent}")
    print("="*60 + "\n")

    results = []

    try:
        with ThreadPoolExecutor(max_workers=args.threads) as executor:
            # 将参数包装
            futures = {executor.submit(scan_path, target_url, p, args.timeout, headers, proxies, args.delay, args.random_agent): p for p in paths}
            
            with tqdm(total=len(paths), desc="Scanning", unit="req", ncols=80) as pbar:
                for future in as_completed(futures):
                    if error_counter >= MAX_ALLOWED_ERRORS:
                        print(f"\n[!] 警告: 连续错误过多，可能已被封禁。正在停止任务...")
                        executor.shutdown(wait=False)
                        break
                    
                    result = future.result()
                    if result:
                        tqdm.write(result)
                        results.append(result)
                    pbar.update(1)
    except KeyboardInterrupt:
        print("\n[!] 用户中断。")

    if args.output and results:
        with open(args.output, "w") as f:
            f.write("\n".join(results))
        print(f"[*] 结果已保存至: {args.output}")

if __name__ == "__main__":
    main()