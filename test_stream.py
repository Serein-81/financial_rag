import requests
import json
import sys

# 已经填好你的 Token 和 知识库 ID
TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJleHAiOjE3NzI1MjM0NTksInN1YiI6IjYxN2Q1Yjk3LWQwYTItNGI1NC1iMmFjLWYwMTczZDAxMzhmMiJ9.gNzcQQ07c_0uKmpj89nzYYqiboGlIgIRplpdDeL_Vlc"
KB_ID = "f8a65346-ad34-40a6-bfc6-61c384d5a031"

url = "http://127.0.0.1:8000/api/v1/chat/agent_chat_stream"
headers = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json"
}
payload = {
    "kb_id": KB_ID,
    "query": "讲一个关于程序员的长笑话",
    "session_id": ""
}

print("🤖 开始呼叫 Agent，等待回答中...\n")

try:
    with requests.post(url, headers=headers, json=payload, stream=True) as response:
        if response.status_code != 200:
            print(f"❌ 请求失败，状态码: {response.status_code}")
            print(response.text)
            sys.exit(1)

        # 逐行读取大模型吐出来的流式数据
        for line in response.iter_lines():
            if line:
                decoded_line = line.decode('utf-8')

                # SSE 格式是 "data: {...}"，我们把 "data: " 前缀切掉，还原成 JSON
                if decoded_line.startswith("data: "):
                    json_str = decoded_line[6:]
                    data = json.loads(json_str)

                    if data["type"] == "init":
                        print(f"🔗 [连接建立] 记忆 ID (Session ID): {data['session_id']}\n")
                    elif data["type"] == "chunk":
                        # 关键！加 end="" 让文字像打字机一样连续输出
                        print(data["content"], end="", flush=True)
                    elif data["type"] == "done":
                        print("\n\n✅ [输出完毕]")
except Exception as e:
    print(f"❌ 运行出错: {e}")