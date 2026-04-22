"""
TG 批量私信系统 - 多功能标签页预览
功能：账号管理、私信广告、采集用户
"""

import tkinter as tk
from tkinter import ttk, scrolledtext

def show_preview():
    root = tk.Tk()
    root.title("TG 批量私信系统 v1.3 - 多功能版预览")
    root.geometry("1200x800")
    
    # ========== 顶部标题栏 ==========
    title_frame = ttk.Frame(root, padding="10")
    title_frame.pack(fill=tk.X)
    
    ttk.Label(title_frame, text="📱 TG 批量私信系统 v1.3", 
             font=("微软雅黑", 16, "bold")).pack(side=tk.LEFT, padx=10)
    
    ttk.Button(title_frame, text="🚀 开始", width=10).pack(side=tk.RIGHT, padx=5)
    ttk.Button(title_frame, text="⏸️ 停止", width=10).pack(side=tk.RIGHT, padx=5)
    
    # ========== 功能标签栏 ==========
    tab_frame = ttk.Frame(root)
    tab_frame.pack(fill=tk.X, padx=10)
    
    notebook = ttk.Notebook(tab_frame)
    notebook.pack(fill=tk.BOTH, expand=True)
    
    # ========== 功能1: 账号管理 ==========
    tab1 = ttk.Frame(notebook, padding="10")
    notebook.add(tab1, text="📂 账号管理")
    
    # 按钮组
    btn_frame1 = ttk.Frame(tab1)
    btn_frame1.pack(fill=tk.X, pady=(0, 10))
    
    ttk.Button(btn_frame1, text="📁 导入 Session 文件夹", width=20).pack(side=tk.LEFT, padx=5)
    ttk.Button(btn_frame1, text="✅ 全选", width=8).pack(side=tk.LEFT, padx=2)
    ttk.Button(btn_frame1, text="❌ 清空", width=8).pack(side=tk.LEFT, padx=2)
    ttk.Button(btn_frame1, text="🔍 检测状态", width=12).pack(side=tk.LEFT, padx=5)
    ttk.Button(btn_frame1, text="🗑️ 删除失效", width=12).pack(side=tk.LEFT, padx=2)
    
    # 账号列表
    tree_frame1 = ttk.Frame(tab1)
    tree_frame1.pack(fill=tk.BOTH, expand=True)
    
    tree1 = ttk.Treeview(tree_frame1, 
                         columns=("选择", "账号文件", "用户名", "手机号", "状态", "最后登录"), 
                         show="headings", height=25)
    
    tree1.heading("选择", text="✓")
    tree1.heading("账号文件", text="账号文件")
    tree1.heading("用户名", text="用户名")
    tree1.heading("手机号", text="手机号")
    tree1.heading("状态", text="状态")
    tree1.heading("最后登录", text="最后登录")
    
    tree1.column("选择", width=40, anchor=tk.CENTER)
    tree1.column("账号文件", width=180)
    tree1.column("用户名", width=150)
    tree1.column("手机号", width=120)
    tree1.column("状态", width=100)
    tree1.column("最后登录", width=150)
    
    # 示例数据
    tree1.insert("", tk.END, values=("✓", "85256387511.session", "@user123", "+85256387511", "✅ 正常", "2026-04-22 10:30"))
    tree1.insert("", tk.END, values=("✓", "85270904746.session", "@user456", "+85270904746", "✅ 正常", "2026-04-22 10:31"))
    tree1.insert("", tk.END, values=("", "85298283589.session", "未设置", "+85298283589", "⚠️ 未检测", "-"))
    tree1.insert("", tk.END, values=("", "account4.session", "-", "-", "❌ 登录失败", "-"))
    
    tree1.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    
    scrollbar1 = ttk.Scrollbar(tree_frame1, orient=tk.VERTICAL, command=tree1.yview)
    scrollbar1.pack(side=tk.RIGHT, fill=tk.Y)
    tree1.config(yscrollcommand=scrollbar1.set)
    
    # 统计信息
    stats_frame1 = ttk.Frame(tab1)
    stats_frame1.pack(fill=tk.X, pady=(10, 0))
    ttk.Label(stats_frame1, text="📊 统计: 总数 4 | 已选 2 | 正常 2 | 异常 1 | 未检测 1", 
             font=("微软雅黑", 10)).pack(side=tk.LEFT)
    
    # ========== 功能2: 私信广告 ==========
    tab2 = ttk.Frame(notebook, padding="10")
    notebook.add(tab2, text="✉️ 私信广告")
    
    # 左右分栏
    paned2 = ttk.PanedWindow(tab2, orient=tk.HORIZONTAL)
    paned2.pack(fill=tk.BOTH, expand=True)
    
    # 左侧：消息设置
    left2 = ttk.Frame(paned2)
    paned2.add(left2, weight=2)
    
    # 选择账号
    account_frame = ttk.LabelFrame(left2, text="📱 选择账号", padding="10")
    account_frame.pack(fill=tk.X, pady=(0, 10))
    
    ttk.Label(account_frame, text="使用账号管理中已选的账号").pack(anchor=tk.W)
    ttk.Label(account_frame, text="✓ 已选择 2 个账号", 
             foreground="green", font=("微软雅黑", 10, "bold")).pack(anchor=tk.W, pady=5)
    
    # 发送类型
    type_frame = ttk.LabelFrame(left2, text="📝 发送类型", padding="10")
    type_frame.pack(fill=tk.X, pady=(0, 10))
    
    send_type = tk.StringVar(value="text")
    ttk.Radiobutton(type_frame, text="📝 文本消息", variable=send_type, value="text").pack(anchor=tk.W, pady=2)
    ttk.Radiobutton(type_frame, text="🔗 转发贴子", variable=send_type, value="forward").pack(anchor=tk.W, pady=2)
    ttk.Radiobutton(type_frame, text="🖼️ 图片消息", variable=send_type, value="image").pack(anchor=tk.W, pady=2)
    
    # 消息内容
    msg_frame = ttk.LabelFrame(left2, text="✉️ 消息内容", padding="10")
    msg_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
    
    message_text = scrolledtext.ScrolledText(msg_frame, height=8, 
                                             font=("微软雅黑", 10), wrap=tk.WORD)
    message_text.pack(fill=tk.BOTH, expand=True)
    message_text.insert("1.0", "你好 {firstname}！\n\n这是一条广告消息。\n\n支持变量：\n• {username} - 用户名\n• {firstname} - 名字")
    
    # 目标用户
    target_frame = ttk.LabelFrame(left2, text="👥 目标用户", padding="10")
    target_frame.pack(fill=tk.BOTH, expand=True)
    
    target_btn_frame = ttk.Frame(target_frame)
    target_btn_frame.pack(fill=tk.X, pady=(0, 5))
    ttk.Button(target_btn_frame, text="📥 从采集导入", width=15).pack(side=tk.LEFT, padx=2)
    ttk.Button(target_btn_frame, text="📄 从文件导入", width=15).pack(side=tk.LEFT, padx=2)
    ttk.Button(target_btn_frame, text="🗑️ 清空列表", width=12).pack(side=tk.LEFT, padx=2)
    
    target_text = scrolledtext.ScrolledText(target_frame, height=6, 
                                            font=("微软雅黑", 10), wrap=tk.WORD)
    target_text.pack(fill=tk.BOTH, expand=True)
    target_text.insert("1.0", "@user1\n@user2\n@user3\n@user4\n@user5")
    
    ttk.Label(target_frame, text="共 5 个目标用户", 
             font=("微软雅黑", 9)).pack(anchor=tk.W, pady=(5, 0))
    
    # 右侧：发送设置
    right2 = ttk.Frame(paned2)
    paned2.add(right2, weight=1)
    
    # 并发控制
    concurrent_frame = ttk.LabelFrame(right2, text="⚡ 并发控制", padding="10")
    concurrent_frame.pack(fill=tk.X, pady=(0, 10))
    
    ttk.Label(concurrent_frame, text="并行线程数:").grid(row=0, column=0, sticky=tk.W, pady=3)
    ttk.Spinbox(concurrent_frame, from_=1, to=50, width=12).grid(row=0, column=1, sticky=tk.EW, padx=(10, 0), pady=3)
    
    ttk.Label(concurrent_frame, text="启动间隔(秒):").grid(row=1, column=0, sticky=tk.W, pady=3)
    ttk.Spinbox(concurrent_frame, from_=0, to=60, width=12).grid(row=1, column=1, sticky=tk.EW, padx=(10, 0), pady=3)
    
    concurrent_frame.columnconfigure(1, weight=1)
    
    # 额度限制
    limit_frame = ttk.LabelFrame(right2, text="📊 额度限制", padding="10")
    limit_frame.pack(fill=tk.X, pady=(0, 10))
    
    ttk.Label(limit_frame, text="单账号上限:").grid(row=0, column=0, sticky=tk.W, pady=3)
    ttk.Spinbox(limit_frame, from_=1, to=1000, width=12).grid(row=0, column=1, sticky=tk.EW, padx=(10, 0), pady=3)
    
    ttk.Label(limit_frame, text="任务总上限:").grid(row=1, column=0, sticky=tk.W, pady=3)
    ttk.Spinbox(limit_frame, from_=1, to=100000, width=12).grid(row=1, column=1, sticky=tk.EW, padx=(10, 0), pady=3)
    
    limit_frame.columnconfigure(1, weight=1)
    
    # 发送间隔
    interval_frame = ttk.LabelFrame(right2, text="⏱️ 发送间隔", padding="10")
    interval_frame.pack(fill=tk.X, pady=(0, 10))
    
    ttk.Label(interval_frame, text="间隔范围:").grid(row=0, column=0, sticky=tk.W, pady=3)
    range_frame = ttk.Frame(interval_frame)
    range_frame.grid(row=0, column=1, sticky=tk.EW, padx=(10, 0), pady=3)
    
    ttk.Spinbox(range_frame, from_=1, to=60, width=5).pack(side=tk.LEFT)
    ttk.Label(range_frame, text="~").pack(side=tk.LEFT, padx=3)
    ttk.Spinbox(range_frame, from_=1, to=60, width=5).pack(side=tk.LEFT)
    ttk.Label(range_frame, text="秒").pack(side=tk.LEFT, padx=(3, 0))
    
    interval_frame.columnconfigure(1, weight=1)
    
    # 其他选项
    option_frame = ttk.LabelFrame(right2, text="🔧 其他选项", padding="10")
    option_frame.pack(fill=tk.X)
    
    ttk.Checkbutton(option_frame, text="遇到限制自动切换账号").pack(anchor=tk.W, pady=2)
    ttk.Checkbutton(option_frame, text="发送失败自动重试").pack(anchor=tk.W, pady=2)
    ttk.Checkbutton(option_frame, text="跳过已发送用户").pack(anchor=tk.W, pady=2)
    
    # ========== 功能3: 采集用户 ==========
    tab3 = ttk.Frame(notebook, padding="10")
    notebook.add(tab3, text="👥 采集用户")
    
    # 左右分栏
    paned3 = ttk.PanedWindow(tab3, orient=tk.HORIZONTAL)
    paned3.pack(fill=tk.BOTH, expand=True)
    
    # 左侧：采集设置
    left3 = ttk.Frame(paned3)
    paned3.add(left3, weight=1)
    
    # 采集来源
    source_frame = ttk.LabelFrame(left3, text="📌 采集来源", padding="10")
    source_frame.pack(fill=tk.X, pady=(0, 10))
    
    source_type = tk.StringVar(value="group")
    ttk.Radiobutton(source_frame, text="👥 从群组采集", variable=source_type, value="group").pack(anchor=tk.W, pady=2)
    ttk.Radiobutton(source_frame, text="📢 从频道采集", variable=source_type, value="channel").pack(anchor=tk.W, pady=2)
    ttk.Radiobutton(source_frame, text="💬 从评论采集", variable=source_type, value="comments").pack(anchor=tk.W, pady=2)
    
    # 目标链接
    link_frame = ttk.LabelFrame(left3, text="🔗 目标链接", padding="10")
    link_frame.pack(fill=tk.X, pady=(0, 10))
    
    ttk.Label(link_frame, text="输入群组/频道链接:").pack(anchor=tk.W)
    ttk.Entry(link_frame, font=("微软雅黑", 10)).pack(fill=tk.X, pady=5)
    
    ttk.Button(link_frame, text="➕ 添加到列表", width=15).pack(anchor=tk.W)
    
    # 目标列表
    targets_frame = ttk.LabelFrame(left3, text="📋 采集目标列表", padding="10")
    targets_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
    
    targets_list = tk.Listbox(targets_frame, font=("微软雅黑", 10), height=8)
    targets_list.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
    
    targets_list.insert(tk.END, "https://t.me/group1")
    targets_list.insert(tk.END, "https://t.me/channel2")
    targets_list.insert(tk.END, "@group3")
    
    targets_scroll = ttk.Scrollbar(targets_frame, orient=tk.VERTICAL, command=targets_list.yview)
    targets_scroll.pack(side=tk.RIGHT, fill=tk.Y)
    targets_list.config(yscrollcommand=targets_scroll.set)
    
    # 过滤选项
    filter_frame = ttk.LabelFrame(left3, text="🔍 过滤条件", padding="10")
    filter_frame.pack(fill=tk.X)
    
    ttk.Checkbutton(filter_frame, text="仅采集活跃用户（7天内发言）").pack(anchor=tk.W, pady=2)
    ttk.Checkbutton(filter_frame, text="排除机器人账号").pack(anchor=tk.W, pady=2)
    ttk.Checkbutton(filter_frame, text="仅采集有用户名的用户").pack(anchor=tk.W, pady=2)
    
    ttk.Label(filter_frame, text="采集数量限制:").grid(row=3, column=0, sticky=tk.W, pady=(10, 3))
    ttk.Spinbox(filter_frame, from_=10, to=10000, width=12).grid(row=3, column=1, sticky=tk.W, padx=(10, 0), pady=(10, 3))
    
    # 右侧：采集结果
    right3 = ttk.Frame(paned3)
    paned3.add(right3, weight=2)
    
    # 结果列表
    result_frame = ttk.LabelFrame(right3, text="📊 采集结果", padding="10")
    result_frame.pack(fill=tk.BOTH, expand=True)
    
    result_tree = ttk.Treeview(result_frame, 
                               columns=("选择", "用户名", "名字", "来源", "最后活跃"), 
                               show="headings", height=20)
    
    result_tree.heading("选择", text="✓")
    result_tree.heading("用户名", text="用户名")
    result_tree.heading("名字", text="名字")
    result_tree.heading("来源", text="来源")
    result_tree.heading("最后活跃", text="最后活跃")
    
    result_tree.column("选择", width=40, anchor=tk.CENTER)
    result_tree.column("用户名", width=150)
    result_tree.column("名字", width=150)
    result_tree.column("来源", width=150)
    result_tree.column("最后活跃", width=120)
    
    # 示例数据
    result_tree.insert("", tk.END, values=("✓", "@user1", "张三", "t.me/group1", "2小时前"))
    result_tree.insert("", tk.END, values=("✓", "@user2", "李四", "t.me/group1", "5小时前"))
    result_tree.insert("", tk.END, values=("", "@user3", "王五", "t.me/channel2", "1天前"))
    
    result_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    
    result_scroll = ttk.Scrollbar(result_frame, orient=tk.VERTICAL, command=result_tree.yview)
    result_scroll.pack(side=tk.RIGHT, fill=tk.Y)
    result_tree.config(yscrollcommand=result_scroll.set)
    
    # 操作按钮
    action_frame = ttk.Frame(right3)
    action_frame.pack(fill=tk.X, pady=(10, 0))
    
    ttk.Button(action_frame, text="✅ 全选", width=10).pack(side=tk.LEFT, padx=2)
    ttk.Button(action_frame, text="❌ 清空", width=10).pack(side=tk.LEFT, padx=2)
    ttk.Button(action_frame, text="📤 导出到私信广告", width=18).pack(side=tk.LEFT, padx=5)
    ttk.Button(action_frame, text="💾 保存为文件", width=15).pack(side=tk.LEFT, padx=2)
    
    ttk.Label(action_frame, text="已采集 3 个用户，已选 2 个", 
             font=("微软雅黑", 9)).pack(side=tk.RIGHT, padx=10)
    
    # ========== 底部：日志（固定） ==========
    log_frame = ttk.LabelFrame(root, text="📝 运行日志", padding="10")
    log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(5, 10))
    
    log_text = scrolledtext.ScrolledText(log_frame, height=10, 
                                         font=("Consolas", 9))
    log_text.pack(fill=tk.BOTH, expand=True)
    
    # 示例日志
    log_text.insert("1.0", """[11:24:01] ✅ TG 批量私信系统 v1.3 已启动
[11:24:02] 📋 多功能设计：账号管理、私信广告、采集用户
[11:24:03] 📂 当前功能：账号管理
[11:24:04] 💡 点击顶部标签切换功能
[11:24:05] 📝 日志区域固定在底部，所有功能共享""")
    
    root.mainloop()

if __name__ == "__main__":
    show_preview()
