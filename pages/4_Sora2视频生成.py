import streamlit as st
from datetime import datetime
import uuid
import os
from dotenv import load_dotenv
from utils import submit_sora2_task, save_task_to_file, get_task_progress, update_task_progress, auto_translate_if_needed, translate_to_english
from upload_to_oss_with_url import OSSUploader
from app import hosts

# 加载环境变量
load_dotenv()

# 确保session_state已初始化
if 'tasks' not in st.session_state:
    from utils import load_tasks_from_file
    st.session_state.tasks = load_tasks_from_file()
if 'api_key' not in st.session_state:
    # 优先从环境变量加载API_KEY
    st.session_state.api_key = os.getenv('API_KEY', '')
if 'host_type' not in st.session_state:
    st.session_state.host_type = "国内直连"
if 'auto_refresh' not in st.session_state:
    st.session_state.auto_refresh = True
if 'download_dir' not in st.session_state:
    st.session_state.download_dir = os.getenv('DOWNLOAD_DIR', './gen')  # 默认下载目录

# 页面标题
st.title("🎥 Sora2视频生成")

# 初始化OSS上传器
if 'oss_uploader' not in st.session_state:
    try:
        st.session_state.oss_uploader = OSSUploader()
        # 加载配置以验证OSS连接是否正常
        st.session_state.oss_uploader.load_config()
        st.session_state.oss_uploader.create_client()
    except Exception as e:
        st.error(f"OSS上传器初始化失败: {str(e)}")

# 初始化上传的图片会话状态
if 'sora2_uploaded_images' not in st.session_state:
    st.session_state.sora2_uploaded_images = []

# 确保临时目录存在
if 'temp_dir_initialized' not in st.session_state:
    temp_dir = "temp_uploads"
    os.makedirs(temp_dir, exist_ok=True)
    st.session_state.temp_dir_initialized = True

# 检查API Key
if not st.session_state.get('api_key'):
    st.error("API Key未配置，请在.env文件中设置API_KEY")
    st.stop()

# 主机地址映射
hosts = {
    "国内直连": "https://grsai.dakka.com.cn",
    "海外": "https://api.grsai.com"
}

