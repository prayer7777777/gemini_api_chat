import tkinter as tk
from tkinter import scrolledtext, messagebox, filedialog
from google import genai
from google.genai import types
from PIL import Image, ImageTk
from io import BytesIO
import threading
import os
import json
import time
import pathlib
from google.genai.types import Tool, GoogleSearch

client = genai.Client(api_key="your_api_key")
history_file = "history.txt"

class RoundButton(tk.Canvas):
    def __init__(self, master, text, command=None, bg='#20bf6b', fg='white', font=("微软雅黑", 13, "bold"), radius=18, padding=(18, 8), hover_bg='#26de81', **kwargs):
        # 优化宽度计算，适配中文和多字按钮
        width = max(font[1]*len(text)*2, 80) + padding[0]*2
        height = font[1]*2 + padding[1]*2
        super().__init__(master, width=width, height=height, highlightthickness=0, bg=master['bg'], bd=0, **kwargs)
        self.radius = radius
        self.bg = bg
        self.fg = fg
        self.hover_bg = hover_bg
        self.command = command
        self.text = text
        self.font = font
        self.padding = padding
        self.is_hover = False
        self.draw_button(bg)
        self.bind('<Button-1>', self.on_click)
        self.bind('<Enter>', self.on_enter)
        self.bind('<Leave>', self.on_leave)
        self.text_id = self.create_text(int(width)//2, int(height)//2, text=text, fill=fg, font=font)
        self.config(cursor='hand2')
    def draw_button(self, color):
        w = int(self['width'])
        h = int(self['height'])
        r = self.radius
        self.delete('round_rect')
        self.create_round_rect(2, 2, w-2, h-2, r, fill=color, outline=color, tags='round_rect')
        # 先删除旧文字再重绘
        if hasattr(self, 'text_id'):
            self.delete(self.text_id)
        self.text_id = self.create_text(w//2, h//2, text=self.text, fill=self.fg, font=self.font)
    def create_round_rect(self, x1, y1, x2, y2, r, **kwargs):
        points = [x1+r, y1,
                  x2-r, y1,
                  x2, y1,
                  x2, y1+r,
                  x2, y2-r,
                  x2, y2,
                  x2-r, y2,
                  x1+r, y2,
                  x1, y2,
                  x1, y2-r,
                  x1, y1+r,
                  x1, y1]
        return self.create_polygon(points, smooth=True, **kwargs)
    def on_click(self, event):
        if self.command:
            self.command()
    def on_enter(self, event):
        self.is_hover = True
        self.draw_button(self.hover_bg)
    def on_leave(self, event):
        self.is_hover = False
        self.draw_button(self.bg)

class GeminiChatGUI:
    def __init__(self, root):
        # 先初始化所有自定义设置相关变量，API Key默认为空字符串
        self.api_key_var = tk.StringVar(value="")
        self.current_api_key = ""
        self.model_var = tk.StringVar(value="gemini-2.0-flash")
        # 全部模型类型
        self.all_model_options = [
            "gemini-2.0-flash",
            "gemini-2.0-pro",
            "gemini-1.5-pro",
            "gemini-1.5-flash-8b",
            "gemini-2.0-flash-exp-image-generation"
        ]
        self.text_model_options = [
            "gemini-2.0-flash",
            "gemini-2.0-pro",
            "gemini-1.5-pro",
            "gemini-1.5-flash-8b"
        ]
        self.image_model_options = [
            "gemini-2.0-flash-exp-image-generation"
        ]
        self.model_options = self.text_model_options.copy()
        self.image_save_dir = tk.StringVar(value=os.getcwd())
        self.history_save_dir = tk.StringVar(value=os.getcwd())
        # 检测可用模型
        self.available_models = set()
        self.detect_available_models()
        # 加载本地设置
        self.load_config()
        # 统一提前定义所有设置相关变量
        self.sysinst_var = tk.StringVar(value="")
        self.temp_var = tk.DoubleVar(value=0.2)
        self.max_tokens_var = tk.IntVar(value=200)
        self.struct_format_var = tk.StringVar(value="无")
        self.func_templates = {
            "安排会议": (
                '{\n'
                '  "name": "schedule_meeting",\n'
                '  "description": "安排一个会议，指定与会人员、日期、时间和主题。",\n'
                '  "parameters": {\n'
                '    "type": "object",\n'
                '    "properties": {\n'
                '      "attendees": {"type": "array", "items": {"type": "string"}, "description": "与会人员列表"},\n'
                '      "date": {"type": "string", "description": "会议日期（如 \'2024-07-29\'）"},\n'
                '      "time": {"type": "string", "description": "会议时间（如 \'15:00\'）"},\n'
                '      "topic": {"type": "string", "description": "会议主题"}\n'
                '    },\n'
                '    "required": ["attendees", "date", "time", "topic"]\n'
                '  }\n'
                '}'),
            "查天气": (
                '{\n'
                '  "name": "get_weather",\n'
                '  "description": "获取指定城市的天气信息。",\n'
                '  "parameters": {\n'
                '    "type": "object",\n'
                '    "properties": {\n'
                '      "city": {"type": "string", "description": "城市名称"},\n'
                '      "date": {"type": "string", "description": "日期（可选，格式如 \'2024-07-29\'）"}\n'
                '    },\n'
                '    "required": ["city"]\n'
                '  }\n'
                '}'),
            "发送邮件": (
                '{\n'
                '  "name": "send_email",\n'
                '  "description": "发送一封电子邮件。",\n'
                '  "parameters": {\n'
                '    "type": "object",\n'
                '    "properties": {\n'
                '      "to": {"type": "string", "description": "收件人邮箱"},\n'
                '      "subject": {"type": "string", "description": "邮件主题"},\n'
                '      "body": {"type": "string", "description": "邮件正文"}\n'
                '    },\n'
                '    "required": ["to", "subject", "body"]\n'
                '  }\n'
                '}'),
        }
        self.root = root
        self.root.title("Gemini 聊天机器人（多功能版）")
        self.root.geometry("900x750")
        self.root.configure(bg="#f5f6fa")

        # 聊天输出区：Text文本框+滚动条，支持选择和复制
        output_frame = tk.Frame(root, bg="#f5f6fa")
        output_frame.pack(padx=12, pady=12, fill=tk.BOTH, expand=True)
        self.chat_area = tk.Text(output_frame, wrap=tk.WORD, state='disabled', font=("微软雅黑", 12), bg="#f5f6fa", relief=tk.FLAT)
        self.chat_area.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        chat_scroll = tk.Scrollbar(output_frame, command=self.chat_area.yview)
        chat_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.chat_area.config(yscrollcommand=chat_scroll.set)
        # 定义tag用于区分用户/AI/系统/错误
        self.chat_area.tag_configure('user', foreground='#3867d6')
        self.chat_area.tag_configure('ai', foreground='#20bf6b')
        self.chat_area.tag_configure('system', foreground='#e17055')
        self.chat_area.tag_configure('error', foreground='#d7263d')
        self.chat_area.tag_configure('timer', font=("微软雅黑", 10), foreground="#888888")

        # 功能选择与设置按钮同一行
        self.mode_var = tk.StringVar(value="文本生成")
        self.mode_options = ["文本生成", "图片理解", "流式对话", "图片生成", "文档理解", "视频理解", "音频理解"]
        top_btn_frame = tk.Frame(root, bg="#f5f6fa", bd=0, highlightthickness=0)
        top_btn_frame.pack(pady=(0,8), fill=tk.X, padx=10)
        tk.Label(top_btn_frame, text="功能选择：", font=("微软雅黑", 11, "bold"), bg="#f5f6fa", fg="#3867d6").pack(side=tk.LEFT, padx=(0,5))
        self.mode_btn = RoundButton(top_btn_frame, text=self.mode_var.get(), command=self.show_mode_menu, font=("微软雅黑", 11, "bold"), bg="#4b7bec", fg="white", hover_bg="#3867d6", radius=16)
        self.mode_btn.pack(side=tk.LEFT)
        settings_btn = RoundButton(top_btn_frame, text="设置", command=self.open_settings, font=("微软雅黑", 11, "bold"), bg="#778beb", fg="white", hover_bg="#4b7bec", radius=16)
        settings_btn.pack(side=tk.LEFT, padx=(16,0))
        self.mode_menu_window = None
        self.mode_var.trace_add('write', self.update_mode_btn_text)

        # 图片路径显示
        self.image_path = tk.StringVar()
        self.image_frame = tk.Frame(root, bg="#f5f6fa")
        self.image_btn = RoundButton(self.image_frame, text="选择图片", command=self.select_image, font=("微软雅黑", 11, "bold"), bg="#4b7bec", fg="white", hover_bg="#3867d6", radius=18)
        self.image_btn.pack(side=tk.LEFT, padx=(0,5))
        self.image_label = tk.Label(self.image_frame, textvariable=self.image_path, font=("微软雅黑", 10), bg="#f5f6fa", fg="#3867d6")
        self.image_label.pack(side=tk.LEFT)
        self.toggle_image_widgets(False)

        # 文档路径显示
        self.doc_path = tk.StringVar()
        self.doc_frame = tk.Frame(root, bg="#f5f6fa")
        self.doc_btn = RoundButton(self.doc_frame, text="选择文档", command=self.select_doc, font=("微软雅黑", 11, "bold"), bg="#4b7bec", fg="white", hover_bg="#3867d6", radius=18)
        self.doc_btn.pack(side=tk.LEFT, padx=(0,5))
        self.doc_label = tk.Label(self.doc_frame, textvariable=self.doc_path, font=("微软雅黑", 10), bg="#f5f6fa", fg="#3867d6")
        self.doc_label.pack(side=tk.LEFT)
        self.toggle_doc_widgets(False)

        # 视频路径显示
        self.video_path = tk.StringVar()
        self.video_frame = tk.Frame(root, bg="#f5f6fa")
        self.video_btn = RoundButton(self.video_frame, text="选择视频", command=self.select_video, font=("微软雅黑", 11, "bold"), bg="#4b7bec", fg="white", hover_bg="#3867d6", radius=18)
        self.video_btn.pack(side=tk.LEFT, padx=(0,5))
        self.video_label = tk.Label(self.video_frame, textvariable=self.video_path, font=("微软雅黑", 10), bg="#f5f6fa", fg="#3867d6")
        self.video_label.pack(side=tk.LEFT)
        self.toggle_video_widgets(False)

        # 音频路径显示
        self.audio_path = tk.StringVar()
        self.audio_frame = tk.Frame(root, bg="#f5f6fa")
        self.audio_btn = RoundButton(self.audio_frame, text="选择音频", command=self.select_audio, font=("微软雅黑", 11, "bold"), bg="#4b7bec", fg="white", hover_bg="#3867d6", radius=18)
        self.audio_btn.pack(side=tk.LEFT, padx=(0,5))
        self.audio_label = tk.Label(self.audio_frame, textvariable=self.audio_path, font=("微软雅黑", 10), bg="#f5f6fa", fg="#3867d6")
        self.audio_label.pack(side=tk.LEFT)
        self.toggle_audio_widgets(False)

        # 输入和发送按钮同一行
        input_frame = tk.Frame(root, bg="#f5f6fa")
        input_frame.pack(padx=10, pady=(0,12), fill=tk.X)
        self.entry = tk.Text(input_frame, font=("微软雅黑", 13), height=1, wrap=tk.WORD, undo=True)
        self.entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0,12))
        entry_scroll = tk.Scrollbar(input_frame, command=self.entry.yview)
        entry_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.entry.config(yscrollcommand=entry_scroll.set)
        self.entry.bind('<Return>', self.on_enter)
        self.entry.bind('<Shift-Return>', self.on_shift_enter)
        self.entry.bind('<KeyRelease>', self.on_text_change)
        self.entry.focus_set()
        self.send_btn = RoundButton(input_frame, text="发送", command=self.send_message, font=("微软雅黑", 13, "bold"), bg="#20bf6b", fg="white", hover_bg="#26de81", radius=18)
        self.send_btn.pack(side=tk.LEFT)

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.append_chat("系统", "欢迎使用 Gemini 聊天机器人！请选择功能并开始对话。")
        self.chat = None  # 多轮对话对象
        self.image_refs = []  # 防止图片被垃圾回收

        self.settings_window = None
        self.func_decl_text = None

        # 只绑定一次，放在__init__最后
        self.mode_var.trace_add('write', self.on_mode_change)

        # 在相关设置变更处调用save_config
        # 1. apply_api_key、on_model_select、select_image_dir、select_history_dir等方法已调用
        # 2. 结构化格式、温度、最大输出长度、系统指令、函数声明等控件变更时也需调用save_config
        # 例如：
        self.struct_format_var.trace_add('write', self.on_struct_format_change)
        self.temp_var.trace_add('write', self.on_temp_change)
        self.max_tokens_var.trace_add('write', self.on_max_tokens_change)
        self.sysinst_var.trace_add('write', self.on_sysinst_change)
        # 函数声明输入框绑定内容变化
        if self.func_decl_text is not None:
            self.func_decl_text.bind('<KeyRelease>', self.on_func_decl_change)

        # 保证所有控件创建后再加载设置
        self.load_config()

        self.enable_grounding_var = tk.BooleanVar(value=False)

    def toggle_image_widgets(self, show):
        if show:
            self.image_frame.pack(pady=(0,5), fill=tk.X)
        else:
            self.image_frame.pack_forget()
            self.image_path.set("")

    def toggle_doc_widgets(self, show):
        if show:
            self.doc_frame.pack(pady=(0,5), fill=tk.X)
        else:
            self.doc_frame.pack_forget()
            self.doc_path.set("")

    def toggle_video_widgets(self, show):
        if show:
            self.video_frame.pack(pady=(0,5), fill=tk.X)
        else:
            self.video_frame.pack_forget()
            self.video_path.set("")

    def toggle_audio_widgets(self, show):
        if show:
            self.audio_frame.pack(pady=(0,5), fill=tk.X)
        else:
            self.audio_frame.pack_forget()
            self.audio_path.set("")

    def on_mode_change(self, *args):
        mode = self.mode_var.get()
        self.toggle_image_widgets(mode == "图片理解")
        self.toggle_doc_widgets(mode == "文档理解")
        self.toggle_video_widgets(mode == "视频理解")
        self.toggle_audio_widgets(mode == "音频理解")
        # 每次切换功能都重新检测可用模型
        self.detect_available_models()
        # 动态调整模型选项
        if mode == "图片生成":
            self.model_options = self.image_model_options.copy()
            if self.model_options[0] in self.available_models:
                self.model_var.set(self.model_options[0])
            else:
                # 若图片生成模型不可用，选第一个可用模型
                for opt in self.model_options:
                    if opt in self.available_models:
                        self.model_var.set(opt)
                        break
        else:
            self.model_options = self.text_model_options.copy()
            if self.model_var.get() not in self.model_options or self.model_var.get() not in self.available_models:
                for opt in self.model_options:
                    if opt in self.available_models:
                        self.model_var.set(opt)
                        break
        # 刷新模型下拉菜单，标记不可用模型
        if hasattr(self, 'model_menu'):
            menu = self.model_menu['menu']
            menu.delete(0, 'end')
            for opt in self.model_options:
                label = opt if opt in self.available_models else f"[不可用]{opt}"
                menu.add_command(label=label, command=lambda o=opt: self.on_model_select(label))
        self.update_model_desc()

    def select_image(self):
        file_path = filedialog.askopenfilename(filetypes=[("Image Files", "*.png;*.jpg;*.jpeg;*.bmp;*.gif")])
        if file_path:
            self.image_path.set(file_path)

    def select_doc(self):
        file_path = filedialog.askopenfilename(filetypes=[
            ("支持的文档", "*.pdf;*.txt;*.html;*.htm;*.md;*.csv;*.xml"),
            ("PDF", "*.pdf"),
            ("文本", "*.txt"),
            ("HTML", "*.html;*.htm"),
            ("Markdown", "*.md"),
            ("CSV", "*.csv"),
            ("XML", "*.xml")
        ])
        if file_path:
            self.doc_path.set(file_path)

    def select_video(self):
        file_path = filedialog.askopenfilename(filetypes=[
            ("视频文件", "*.mp4;*.avi;*.mov;*.mpeg;*.mpg;*.wmv;*.flv;*.webm;*.3gpp"),
            ("MP4", "*.mp4"),
            ("AVI", "*.avi"),
            ("MOV", "*.mov"),
            ("MPEG", "*.mpeg;*.mpg"),
            ("WMV", "*.wmv"),
            ("FLV", "*.flv"),
            ("WEBM", "*.webm"),
            ("3GPP", "*.3gpp")
        ])
        if file_path:
            self.video_path.set(file_path)

    def select_audio(self):
        file_path = filedialog.askopenfilename(filetypes=[
            ("音频文件", "*.mp3;*.wav;*.aac;*.ogg;*.flac;*.aiff"),
            ("MP3", "*.mp3"),
            ("WAV", "*.wav"),
            ("AAC", "*.aac"),
            ("OGG", "*.ogg"),
            ("FLAC", "*.flac"),
            ("AIFF", "*.aiff")
        ])
        if file_path:
            self.audio_path.set(file_path)

    def append_chat(self, sender, message):
        self.chat_area.config(state='normal')
        # 区分tag
        if sender == "你":
            tag = 'user'
            prefix = "你："
        elif sender == "Gemini":
            tag = 'ai'
            prefix = "Gemini："
        elif sender == "系统" or sender == "System":
            tag = 'timer'
            prefix = "System："
            # 删除所有System计时行（全局搜索）
            start_idx = '1.0'
            while True:
                idx = self.chat_area.search("System：", start_idx, stopindex=tk.END, regexp=False)
                if not idx:
                    break
                tags = self.chat_area.tag_names(idx)
                if 'timer' in tags:
                    line_end = self.chat_area.index(f"{idx} lineend")
                    self.chat_area.delete(idx, f"{line_end}+1c")
                    start_idx = idx
                else:
                    start_idx = self.chat_area.index(f"{idx} +1c")
        elif sender == "错误":
            tag = 'error'
            prefix = "错误："
        else:
            tag = 'system'
            prefix = f"{sender}："
        self.chat_area.insert(tk.END, f"{prefix}{message}\n", tag)
        self.chat_area.see(tk.END)
        self.chat_area.config(state='disabled')
        # 保存到自定义历史文件
        history_file = os.path.join(self.history_save_dir.get(), "history.txt")
        with open(history_file, "a", encoding="utf-8") as f:
            f.write(f"[{sender}] {message}\n")

    def append_image(self, pil_img, filename_hint="gen_image.png"):
        # 保存图片到自定义目录
        save_path = os.path.join(self.image_save_dir.get(), filename_hint)
        pil_img.save(save_path)
        # 显示图片到聊天区
        img = pil_img.copy().resize((256, 256))
        tk_img = ImageTk.PhotoImage(img)
        self.image_refs.append(tk_img)  # 防止被回收
        self.chat_area.config(state='normal')
        self.chat_area.image_create(tk.END, image=tk_img)
        self.chat_area.insert(tk.END, f"\n[图片已保存: {save_path}]\n")
        self.chat_area.config(state='disabled')

    def on_enter(self, event):
        if not (event.state & 0x0001):  # 没有按下Shift
            self.send_message()
            return 'break'  # 阻止默认换行
        else:
            self.on_text_change()

    def on_shift_enter(self, event):
        self.entry.insert(tk.INSERT, '\n')
        self.on_text_change()
        return 'break'

    def on_text_change(self, event=None):
        # 根据实际显示行数动态调整高度，最小1行，最大10行
        content = self.entry.get("1.0", tk.END)
        # 计算实际显示行数（考虑自动换行）
        widget_width = self.entry.winfo_width() or 1
        font = self.entry.cget("font")
        # 估算每行可容纳字符数
        try:
            import tkinter.font as tkfont
            f = tkfont.Font(font=font)
            char_width = f.measure('一') or 10
            max_chars_per_line = max(int(widget_width / char_width), 1)
        except Exception:
            max_chars_per_line = 30
        lines = 0
        for line in content.splitlines() or ['']:
            lines += max(1, (len(line) + max_chars_per_line - 1) // max_chars_per_line)
        lines = min(max(lines, 1), 10)
        self.entry.configure(height=lines)

    def send_message(self, event=None):
        user_input = self.entry.get("1.0", tk.END).strip()
        mode = self.mode_var.get()
        if mode == "图片理解" and not self.image_path.get():
            messagebox.showwarning("提示", "请选择一张图片！")
            return
        if mode == "文档理解" and not self.doc_path.get():
            messagebox.showwarning("提示", "请选择一个文档！")
            return
        if mode == "视频理解" and not self.video_path.get():
            messagebox.showwarning("提示", "请选择一个视频文件！")
            return
        if mode == "音频理解" and not self.audio_path.get():
            messagebox.showwarning("提示", "请选择一个音频文件！")
            return
        if not user_input and mode not in ["图片理解", "图片生成", "文档理解", "视频理解", "音频理解"]:
            return
        if mode not in ["图片理解", "图片生成", "文档理解", "视频理解", "音频理解"]:
            self.append_chat("你", user_input)
            if mode in ["文本生成", "流式对话"]:
                self.gen_start_time = time.time()
                self.gen_timer_id = None
                self.gen_timer_line = self.append_gen_timer(gen_type="文本")
                self.update_gen_timer(gen_type="文本")
        elif mode == "图片生成":
            self.append_chat("你", f"[图片生成] {user_input}")
            self.gen_start_time = time.time()
            self.gen_timer_id = None
            self.gen_timer_line = self.append_gen_timer(gen_type="图片")
            self.update_gen_timer(gen_type="图片")
        elif mode == "文档理解":
            self.append_chat("你", f"[文档理解] {os.path.basename(self.doc_path.get())} + {user_input}")
            self.gen_start_time = time.time()
            self.gen_timer_id = None
            self.gen_timer_line = self.append_gen_timer(gen_type="文档")
            self.update_gen_timer(gen_type="文档")
        elif mode == "视频理解":
            self.append_chat("你", f"[视频理解] {os.path.basename(self.video_path.get())} + {user_input}")
            self.gen_start_time = time.time()
            self.gen_timer_id = None
            self.gen_timer_line = self.append_gen_timer(gen_type="视频")
            self.update_gen_timer(gen_type="视频")
        elif mode == "音频理解":
            self.append_chat("你", f"[音频理解] {os.path.basename(self.audio_path.get())} + {user_input}")
            self.gen_start_time = time.time()
            self.gen_timer_id = None
            self.gen_timer_line = self.append_gen_timer(gen_type="音频")
            self.update_gen_timer(gen_type="音频")
        else:
            self.append_chat("你", f"[图片] {os.path.basename(self.image_path.get())} + {user_input}")
        self.entry.delete("1.0", tk.END)
        self.entry.configure(height=1)
        threading.Thread(target=self.get_gemini_reply, args=(user_input, mode), daemon=True).start()

    def append_gen_timer(self, gen_type="图片"):
        self.chat_area.config(state='normal')
        self.chat_area.insert(tk.END, f"Gemini：{gen_type}生成中... 用时：0.00秒\n", 'timer')
        self.chat_area.see(tk.END)
        self.chat_area.config(state='disabled')
        return self.chat_area.index(tk.END + "-2l")  # 返回插入行的索引

    def update_gen_timer(self, gen_type="图片"):
        if hasattr(self, 'gen_start_time') and self.gen_start_time:
            elapsed = time.time() - self.gen_start_time
            line_idx = getattr(self, 'gen_timer_line', None)
            if line_idx:
                self.chat_area.config(state='normal')
                self.chat_area.delete(line_idx, f"{line_idx} lineend")
                self.chat_area.insert(line_idx, f"Gemini：{gen_type}生成中... 用时：{elapsed:.2f}秒", 'timer')
                self.chat_area.config(state='disabled')
            self.gen_timer_id = self.root.after(100, lambda: self.update_gen_timer(gen_type=gen_type))

    def stop_gen_timer(self, final_time=None, gen_type="图片"):
        if hasattr(self, 'gen_timer_id') and self.gen_timer_id:
            self.root.after_cancel(self.gen_timer_id)
            self.gen_timer_id = None
        self.gen_start_time = None
        self.gen_timer_line = None
        if final_time is not None:
            return f"{gen_type}生成完成！总用时：{final_time:.2f}秒"
        return None

    def get_gemini_reply(self, user_input, mode):
        try:
            # 获取当前模型
            model_name = self.model_var.get()
            # 多轮对话对象初始化
            if mode in ["文本生成", "流式对话"]:
                if self.chat is None:
                    self.chat = client.chats.create(model=model_name)
            # 构造自定义参数和系统指令
            config_kwargs = {}
            sysinst = self.sysinst_var.get().strip()
            if sysinst:
                config_kwargs['system_instruction'] = sysinst
            temp = self.temp_var.get()
            max_tokens = self.max_tokens_var.get()
            if temp != 0.2 or max_tokens != 200:
                config_kwargs['temperature'] = temp
                config_kwargs['max_output_tokens'] = max_tokens
            # 搜索接地工具
            tools = None
            if self.enable_grounding_var.get():
                tools = Tool(google_search=GoogleSearch())
            # 结构化格式处理
            struct_format = self.struct_format_var.get()
            struct_prompt_map = {
                "JSON": "请用 JSON 格式输出：",
                "Markdown": "请用 markdown 格式输出：",
                "YAML": "请用 YAML 格式输出：",
                "CSV": "请用 CSV 格式输出：",
                "HTML": "请用 HTML 格式输出：",
                "LaTeX": "请用 LaTeX 格式输出：",
                "XML": "请用 XML 格式输出：",
                "表格": "请用纯文本表格格式输出："
            }
            if struct_format != "无" and mode in ["文本生成", "流式对话"]:
                user_input = struct_prompt_map[struct_format] + user_input
            # 函数声明处理
            func_decl_str = ""
            if self.func_decl_text is not None:
                func_decl_str = self.func_decl_text.get("1.0", tk.END).strip()
            if func_decl_str:
                try:
                    func_decl = json.loads(func_decl_str)
                    if tools:
                        tools = [tools, types.Tool(function_declarations=[func_decl])]
                    else:
                        tools = [types.Tool(function_declarations=[func_decl])]
                except Exception as e:
                    self.append_chat("错误", f"函数声明JSON解析失败: {e}")
                    return
            elif tools:
                tools = [tools]
            if mode == "文本生成":
                if tools:
                    config = types.GenerateContentConfig(**config_kwargs, tools=tools)
                elif config_kwargs:
                    config = types.GenerateContentConfig(**config_kwargs)
                else:
                    config = None
                if config:
                    response = self.chat.send_message(user_input, config=config)
                else:
                    response = self.chat.send_message(user_input)
                part = response.candidates[0].content.parts[0]
                if hasattr(part, 'function_call') and part.function_call:
                    func_name = part.function_call.name
                    func_args = part.function_call.args
                    self.append_chat("Gemini", f"建议调用函数：{func_name}\n参数：{func_args}")
                else:
                    ai_reply = getattr(response, 'text', str(response))
                    self.append_chat("Gemini", ai_reply)
                # 展示grounding_metadata
                if hasattr(response.candidates[0], 'grounding_metadata') and getattr(response.candidates[0], 'grounding_metadata', None):
                    meta = response.candidates[0].grounding_metadata
                    if hasattr(meta, 'search_entry_point') and hasattr(meta.search_entry_point, 'rendered_content'):
                        self.append_chat("[权威来源]", meta.search_entry_point.rendered_content)
                final_time = None
                if hasattr(self, 'gen_start_time') and self.gen_start_time:
                    final_time = time.time() - self.gen_start_time
                use_time_str = self.stop_gen_timer(final_time, gen_type="文本")
                if use_time_str:
                    self.append_chat("System", use_time_str)
            elif mode == "流式对话":
                ai_reply = ""
                self.chat_area.config(state='normal')
                self.chat_area.insert(tk.END, "Gemini：")
                self.chat_area.see(tk.END)
                self.chat_area.config(state='disabled')
                if tools:
                    config = types.GenerateContentConfig(**config_kwargs, tools=tools)
                elif config_kwargs:
                    config = types.GenerateContentConfig(**config_kwargs)
                else:
                    config = None
                if config:
                    response = self.chat.send_message_stream(user_input, config=config)
                else:
                    response = self.chat.send_message_stream(user_input)
                # 检查流式返回是否有函数调用
                func_call_checked = False
                for chunk in response:
                    if not func_call_checked:
                        part = getattr(chunk, 'parts', [None])[0]
                        if part and hasattr(part, 'function_call') and part.function_call:
                            func_name = part.function_call.name
                            func_args = part.function_call.args
                            self.chat_area.config(state='normal')
                            self.chat_area.insert(tk.END, f"建议调用函数：{func_name}\n参数：{func_args}\n")
                            self.chat_area.config(state='disabled')
                            func_call_checked = True
                            continue
                    self.chat_area.config(state='normal')
                    self.chat_area.insert(tk.END, chunk.text)
                    self.chat_area.see(tk.END)
                    self.chat_area.config(state='disabled')
                    ai_reply += chunk.text
                self.chat_area.config(state='normal')
                self.chat_area.insert(tk.END, "\n")
                self.chat_area.config(state='disabled')
                final_time = None
                if hasattr(self, 'gen_start_time') and self.gen_start_time:
                    final_time = time.time() - self.gen_start_time
                use_time_str = self.stop_gen_timer(final_time, gen_type="文本")
                if use_time_str:
                    self.append_chat("System", use_time_str)
            elif mode == "函数调用":
                func_decl_str = ""
                if self.func_decl_text is not None:
                    func_decl_str = self.func_decl_text.get("1.0", tk.END).strip()
                try:
                    func_decl = json.loads(func_decl_str)
                except Exception as e:
                    self.append_chat("错误", f"函数声明JSON解析失败: {e}")
                    return
                tools = types.Tool(function_declarations=[func_decl])
                config = types.GenerateContentConfig(tools=[tools])
                response = client.models.generate_content(
                    model=model_name,
                    contents=user_input,
                    config=config
                )
                part = response.candidates[0].content.parts[0]
                if hasattr(part, 'function_call') and part.function_call:
                    func_name = part.function_call.name
                    func_args = part.function_call.args
                    self.append_chat("Gemini", f"建议调用函数：{func_name}\n参数：{func_args}")
                else:
                    self.append_chat("Gemini", response.text)
            elif mode == "图片理解":
                image = Image.open(self.image_path.get())
                response = client.models.generate_content(
                    model=model_name,
                    contents=[image, user_input or "请描述这张图片"]
                )
                ai_reply = getattr(response, 'text', str(response))
                self.append_chat("Gemini", ai_reply)
            elif mode == "图片生成":
                response = client.models.generate_content(
                    model=model_name,
                    contents=user_input,
                    config=types.GenerateContentConfig(
                        response_modalities=['TEXT', 'IMAGE']
                    )
                )
                final_time = None
                if hasattr(self, 'gen_start_time') and self.gen_start_time:
                    final_time = time.time() - self.gen_start_time
                for part in response.candidates[0].content.parts:
                    if hasattr(part, 'text') and part.text:
                        self.append_chat("Gemini", part.text)
                    elif hasattr(part, 'inline_data') and part.inline_data:
                        try:
                            pil_img = Image.open(BytesIO(part.inline_data.data))
                            self.append_image(pil_img)
                        except Exception as e:
                            self.append_chat("Gemini", f"[图片解析失败] {e}")
                use_time_str = self.stop_gen_timer(final_time, gen_type="图片")
                if use_time_str:
                    self.append_chat("System", use_time_str)
            elif mode == "自定义参数":
                response = client.models.generate_content(
                    model=model_name,
                    contents=[user_input],
                    config=types.GenerateContentConfig(
                        max_output_tokens=self.max_tokens_var.get(),
                        temperature=self.temp_var.get()
                    )
                )
                ai_reply = getattr(response, 'text', str(response))
                self.append_chat("Gemini", ai_reply)
            elif mode == "系统指令":
                response = client.models.generate_content(
                    model=model_name,
                    config=types.GenerateContentConfig(
                        system_instruction=self.sysinst_var.get()),
                    contents=user_input or "你好"
                )
                ai_reply = getattr(response, 'text', str(response))
                self.append_chat("Gemini", ai_reply)
            elif mode == "文档理解":
                import pathlib
                file_path = pathlib.Path(self.doc_path.get())
                # 自动识别MIME类型
                ext = file_path.suffix.lower()
                mime_map = {
                    ".pdf": "application/pdf",
                    ".txt": "text/plain",
                    ".html": "text/html",
                    ".htm": "text/html",
                    ".md": "text/md",
                    ".csv": "text/csv",
                    ".xml": "text/xml"
                }
                mime_type = mime_map.get(ext, "application/octet-stream")
                prompt = user_input or "请总结该文档"
                response = client.models.generate_content(
                    model=model_name,
                    contents=[
                        types.Part.from_bytes(
                            data=file_path.read_bytes(),
                            mime_type=mime_type,
                        ),
                        prompt
                    ]
                )
                ai_reply = getattr(response, 'text', str(response))
                self.append_chat("Gemini", ai_reply)
                final_time = None
                if hasattr(self, 'gen_start_time') and self.gen_start_time:
                    final_time = time.time() - self.gen_start_time
                use_time_str = self.stop_gen_timer(final_time, gen_type="文档")
                if use_time_str:
                    self.append_chat("System", use_time_str)
            elif mode == "视频理解":
                # 上传视频文件
                video_file = client.files.upload(file=self.video_path.get())
                # 轮询等待文件变为ACTIVE
                import time as _time
                file_id = getattr(video_file, "name", None) or getattr(video_file, "id", None)
                file_info = None
                for _ in range(30):  # 最多等30秒
                    try:
                        # 优先尝试只传一个参数
                        file_info = client.files.get(file_id)
                    except TypeError as e:
                        try:
                            # 尝试关键字参数
                            file_info = client.files.get(name=file_id)
                        except Exception as e2:
                            self.append_chat("错误", f"文件状态检测失败: {e2}")
                            return
                    except Exception as e:
                        self.append_chat("错误", f"文件状态检测失败: {e}")
                        return
                    if getattr(file_info, "state", None) == "ACTIVE":
                        break
                    _time.sleep(1)
                else:
                    self.append_chat("错误", "视频文件处理超时，请稍后重试。")
                    return
                response = client.models.generate_content(
                    model=self.model_var.get(),
                    contents=[
                        video_file,
                        user_input or "请总结该视频内容"
                    ]
                )
                ai_reply = getattr(response, 'text', str(response))
                self.append_chat("Gemini", ai_reply)
                final_time = None
                if hasattr(self, 'gen_start_time') and self.gen_start_time:
                    final_time = time.time() - self.gen_start_time
                use_time_str = self.stop_gen_timer(final_time, gen_type="视频")
                if use_time_str:
                    self.append_chat("System", use_time_str)
            elif mode == "音频理解":
                # 上传音频文件
                audio_file = client.files.upload(file=self.audio_path.get())
                # 轮询等待文件变为ACTIVE
                import time as _time
                file_id = getattr(audio_file, "name", None) or getattr(audio_file, "id", None)
                file_info = None
                for _ in range(30):  # 最多等30秒
                    try:
                        file_info = client.files.get(file_id)
                    except TypeError as e:
                        try:
                            file_info = client.files.get(name=file_id)
                        except Exception as e2:
                            self.append_chat("错误", f"音频文件状态检测失败: {e2}")
                            return
                    except Exception as e:
                        self.append_chat("错误", f"音频文件状态检测失败: {e}")
                        return
                    if getattr(file_info, "state", None) == "ACTIVE":
                        break
                    _time.sleep(1)
                else:
                    self.append_chat("错误", "音频文件处理超时，请稍后重试。")
                    return
                response = client.models.generate_content(
                    model=self.model_var.get(),
                    contents=[
                        user_input or "请描述该音频内容",
                        audio_file
                    ]
                )
                ai_reply = getattr(response, 'text', str(response))
                self.append_chat("Gemini", ai_reply)
                final_time = None
                if hasattr(self, 'gen_start_time') and self.gen_start_time:
                    final_time = time.time() - self.gen_start_time
                use_time_str = self.stop_gen_timer(final_time, gen_type="音频")
                if use_time_str:
                    self.append_chat("System", use_time_str)
            else:
                ai_reply = "暂不支持该模式。"
                self.append_chat("Gemini", ai_reply)
        except Exception as e:
            err_str = str(e)
            # 检查是否为500服务端错误
            if '500' in err_str or 'INTERNAL' in err_str:
                messagebox.showerror("服务故障", "服务端发生故障，请稍后重试或参考官方故障排查页面。\nhttps://developers.generativeai.google/guide/troubleshooting")
                self.append_chat("错误", "服务端发生故障，请稍后重试或参考官方故障排查页面：\nhttps://developers.generativeai.google/guide/troubleshooting")
            else:
                self.append_chat("错误", err_str)

    def on_close(self):
        if messagebox.askokcancel("退出", "确定要退出 Gemini 聊天机器人吗？"):
            self.root.destroy()

    def insert_func_template(self, key):
        if key in self.func_templates:
            self.func_decl_text.delete("1.0", tk.END)
            self.func_decl_text.insert(tk.END, self.func_templates[key])

    def open_settings(self):
        if self.settings_window and tk.Toplevel.winfo_exists(self.settings_window):
            self.settings_window.deiconify()
            self.settings_window.lift()
            return
        self.settings_window = tk.Toplevel(self.root)
        self.settings_window.title("设置")
        self.settings_window.geometry("700x750")
        self.settings_window.configure(bg="#f5f6fa")
        self.settings_window.protocol("WM_DELETE_WINDOW", self.hide_settings_window)
        # API Key
        api_frame = tk.Frame(self.settings_window, bg="#f5f6fa")
        tk.Label(api_frame, text="Gemini API Key:", font=("微软雅黑", 10), bg="#f5f6fa").pack(side=tk.LEFT, padx=(0,2))
        api_entry = tk.Entry(api_frame, textvariable=self.api_key_var, width=50, font=("微软雅黑", 10))  # 明文显示
        api_entry.pack(side=tk.LEFT, padx=(0,2))
        tk.Button(api_frame, text="复制", font=("微软雅黑", 10), command=lambda: self.copy_to_clipboard(self.api_key_var.get())).pack(side=tk.LEFT, padx=(2,0))
        tk.Button(api_frame, text="应用", font=("微软雅黑", 10), command=self.apply_api_key).pack(side=tk.LEFT, padx=(4,0))
        api_frame.pack(pady=(0,5), fill=tk.X)
        self.api_key_label = tk.Label(self.settings_window, text=f"当前API Key: {self.current_api_key}", font=("微软雅黑", 9), bg="#f5f6fa", fg="#3867d6")
        self.api_key_label.pack(anchor=tk.W, padx=12)
        # 绑定输入框内容变化，实时刷新API Key显示
        self.api_key_var.trace_add('write', lambda *args: self.api_key_label.config(text=f"当前API Key: {self.api_key_var.get()}"))
        # 模型选择
        model_frame = tk.Frame(self.settings_window, bg="#f5f6fa")
        tk.Label(model_frame, text="模型选择:", font=("微软雅黑", 10), bg="#f5f6fa").pack(side=tk.LEFT, padx=(0,2))
        # 构造下拉菜单内容
        menu_options = []
        for opt in self.model_options:
            if opt in self.available_models:
                menu_options.append(opt)
            else:
                menu_options.append(f"[不可用]{opt}")
        self.model_menu = tk.OptionMenu(model_frame, self.model_var, *menu_options, command=self.on_model_select)
        self.model_menu.config(font=("微软雅黑", 10), bg="#d1d8e0", relief=tk.GROOVE, highlightthickness=0, bd=0, activebackground="#778beb")
        self.model_menu.pack(side=tk.LEFT)
        model_frame.pack(pady=(0,5), fill=tk.X)
        # 模型说明
        self.model_desc_label = tk.Label(self.settings_window, text="", font=("微软雅黑", 9), bg="#f5f6fa", fg="#3867d6", wraplength=600, justify=tk.LEFT)
        self.model_desc_label.pack(anchor=tk.W, padx=12, pady=(0,8))
        self.update_model_desc()
        # 不可用模型提示
        if len(self.available_models) < len(self.model_options):
            unavailable = [m for m in self.model_options if m not in self.available_models]
            if unavailable:
                tk.Label(self.settings_window, text=f"不可用模型: {', '.join(unavailable)}（当前API Key不可用）", font=("微软雅黑", 9), bg="#f5f6fa", fg="#e17055").pack(anchor=tk.W, padx=12, pady=(0,8))
        # 图片保存路径
        img_dir_frame = tk.Frame(self.settings_window, bg="#f5f6fa")
        tk.Label(img_dir_frame, text="图片保存路径:", font=("微软雅黑", 10), bg="#f5f6fa").pack(side=tk.LEFT, padx=(0,2))
        img_dir_entry = tk.Entry(img_dir_frame, textvariable=self.image_save_dir, width=40, font=("微软雅黑", 10))
        img_dir_entry.pack(side=tk.LEFT, padx=(0,2))
        tk.Button(img_dir_frame, text="选择", font=("微软雅黑", 10), command=self.select_image_dir).pack(side=tk.LEFT, padx=(4,0))
        img_dir_frame.pack(pady=(0,5), fill=tk.X)
        # 历史文件保存路径
        hist_dir_frame = tk.Frame(self.settings_window, bg="#f5f6fa")
        tk.Label(hist_dir_frame, text="历史文件保存路径:", font=("微软雅黑", 10), bg="#f5f6fa").pack(side=tk.LEFT, padx=(0,2))
        hist_dir_entry = tk.Entry(hist_dir_frame, textvariable=self.history_save_dir, width=40, font=("微软雅黑", 10))
        hist_dir_entry.pack(side=tk.LEFT, padx=(0,2))
        tk.Button(hist_dir_frame, text="选择", font=("微软雅黑", 10), command=self.select_history_dir).pack(side=tk.LEFT, padx=(4,0))
        hist_dir_frame.pack(pady=(0,5), fill=tk.X)
        # 系统指令区
        sysinst_frame = tk.Frame(self.settings_window, bg="#f5f6fa")
        tk.Label(sysinst_frame, text="系统指令:", font=("微软雅黑", 10), bg="#f5f6fa").pack(side=tk.LEFT, padx=(0,2))
        self.sysinst_entry = tk.Entry(sysinst_frame, textvariable=self.sysinst_var, width=40, font=("微软雅黑", 10))
        self.sysinst_entry.pack(side=tk.LEFT, padx=(0,2))
        sysinst_frame.pack(pady=(0,5), fill=tk.X)
        # 参数调节区
        param_frame = tk.Frame(self.settings_window, bg="#f5f6fa")
        tk.Label(param_frame, text="温度 (temperature):", font=("微软雅黑", 10), bg="#f5f6fa").grid(row=0, column=0, sticky=tk.W, padx=2)
        self.temp_scale = tk.Scale(param_frame, from_=0.0, to=1.0, resolution=0.01, orient=tk.HORIZONTAL, variable=self.temp_var, length=180, bg="#f5f6fa")
        self.temp_scale.grid(row=0, column=1, padx=2)
        tk.Label(param_frame, text="最大输出长度:", font=("微软雅黑", 10), bg="#f5f6fa").grid(row=0, column=2, sticky=tk.W, padx=2)
        self.max_tokens_entry = tk.Entry(param_frame, textvariable=self.max_tokens_var, width=6, font=("微软雅黑", 10))
        self.max_tokens_entry.grid(row=0, column=3, padx=2)
        param_frame.pack(pady=(0,5), fill=tk.X)
        # 结构化格式选择
        struct_frame = tk.Frame(self.settings_window, bg="#f5f6fa")
        tk.Label(struct_frame, text="结构化格式：", font=("微软雅黑", 10), bg="#f5f6fa").pack(side=tk.LEFT, padx=(0,2))
        self.struct_menu = tk.OptionMenu(struct_frame, self.struct_format_var, "无", "JSON", "Markdown", "YAML", "CSV", "HTML", "LaTeX", "XML", "表格")
        self.struct_menu.config(font=("微软雅黑", 10), bg="#d1d8e0", relief=tk.GROOVE, highlightthickness=0, bd=0, activebackground="#778beb")
        self.struct_menu.pack(side=tk.LEFT)
        struct_frame.pack(pady=(0,5), fill=tk.X)
        # 函数声明区
        func_frame = tk.Frame(self.settings_window, bg="#f5f6fa")
        tk.Label(func_frame, text="函数声明（JSON，可选）：", font=("微软雅黑", 10), bg="#f5f6fa").pack(side=tk.LEFT, padx=(0,2))
        self.func_template_var = tk.StringVar(value="选择模板")
        self.func_template_menu = tk.OptionMenu(func_frame, self.func_template_var, *(["选择模板"] + list(self.func_templates.keys())), command=self.insert_func_template)
        self.func_template_menu.config(font=("微软雅黑", 10), bg="#d1d8e0", relief=tk.GROOVE, highlightthickness=0, bd=0, activebackground="#778beb")
        self.func_template_menu.pack(side=tk.LEFT, padx=(0,2))
        func_decl_scroll = tk.Scrollbar(func_frame, orient=tk.VERTICAL)
        self.func_decl_text = tk.Text(func_frame, font=("微软雅黑", 10), height=4, width=60, wrap=tk.WORD, yscrollcommand=func_decl_scroll.set, maxundo=20)
        func_decl_scroll.config(command=self.func_decl_text.yview)
        self.func_decl_text.pack(side=tk.LEFT, padx=(0,2), fill=tk.BOTH, expand=False)
        func_decl_scroll.pack(side=tk.LEFT, fill=tk.Y)
        func_frame.pack(pady=(0,5), fill=tk.X)
        # Google 搜索接地开关
        grounding_frame = tk.Frame(self.settings_window, bg="#f5f6fa")
        self.grounding_checkbox = tk.Checkbutton(grounding_frame, text="启用Google搜索接地（权威来源/搜索建议）", variable=self.enable_grounding_var, bg="#f5f6fa", font=("微软雅黑", 10))
        self.grounding_checkbox.pack(side=tk.LEFT)
        grounding_frame.pack(pady=(0,5), fill=tk.X)
        # 刷新所有设置区控件为当前值
        self.api_key_var.set(self.current_api_key)
        self.model_var.set(self.model_var.get())
        self.image_save_dir.set(self.image_save_dir.get())
        self.history_save_dir.set(self.history_save_dir.get())

    def hide_settings_window(self):
        if self.settings_window:
            self.settings_window.withdraw()

    def show_mode_menu(self):
        if self.mode_menu_window and tk.Toplevel.winfo_exists(self.mode_menu_window):
            self.mode_menu_window.lift()
            return
        self.mode_menu_window = tk.Toplevel(self.root)
        self.mode_menu_window.overrideredirect(True)
        self.mode_menu_window.configure(bg="#e3eafc")
        # 定位到mode_btn下方
        x = self.mode_btn.winfo_rootx()
        y = self.mode_btn.winfo_rooty() + self.mode_btn.winfo_height()
        menu_height = len(self.mode_options)*44 + 8  # 每个按钮44像素，上下各4像素padding
        self.mode_menu_window.geometry(f"160x{menu_height}+{x}+{y}")
        # 顶部空白
        tk.Frame(self.mode_menu_window, height=4, bg="#e3eafc").pack(fill=tk.X)
        for idx, opt in enumerate(self.mode_options):
            btn = RoundButton(self.mode_menu_window, text=opt, command=lambda o=opt: self.select_mode(o), font=("微软雅黑", 11, "bold"), bg="#4b7bec" if self.mode_var.get()!=opt else "#20bf6b", fg="white", hover_bg="#26de81", radius=14)
            btn.pack(fill=tk.X, padx=8, pady=2)
        # 底部空白
        tk.Frame(self.mode_menu_window, height=4, bg="#e3eafc").pack(fill=tk.X)
        # 点击菜单外自动关闭
        self.mode_menu_window.bind("<FocusOut>", lambda e: self.mode_menu_window.destroy())
        self.mode_menu_window.focus_set()

    def select_mode(self, mode):
        self.mode_var.set(mode)
        self.mode_btn.itemconfig(self.mode_btn.text_id, text=mode)
        if self.mode_menu_window:
            self.mode_menu_window.destroy()

    def update_mode_btn_text(self, *args):
        new_text = self.mode_var.get()
        self.mode_btn.text = new_text  # 同步更新按钮的text属性
        self.mode_btn.itemconfig(self.mode_btn.text_id, text=new_text)
        self.mode_btn.draw_button(self.mode_btn.bg)  # 立即重绘，确保显示

    def apply_api_key(self):
        global client
        client = genai.Client(api_key=self.api_key_var.get())
        self.current_api_key = self.api_key_var.get()
        if hasattr(self, 'api_key_label'):
            self.api_key_label.config(text=f"当前API Key: {self.current_api_key}")
        self.save_config()
        messagebox.showinfo("提示", "API Key 已应用！")

    def select_image_dir(self):
        dir_path = filedialog.askdirectory()
        if dir_path:
            self.image_save_dir.set(dir_path)
            self.save_config()
    def select_history_dir(self):
        dir_path = filedialog.askdirectory()
        if dir_path:
            self.history_save_dir.set(dir_path)
            self.save_config()

    def copy_to_clipboard(self, text):
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        messagebox.showinfo("提示", "API Key 已复制到剪贴板！")

    def update_model_desc(self, *args):
        desc_map = {
            "gemini-2.0-flash": "gemini-2.0-flash：适合高并发、低延迟场景，价格低廉，适合大批量请求。",
            "gemini-2.0-pro": "gemini-2.0-pro：适合高质量文本生成、复杂推理、内容创作等场景，价格略高，效果更好。",
            "gemini-1.5-pro": "gemini-1.5-pro：上下文窗口长达200万token，适合超长文档、复杂推理。",
            "gemini-1.5-flash-8b": "gemini-1.5-flash-8b：适合对速度要求高、智能度要求较低的场景。",
            "gemini-2.0-flash-exp-image-generation": "gemini-2.0-flash-exp-image-generation：适合图片生成任务，支持文本到图片的高效生成。"
        }
        model = self.model_var.get().replace("[不可用]", "")
        if hasattr(self, 'model_desc_label') and self.model_desc_label:
            self.model_desc_label.config(text=desc_map.get(model, ""))

    def detect_available_models(self):
        try:
            model_list = client.models.list()
            self.available_models = set([m.name.split("/")[-1] for m in model_list])
        except Exception as e:
            self.available_models = set(["gemini-2.0-flash", "gemini-2.0-flash-exp-image-generation"])  # 最基础兜底

    def on_model_select(self, value):
        # 只允许选择可用模型
        if value.startswith("[不可用]"):
            messagebox.showwarning("提示", "该模型当前API Key不可用，请选择可用模型！")
            # 自动切回第一个可用模型
            for opt in self.model_options:
                if opt in self.available_models:
                    self.model_var.set(opt)
                    break
        else:
            self.model_var.set(value)
        self.update_model_desc()
        self.save_config()

    def save_config(self):
        config = {
            "api_key": getattr(self, 'current_api_key', ""),
            "model": self.model_var.get() if hasattr(self, 'model_var') else "",
            "image_save_dir": self.image_save_dir.get() if hasattr(self, 'image_save_dir') else "",
            "history_save_dir": self.history_save_dir.get() if hasattr(self, 'history_save_dir') else "",
            "temperature": self.temp_var.get() if hasattr(self, 'temp_var') else 0.2,
            "max_output_tokens": self.max_tokens_var.get() if hasattr(self, 'max_tokens_var') else 200,
            "system_instruction": self.sysinst_var.get() if hasattr(self, 'sysinst_var') else "",
            "struct_format": self.struct_format_var.get() if hasattr(self, 'struct_format_var') else "无",
            "func_decl": self.func_decl_text.get("1.0", tk.END) if hasattr(self, 'func_decl_text') and self.func_decl_text else "",
            "enable_grounding": self.enable_grounding_var.get(),
        }
        with open("config.json", "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)

    def load_config(self):
        import pathlib
        config_path = pathlib.Path("config.json")
        if config_path.exists():
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    config = json.load(f)
                if "api_key" in config and hasattr(self, 'api_key_var'):
                    self.api_key_var.set(config["api_key"])
                    self.current_api_key = config["api_key"]
                    global client
                    client = genai.Client(api_key=self.current_api_key)
                if "model" in config and hasattr(self, 'model_var') and config["model"] in self.all_model_options:
                    self.model_var.set(config["model"])
                if "image_save_dir" in config and hasattr(self, 'image_save_dir'):
                    self.image_save_dir.set(config["image_save_dir"])
                if "history_save_dir" in config and hasattr(self, 'history_save_dir'):
                    self.history_save_dir.set(config["history_save_dir"])
                if "temperature" in config and hasattr(self, 'temp_var'):
                    self.temp_var.set(config["temperature"])
                if "max_output_tokens" in config and hasattr(self, 'max_tokens_var'):
                    self.max_tokens_var.set(config["max_output_tokens"])
                if "system_instruction" in config and hasattr(self, 'sysinst_var'):
                    self.sysinst_var.set(config["system_instruction"])
                if "struct_format" in config and hasattr(self, 'struct_format_var'):
                    self.struct_format_var.set(config["struct_format"])
                if "func_decl" in config and hasattr(self, 'func_decl_text') and self.func_decl_text is not None:
                    self.func_decl_text.delete("1.0", tk.END)
                    self.func_decl_text.insert(tk.END, config["func_decl"])
                if "enable_grounding" in config and hasattr(self, 'enable_grounding_var'):
                    self.enable_grounding_var.set(config["enable_grounding"])
            except Exception as e:
                print(f"加载配置文件失败: {e}")

    def on_struct_format_change(self, *args):
        self.save_config()
    def on_temp_change(self, *args):
        self.save_config()
    def on_max_tokens_change(self, *args):
        self.save_config()
    def on_sysinst_change(self, *args):
        self.save_config()
    def on_func_decl_change(self, event=None):
        self.save_config()

if __name__ == "__main__":
    root = tk.Tk()
    app = GeminiChatGUI(root)
    root.mainloop() 
