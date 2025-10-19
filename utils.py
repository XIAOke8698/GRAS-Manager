import json
import os
import shutil
from datetime import datetime
import streamlit as st
import uuid
import requests
from dotenv import load_dotenv

# 导入LLM客户端
from openai_llm import llm_client

# 加载.env文件中的环境变量
load_dotenv()

# 从环境变量获取配置
API_KEY = os.getenv('API_KEY')
BASE_URL = os.getenv('BASE_URL', 'https://grsai.dakka.com.cn')
# OpenAI API 配置
OPENAI_API_URL = os.getenv('OPENAI_API_URL', 'https://api.deepseek.com/v1')
OPENAI_MODEL = os.getenv('OPENAI_MODEL', 'gpt-4o-mini')


def load_tasks_from_file():
    """从文件加载任务历史"""
    filename = "video_tasks.json"
    if os.path.exists(filename):
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"加载任务文件失败: {e}")
            return []
    return []


def ensure_download_dir():
    """确保下载目录存在"""
    download_dir = st.session_state.get('download_dir', './downloads')
    if not os.path.exists(download_dir):
        os.makedirs(download_dir)
    return download_dir

def cleanup_temp_files(temp_dir="temp_uploads"):
    """清理临时上传的文件
    
    参数:
        temp_dir: 临时文件存储目录
    """
    try:
        # 清理指定的临时目录
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
            os.makedirs(temp_dir, exist_ok=True)
        
        # 清理session_state中相关的临时路径
        if 'first_frame_temp_path' in st.session_state:
            if os.path.exists(st.session_state.first_frame_temp_path):
                try:
                    os.remove(st.session_state.first_frame_temp_path)
                except:
                    pass
            del st.session_state.first_frame_temp_path
        
        # 清理上传的图片列表中的临时文件
        if 'uploaded_images' in st.session_state:
            for img in st.session_state.uploaded_images:
                if 'temp_path' in img and os.path.exists(img['temp_path']):
                    try:
                        os.remove(img['temp_path'])
                    except:
                        pass
        
        return True
    except Exception as e:
        print(f"清理临时文件失败: {str(e)}")
        return False


def save_task_to_file(tasks):
    """保存任务到本地文件"""
    filename = "video_tasks.json"
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(tasks, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"保存任务失败: {e}")


def get_task_progress(task_id):
    """获取任务进度 - 增强错误处理"""
    url = f"{BASE_URL}/v1/draw/result"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }

    payload = {"id": task_id}

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        if response.status_code == 200:
            result = response.json()

            # 检查API返回的错误
            if result.get('code') == 0:
                data = result.get('data', {})

                # 处理生成失败的情况
                if data.get('status') == 'failed':
                    error_msg = data.get('error', '未知错误')
                    failure_reason = data.get('failure_reason', 'error')
                    print(f"任务 {task_id} 失败: {failure_reason} - {error_msg}")

                    # 返回完整的错误信息
                    return {
                        'code': 0,  # API返回0表示请求成功，但任务本身失败
                        'data': {
                            'status': 'failed',
                            'progress': data.get('progress', 0),
                            'failure_reason': failure_reason,
                            'error': error_msg,
                            'id': task_id
                        },
                        'msg': 'success'
                    }

                return result
            else:
                # API返回非0状态码
                error_msg = result.get('msg', 'API请求失败')
                print(f"API错误: {error_msg}")
                return {
                    'code': result.get('code', -1),
                    'msg': error_msg
                }
        else:
            error_msg = f"HTTP错误: {response.status_code}"
            print(error_msg)
            return {
                'code': -1,
                'msg': error_msg
            }
    except Exception as e:
        error_msg = f"请求异常: {str(e)}"
        print(error_msg)
        return {
            'code': -1,
            'msg': error_msg
        }


