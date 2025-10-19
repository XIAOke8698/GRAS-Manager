import streamlit as st
import json
import os
from datetime import datetime
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 页面配置
st.set_page_config(
    page_title="AI生成工作台",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 导入工具函数
from utils import load_tasks_from_file, save_task_to_file, update_task_progress, download_video, update_all_tasks_progress

# 初始化session_state
def initialize_session_state():
    """初始化全局状态"""
    if 'tasks' not in st.session_state:
        st.session_state.tasks = load_tasks_from_file()
    if 'api_key' not in st.session_state:
        # 优先从环境变量加载API_KEY
        st.session_state.api_key = os.getenv('API_KEY', '')
    if 'host_type' not in st.session_state:
        st.session_state.host_type = "国内直连"
    if 'auto_refresh' not in st.session_state:
        st.session_state.auto_refresh = True
    if 'download_dir' not in st.session_state:
        st.session_state.download_dir = "E:\AI项目\gen"


initialize_session_state()

# 主机地址映射
hosts = {
    "国内直连": "https://grsai.dakka.com.cn",
    "海外": "https://api.grsai.com"
}

# 侧边栏配置
st.sidebar.title("🎬 AI生成工作台")
st.sidebar.markdown("---")

# 全局配置区域
st.sidebar.subheader("⚙️ 全局配置")
api_key = st.sidebar.text_input("API Key", value=os.getenv('API_KEY', ''), type="password")
st.session_state.api_key = api_key

host_type = st.sidebar.radio("API节点", ["国内直连", "海外"],
                             index=0 if st.session_state.host_type == "国内直连" else 1)
st.session_state.host_type = host_type

st.session_state.auto_refresh = st.sidebar.checkbox("🔄 自动刷新进度", value=st.session_state.auto_refresh)

# 任务统计
st.sidebar.markdown("---")
st.sidebar.subheader("📈 任务统计")
if st.session_state.tasks:
    total_tasks = len(st.session_state.tasks)
    completed_tasks = len([t for t in st.session_state.tasks if t.get('status') == 'succeeded'])
    failed_tasks = len([t for t in st.session_state.tasks if t.get('status') == 'failed'])
    running_tasks = len([t for t in st.session_state.tasks if t.get('status') in ['submitted', 'running']])

    st.sidebar.metric("总任务数", total_tasks)
    st.sidebar.metric("已完成", completed_tasks)
    st.sidebar.metric("进行中", running_tasks)
    st.sidebar.metric("失败", failed_tasks)
    
    # 添加简单的柱状统计图
    import pandas as pd
    import matplotlib.pyplot as plt
    
    # 设置中文字体
    plt.rcParams["font.family"] = ["SimHei", "WenQuanYi Micro Hei", "Heiti TC"]
    
    # 创建数据
    status_data = pd.DataFrame({
        '状态': ['已完成', '进行中', '失败'],
        '数量': [completed_tasks, running_tasks, failed_tasks]
    })
    
    # 创建柱状图
    fig, ax = plt.subplots(figsize=(4, 3))
    bars = ax.bar(status_data['状态'], status_data['数量'], color=['green', 'orange', 'red'])
    
    # 添加数据标签
    for bar in bars:
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height, f'{int(height)}',
                ha='center', va='bottom')
    
    ax.set_title('任务状态分布')
    ax.set_ylim(0, max(status_data['数量']) * 1.1 if max(status_data['数量']) > 0 else 1)
    
    # 在侧边栏中显示图表
    st.sidebar.pyplot(fig)
else:
    st.sidebar.info("暂无任务数据")

# 主页面内容
st.title("🎯 AI生成任务管理中心")
st.markdown("欢迎使用AI生成工作台！请使用左侧导航栏选择不同的生成类型。")

# 全局任务管理界面
st.subheader("📊 所有任务管理")