# 任务创建区域
with st.expander("📋 创建新Sora2视频生成任务", expanded=True):
    col1, col2 = st.columns(2)

    with col1:
        # Sora2模型是固定的
        st.markdown("**模型**: sora-2")
        
        # 初始化翻译相关的session_state
        if 'enable_auto_translate' not in st.session_state:
            st.session_state.enable_auto_translate = True
        if 'translated_prompt' not in st.session_state:
            st.session_state.translated_prompt = ""
        if 'last_chinese_prompt' not in st.session_state:
            st.session_state.last_chinese_prompt = ""
        
        # 启用自动翻译复选框
        st.session_state.enable_auto_translate = st.checkbox(
            "启用自动翻译", 
            value=st.session_state.enable_auto_translate,
            help="勾选后可以输入中文，系统会自动翻译成英文"
        )
        
        # 中文提示词输入框
        chinese_prompt = st.text_area(
            "提示词" + (" (中文)" if st.session_state.enable_auto_translate else " (英文)"),
            placeholder="输入提示词...", 
            height=100,
            help="视频内容描述，如果启用了自动翻译，这里可以输入中文"
        )
        
        # 英文翻译结果展示区域
        translated_prompt = chinese_prompt  # 默认不翻译
        if st.session_state.enable_auto_translate:
            # 检查是否需要重新翻译
            if ('last_chinese_prompt' not in st.session_state or 
                st.session_state.last_chinese_prompt != chinese_prompt or 
                not st.session_state.translated_prompt):
                
                if chinese_prompt.strip():
                    with st.spinner("正在翻译提示词..."):
                        try:
                            # 调用翻译函数
                            translated_prompt = translate_to_english(chinese_prompt)
                            st.session_state.translated_prompt = translated_prompt
                            st.session_state.last_chinese_prompt = chinese_prompt
                        except Exception as e:
                            st.error(f"翻译失败: {str(e)}")
                            translated_prompt = ""  # 设置为空，防止使用错误的翻译结果
                            st.stop()  # 阻断后续操作
                else:
                    translated_prompt = ""
                    st.session_state.translated_prompt = ""
            else:
                # 使用缓存的翻译结果
                translated_prompt = st.session_state.translated_prompt
            
            # 显示翻译结果和重新翻译按钮
            with st.expander("翻译结果", expanded=True):
                col_translate1, col_translate2 = st.columns([5, 1])
                with col_translate1:
                    translated_prompt = st.text_area(
                        "英文提示词", 
                        value=translated_prompt,
                        placeholder="翻译结果将显示在这里...",
                        height=80,
                        help="你可以手动编辑翻译结果"
                    )
                with col_translate2:
                    st.markdown(" ")  # 调整垂直位置
                    if st.button("🔄 重新翻译", key="retranslate_sora2"):
                        if chinese_prompt.strip():
                            with st.spinner("正在重新翻译..."):
                                try:
                                    translated_prompt = translate_to_english(chinese_prompt)
                                    st.session_state.translated_prompt = translated_prompt
                                    st.session_state.last_chinese_prompt = chinese_prompt
                                except Exception as e:
                                    st.error(f"翻译失败: {str(e)}")
                                    translated_prompt = ""
                                    st.stop()  # 阻断后续操作
                            st.rerun()

        # 参考图片上传区域
        st.subheader("参考图片 (可选)")
        st.info("上传一张参考图片，用于内容参考")

        # 本地图片上传组件
        uploaded_file = st.file_uploader(
            "上传本地图片", 
            type=["jpg", "jpeg", "png"],
            accept_multiple_files=False,
            key="sora2_local_image_uploader"
        )

        reference_image_url = ""
        
        # 处理上传的本地图片
        if uploaded_file:
            try:
                # 保存临时文件
                temp_dir = "temp_uploads"
                os.makedirs(temp_dir, exist_ok=True)
                temp_file_path = os.path.join(temp_dir, f"sora2_ref_{uuid.uuid4()}_{uploaded_file.name}")
                
                with open(temp_file_path, "wb") as f:
                    f.write(uploaded_file.getbuffer())
                
                # 上传到OSS
                with st.spinner(f"正在上传 {uploaded_file.name} 到OSS..."):
                    reference_image_url = st.session_state.oss_uploader.upload_file(temp_file_path)
                
                # 存储上传的图片信息
                st.session_state.sora2_uploaded_images = [{
                    'name': uploaded_file.name,
                    'url': reference_image_url,
                    'temp_path': temp_file_path
                }]
                
                # 显示成功消息和预览
                st.success(f"图片 {uploaded_file.name} 上传成功！")
                st.image(reference_image_url, caption="上传的参考图片", use_column_width=True)
            except Exception as e:
                st.error(f"上传图片 {uploaded_file.name} 失败: {str(e)}")
        
        # 也可以直接输入图片URL
        st.markdown("或者直接输入图片URL:")
        url_input = st.text_input(
            "参考图片URL",
            placeholder="https://example.com/image.png",
            key="sora2_ref_url_input"
        )
        
        # 如果输入了URL，则使用URL
        if url_input:
            reference_image_url = url_input
            try:
                st.image(reference_image_url, caption="参考图片预览", use_column_width=True)
            except:
                st.warning("无法预览该图片，请检查URL是否正确")
        
        # 移除参考图片按钮
        if st.session_state.sora2_uploaded_images:
            if st.button("移除上传的图片", key="remove_sora2_ref_image"):
                # 删除临时文件
                img_info = st.session_state.sora2_uploaded_images[0]
                if os.path.exists(img_info['temp_path']):
                    os.remove(img_info['temp_path'])
                # 清空上传图片列表
                st.session_state.sora2_uploaded_images = []
                # 清空URL输入
                st.session_state[f"sora2_ref_url_input"] = ""
                st.rerun()

    with col2:
        # Sora2特定选项
        # 视频比例
        aspect_ratio = st.selectbox(
            "视频比例", 
            ["9:16", "16:9"], 
            index=0, 
            help="支持的比例: 9:16 或 16:9"
        )
        
        # 视频时长
        duration = st.selectbox(
            "视频时长 (秒)", 
            [10, 15], 
            index=0, 
            help="支持的时长: 10秒 或 15秒"
        )
        
        # 视频清晰度
        size = st.selectbox(
            "视频清晰度", 
            ["small", "large"], 
            index=0, 
            help="small: 标准清晰度, large: 高清晰度"
        )

        # 高级选项
        with st.expander("高级选项"):
            webhook_url = st.text_input("Webhook URL (可选)", placeholder="https://example.com/callback")
            shut_progress = st.checkbox("关闭进度回复", value=False)

    if st.button("🚀 提交Sora2生成任务", use_container_width=True):
        if not translated_prompt:
            st.error("请填写提示词")
        else:
            # 准备任务数据
            task_data = {
                'task_type': 'Sora2视频生成',
                'model': 'sora-2',
                'prompt': translated_prompt,
                'reference_image_url': reference_image_url if reference_image_url else "",
                'aspect_ratio': aspect_ratio,
                'duration': duration,
                'size': size,
                'webhook_url': webhook_url,
                'shut_progress': shut_progress
            }
            
            # 添加原始中文提示词和翻译状态信息
            task_data['original_prompt'] = chinese_prompt
            task_data['translation_enabled'] = st.session_state.enable_auto_translate

            # 提交任务
            result, success, message = submit_sora2_task(
                task_data, hosts[st.session_state.host_type]
            )

            if success:
                # 保存到全局任务列表
                st.session_state.tasks.append(result)
                save_task_to_file(st.session_state.tasks)

                st.success(f"✅ {message}! 任务ID: `{result['task_id']}`")
                st.balloons()
                
                # 清理临时文件
                from utils import cleanup_temp_files
                cleanup_temp_files()
                
                # 清空上传的图片列表
                st.session_state.sora2_uploaded_images = []
            else:
                st.error(f"❌ {message}")

# 显示当前页面的任务
st.markdown("---")
st.subheader("Sora2视频生成任务")

# 过滤出Sora2视频生成任务
sora2_tasks = [t for t in st.session_state.tasks if t.get('task_type') == 'Sora2视频生成']
sora2_tasks.reverse()  # 最新的在前面

if sora2_tasks:
    for i, task in enumerate(sora2_tasks):
        # 使用主页的任务卡片渲染函数
        from app import render_task_card

        render_task_card(task, i)
else:
    st.info("暂无Sora2视频生成任务")