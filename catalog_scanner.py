import requests
from concurrent.futures import ThreadPoolExecutor  # 导入线程池模块

# --- 全局配置 ---
TARGET_URL = input("Target URL (e.g., http://example.com): ").rstrip("/")
DICT_PATH = "D:\\code\\tool\\dict_scan\\dict.txt"
THREADS = 20  # 设置线程数，你可以根据电脑性能调整
TIMEOUT = 3
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}

def scan_path(path):
    """
    负责执行单个路径扫描的任务函数
    """
    # 确保路径以 / 开头
    if not path.startswith("/"):
        path = "/" + path
    
    url = TARGET_URL + path

    try:
        # 设置 allow_redirects=False ，不让requests自动跳转，这样能看到真实的301/302状态
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT, allow_redirects=False)
        
        # 只打印我们关心的状态码（过滤掉404，让输出更干净）
        if r.status_code != 404:
            print(f"[{r.status_code}] {url} - Size: {len(r.content)}")
            
    except requests.exceptions.RequestException:
        # 实际实战中，报错通常不打印，以免干扰视觉，或者记录到日志里
        # print(f"[Error] {url}")
        pass

def main():
    """
    主程序入口：负责读取字典、分配线程
    """
    print(f"[*] Starting scan on: {TARGET_URL}")
    print(f"[*] Using {THREADS} threads...")
    print("-" * 50)

    # 1. 读取字典
    try:
        with open(DICT_PATH, "r", encoding="utf-8") as f:
            # 使用列表推导式快速读取并清洗数据
            paths = [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        print(f"[!] Dictionary file not found: {DICT_PATH}")
        return

    # 2. 使用线程池进行并发扫描
    # ThreadPoolExecutor 会自动管理线程的开启和关闭
    with ThreadPoolExecutor(max_workers=THREADS) as executor:
        # submit 是把函数和参数丢进池子里，让它自动运行
        for path in paths:
            executor.submit(scan_path, path)

    print("-" * 50)
    print("[*] Scan completed.")

if __name__ == "__main__":
    main()