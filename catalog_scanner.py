import requests
import argparse
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm

# --- 默认配置 ---
DEFAULT_THREADS = 20
DEFAULT_TIMEOUT = 3
DEFAULT_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"

def scan_path(url_base, path, timeout, headers):
    """
    执行单个路径的扫描
    """
    if not path.startswith("/"):
        path = "/" + path
    url = url_base + path

    try:
        # allow_redirects=False 通常用于目录扫描，防止跳转到统一的错误页
        r = requests.get(url, headers=headers, timeout=timeout, allow_redirects=False)
        
        # 简单过滤：只返回非 404 的页面
        if r.status_code != 404:
            return f"[{r.status_code}] {url} - Size: {len(r.content)}"
    except Exception:
        pass
    return None

def main():
    # 1. 设置命令行参数解析
    parser = argparse.ArgumentParser(description="A simple directory scanner.")
    
    # 必需参数
    parser.add_argument("-u", "--url", help="Target URL (e.g., http://example.com)", required=True)
    parser.add_argument("-w", "--wordlist", help="Path to dictionary file", required=True)
    
    # 可选参数
    parser.add_argument("-t", "--threads", type=int, default=DEFAULT_THREADS, help=f"Number of threads (default: {DEFAULT_THREADS})")
    parser.add_argument("-x", "--timeout", type=int, default=DEFAULT_TIMEOUT, help=f"Request timeout in seconds (default: {DEFAULT_TIMEOUT})")
    parser.add_argument("-o", "--output", help="Save results to a file")
    parser.add_argument("--ua", default=DEFAULT_UA, help="Custom User-Agent")

    args = parser.parse_args()

    # 处理 URL 末尾的斜杠
    target_url = args.url.rstrip("/")
    headers = {"User-Agent": args.ua}

    # 2. 读取字典
    try:
        with open(args.wordlist, "r", encoding="utf-8") as f:
            paths = [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        print(f"[-] Error: Dictionary file '{args.wordlist}' not found.")
        sys.exit(1)

    print(f"[*] Starting scan on: {target_url}")
    print(f"[*] Total paths: {len(paths)} | Threads: {args.threads} | Timeout: {args.timeout}")
    print("-" * 60)

    results = []

    # 3. 使用线程池执行
    try:
        with ThreadPoolExecutor(max_workers=args.threads) as executor:
            # 提交任务
            futures = {executor.submit(scan_path, target_url, p, args.timeout, headers): p for p in paths}
            
            with tqdm(total=len(paths), desc="Scanning", unit="req", ncols=80) as pbar:
                for future in as_completed(futures):
                    result = future.result()
                    if result:
                        tqdm.write(result)
                        results.append(result)
                    pbar.update(1)
    except KeyboardInterrupt:
        print("\n[!] Scan interrupted by user.")

    # 4. 结果输出到文件
    if args.output and results:
        with open(args.output, "w", encoding="utf-8") as f:
            for item in results:
                f.write(item + "\n")
        print(f"[*] Results saved to: {args.output}")

    print("-" * 60)
    print("[*] Scan completed.")

if __name__ == "__main__":
    main()