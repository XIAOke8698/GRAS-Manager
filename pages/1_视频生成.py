import streamlit as st
from datetime import datetime
import uuid
import os
from dotenv import load_dotenv
from utils import submit_video_task, save_task_to_file, get_task_progress, update_task_progress, auto_translate_if_needed, translate_to_english
from upload_to_oss_with_url import OSSUploader

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
st.title("🎥 视频生成")

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
if 'uploaded_images' not in st.session_state:
    st.session_state.uploaded_images = []

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
base_url = hosts[st.session_state.host_type]

# 任务创建区域
with st.expander("📋 创建新视频生成任务", expanded=True):
    col1, col2 = st.columns(2)

    with col1:
        model = st.selectbox("模型选择", ["veo3-fast", "veo3-pro"], index=0)
        
        # 初始化会话状态
        if 'enable_auto_translate' not in st.session_state:
            st.session_state.enable_auto_translate = True
        if 'translated_prompt' not in st.session_state:
            st.session_state.translated_prompt = ""
        
        # 自动翻译复选框
        st.session_state.enable_auto_translate = st.checkbox(
            "启用自动翻译", 
            value=st.session_state.enable_auto_translate,
            help="勾选后，系统会自动将您输入的中文提示词翻译成英文"
        )
        
        # 中文提示词输入
        chinese_prompt = st.text_area(
            "提示词", 
            placeholder="输入提示词（支持中文，会自动翻译为英文）", 
            height=100,
            help="视频内容描述，若启用自动翻译，系统会将中文翻译为英文"
        )
        
        # 翻译结果区域
        translated_prompt = ""
        if st.session_state.enable_auto_translate and chinese_prompt:
            # 检查是否需要重新翻译
            if ('last_chinese_prompt' not in st.session_state or 
                st.session_state.last_chinese_prompt != chinese_prompt or 
                not st.session_state.translated_prompt):
                
                with st.spinner("正在翻译提示词..."):
                    try:
                        # 调用翻译函数
                        st.session_state.translated_prompt = auto_translate_if_needed(chinese_prompt)
                        st.session_state.last_chinese_prompt = chinese_prompt
                    except Exception as e:
                        st.error(f"翻译失败: {str(e)}")
                        st.session_state.translated_prompt = ""
                        st.stop()  # 阻断后续操作
                    
            translated_prompt = st.session_state.translated_prompt
            
            # 显示翻译结果和重新生成按钮
            with st.expander("翻译结果", expanded=True):
                col1, col2 = st.columns([4, 1])
                with col1:
                    st.text_area(
                        "英文提示词", 
                        value=translated_prompt, 
                        height=80,
                        disabled=False,
                        key="translated_prompt_display"
                    )
                with col2:
                    if st.button("🔄 重新翻译", key="retranslate_btn", use_container_width=True):
                        try:
                            # 清除缓存，触发重新翻译
                            if 'last_chinese_prompt' in st.session_state:
                                del st.session_state.last_chinese_prompt
                            st.session_state.translated_prompt = ""
                            # 立即调用翻译函数而不是通过rerun来触发
                            with st.spinner("正在重新翻译..."):
                                st.session_state.translated_prompt = auto_translate_if_needed(chinese_prompt)
                                st.session_state.last_chinese_prompt = chinese_prompt
                            st.rerun()
                        except Exception as e:
                            st.error(f"翻译失败: {str(e)}")
                            st.session_state.translated_prompt = ""
                            st.stop()  # 阻断后续操作
        else:
            # 如果未启用自动翻译，直接使用输入作为英文提示词
            translated_prompt = chinese_prompt

        # 参考图片列表（多个）
        st.subheader("参考图片 (可选)")
        st.info("可添加多个参考图片URL，用于内容参考（非首帧）")

        # 本地图片上传组件
        uploaded_files = st.file_uploader(
            "上传本地图片", 
            type=["jpg", "jpeg", "png", "gif"],
            accept_multiple_files=True,
            key="local_image_uploader"
        )

        # 处理上传的本地图片
        if uploaded_files:
            for uploaded_file in uploaded_files:
                # 检查图片是否已上传
                if uploaded_file.name not in [img['name'] for img in st.session_state.uploaded_images]:
                    try:
                        # 保存临时文件
                        temp_dir = "temp_uploads"
                        os.makedirs(temp_dir, exist_ok=True)
                        temp_file_path = os.path.join(temp_dir, f"{uuid.uuid4()}_{uploaded_file.name}")
                        
                        with open(temp_file_path, "wb") as f:
                            f.write(uploaded_file.getbuffer())
                        
                        # 上传到OSS
                        with st.spinner(f"正在上传 {uploaded_file.name} 到OSS..."):
                            public_url = st.session_state.oss_uploader.upload_file(temp_file_path)
                        
                        # 存储上传的图片信息
                        st.session_state.uploaded_images.append({
                            'name': uploaded_file.name,
                            'url': public_url,
                            'temp_path': temp_file_path
                        })
                        
                        # 显示成功消息
                        st.success(f"图片 {uploaded_file.name} 上传成功！")
                    except Exception as e:
                        st.error(f"上传图片 {uploaded_file.name} 失败: {str(e)}")
                        continue
            
            # 刷新页面以显示上传的图片
            if uploaded_files:
                st.rerun()

        # 动态添加参考图片URL
        if 'reference_urls' not in st.session_state:
            st.session_state.reference_urls = [""]

        # 合并上传的图片到参考图片列表
        if st.session_state.uploaded_images:
            # 确保上传的图片URL已添加到参考URL列表
            uploaded_urls = [img['url'] for img in st.session_state.uploaded_images]
            for url in uploaded_urls:
                if url not in st.session_state.reference_urls:
                    st.session_state.reference_urls.append(url)
            
            # 显示上传的图片缩略图
            if uploaded_urls:
                st.markdown("### 已上传的图片")
                cols = st.columns(3)  # 创建3列布局
                
                for i, img_info in enumerate(st.session_state.uploaded_images):
                    with cols[i % 3]:  # 循环使用列
                        st.image(img_info['url'], caption=img_info['name'], use_column_width=True)
                        if st.button(f"移除 {img_info['name']}", key=f"remove_uploaded_{i}"):
                            # 从上传图片列表中移除
                            st.session_state.uploaded_images.pop(i)
                            # 从参考URL列表中移除
                            if img_info['url'] in st.session_state.reference_urls:
                                st.session_state.reference_urls.remove(img_info['url'])
                            # 删除临时文件
                            if os.path.exists(img_info['temp_path']):
                                os.remove(img_info['temp_path'])
                            st.rerun()

        # 显示并允许编辑参考图片URL
        for i, url in enumerate(st.session_state.reference_urls):
            if url:  # 只显示非空的URL
                col_url, col_btn = st.columns([4, 1])
                with col_url:
                    st.session_state.reference_urls[i] = st.text_input(
                        f"参考图片URL {i + 1}",
                        value=url,
                        placeholder="https://example.com/image.png",
                        key=f"ref_url_{i}"
                    )
                with col_btn:
                    if st.button("❌", key=f"remove_ref_{i}"):
                        # 检查是否是上传的图片URL
                        uploaded_img = next((img for img in st.session_state.uploaded_images if img['url'] == url), None)
                        if uploaded_img:
                            # 删除临时文件
                            if os.path.exists(uploaded_img['temp_path']):
                                os.remove(uploaded_img['temp_path'])
                            # 从上传图片列表中移除
                            st.session_state.uploaded_images.remove(uploaded_img)
                        
                        # 从参考URL列表中移除
                        st.session_state.reference_urls.pop(i)
                        st.rerun()

        # 添加更多参考图片URL的按钮
        if st.button("➕ 添加更多参考图片URL"):
            st.session_state.reference_urls.append("")
            st.rerun()

    with col2:
        # 首帧图片上传区域
        st.subheader("首帧图片")
        st.info("视频的第一帧图片，可以是本地上传或公网可访问的URL")
        
        # 首帧图片上传选项
        first_frame_option = st.radio(
            "首帧图片来源",
            ["上传本地图片", "输入图片URL"],
            key="first_frame_option"
        )
        
        first_frame_url = ""
        
        if first_frame_option == "上传本地图片":
            first_frame_file = st.file_uploader(
                "选择首帧图片",
                type=["jpg", "jpeg", "png"],
                accept_multiple_files=False,
                key="first_frame_uploader"
            )
            
            if first_frame_file:
                try:
                    # 保存临时文件
                    temp_dir = "temp_uploads"
                    os.makedirs(temp_dir, exist_ok=True)
                    temp_file_path = os.path.join(temp_dir, f"first_frame_{uuid.uuid4()}_{first_frame_file.name}")
                    
                    with open(temp_file_path, "wb") as f:
                        f.write(first_frame_file.getbuffer())
                    
                    # 上传到OSS
                    with st.spinner(f"正在上传首帧图片 {first_frame_file.name} 到OSS..."):
                        first_frame_url = st.session_state.oss_uploader.upload_file(temp_file_path)
                    
                    # 显示上传的图片预览
                    st.image(first_frame_url, caption="上传的首帧图片", use_column_width=True)
                    st.success(f"首帧图片 {first_frame_file.name} 上传成功！")
                    
                    # 存储首帧图片临时路径，便于清理
                    st.session_state.first_frame_temp_path = temp_file_path
                except Exception as e:
                    st.error(f"上传首帧图片失败: {str(e)}")
        else:
            first_frame_url = st.text_input(
                "首帧图片URL",
                placeholder="https://example.com/firstframe.png",
                key="first_frame_url_input"
            )
            
            # 如果输入了URL，尝试显示预览
            if first_frame_url:
                try:
                    st.image(first_frame_url, caption="首帧图片预览", use_column_width=True)
                except:
                    st.warning("无法预览该图片，请检查URL是否正确")

        # 完整的比例选项
        aspect_ratio = st.selectbox("视频比例", ["16:9", "9:16", "1:1", "4:3", "auto"], index=0)

        # 高级选项
        with st.expander("高级选项"):
            webhook_url = st.text_input("Webhook URL (可选)", placeholder="https://example.com/callback")
            shut_progress = st.checkbox("关闭进度回复", value=False)

    if st.button("🚀 提交生成任务", use_container_width=True):
        if not translated_prompt:
            st.error("请填写提示词")
        else:
            # 过滤空白的参考图片URL
            reference_images = [url for url in st.session_state.reference_urls if url.strip()]

            # 准备任务数据
            task_data = {
                'task_type': '视频生成',
                'model': model,
                'prompt': translated_prompt,
                'reference_images': reference_images,
                'first_frame_url': first_frame_url if first_frame_url else "",
                'aspect_ratio': aspect_ratio,
                'webhook_url': webhook_url,
                'shut_progress': shut_progress
            }
            
            # 添加原始中文提示词和翻译状态信息（便于调试和记录）
            task_data['original_prompt'] = chinese_prompt
            task_data['translation_enabled'] = st.session_state.enable_auto_translate

            # 提交任务
            result, success, message = submit_video_task(
                task_data
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
                
                # 清空上传的图片列表和参考URL列表
                st.session_state.uploaded_images = []
                st.session_state.reference_urls = [""]
            else:
                st.error(f"❌ {message}")

# 显示当前页面的任务（可选）
st.markdown("---")
st.subheader("本类型任务")

# 过滤出视频生成任务
video_tasks = [t for t in st.session_state.tasks if t.get('task_type') == '视频生成']
video_tasks.reverse()  # 最新的在前面

if video_tasks:
    for i, task in enumerate(video_tasks):
        # 使用主页的任务卡片渲染函数
        from app import render_task_card

        render_task_card(task, i)
else:
    st.info("暂无视频生成任务")