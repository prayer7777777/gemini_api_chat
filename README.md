# Gemini 聊天机器人（多功能桌面版）

## 项目简介

本项目是基于 Google Gemini API 的多功能桌面聊天机器人，支持文本生成、图片/文档/音频/视频理解、函数调用、结构化输出、Google 搜索接地等多种能力，界面美观，交互友好，适合学习、科研与日常使用。

## 主要功能

- 文本生成与多轮对话
- 图片、文档、音频、视频理解
- 图片生成
- 函数调用（Function Calling）
- 结构化输出（JSON/Markdown/表格等）
- Google 搜索接地（权威来源/搜索建议）
- 支持自定义系统指令、参数调节
- 聊天历史与配置自动保存

## 环境依赖

请确保已安装 Python 3.8 及以上版本。

安装依赖：
```bash
pip install -r requirements.txt
```

`requirements.txt` 内容如下：
```
flask==2.0.1
python-docx==0.8.11
werkzeug==2.0.3
tk
Pillow
google-generativeai
```

## 快速开始

1. **获取 Gemini API Key**  
   前往 [Google AI Studio](https://aistudio.google.com/app/apikey) 获取你的 API Key。

2. **配置 API Key**  
   - 启动程序后，点击“设置”，在“Gemini API Key”处粘贴你的 Key 并点击“应用”。
   - API Key 会自动保存到本地 config.json。

3. **运行主程序**
   ```bash
   python gemini_chat.py
   ```

4. **开始对话**  
   - 选择功能（文本生成、图片理解、音频理解等）
   - 输入内容，点击“发送”即可体验多模态 Gemini 聊天。

## 文件说明

- `gemini_chat.py`：主程序，Tkinter 图形界面，全部功能集成。
- `requirements.txt`：依赖列表。
- `config.json`：本地配置文件（自动生成/保存）。
- `history.txt`：聊天历史记录（自动生成/保存）。
- `gemini_ai.py`、`gemini_ai_gui.py`、`gemini.py`：命令行/简化版示例（可选）。

## 常见问题

- **API Key 无效/模型不可用？**  
  请确认 API Key 有效且已绑定 Gemini API 权限，部分模型需付费或区域支持。
- **界面乱码？**  
  请确保系统已安装微软雅黑字体，或修改代码中的字体设置。
- **依赖安装失败？**  
  建议使用最新版 pip，或手动安装缺失的包。

## 参考文档

- [Google Gemini API 官方文档](https://ai.google.dev/gemini-api/docs)
- [Google AI Studio](https://aistudio.google.com/app/apikey)

---

如有建议或问题，欢迎 issue 或 PR！  
Enjoy Gemini AI！
