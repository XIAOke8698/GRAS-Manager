import os
import json
from dotenv import load_dotenv
from openai import OpenAI
import time

# 加载.env文件中的环境变量
load_dotenv()

# 临时移除可能的代理环境变量，避免影响OpenAI客户端初始化
saved_proxies = {}
for proxy_key in ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy']:
    if proxy_key in os.environ:
        saved_proxies[proxy_key] = os.environ[proxy_key]
        del os.environ[proxy_key]

class LLM:
    """LLM客户端类，用于与DeepSeek API交互（使用官方openai包）"""
    
    def __init__(self, api_key=None, base_url=None, model="deepseek-chat"):
        """初始化LLM客户端
        
        参数:
            api_key: API密钥，如果为None则从环境变量获取
            base_url: API基础地址，如果为None则使用默认地址
            model: 使用的模型，默认为deepseek-chat
        """
        self.api_key = api_key or os.getenv('DEEPSEEK_API_KEY')
        self.base_url = os.getenv('OPENAI_BASE_URL', 'https://api.deepseek.com/v1')
        self.model = model
        
        # 验证必要的配置
        if not self.api_key:
            raise ValueError("API密钥未提供，请设置环境变量DEEPSEEK_API_KEY或直接传入")
        
        # 最简化地初始化OpenAI客户端，只传递必要的参数
        try:
            self.client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url
            )
            print(f"DeepSeek客户端初始化成功: Base URL={self.base_url}")
        except Exception as e:
            print(f"初始化DeepSeek客户端时出错: {str(e)}")
            import sys
            print(f"Python版本: {sys.version}")
            try:
                import importlib.metadata
                print(f"OpenAI包版本: {importlib.metadata.version('openai')}")
            except:
                print("无法获取OpenAI包版本")
            raise
    
    def chat(self, messages, stream=False, temperature=0.7, max_tokens=1000, timeout=30):
        """发送聊天请求到DeepSeek API
        
        参数:
            messages: 消息列表，格式为[{"role": "user", "content": "你的问题"}]
            stream: 是否使用流式响应
            temperature: 控制输出的随机性，值越大越随机
            max_tokens: 最大生成的token数
            timeout: 请求超时时间（秒）
        
        返回:
            API响应结果
        """
        try:
            # 记录开始时间，用于计算请求耗时
            start_time = time.time()
            
            # 使用OpenAI客户端发送请求
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                stream=stream,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=timeout
            )
            
            # 计算请求耗时
            elapsed_time = time.time() - start_time
            
            # 格式化响应
            if not stream:
                # 非流式响应
                result = {
                    "id": response.id,
                    "model": response.model,
                    "object": "chat.completion",
                    "created": response.created,
                    "choices": [
                        {
                            "index": 0,
                            "message": {
                                "role": response.choices[0].message.role,
                                "content": response.choices[0].message.content
                            },
                            "finish_reason": response.choices[0].finish_reason
                        }
                    ],
                    "usage": {
                        "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                        "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                        "total_tokens": response.usage.total_tokens if response.usage else 0
                    }
                }
                
                # 记录请求信息
                print(f"请求成功，耗时: {elapsed_time:.2f}秒")
                print(f"模型: {self.model}")
                
                return result
            else:
                # 流式响应处理
                return response
        
        except Exception as e:
            # 处理请求过程中的异常
            print(f"发送聊天请求时出错: {str(e)}")
            # 尝试捕获OpenAI特定异常
            if hasattr(e, 'response'):
                try:
                    error_data = e.response.json()
                    print(f"API错误详情: {error_data}")
                    return {"error": error_data}
                except:
                    print(f"无法解析API错误响应: {str(e)}")
                    return {"error": str(e)}


# 创建全局的LLM客户端实例，遵循单例模式
# 当其他模块导入llm_client时，会使用这个全局实例
# 注意：只有在确保环境变量已经正确加载的情况下才会创建实例
llm_client = None

# 尝试创建全局客户端实例
try:
    # 延迟创建直到实际需要时，避免过早加载环境变量
    if os.getenv('DEEPSEEK_API_KEY'):
        api_key = os.getenv('DEEPSEEK_API_KEY')
        ds_base_url = os.getenv('OPENAI_BASE_URL', 'https://api.deepseek.com/v1')

        print(f"使用Base URL: {ds_base_url}")

        # 创建LLM实例
        llm_client = LLM(api_key=api_key, base_url=ds_base_url)
        print(f"全局LLM客户端实例已创建: model={llm_client.model}")
    else:
        print("未创建全局LLM客户端实例: 环境变量DEEPSEEK_API_KEY未设置")
except Exception as e:
    print(f"创建全局LLM客户端实例失败: {str(e)}")