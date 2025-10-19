import argparse
import alibabacloud_oss_v2 as oss
import os
import json
import uuid
import sys
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

"""
阿里云OSS文件上传脚本
功能：上传本地文件到OSS并返回公网URL，专为参考图片API使用而设计
注意：需要用户已开启OSS Bucket的公共读权限
"""

DEFAULT_CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'oss_config.json')

class OSSUploader:
    """OSS文件上传器类，提供独立集成的方法"""
    
    def __init__(self, config_path=None):
        """
        初始化OSS上传器
        参数:
            config_path: OSS配置文件路径，默认为脚本同目录下的oss_config.json
        """
        self.config_path = config_path or DEFAULT_CONFIG_PATH
        self.config = None
        self.client = None
    
    def load_config(self):
        """从环境变量或配置文件加载OSS配置信息"""
        try:
            # 首先尝试从环境变量加载配置
            oss_config = {
                'region': os.getenv('OSS_REGION'),
                'bucket_name': os.getenv('OSS_BUCKET_NAME'),
                'access_key_id': os.getenv('OSS_ACCESS_KEY_ID'),
                'access_key_secret': os.getenv('OSS_ACCESS_KEY_SECRET'),
                'endpoint': os.getenv('OSS_ENDPOINT')
            }
            
            # 检查是否所有必要的环境变量都已设置
            required_keys = ['region', 'bucket_name', 'access_key_id', 'access_key_secret', 'endpoint']
            has_all_env_vars = all(oss_config[key] for key in required_keys)
            
            if has_all_env_vars:
                # 所有环境变量都已设置，使用环境变量配置
                self.config = oss_config
                return self.config
            else:
                # 环境变量不完整，回退到从配置文件加载
                if not os.path.exists(self.config_path):
                    raise FileNotFoundError(f"配置文件不存在: {self.config_path}\n请先使用 --create_config 参数创建配置文件或设置OSS相关环境变量")
                
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    self.config = json.load(f)
                
                # 验证必要的配置项
                for key in required_keys:
                    if key not in self.config:
                        raise ValueError(f"配置文件缺少必要项: {key}")
                
                return self.config
        except json.JSONDecodeError as e:
            raise ValueError(f"配置文件格式错误: {str(e)}")
        except Exception as e:
            raise Exception(f"加载配置失败: {str(e)}")
    
    def create_client(self):
        """创建OSS客户端"""
        if not self.config:
            self.load_config()
            
        # 使用配置中的凭证创建凭证提供者
        credentials_provider = oss.credentials.StaticCredentialsProvider(
            access_key_id=self.config["access_key_id"],
            access_key_secret=self.config["access_key_secret"]
        )
        
        # 配置OSS客户端
        cfg = oss.config.load_default()
        cfg.credentials_provider = credentials_provider
        cfg.region = self.config["region"]
        cfg.endpoint = self.config["endpoint"]
        
        # 创建客户端
        self.client = oss.Client(cfg)
        return self.client
    
    def generate_unique_filename(self, file_path):
        """
        生成UUID唯一文件名，并添加/image路径前缀
        参数:
            file_path: 本地文件路径
        返回:
            唯一文件名 (image/UUID + 文件扩展名)
        """
        # 获取文件扩展名
        _, ext = os.path.splitext(file_path)
        ext = ext.lower()  # 保留扩展名的点号
        
        # 生成UUID并拼接扩展名，添加/image路径前缀
        unique_name = f"image/{uuid.uuid4()}{ext}"
        return unique_name
    
    def upload_file(self, file_path, object_name=None):
        """
        上传本地文件到OSS，使用UUID生成唯一文件名
        参数:
            file_path: 本地文件路径
            object_name: 自定义对象名称（可选，不提供则自动生成UUID名称）
        返回:
            public_url: 公网可访问的URL
        """
        if not self.client:
            self.create_client()
            
        # 检查文件是否存在
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"文件不存在: {file_path}")
        
        # 生成唯一文件名（如果没有提供）
        if not object_name:
            object_name = self.generate_unique_filename(file_path)
        else:
            # 如果用户提供了自定义对象名，确保它包含/image前缀
            if not object_name.startswith('image/'):
                object_name = f"image/{object_name}"
        
        try:
            # 上传文件
            print(f"开始上传文件: {file_path} 到 {self.config['bucket_name']}/{object_name}")
            result = self.client.put_object_from_file(
                oss.PutObjectRequest(
                    bucket=self.config["bucket_name"],
                    key=object_name
                ),
                file_path
            )
            
            # 检查上传是否成功
            if result.status_code == 200:
                print(f"✅ 文件上传成功")
                print(f"  - 状态码: {result.status_code}")
                print(f"  - 请求ID: {result.request_id}")
                print(f"  - ETag: {result.etag}")
                # 生成公网URL
                public_url = self.generate_public_url(object_name)
                return public_url
            else:
                raise Exception(f"文件上传失败，状态码: {result.status_code}")
        except Exception as e:
            print(f"❌ 上传文件失败: {str(e)}")
            raise
    
    def generate_public_url(self, object_name):
        """
        生成带签名的临时授权URL（包含Expires、OSSAccessKeyId和Signature参数）
        参数:
            object_name: OSS中的对象名称
        返回:
            public_url: 带签名的公网可访问URL，有效期为7天
        """
        if not self.config:
            self.load_config()
        
        if not self.client:
            self.create_client()

        try:
            base_url = f"https://{self.config['bucket_name']}.{self.config['endpoint']}/{object_name}"

            return base_url
        except Exception as e:
            print(f"生成预签名URL失败: {str(e)}")
            # 如果生成签名URL失败，回退到基本URL
            return ''
    