def render_task_card(task, display_index):
    """渲染单个任务卡片"""
    try:
        task_index = st.session_state.tasks.index(task)  # 获取实际索引
    except ValueError:
        # 如果任务不在列表中（可能已被删除），跳过渲染
        return

    # 生成唯一标识符，避免页面重载时的key冲突
    import hashlib
    task_hash = hashlib.md5(f"{task['task_id']}_{display_index}".encode()).hexdigest()[:8]

    # 使用容器组织任务卡片
    with st.container(border=True):
        st.markdown("### 任务信息")
        
        # 任务头信息
        col1, col2, col3 = st.columns([3, 1, 1])

        with col1:
            # 任务类型和ID
            task_type_emoji = {
                "视频生成": "🎥",
                "图片生成": "🖼️",
                "文生图": "🖼️",
                "图生视频": "🎬"
            }.get(task.get('task_type', '视频生成'), '📋')

            st.markdown(f"**{task_type_emoji} {task.get('task_type', '视频生成')}任务**")
            st.markdown(f"**任务ID:** `{task['task_id']}`")
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

            # 显示任务参数
            if task.get('aspect_ratio'):
                st.markdown(f"**比例:** {task['aspect_ratio']}")
            if task.get('model'):
                st.markdown(f"**模型:** {task['model']}")

        with col3:
            # 操作按钮组
            with st.container():
                # 刷新按钮 - 使用任务ID和哈希值确保唯一性
                if task.get('status') not in ['succeeded', 'failed']:
                    if st.button("🔄 刷新", key=f"refresh_{task['task_id']}_{task_hash}"):
                        from utils import update_task_progress
                        updated_task = update_task_progress(
                            task
                        )
                        # 根据task_id找到任务并更新
                        for i, t in enumerate(st.session_state.tasks):
                            if t['task_id'] == task['task_id']:
                                st.session_state.tasks[i] = updated_task
                                break
                        save_task_to_file(st.session_state.tasks)
                        st.rerun()
                
                # 删除按钮 - 使用任务ID和哈希值确保唯一性
                if st.button("🗑️ 删除", key=f"delete_{task['task_id']}_{task_hash}"):
                    # 根据task_id找到任务并删除
                    st.session_state.tasks = [t for t in st.session_state.tasks if t['task_id'] != task['task_id']]
                    save_task_to_file(st.session_state.tasks)
                    st.rerun()

        # 进度条
        progress_value = task.get('progress', 0) / 100
        st.progress(progress_value, text=f"进度: {task.get('progress', 0)}%")

        # 错误信息显示（增强）
        if task.get('status') == 'failed':
            with st.container(border=True):
                st.error("❌ 任务失败")

                # 显示详细的错误信息
                if task.get('failure_reason'):
                    st.markdown(f"**失败原因:** {task['failure_reason']}")

                if task.get('error'):
                    st.markdown("**错误详情:**")
                    st.code(task['error'])

                # 显示API响应日志（用于调试）
                if task.get('last_api_response'):
                    with st.expander("📋 API响应详情（调试）"):
                        st.json(task['last_api_response'])

        # 展开详细信息
        with st.expander("📋 任务详细信息", expanded=False):
            # 提示词和参数
            st.markdown("**提示词:**")
            st.info(task.get('prompt', '无')[:200] + ('...' if len(task.get('prompt', '')) > 200 else ''))

            # 参考图片列表
            if task.get('reference_images'):
                st.markdown("**参考图片:**")
                for j, img_url in enumerate(task.get('reference_images', [])):
                    if img_url:
                        st.markdown(f"{j + 1}. [{img_url}]({img_url})")

            # 首帧图片
            if task.get('first_frame_url'):
                st.markdown("**首帧图片:**")
                try:
                    st.image(task['first_frame_url'], caption="首帧图片", use_container_width=True)
                except Exception as e:
                    st.markdown(f"[{task['first_frame_url']}]({task['first_frame_url']})")

            # 模型和参数
            col_params1, col_params2 = st.columns(2)
            with col_params1:
                if task.get('model'):
                    st.markdown(f"**模型:** {task['model']}")
                if task.get('aspect_ratio'):
                    st.markdown(f"**画面比例:** {task['aspect_ratio']}")

            with col_params2:
                if task.get('duration'):
                    st.markdown(f"**视频时长:** {task['duration']}秒")

        # 完成后的预览和下载区域
        if task.get('status') == 'succeeded':
            st.success("✅ 任务完成！")
            
            # 视频任务处理
            if task.get('task_type') in ['视频生成', '图生视频', 'Sora2视频生成']:
                # 获取视频URL（处理不同存储位置）
                video_url = task.get('video_url')
                # 如果video_url为空但任务类型是Sora2视频生成，尝试从results中获取
                if not video_url and task.get('task_type') == 'Sora2视频生成' and task.get('results') and len(task.get('results')) > 0:
                    video_url = task.get('results')[0].get('url')
                
                if video_url:
                    with st.container(border=True):
                        st.subheader("🎬 视频预览")
                        try:
                            st.video(video_url)
                        except Exception as e:
                            st.warning(f"视频预览加载失败: {str(e)}")
                            st.markdown(f"视频链接: [点击查看]({video_url})")

                        # 下载区域
                        st.subheader("📥 下载选项")
                        # 下载按钮 - 使用任务ID和哈希值确保唯一性
                        if task.get('downloaded'):
                            st.info(f"视频已下载至本地: {task.get('local_video_path', '未知路径')}")
                            # 提供打开文件夹按钮
                            if st.button("打开下载文件夹", key=f"open_folder_{task['task_id']}_{task_hash}"):
                                import os
                                import subprocess
                                try:
                                    # 根据操作系统打开文件夹
                                    if os.name == 'nt':  # Windows
                                        subprocess.Popen(f"explorer /select,\"{task.get('local_video_path', '')}\"")
                                    else:  # macOS or Linux
                                        subprocess.Popen(['xdg-open', os.path.dirname(task.get('local_video_path', '.'))])
                                    st.success("已尝试打开下载文件夹")
                                except Exception as e:
                                    st.warning(f"无法打开文件夹: {str(e)}")
                        else:
                            # 对于在线视频，显示下载按钮
                            if st.button("下载视频", key=f"download_{task['task_id']}_{task_hash}"):
                                if download_video(video_url, task['task_id']):
                                    st.success("视频下载成功")
            
            # 图片任务处理
            elif task.get('task_type') in ['图片生成', '文生图']:
                # 尝试从results获取数据，如果为空则从last_api_response获取
                results = task.get('results', [])
                if not results and task.get('last_api_response', {}).get('data', {}).get('results'):
                    results = task.get('last_api_response', {}).get('data', {}).get('results', [])
                    
                if results:
                    with st.container(border=True):
                        st.subheader("🖼️ 图片预览")
                        
                        for j, result in enumerate(results):
                            col_img, col_info = st.columns([2, 3])
                            
                            with col_img:
                                if result.get('url'):
                                    try:
                                        st.image(result['url'], caption=f"图片 {j + 1}", use_container_width=True)
                                    except Exception as e:
                                        st.warning(f"图片加载失败: {str(e)}")
                                        st.markdown(f"图片链接: [点击查看]({result['url']})")
                            
                            with col_info:
                                st.markdown(f"**图片 {j + 1}**")
                                if result.get('content'):
                                    st.info(f"**描述:** {result['content']}")
                                
                                # 下载按钮
                                if result.get('url'):
                                    if st.button(f"📥 下载图片 {j + 1}", key=f"download_image_{task['task_id']}_{j}_{task_hash}"):
                                        from utils import download_image
                                        if download_image(result['url'], task['task_id'], j):
                                            st.success("图片下载成功")
                            
                            if j < len(results) - 1:
                                st.divider()
            
            # 重新生成选项（基于当前参数）
            with st.container():
                st.subheader("🔄 重新生成")
                # 重新生成按钮 - 使用任务ID和哈希值确保唯一性
                if st.button("使用相同参数重新生成", key=f"regenerate_{task['task_id']}_{task_hash}"):
                    # 根据任务类型调用不同的重新生成逻辑
                    if task.get('task_type') == '视频生成':
                        from utils import submit_video_task
                        
                        # 准备重新生成的任务数据
                        regenerate_data = {
                            'task_type': '视频生成',
                            'model': task.get('model', 'veo3-fast'),
                            'prompt': task.get('prompt', ''),
                            'reference_images': task.get('reference_images', []),
                            'first_frame_url': task.get('first_frame_url', ''),
                            'aspect_ratio': task.get('aspect_ratio', '16:9'),
                            'webhook_url': task.get('webhook_url', ''),
                            'shut_progress': task.get('shut_progress', False)
                        }
                    elif task.get('task_type') == 'Sora2视频生成':
                        from utils import submit_sora2_task
                        
                        # 准备重新生成的任务数据
                        regenerate_data = {
                            'task_type': 'Sora2视频生成',
                            'model': task.get('model', 'sora-2'),
                            'prompt': task.get('prompt', ''),
                            'aspect_ratio': task.get('aspect_ratio', '16:9'),
                            'duration': task.get('duration', 10),
                            'size': task.get('size', '720p'),
                            'reference_image_url': task.get('reference_image_url', ''),
                            'webhook_url': task.get('webhook_url', ''),
                            'shut_progress': task.get('shut_progress', False)
                        }
                        
                        # 提交重新生成任务
                        if task.get('task_type') == 'Sora2视频生成':
                            # 对于Sora2视频，传入当前选择的base_url
                            result, success, message = submit_sora2_task(regenerate_data, hosts[st.session_state.host_type])
                        else:
                            # 普通视频生成任务
                            result, success, message = submit_video_task(
                                st.session_state.api_key, hosts[st.session_state.host_type], regenerate_data
                            )
                        
                        if success:
                            st.session_state.tasks.append(result)
                            save_task_to_file(st.session_state.tasks)
                            st.success(f"✅ 重新生成任务提交成功! 任务ID: `{result['task_id']}`")
                            st.rerun()
                        else:
                            st.error(f"❌ 重新生成失败: {message}")
                    elif task.get('task_type') in ['图片生成', '文生图']:
                        from utils import submit_nano_banana_task
                        
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
                            regenerate_data
                        )
                        
                        if success:
                            st.session_state.tasks.append(result)
                            save_task_to_file(st.session_state.tasks)
                            st.success(f"✅ 重新生成任务提交成功! 任务ID: `{result['task_id']}`")
                            st.rerun()
                        else:
                            st.error(f"❌ 重新生成失败: {message}")


