import requests
from dotenv import load_dotenv
import os

# 加载环境变量
load_dotenv()

def get_task_progress(api_key, base_url, task_id):
    """获取任务进度"""
    url = f"{base_url}/v1/draw/result"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }

    payload = {"id": task_id}

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=20)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"获取进度失败: HTTP {response.status_code}")
            return None
    except Exception as e:
        print(f"获取进度异常: {e}")
        return None