def create_config_template(config_path=None):
    """
    创建OSS配置文件模板
    参数:
        config_path: 配置文件保存路径
    """
    config_path = config_path or DEFAULT_CONFIG_PATH
    
    # 配置模板
    config_template = {
        "region": "oss-cn-beijing",  # 示例：OSS区域
        "bucket_name": "your-bucket-name",  # 示例：存储空间名称
        "access_key_id": "your-access-key-id",  # 示例：阿里云AccessKey ID
        "access_key_secret": "your-access-key-secret",  # 示例：阿里云AccessKey Secret
        "endpoint": "oss-cn-beijing.aliyuncs.com"  # 示例：OSS访问域名
    }
    
    # 保存配置文件
    try:
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config_template, f, ensure_ascii=False, indent=2)
        
        
        print(f"✅ 配置文件模板已创建: {config_path}")
        print("请编辑配置文件，填入您的阿里云OSS信息")
        return config_path
    except Exception as e:
        print(f"❌ 创建配置文件失败: {str(e)}")
        return None


def upload_to_oss_and_get_url(file_path):
    """
    独立集成方法：上传文件到OSS并获取公网URL
    参数:
        file_path: 本地文件路径
    返回:
        public_url: 公网可访问的URL，如果失败则返回None
    """
    try:
        uploader = OSSUploader()
        public_url = uploader.upload_file(file_path)
        return public_url
    except Exception as e:
        print(f"❌ 上传文件到OSS失败: {str(e)}")
        return None


def main():
    """命令行工具主函数"""
    # 创建命令行参数解析器
    parser = argparse.ArgumentParser(description="上传文件到阿里云OSS并返回公网URL（专为参考图片API使用设计）")
    parser.add_argument('--file_path', help='本地文件路径', required=False)
    parser.add_argument('--create_config', action='store_true', help='创建配置文件模板')
    parser.add_argument('--config_path', help='配置文件路径，默认为oss_config.json', required=False)
    
    args = parser.parse_args()
    
    # 创建配置文件模板
    if args.create_config:
        create_config_template(args.config_path)
        sys.exit(0)
    
    # 上传文件
    if args.file_path:
        try:
            uploader = OSSUploader(args.config_path)
            public_url = uploader.upload_file(args.file_path)
            
            print("\n🎉 上传完成！")
            print(f"公网可访问URL: {public_url}")
            print("\n注意：")
            print("1. 请确保您的OSS Bucket已开启公共读权限")
            print("2. 该URL可直接用于API的参考图片上传")
            
        except Exception as e:
            print(f"❌ 程序执行失败: {str(e)}")
            print("请检查配置文件和网络连接后重试")
            sys.exit(1)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    url = r'E:\AI项目\01-三角粥\jimeng-2025-09-21-5878-给这个小猫咪带上这个战术头盔.png'

    url = upload_to_oss_and_get_url(url)
    print(url)
