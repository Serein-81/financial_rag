import requests
import json
import time


def test_stream():
    url = "http://127.0.0.1:8000/api/v1/chat/completions_stream"

    payload = {
        "query": "备案承诺书有效期是多久？如果不通过会有什么后果？",
        "top_k": 3,
        "history": []
    }

    print(f"🚀 开始请求: {url}")
    start_time = time.time()

    # stream=True 是关键，告诉 requests 库不要等收完，收一点给一点
    try:
        with requests.post(url, json=payload, stream=True) as response:
            if response.status_code != 200:
                print(f"❌ 请求失败: {response.status_code}")
                print(response.text)
                return

            print("✅ 连接建立成功，开始接收数据流...\n")
            print("-" * 50)

            # 逐行读取数据
            for line in response.iter_lines():
                if line:
                    decoded_line = line.decode('utf-8')

                    # 尝试解析 JSON
                    try:
                        data = json.loads(decoded_line)

                        # 情况 A: 收到引用来源
                        if data['type'] == 'sources':
                            print(f"\n📚 [引用来源] 找到了 {len(data['data'])} 个参考文件")
                            for source in data['data']:
                                print(f"   - {source['filename']} (相似度: {source['score']})")
                            print("\n🤖 [AI 回答]: ", end="", flush=True)

                        # 情况 B: 收到文字内容
                        elif data['type'] == 'content':
                            # end="" 表示不换行，flush=True 表示立即输出
                            print(data['delta'], end="", flush=True)

                    except json.JSONDecodeError:
                        print(f"解析错误: {decoded_line}")

            print("\n" + "-" * 50)
            print(f"\n✨ 结束! 总耗时: {time.time() - start_time:.2f}秒")

    except Exception as e:
        print(f"❌ 发生错误: {e}")


if __name__ == "__main__":
    # 确保你安装了 requests 库 (pip install requests)
    test_stream()