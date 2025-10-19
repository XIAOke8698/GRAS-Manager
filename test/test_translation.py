#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""测试翻译功能的脚本

此脚本用于测试DeepSeek API的翻译功能，检查是否存在404错误和配置问题。
"""

import os
import sys
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 加载.env文件中的环境变量
load_dotenv()

# 打印当前环境变量配置，用于调试
def print_config_info():
    """打印当前的配置信息"""
    print("=== 配置信息 ===")
    print(f"API_KEY: {os.getenv('API_KEY')}")
    print(f"BASE_URL: {os.getenv('BASE_URL')}")
    print(f"OPENAI_BASE_URL: {os.getenv('OPENAI_BASE_URL')}")
    print(f"DEEPSEEK_API_KEY: {os.getenv('DEEPSEEK_API_KEY')}")
    print("=== 代理环境变量 ===")
    proxy_keys = ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy']
    for key in proxy_keys:
        value = os.getenv(key, '未设置')
        print(f"{key}: {value}")
    print("="*30)

# 修复openai_llm.py文件中的导入问题
def fix_openai_llm_import():
    """修复openai_llm.py文件中缺少os模块导入的问题"""
    llm_file_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "openai_llm.py")
    
    try:
        with open(llm_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 检查是否已导入os模块
        if 'import os' not in content:
            # 在文件开头添加os模块导入
            new_content = "import os\n" + content
            
            with open(llm_file_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            
            print(f"已修复 {llm_file_path} 中的os模块导入问题")
        else:
            print("openai_llm.py 中已导入os模块")
        
        return True
    except Exception as e:
        print(f"修复openai_llm.py文件失败: {str(e)}")
        return False

# 测试翻译功能
def test_translation():
    """测试翻译功能是否正常工作"""
    try:
        # 尝试导入翻译函数
        from utils import translate_to_english, auto_translate_if_needed
        
        # 测试文本
        test_text = "这是一个测试翻译功能的示例文本。"
        
        print(f"原始文本: {test_text}")
        
        # 测试translate_to_english函数
        print("\n测试translate_to_english函数:")
        translated_text = translate_to_english(test_text)
        print(f"翻译结果: {translated_text}")
        
        # 测试auto_translate_if_needed函数
        print("\n测试auto_translate_if_needed函数:")
        auto_translated = auto_translate_if_needed(test_text)
        print(f"自动翻译结果: {auto_translated}")
        
        # 测试使用英文文本（不应翻译）
        print("\n测试英文文本（不应翻译）:")
        english_text = "This is an English test text."
        non_translated = auto_translate_if_needed(english_text)
        print(f"原始英文: {english_text}")
        print(f"翻译结果: {non_translated}")
        
        return True
    except Exception as e:
        print(f"翻译测试失败: {str(e)}")
        # 尝试获取更详细的错误信息
        import traceback
        print("错误详情:")
        traceback.print_exc()
        return False

# 测试LLM客户端连接
def test_llm_connection():
    """直接测试LLM客户端连接"""
    try:
        from openai_llm import LLM
        
        print("\n测试LLM客户端连接:")
        llm = LLM()
        print(f"LLM客户端初始化成功，使用模型: {llm.model}")
        
        # 简单的测试消息
        messages = [
            {"role": "user", "content": "你好，这是一个测试。"}
        ]
        
        print("发送测试消息...")
        response = llm.chat(messages)
        print(f"响应成功: {response['choices'][0]['message']['content']}")
        
        return True
    except Exception as e:
        print(f"LLM客户端连接测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

# 主函数
def main():
    """主函数"""
    print("===== DeepSeek API 翻译功能测试 ======")
    
    # 打印配置信息
    print_config_info()
    
    # 修复openai_llm.py中的导入问题
    fix_openai_llm_import()
    
    # 测试翻译功能
    print("\n===== 开始测试翻译功能 =====")
    translation_success = test_translation()
    
    # 测试LLM客户端连接
    print("\n===== 开始测试LLM客户端连接 =====")
    connection_success = test_llm_connection()
    
    # 总结测试结果
    print("\n===== 测试总结 =====")
    print(f"翻译功能测试: {'成功' if translation_success else '失败'}")
    print(f"LLM客户端连接测试: {'成功' if connection_success else '失败'}")
    
    if translation_success and connection_success:
        print("\n🎉 所有测试通过！翻译功能正常工作。")
    else:
        print("\n❌ 测试未全部通过，请检查错误信息并修复问题。")
        
        # 提供可能的解决方案
        print("\n可能的解决方案：")
        print("1. 确保.env文件中的DEEPSEEK_API_KEY和OPENAI_BASE_URL配置正确")
        print("2. 检查网络连接是否正常，特别是是否能访问DeepSeek API")
        print("3. 确认API密钥是否有效")

if __name__ == "__main__":
    main()