if not st.session_state.tasks:
    st.info("📝 暂无任务记录，请先创建生成任务。")
else:
    # 任务筛选选项
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        filter_status = st.selectbox("筛选状态", ["全部", "进行中", "已完成", "失败"])
    with col2:
        filter_type = st.selectbox("筛选类型", ["全部", "视频生成", "文生图", "图生视频", "Sora2视频生成"])
    with col3:
        st.write("")  # 占位
        if st.button("🔄 刷新所有进度"):
            from utils import update_all_tasks_progress

            st.session_state.tasks = update_all_tasks_progress(
                st.session_state.tasks
            )
            st.rerun()

    # 过滤任务
    filtered_tasks = st.session_state.tasks.copy()

    if filter_status != "全部":
        status_map = {
            "进行中": ["submitted", "running"],
            "已完成": ["succeeded"],
            "失败": ["failed"]
        }
        filtered_tasks = [t for t in filtered_tasks if t.get('status') in status_map[filter_status]]

    if filter_type != "全部":
        filtered_tasks = [t for t in filtered_tasks if t.get('task_type') == filter_type]

    # 倒序显示（最新的在前面）
    filtered_tasks.reverse()

    # 显示任务卡片
    for i, task in enumerate(filtered_tasks):
        render_task_card(task, i)