def update_task_progress(task):
    """更新单个任务进度 - 增强错误处理"""
    if task.get('status') in ['succeeded', 'failed']:
        return task

    result = get_task_progress(task['task_id'])

    if result:
        if result.get('code') == 0:
            data = result.get('data', {})
            task['progress'] = data.get('progress', task.get('progress', 0))
            task['status'] = data.get('status', task.get('status', 'submitted'))

            # 更新其他字段
            if data.get('url'):
                task['video_url'] = data['url']
            if data.get('failure_reason'):
                task['failure_reason'] = data['failure_reason']
            if data.get('error'):
                task['error'] = data['error']

            # 处理图片任务的results
            if data.get('results'):
                task['results'] = data['results']

            # 当进度为100%且状态不是失败时，标记任务为已完成
            if data.get('progress') == 100 and data.get('status') != 'failed':
                task['completed'] = True
                task['status'] = 'succeeded'  # 确保状态正确设置为succeeded

            task['last_check'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # 记录API响应日志（用于调试）
            task['last_api_response'] = {
                'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'data': data
            }
        else:
            # API调用失败，但不改变任务状态（可能是网络问题）
            error_msg = result.get('msg', '未知错误')
            task['last_check'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            task['last_error'] = error_msg
            print(f"获取任务 {task['task_id']} 进度失败: {error_msg}")

    return task


def update_all_tasks_progress(tasks):
    """更新所有任务进度"""
    for i, task in enumerate(tasks):
        if task.get('status') not in ['succeeded', 'failed']:
            tasks[i] = update_task_progress(task)

    # 保存更新后的任务
    save_task_to_file(tasks)
    return tasks


def download_video(video_url, task_id):
    """下载视频文件到本地并更新任务记录"""
    try:
        download_dir = ensure_download_dir()

        # 生成文件名
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"video_{task_id}_{timestamp}.mp4"
        local_path = os.path.join(download_dir, filename)

        # 下载文件
        response = requests.get(video_url, stream=True, timeout=30)
        if response.status_code == 200:
            with open(local_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            # 更新任务记录
            for i, task in enumerate(st.session_state.tasks):
                if task.get('task_id') == task_id:
                    # 将video_url更新为本地路径，确保显示和下载都使用本地文件
                    st.session_state.tasks[i]['video_url'] = local_path
                    # 保留原始信息
                    st.session_state.tasks[i]['original_video_url'] = video_url
                    st.session_state.tasks[i]['local_video_path'] = local_path
                    st.session_state.tasks[i]['downloaded'] = True
                    st.session_state.tasks[i]['completed'] = True
                    st.session_state.tasks[i]['download_time'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    break

            # 保存更新后的任务列表
            save_task_to_file(st.session_state.tasks)

            st.success(f"✅ 视频已下载到: {local_path}")
            return True
        else:
            st.error(f"❌ 视频下载失败: HTTP {response.status_code}")
            return False
    except Exception as e:
        st.error(f"❌ 下载异常: {str(e)}")
        return False


def translate_to_english(chinese_text, preserve_chinese_text=True, model=None):
    """将中文提示词翻译成英文，保留台词和文字中的中文
    
    参数:
        chinese_text: 要翻译的中文文本
        preserve_chinese_text: 是否保留台词和文字中的中文
        model: 可选，使用的模型名称
        
    返回:
        翻译后的英文文本
    """
    if not chinese_text:
        return ""
    
    # 准备提示词
    system_prompt = """你是一个专业的翻译助手。请将用户提供的中文提示词翻译成英文。"""
    
    if preserve_chinese_text:
        system_prompt += " 请保留所有台词、直接引语和特殊名称中的中文内容，不要翻译这些部分。"
    
    user_prompt = f"请翻译以下内容：\n{chinese_text}"
    
    try:
        # 构建消息列表
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        # 调用LLM进行翻译
        # 如果指定了模型，则使用指定的模型，否则使用默认模型

            # 创建一个临时的LLM实例使用指定的模型

        response = llm_client.chat(messages)
        if response and 'choices' in response and response['choices']:
            print(f"响应成功: {response['choices'][0]['message']['content']}")
            return response['choices'][0]['message']['content']
        else:
            print(f"响应格式异常: {response}")
            raise Exception("翻译响应格式异常")
    except Exception as e:
        print(f"翻译失败: {str(e)}")
        # 如果翻译失败，返回原始文本
        return chinese_text


def auto_translate_if_needed(text, target_language="en", check_threshold=0.5, model=None):
    """自动检测并翻译文本到指定语言
    
    参数:
        text: 输入文本
        target_language: 目标语言，默认为'en'（英文）
        check_threshold: 中文检测阈值，默认为0.5
        model: 可选，使用的模型名称
        
    返回:
        翻译后的文本或原始文本
    
    异常:
        Exception: 当翻译失败时抛出异常
    """
    # 简单的中文检测逻辑
    chinese_chars_count = sum(1 for char in text if '\u4e00' <= char <= '\u9fff')
    total_chars_count = max(len(text), 1)  # 避免除零
    
    # 计算中文比例
    chinese_ratio = chinese_chars_count / total_chars_count
    
    # 如果中文比例超过阈值，则进行翻译
    if target_language == "en" and chinese_ratio >= check_threshold:
        # 调用translate_to_english，它现在会在失败时抛出异常
        return translate_to_english(text, preserve_chinese_text=True, model=model)
    
    # 否则返回原始文本
    return text


def submit_video_task(task_data):
    """提交视频生成任务"""
    url = f"{BASE_URL}/v1/video/veo"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }

    # 构建请求参数
    payload = {
        "model": task_data['model'],
        "prompt": task_data['prompt'],
        "aspectRatio": task_data['aspect_ratio'],
        "webHook": "-1",  # 使用轮询方式获取结果
        "shutProgress": task_data.get('shut_progress', False)
    }

    # 可选参数
    if task_data.get('first_frame_url'):
        payload["firstFrameUrl"] = task_data['first_frame_url']
    if task_data.get('webhook_url') and task_data['webhook_url'] != "-1":
        payload["webHook"] = task_data['webhook_url']

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)

        if response.status_code == 200:
            result = response.json()
            if result.get("code") == 0:
                task_id = result["data"]["id"]

                # 完善任务数据
                task_data['task_id'] = task_id
                task_data['status'] = 'submitted'
                task_data['progress'] = 0
                task_data['submit_time'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                task_data['last_check'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                task_data['video_url'] = ""
                task_data['failure_reason'] = ""
                task_data['error'] = ""
                task_data['completed'] = False

                return task_data, True, "任务提交成功"
            else:
                return None, False, f"任务提交失败: {result.get('msg', '未知错误')}"
        else:
            return None, False, f"API请求失败: HTTP {response.status_code}"
    except Exception as e:
        return None, False, f"请求异常: {str(e)}"


def submit_nano_banana_task(task_data):
    """提交Nano Banana图片生成任务"""
    url = f"{BASE_URL}/v1/draw/nano-banana"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }

    # 构建请求参数
    payload = {
        "model": task_data['model'],
        "prompt": task_data['prompt'],
        "webHook": "-1",  # 使用轮询方式获取结果
        "shutProgress": task_data.get('shut_progress', False)
    }

    # 可选参数 - 参考图片URL列表
    if task_data.get('urls'):
        payload["urls"] = task_data['urls']

    # 可选参数 - webhook
    if task_data.get('webhook_url') and task_data['webhook_url'] != "-1":
        payload["webHook"] = task_data['webhook_url']

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)

        if response.status_code == 200:
            result = response.json()
            if result.get("code") == 0:
                task_id = result["data"]["id"]

                # 完善任务数据
                task_data['task_id'] = task_id
                task_data['status'] = 'submitted'
                task_data['progress'] = 0
                task_data['submit_time'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                task_data['last_check'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                task_data['results'] = []  # 图片结果列表
                task_data['failure_reason'] = ""
                task_data['error'] = ""
                task_data['completed'] = False

                return task_data, True, "任务提交成功"
            else:
                return None, False, f"任务提交失败: {result.get('msg', '未知错误')}"
        else:
            return None, False, f"API请求失败: HTTP {response.status_code}"
    except Exception as e:
        return None, False, f"请求异常: {str(e)}"


def get_local_video_path(task_id):
    """获取任务的本地视频路径"""
    for task in st.session_state.tasks:
        if task.get('task_id') == task_id:
            return task.get('local_video_path')
    return None


def get_local_image_paths(task_id):
    """获取任务的本地图片路径列表"""
    for task in st.session_state.tasks:
        if task.get('task_id') == task_id:
            return task.get('local_image_paths', [])
    return []


def submit_sora2_task(task_data, base_url=None):
    """提交Sora2视频生成任务"""
    # 使用传入的base_url，如果没有则使用默认的BASE_URL
    api_base_url = base_url if base_url else BASE_URL
    url = f"{api_base_url}/v1/video/sora-video"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }

    # 构建请求参数
    payload = {
        "model": "sora-2",
        "prompt": task_data['prompt'],
        "aspectRatio": task_data['aspect_ratio'],
        "duration": task_data['duration'],
        "size": task_data['size'],
        "webHook": "-1",  # 使用轮询方式获取结果
        "shutProgress": task_data.get('shut_progress', False)
    }

    # 可选参数
    if task_data.get('reference_image_url'):
        payload["url"] = task_data['reference_image_url']
    if task_data.get('webhook_url') and task_data['webhook_url'] != "-1":
        payload["webHook"] = task_data['webhook_url']

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)

        if response.status_code == 200:
            result = response.json()
            if result.get("code") == 0:
                task_id = result["data"]["id"]

                # 完善任务数据
                task_data['task_id'] = task_id
                task_data['status'] = 'submitted'
                task_data['progress'] = 0
                task_data['submit_time'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                task_data['last_check'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                task_data['video_url'] = ""
                task_data['failure_reason'] = ""
                task_data['error'] = ""
                task_data['completed'] = False

                return task_data, True, "任务提交成功"
            else:
                return None, False, f"任务提交失败: {result.get('msg', '未知错误')}"
        else:
            return None, False, f"API请求失败: HTTP {response.status_code}"
    except Exception as e:
        return None, False, f"请求异常: {str(e)}"

def download_image(image_url, task_id, image_index=0):
    """下载图片文件到本地并更新任务记录"""
    try:
        download_dir = ensure_download_dir()

        # 生成文件名
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"image_{task_id}_{image_index}_{timestamp}.png"
        local_path = os.path.join(download_dir, filename)

        # 下载文件
        response = requests.get(image_url, stream=True, timeout=30)
        if response.status_code == 200:
            with open(local_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            # 更新任务记录中的URL为本地路径
            for i, task in enumerate(st.session_state.tasks):
                if task.get('task_id') == task_id:
                    # 确保有local_image_paths列表
                    if 'local_image_paths' not in st.session_state.tasks[i]:
                        st.session_state.tasks[i]['local_image_paths'] = []

                    # 确保列表足够长
                    while len(st.session_state.tasks[i]['local_image_paths']) <= image_index:
                        st.session_state.tasks[i]['local_image_paths'].append(None)

                    st.session_state.tasks[i]['local_image_paths'][image_index] = local_path
                    st.session_state.tasks[i]['downloaded'] = True
                    st.session_state.tasks[i]['download_time'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                     
                    # 更新results中的url为本地路径
                    if 'results' in st.session_state.tasks[i] and st.session_state.tasks[i]['results']:
                        if image_index < len(st.session_state.tasks[i]['results']):
                            st.session_state.tasks[i]['results'][image_index]['url'] = local_path
                    break

            # 保存更新后的任务列表
            save_task_to_file(st.session_state.tasks)

            st.success(f"✅ 图片已下载到: {local_path}")
            return True
        else:
            st.error(f"❌ 图片下载失败: HTTP {response.status_code}")
            return False
    except Exception as e:
        st.error(f"❌ 下载异常: {str(e)}")
        return False

