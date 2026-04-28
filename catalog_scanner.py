import requests
import argparse
import sys
import os
import uuid
import hashlib
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm

# --- 全局默认配置 ---
DEFAULT_DICT = "dict.txt"
DEFAULT_THREADS = 20
DEFAULT_TIMEOUT = 3
DEFAULT_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"

# 用于存储404页面的特征
fingerprint = {
    "status_code": 404,
    "content_length": -1,
    "content_hash": "",
    "is_soft_404": False
}

def get_content_hash(content):
    """计算响应内容的MD5，用于精确对比"""
    return hashlib.md5(content).hexdigest()

def get_404_fingerprint(url_base, headers, timeout):
    """
    通过访问一个随机路径来获取该站点的404特征
    """
    random_path = "/" + str(uuid.uuid4()) + ".html"
    url = url_base + random_path
    try:
        # 允许重定向，因为很多伪造404会跳转到 /404.html 或 首页
        r = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
        fingerprint["status_code"] = r.status_code
        fingerprint["content_length"] = len(r.content)
        fingerprint["content_hash"] = get_content_hash(r.content)
        
        if r.status_code == 200:
            print(f"[*] 检测到 Soft 404 (伪造404)。特征: 状态码 200, 长度 {len(r.content)}")
            fingerprint["is_soft_404"] = True
        else:
            print(f"[*] 站点使用标准响应码: {r.status_code}")
            
    except Exception as e:
        print(f"[-] 无法获取404特征，将使用默认404过滤: {e}")

def scan_path(url_base, path, timeout, headers):
    if not path.startswith("/"):
        path = "/" + path
    url = url_base + path
    try:
        # 扫描时建议跟随重定向，以匹配指纹获取时的逻辑
        r = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
        
        # --- 过滤逻辑开始 ---
        
        # 1. 物理状态码过滤 (如果指纹是404，且当前也是404，直接过滤)
        if r.status_code == 404:
            return None
            
        # 2. 特征匹配过滤
        current_hash = get_content_hash(r.content)
        current_len = len(r.content)
        
        # 如果当前响应与404指纹的长度和哈希一致，判定为404
        if current_hash == fingerprint["content_hash"]:
            return None
        
        # 有些动态404页面（带时间戳或随机数）长度会微小变化，这里检查长度差值
        # 如果长度完全一样但内容Hash不同，通常也是404页面（可能包含请求路径）
        if current_len == fingerprint["content_length"]:
            return None

        # --- 过滤逻辑结束 ---

        return f"[{r.status_code}] {url} - Size: {current_len}"
    except Exception:
        pass
    return None

def main():
    parser = argparse.ArgumentParser(description="A directory scanner with Soft 404 detection.")
    parser.add_argument("-u", "--url", help="Target URL (e.g., http://example.com)")
    parser.add_argument("-w", "--wordlist", help="Path to dictionary file")
    parser.add_argument("-t", "--threads", type=int, default=DEFAULT_THREADS, help=f"Threads (default: {DEFAULT_THREADS})")
    parser.add_argument("-x", "--timeout", type=int, default=DEFAULT_TIMEOUT, help=f"Timeout (default: {DEFAULT_TIMEOUT})")
    parser.add_argument("-o", "--output", help="Save results to a file")
    parser.add_argument("--ua", default=DEFAULT_UA, help="Custom User-Agent")

    args = parser.parse_args()

    target_url = args.url
    if not target_url:
        target_url = input("请输入目标 URL (例如 http://example.com): ").strip()
    
    if not target_url.startswith("http"):
        print("[-] 错误: URL 必须以 http:// 或 https:// 开头")
        sys.exit(1)
    
    target_url = target_url.rstrip("/")

    dict_path = args.wordlist
    if not dict_path:
        if os.path.exists(DEFAULT_DICT):
            dict_path = DEFAULT_DICT
            print(f"[*] 未指定字典，自动使用当前目录下默认字典: {DEFAULT_DICT}")
        else:
            dict_path = input("未找到默认字典，请输入字典文件路径: ").strip()

    try:
        with open(dict_path, "r", encoding="utf-8") as f:
            paths = [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        print(f"[-] 错误: 找不到文件 '{dict_path}'")
        sys.exit(1)

    headers = {"User-Agent": args.ua}

    # --- 获取404指纹 ---
    print(f"[*] 正在识别目标 404 特征...")
    get_404_fingerprint(target_url, headers, args.timeout)

    print("\n" + "="*60)
    print(f" 目标: {target_url}")
    print(f" 字典: {dict_path} ({len(paths)} 行)")
    print(f" 线程: {args.threads} | 超时: {args.timeout}s")
    print("="*60 + "\n")

    results = []

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

    if args.output and results:
        with open(args.output, "w", encoding="utf-8") as f:
            for item in results:
                f.write(item + "\n")
        print(f"\n[*] 结果已保存至: {args.output}")

    print("\n[*] 扫描完成。")

if __name__ == "__main__":
    main()