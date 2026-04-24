import requests
import argparse
import sys
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm

# --- 全局默认配置 ---
DEFAULT_DICT = "dict.txt"  # 默认字典文件名
DEFAULT_THREADS = 20
DEFAULT_TIMEOUT = 3
DEFAULT_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"

def scan_path(url_base, path, timeout, headers):
    if not path.startswith("/"):
        path = "/" + path
    url = url_base + path
    try:
        r = requests.get(url, headers=headers, timeout=timeout, allow_redirects=False)
        if r.status_code != 404:
            return f"[{r.status_code}] {url} - Size: {len(r.content)}"
    except Exception:
        pass
    return None

def main():
    # 1. 设置参数解析 (将 required 改为 False)
    parser = argparse.ArgumentParser(description="A directory scanner.")
    parser.add_argument("-u", "--url", help="Target URL (e.g., http://example.com)")
    parser.add_argument("-w", "--wordlist", help="Path to dictionary file")
    parser.add_argument("-t", "--threads", type=int, default=DEFAULT_THREADS, help=f"Threads (default: {DEFAULT_THREADS})")
    parser.add_argument("-x", "--timeout", type=int, default=DEFAULT_TIMEOUT, help=f"Timeout (default: {DEFAULT_TIMEOUT})")
    parser.add_argument("-o", "--output", help="Save results to a file")
    parser.add_argument("--ua", default=DEFAULT_UA, help="Custom User-Agent")

    args = parser.parse_args()

    # 2. 交互式补充缺失参数
    # 处理 URL
    target_url = args.url
    if not target_url:
        target_url = input("请输入目标 URL (例如 http://example.com): ").strip()
    
    if not target_url.startswith("http"):
        print("[-] 错误: URL 必须以 http:// 或 https:// 开头")
        sys.exit(1)
    
    target_url = target_url.rstrip("/")

    # 处理 字典路径
    dict_path = args.wordlist
    if not dict_path:
        if os.path.exists(DEFAULT_DICT):
            dict_path = DEFAULT_DICT
            print(f"[*] 未指定字典，自动使用当前目录下默认字典: {DEFAULT_DICT}")
        else:
            dict_path = input("未找到默认字典，请输入字典文件路径: ").strip()

    # 3. 读取并检查字典
    try:
        with open(dict_path, "r", encoding="utf-8") as f:
            paths = [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        print(f"[-] 错误: 找不到文件 '{dict_path}'")
        sys.exit(1)

    # 4. 开始扫描逻辑
    print("\n" + "="*60)
    print(f" 目标: {target_url}")
    print(f" 字典: {dict_path} ({len(paths)} 行)")
    print(f" 线程: {args.threads} | 超时: {args.timeout}s")
    print("="*60 + "\n")

    results = []
    headers = {"User-Agent": args.ua}

    try:
        with ThreadPoolExecutor(max_workers=args.threads) as executor:
            futures = {executor.submit(scan_path, target_url, p, args.timeout, headers): p for p in paths}
            
            with tqdm(total=len(paths), desc="Scanning", unit="req", ncols=80) as pbar:
                for future in as_completed(futures):
                    result = future.result()
                    if result:
                        tqdm.write(result)
                        results.append(result)
                    pbar.update(1)
    except KeyboardInterrupt:
        print("\n[!] 用户中断扫描。")

    # 5. 结果保存
    if args.output and results:
        with open(args.output, "w", encoding="utf-8") as f:
            for item in results:
                f.write(item + "\n")
        print(f"\n[*] 结果已保存至: {args.output}")

    print("\n[*] 扫描完成。")

if __name__ == "__main__":
    main()