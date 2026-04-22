"""
TG 批量私信系统 - UI 布局预览
展示新的界面布局设计
"""

import tkinter as tk
from tkinter import ttk

def show_preview():
    root = tk.Tk()
    root.title("TG 批量私信系统 v1.3 - 布局预览")
    root.geometry("1200x800")
    
    # ========== 顶部标题栏 ==========
    title_frame = ttk.Frame(root, padding="10")
    title_frame.pack(fill=tk.X)
    
    ttk.Label(title_frame, text="📱 TG 批量私信系统 v1.3", 
             font=("微软雅黑", 16, "bold")).pack(side=tk.LEFT, padx=10)
    
    ttk.Button(title_frame, text="🚀 开始发送").pack(side=tk.RIGHT, padx=5)
    ttk.Button(title_frame, text="⏸️ 停止").pack(side=tk.RIGHT, padx=5)
    
    # ========== 主容器（三列布局）==========
    main_frame = ttk.Frame(root, padding="10")
    main_frame.pack(fill=tk.BOTH, expand=True)
    
    # 配置列权重
    main_frame.columnconfigure(0, weight=2)  # 左：账号
    main_frame.columnconfigure(1, weight=3)  # 中：消息
    main_frame.columnconfigure(2, weight=2)  # 右：设置
    
    # ========== 左列：账号管理 ==========
    left_frame = ttk.LabelFrame(main_frame, text="📂 账号管理", padding="10")
    left_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
    
    # 按钮组
    btn_frame = ttk.Frame(left_frame)
    btn_frame.pack(fill=tk.X, pady=(0, 10))
    
    ttk.Button(btn_frame, text="📁 导入").pack(side=tk.LEFT, padx=2)
    ttk.Button(btn_frame, text="✅ 全选").pack(side=tk.LEFT, padx=2)
    ttk.Button(btn_frame, text="❌ 清空").pack(side=tk.LEFT, padx=2)
    ttk.Button(btn_frame, text="🔍 检测").pack(side=tk.LEFT, padx=2)
    
    # 账号列表
    tree_frame = ttk.Frame(left_frame)
    tree_frame.pack(fill=tk.BOTH, expand=True)
    
    tree = ttk.Treeview(tree_frame, columns=("选择", "账号", "状态"), 
                       show="headings", height=20)
    tree.heading("选择", text="✓")
    tree.heading("账号", text="账号")
    tree.heading("状态", text="状态")
    
    tree.column("选择", width=30, anchor=tk.CENTER)
    tree.column("账号", width=150)
    tree.column("状态", width=100)
    
    # 示例数据
    tree.insert("", tk.END, values=("✓", "85256387511", "正常"))
    tree.insert("", tk.END, values=("✓", "85270904746", "正常 @user1"))
    tree.insert("", tk.END, values=("", "85298283589", "未检测"))
    
    tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    
    scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=tree.yview)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    tree.config(yscrollcommand=scrollbar.set)
    
    # ========== 中列：消息内容 ==========
    middle_frame = ttk.LabelFrame(main_frame, text="✉️ 消息内容", padding="10")
    middle_frame.grid(row=0, column=1, sticky="nsew", padx=5)
    
    # 发送类型
    type_frame = ttk.Frame(middle_frame)
    type_frame.pack(fill=tk.X, pady=(0, 10))
    
    ttk.Label(type_frame, text="发送类型:", font=("微软雅黑", 10, "bold")).pack(side=tk.LEFT, padx=5)
    
    send_type = tk.StringVar(value="text")
    ttk.Radiobutton(type_frame, text="📝 文本消息", variable=send_type, value="text").pack(side=tk.LEFT, padx=10)
    ttk.Radiobutton(type_frame, text="🔗 转发贴子", variable=send_type, value="forward").pack(side=tk.LEFT, padx=10)
    
    # 消息输入区
    msg_label_frame = ttk.LabelFrame(middle_frame, text="消息内容", padding="5")
    msg_label_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
    
    from tkinter import scrolledtext
    message_text = scrolledtext.ScrolledText(msg_label_frame, height=10, 
                                             font=("微软雅黑", 10), wrap=tk.WORD)
    message_text.pack(fill=tk.BOTH, expand=True)
    message_text.insert("1.0", "你好 {firstname}！\n\n这是一条测试消息。\n\n支持变量：\n• {username} - 用户名\n• {firstname} - 名字")
    
    # 目标用户
    target_label_frame = ttk.LabelFrame(middle_frame, text="目标用户 (每行一个)", padding="5")
    target_label_frame.pack(fill=tk.BOTH, expand=True)
    
    target_text = scrolledtext.ScrolledText(target_label_frame, height=8, 
                                            font=("微软雅黑", 10), wrap=tk.WORD)
    target_text.pack(fill=tk.BOTH, expand=True)
    target_text.insert("1.0", "@chadang1ge\n@xueyingqianxun\n@xc13123\n@xinxinxiangrona\n@gg490\n@gf2828218\n@rennd6")
    
    # ========== 右列：发送设置 ==========
    right_frame = ttk.LabelFrame(main_frame, text="⚙️ 发送设置", padding="10")
    right_frame.grid(row=0, column=2, sticky="nsew", padx=(5, 0))
    
    # 并发设置
    ttk.Label(right_frame, text="⚡ 并发控制", 
             font=("微软雅黑", 10, "bold")).pack(anchor=tk.W, pady=(0, 5))
    
    # 使用表格布局
    settings_frame = ttk.Frame(right_frame)
    settings_frame.pack(fill=tk.X, pady=(0, 15))
    
    row = 0
    ttk.Label(settings_frame, text="并行线程:").grid(row=row, column=0, sticky=tk.W, pady=3)
    ttk.Spinbox(settings_frame, from_=1, to=50, width=12).grid(row=row, column=1, sticky=tk.EW, padx=(10, 0), pady=3)
    row += 1
    
    ttk.Label(settings_frame, text="启动间隔:").grid(row=row, column=0, sticky=tk.W, pady=3)
    interval_frame = ttk.Frame(settings_frame)
    interval_frame.grid(row=row, column=1, sticky=tk.EW, padx=(10, 0), pady=3)
    ttk.Spinbox(interval_frame, from_=0, to=60, width=6).pack(side=tk.LEFT)
    ttk.Label(interval_frame, text="秒").pack(side=tk.LEFT, padx=(3, 0))
    row += 1
    
    settings_frame.columnconfigure(1, weight=1)
    
    ttk.Separator(right_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)
    
    # 额度限制
    ttk.Label(right_frame, text="📊 额度限制", 
             font=("微软雅黑", 10, "bold")).pack(anchor=tk.W, pady=(0, 5))
    
    limits_frame = ttk.Frame(right_frame)
    limits_frame.pack(fill=tk.X, pady=(0, 15))
    
    row = 0
    ttk.Label(limits_frame, text="单账号上限:").grid(row=row, column=0, sticky=tk.W, pady=3)
    ttk.Spinbox(limits_frame, from_=1, to=1000, width=12).grid(row=row, column=1, sticky=tk.EW, padx=(10, 0), pady=3)
    row += 1
    
    ttk.Label(limits_frame, text="任务总上限:").grid(row=row, column=0, sticky=tk.W, pady=3)
    ttk.Spinbox(limits_frame, from_=1, to=100000, width=12).grid(row=row, column=1, sticky=tk.EW, padx=(10, 0), pady=3)
    row += 1
    
    limits_frame.columnconfigure(1, weight=1)
    
    ttk.Separator(right_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)
    
    # 发送间隔
    ttk.Label(right_frame, text="⏱️ 发送间隔", 
             font=("微软雅黑", 10, "bold")).pack(anchor=tk.W, pady=(0, 5))
    
    interval_settings = ttk.Frame(right_frame)
    interval_settings.pack(fill=tk.X, pady=(0, 15))
    
    ttk.Label(interval_settings, text="间隔范围:").grid(row=0, column=0, sticky=tk.W, pady=3)
    range_frame = ttk.Frame(interval_settings)
    range_frame.grid(row=0, column=1, sticky=tk.EW, padx=(10, 0), pady=3)
    
    ttk.Spinbox(range_frame, from_=1, to=60, width=5).pack(side=tk.LEFT)
    ttk.Label(range_frame, text="~").pack(side=tk.LEFT, padx=3)
    ttk.Spinbox(range_frame, from_=1, to=60, width=5).pack(side=tk.LEFT)
    ttk.Label(range_frame, text="秒").pack(side=tk.LEFT, padx=(3, 0))
    
    interval_settings.columnconfigure(1, weight=1)
    
    ttk.Separator(right_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)
    
    # 其他选项
    ttk.Label(right_frame, text="🔧 其他选项", 
             font=("微软雅黑", 10, "bold")).pack(anchor=tk.W, pady=(0, 5))
    
    auto_switch = tk.BooleanVar(value=True)
    ttk.Checkbutton(right_frame, text="遇到限制自动切换账号", 
                   variable=auto_switch).pack(anchor=tk.W, pady=3)
    
    # 占位符（把按钮推到底部）
    ttk.Frame(right_frame).pack(fill=tk.BOTH, expand=True)
    
    # ========== 底部：日志 ==========
    log_frame = ttk.LabelFrame(root, text="📝 运行日志", padding="10")
    log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
    
    log_text = scrolledtext.ScrolledText(log_frame, height=10, 
                                         font=("Consolas", 9))
    log_text.pack(fill=tk.BOTH, expand=True)
    
    # 示例日志
    log_text.insert("1.0", """[11:18:01] ✅ TG 批量私信系统 v1.3 已启动
[11:18:02] 📋 新布局：三列分栏设计
[11:18:03] 📂 左列：账号管理（导入/选择/检测）
[11:18:04] ✉️ 中列：消息内容（文本/目标用户）
[11:18:05] ⚙️ 右列：发送设置（并发/额度/间隔）
[11:18:06] 📝 底部：实时日志输出
[11:18:07] 💡 窗口更大（1200x800），布局更清晰
[11:18:08] 🎨 控制按钮移到顶部标题栏""")
    
    root.mainloop()

if __name__ == "__main__":
    show_preview()
