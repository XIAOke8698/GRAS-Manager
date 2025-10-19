import streamlit as st
from datetime import datetime
import uuid
import os
from dotenv import load_dotenv
from utils import submit_video_task, save_task_to_file, get_task_progress, update_task_progress, submit_nano_banana_task
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
    st.session_state.download_dir = "E:\AI项目\gen"  # 默认下载目录
# 页面标题
st.title("🎨 Nano Banana 图片生成")

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
if 'nano_uploaded_images' not in st.session_state:
    st.session_state.nano_uploaded_images = []

# 确保临时目录存在
if 'temp_dir_initialized' not in st.session_state:
    temp_dir = "temp_uploads"
    os.makedirs(temp_dir, exist_ok=True)
    st.session_state.temp_dir_initialized = True

# 检查API Key
if not st.session_state.get('api_key'):
    st.error("API Key未配置")
    st.stop()

# 主机地址映射
hosts = {
    "国内直连": "https://grsai.dakka.com.cn",
    "海外": "https://api.grsai.com"
}
base_url = hosts[st.session_state.host_type]

# 任务创建区域
with st.expander("📋 创建新图片生成任务", expanded=True):
    col1, col2 = st.columns(2)

    with col1:
        model = st.selectbox("模型选择", ["nano-banana-fast", "nano-banana"], index=0,
                             help="nano-banana-fast: 快速模式, nano-banana: 高质量模式")
        prompt = st.text_area("提示词", placeholder="输入图片描述提示词...", height=100,
                              help="描述您想要生成的图片内容")

        # 参考图片区域
        st.subheader("参考图片 (可选)")
        st.info("可添加多个参考图片URL或上传本地图片，用于图片生成参考")

        # 本地图片上传组件
        uploaded_files = st.file_uploader(
            "上传本地图片", 
            type=["jpg", "jpeg", "png", "gif"],
            accept_multiple_files=True,
            key="nano_local_image_uploader"
        )

        # 处理上传的本地图片
        if uploaded_files:
            for uploaded_file in uploaded_files:
                # 检查图片是否已上传
                if uploaded_file.name not in [img['name'] for img in st.session_state.nano_uploaded_images]:
                    try:
                        # 保存临时文件
                        temp_dir = "temp_uploads"
                        os.makedirs(temp_dir, exist_ok=True)
                        temp_file_path = os.path.join(temp_dir, f"nano_{uuid.uuid4()}_{uploaded_file.name}")
                        
                        with open(temp_file_path, "wb") as f:
                            f.write(uploaded_file.getbuffer())
                        
                        # 上传到OSS
                        with st.spinner(f"正在上传 {uploaded_file.name} 到OSS..."):
                            public_url = st.session_state.oss_uploader.upload_file(temp_file_path)
                        
                        # 存储上传的图片信息
                        st.session_state.nano_uploaded_images.append({
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
        if 'nano_ref_urls' not in st.session_state:
            st.session_state.nano_ref_urls = [""]

        # 合并上传的图片到参考图片列表
        if st.session_state.nano_uploaded_images:
            # 确保上传的图片URL已添加到参考URL列表
            uploaded_urls = [img['url'] for img in st.session_state.nano_uploaded_images]
            for url in uploaded_urls:
                if url not in st.session_state.nano_ref_urls:
                    st.session_state.nano_ref_urls.append(url)
            
            # 显示上传的图片缩略图
            if uploaded_urls:
                st.markdown("### 已上传的图片")
                cols = st.columns(3)  # 创建3列布局
                
                for i, img_info in enumerate(st.session_state.nano_uploaded_images):
                    with cols[i % 3]:  # 循环使用列
                        st.image(img_info['url'], caption=img_info['name'], use_column_width=True)
                        if st.button(f"移除 {img_info['name']}", key=f"nano_remove_uploaded_{i}"):
                            # 从上传图片列表中移除
                            st.session_state.nano_uploaded_images.pop(i)
                            # 从参考URL列表中移除
                            if img_info['url'] in st.session_state.nano_ref_urls:
                                st.session_state.nano_ref_urls.remove(img_info['url'])
                            # 删除临时文件
                            if os.path.exists(img_info['temp_path']):
                                os.remove(img_info['temp_path'])
                            st.rerun()

        # 显示并允许编辑参考图片URL
        for i, url in enumerate(st.session_state.nano_ref_urls):
            if url:  # 只显示非空的URL
                col_url, col_btn = st.columns([4, 1])
                with col_url:
                    st.session_state.nano_ref_urls[i] = st.text_input(
                        f"参考图片URL {i + 1}",
                        value=url,
                        placeholder="https://example.com/reference.png",
                        key=f"nano_ref_url_{i}"
                    )
                with col_btn:
                    if st.button("❌", key=f"nano_remove_ref_{i}"):
                        # 检查是否是上传的图片URL
                        uploaded_img = next((img for img in st.session_state.nano_uploaded_images if img['url'] == url), None)
                        if uploaded_img:
                            # 删除临时文件
                            if os.path.exists(uploaded_img['temp_path']):
                                os.remove(uploaded_img['temp_path'])
                            # 从上传图片列表中移除
                            st.session_state.nano_uploaded_images.remove(uploaded_img)
                        
                        # 从参考URL列表中移除
                        st.session_state.nano_ref_urls.pop(i)
                        st.rerun()

        # 添加更多参考图片URL的按钮
        if st.button("➕ 添加更多参考图片URL", key="nano_add_more"):
            st.session_state.nano_ref_urls.append("")
            st.rerun()

    with col2:
        # 高级选项
        with st.expander("高级选项"):
            webhook_url = st.text_input("Webhook URL (可选)",
                                        placeholder="https://example.com/callback",
                                        key="nano_webhook")
            shut_progress = st.checkbox("关闭进度回复", value=False, key="nano_shut_progress")

        # 提示信息
        st.info("""
        **Nano Banana 特点:**
        - 支持中文提示词
        - 可生成单张或多张图片
        - 参考图片可选，用于风格参考
        - 图片有效期为2小时
        """)

    if st.button("🚀 提交图片生成任务", key="nano_submit", use_container_width=True):
        if not prompt:
            st.error("请填写提示词")
        else:
            # 过滤空白的参考图片URL
            reference_urls = [url for url in st.session_state.nano_ref_urls if url.strip()]

            # 准备任务数据
            task_data = {
                'task_type': '图片生成',
                'model': model,
                'prompt': prompt,
                'urls': reference_urls if reference_urls else [],
                'webhook_url': webhook_url if webhook_url else "",
                'shut_progress': shut_progress
            }

            # 提交任务
            result, success, message = submit_nano_banana_task(
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
                st.session_state.nano_uploaded_images = []
                st.session_state.nano_ref_urls = [""]
            else:
                st.error(f"❌ {message}")

# 显示当前页面的任务
st.markdown("---")
st.subheader("本类型任务")

# 过滤出图片生成任务
image_tasks = [t for t in st.session_state.tasks if t.get('task_type') == '图片生成']
image_tasks.reverse()  # 最新的在前面


def render_nano_banana_task_card(task, display_index):
    """渲染Nano Banana任务卡片"""
    # 找到任务在全局列表中的实际索引
    try:
        task_index = st.session_state.tasks.index(task)
    except ValueError:
        # 如果任务不在列表中（可能已被删除），跳过渲染
        return

    # 生成唯一标识符
    import hashlib
    task_hash = hashlib.md5(f"{task['task_id']}_{display_index}".encode()).hexdigest()[:8]

    with st.container():
        st.markdown("---")

        # 任务头信息
        col1, col2, col3 = st.columns([3, 1, 1])

        with col1:
            st.markdown(f"### 🎨 {task.get('task_type', '图片生成')}任务")
            st.markdown(f"**任务ID:** `{task['task_id']}`")
            st.markdown(f"**提示词:** {task.get('prompt', '无')[:100]}{'...' if len(task.get('prompt', '')) > 100 else ''}")
            st.markdown(f"**提交时间:** {task['submit_time']}")
            st.markdown(f"**最后检查:** {task.get('last_check', '从未检查')}")

        with col2:
            # 状态标签
            status_color = {
                'submitted': 'blue',
                'running': 'orange',
                'succeeded': 'green',
                'failed': 'red'
            }.get(task.get('status', 'submitted'), 'gray')

            st.markdown(f"**状态:** :{status_color}[{task.get('status', 'submitted')}]")
            st.markdown(f"**进度:** {task.get('progress', 0)}%")
            st.markdown(f"**模型:** {task.get('model', 'nano-banana')}")

        with col3:
            # 操作按钮 - 使用唯一key
            if task.get('status') not in ['succeeded', 'failed']:
                if st.button("🔄 刷新", key=f"nano_refresh_{task['task_id']}_{task_hash}"):
                    updated_task = update_task_progress(task)
                    # 根据task_id找到任务并更新
                    for i, t in enumerate(st.session_state.tasks):
                        if t['task_id'] == task['task_id']:
                            st.session_state.tasks[i] = updated_task
                            break
                    save_task_to_file(st.session_state.tasks)
                    st.rerun()

            if st.button("🗑️ 删除", key=f"nano_delete_{task['task_id']}_{task_hash}"):
                # 根据task_id找到任务并删除
                st.session_state.tasks = [t for t in st.session_state.tasks if t['task_id'] != task['task_id']]
                save_task_to_file(st.session_state.tasks)
                st.rerun()

        # 进度条
        progress_value = task.get('progress', 0) / 100
        st.progress(progress_value, text=f"进度: {task.get('progress', 0)}%")

        # 错误信息显示
        if task.get('status') == 'failed':
            st.error("❌ 任务失败")

            if task.get('failure_reason'):
                st.markdown(f"**失败原因:** {task['failure_reason']}")

            if task.get('error'):
                st.markdown("**错误详情:**")
                st.code(task['error'])

        # 展开详细信息
        with st.expander("📋 任务详细信息", expanded=False):
            # 提示词
            st.markdown("**完整提示词:**")
            st.info(task.get('prompt', '无'))

            # 参考图片
            if task.get('urls'):
                st.markdown("**参考图片:**")
                for j, img_url in enumerate(task.get('urls', [])):
                    if img_url:
                        st.markdown(f"{j + 1}. [{img_url}]({img_url})")

            # 模型信息
            st.markdown(f"**模型:** {task.get('model', 'nano-banana')}")

        # 完成后的图片预览和下载区域
        if task.get('status') == 'succeeded':
            # 尝试从results获取数据，如果为空则从last_api_response获取
            results = task.get('results', [])
            if not results and task.get('last_api_response', {}).get('data', {}).get('results'):
                results = task.get('last_api_response', {}).get('data', {}).get('results', [])
                
            st.success("✅ 任务完成！")

            # 图片预览
            st.subheader("🖼️ 生成结果")

            for j, result in enumerate(results):
                col_img, col_info = st.columns([2, 3])

                with col_img:
                    # 图片预览
                    if result.get('url'):
                        try:
                            st.image(result['url'], caption=f"图片 {j + 1}", use_container_width=True)
                        except Exception as e:
                            st.warning(f"图片加载失败: {str(e)}")
                            st.markdown(f"图片链接: [点击查看]({result['url']})")

                with col_info:
                    # 图片信息和下载
                    st.markdown(f"**图片 {j + 1}**")
                    if result.get('content'):
                        st.info(f"**描述:** {result['content']}")

                    # 下载按钮
                    if result.get('url'):
                        if st.button(f"📥 下载图片 {j + 1}", key=f"nano_download_{task['task_id']}_{j}_{task_hash}"):
                            from utils import download_image
                            if download_image(result['url'], task['task_id'], j):
                                st.success("下载链接已生成，请点击上方下载按钮")

                st.markdown("---")

        # 重新生成选项
        if task.get('status') == 'succeeded':
            st.subheader("🔄 重新生成")
            if st.button("使用相同参数重新生成", key=f"nano_regenerate_{task['task_id']}_{task_hash}"):
                # 准备重新生成的任务数据
                regenerate_data = {
                    'task_type': '图片生成',
                    'model': task.get('model', 'nano-banana-fast'),
                    'prompt': task.get('prompt', ''),
                    'urls': task.get('urls', []),
                    'webhook_url': task.get('webhook_url', ''),
                    'shut_progress': task.get('shut_progress', False)
                }

                # 提交重新生成任务
                result, success, message = submit_nano_banana_task(
                    api_key, base_url, regenerate_data
                )

                if success:
                    st.session_state.tasks.append(result)
                    save_task_to_file(st.session_state.tasks)
                    st.success(f"✅ 重新生成任务提交成功! 任务ID: `{result['task_id']}`")
                    st.rerun()
                else:
                    st.error(f"❌ 重新生成失败: {message}")


if image_tasks:
    for i, task in enumerate(image_tasks):
        render_nano_banana_task_card(task, i)
else:
    st.info("暂无图片生成任务")


