import requests  

target = input("Target URL: ")    #输入测试url

with open("<字典目录>", "r") as f:    #导入字典
    for line in f:    #遍历字典
        path = line.strip()     #删除每一行的换行符
        url = target.rstrip("/") + path     #检查是否存在双斜杠，有的话就删掉，接着拼接url

        try:
            r = requests.get(url, timeout = 3)    #请求拼接后的url，并设置时间间隔
            print(f"[{r.status_code}] {url}")    #打印响应状态码

        except requests.exceptions.RequestException:
            print(f"[Error] {url}")    #如果报错也打印出来响应url