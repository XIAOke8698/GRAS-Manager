#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""简单的翻译功能测试脚本

此脚本仅测试最基本的翻译功能，帮助诊断404错误问题。
"""

import os
import sys
import traceback
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 加载.env文件中的环境变量
load_dotenv()

# 打印配置信息
def print_config():
    """打印DeepSeek API相关配置"""
    print("=== DeepSeek API 配置信息 ===")
    print(f"DEEPSEEK_API_KEY: {'已设置' if os.getenv('DEEPSEEK_API_KEY') else '未设置'}")
    print(f"OPENAI_BASE_URL: {os.getenv('OPENAI_BASE_URL', '未设置')}")
    print("===========================")

# 测试DeepSeek API连接
def test_deepseek_connection():
    """直接测试DeepSeek API连接"""
    try:
        from openai_llm import LLM
        
        print("\n=== 测试DeepSeek API连接 ===")
        
        # 获取配置
        api_key = os.getenv('DEEPSEEK_API_KEY')
        base_url = os.getenv('OPENAI_BASE_URL', 'https://api.deepseek.com')
        
        print(f"使用Base URL: {base_url}")
        
        # 创建LLM实例
        llm = LLM(api_key=api_key, base_url=base_url)
        print("LLM客户端创建成功")
        
        # 发送简单的测试消息
        messages = [
            {"role": "user", "content": "你好，这是一个测试消息。"}
        ]
        
        print("发送测试消息...")
        response = llm.chat(messages)
        
        # 打印响应
        if response and 'choices' in response and response['choices']:
            print(f"响应成功: {response['choices'][0]['message']['content']}")
            return True
        else:
            print(f"响应格式异常: {response}")
            return False
            
    except Exception as e:
        print(f"连接测试失败: {str(e)}")
        print("错误详情:")
        traceback.print_exc()
        return False

# 主函数
def main():
    """主函数"""
    print("===== 简单翻译功能测试 =====")
    
    # 打印配置
    print_config()
    
    # 测试连接
    success = test_deepseek_connection()
    
    # 总结
    print("\n===== 测试总结 =====")
    if success:
        print("✅ 测试成功！DeepSeek API连接正常。")
    else:
        print("❌ 测试失败！请检查以下问题：")
        print("1. 确认.env文件中的DEEPSEEK_API_KEY是否正确设置")
        print("2. 检查OPENAI_BASE_URL是否正确 (应为https://api.deepseek.com/v1)")
        print("3. 确保网络连接正常，可以访问DeepSeek API")
        print("4. 验证API密钥是否有效")

if __name__ == "__main__":
    main()