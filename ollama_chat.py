#!/usr/bin/env python3
"""
Ollama Chat - A wxPython GUI application for local LLM chat with Ollama
Features:
- Local LLM support through Ollama
- Keyboard shortcuts: Ctrl+N (new chat), Ctrl+S (save chat), Ctrl+M (select model), Ctrl+O (options)
- Screen reader accessibility
- Model management and chat history
- Open saved chats directly
"""

import wx
import json
import os
import subprocess
import threading            
import requests
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional

# Configuration
CONFIG_DIR = Path.home() / ".ollama_chat"
CHATS_DIR = CONFIG_DIR / "chats"
CONFIG_FILE = CONFIG_DIR / "config.json"
OLLAMA_API = "http://localhost:11434"

# Ensure directories exist
CONFIG_DIR.mkdir(exist_ok=True)
CHATS_DIR.mkdir(exist_ok=True)


class OllamaManager:
    """Manages Ollama API interactions"""
    
    @staticmethod
    def get_models() -> List[str]:
        """Fetch available models from Ollama"""
        try:
            response = requests.get(f"{OLLAMA_API}/api/tags", timeout=5)
            if response.status_code == 200:
                data = response.json()
                models = data.get("models", [])
                return [m["name"] for m in models]
        except Exception as e:
            print(f"Error fetching models: {e}")
        return []
    
    @staticmethod
    def pull_model(model_name: str, callback=None) -> bool:
        """Download a model from Ollama"""
        try:
            response = requests.post(
                f"{OLLAMA_API}/api/pull",
                json={"name": model_name},
                stream=True,
                timeout=None
            )
            if response.status_code == 200:
                for line in response.iter_lines():
                    if callback:
                        callback(line.decode() if isinstance(line, bytes) else line)
                return True
        except Exception as e:
            print(f"Error pulling model: {e}")
        return False
    
    @staticmethod
    def generate_response(model: str, prompt: str, callback=None) -> str:
        """Generate response from Ollama"""
        try:
            response = requests.post(
                f"{OLLAMA_API}/api/generate",
                json={
                    "model": model,
                    "prompt": prompt,
                    "stream": True
                },
                stream=True,
                timeout=None
            )
            
            full_response = ""
            if response.status_code == 200:
                for line in response.iter_lines():
                    if line:
                        data = json.loads(line)
                        response_text = data.get("response", "")
                        full_response += response_text
                        if callback:
                            callback(response_text)
            return full_response
        except Exception as e:
            error_msg = f"Error generating response: {e}"
            print(error_msg)
            return error_msg


class ChatManager:
    """Manages chat history and persistence"""
    
    @staticmethod
    def get_chat_list() -> List[Dict]:
        """Get list of saved chats"""
        chats = []
        if CHATS_DIR.exists():
            for chat_file in CHATS_DIR.glob("*.json"):
                try:
                    with open(chat_file, 'r') as f:
                        chat = json.load(f)
                        chats.append(chat)
                except Exception as e:
                    print(f"Error loading chat: {e}")
        return sorted(chats, key=lambda x: x.get("created_at", ""), reverse=True)
    
    @staticmethod
    def save_chat(filepath: str, messages: List[Dict], model: str) -> bool:
        """Save chat to text file"""
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(f"=== Ollama Chat ===\n")
                f.write(f"Model: {model}\n")
                f.write(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write("=" * 50 + "\n\n")
                
                for msg in messages:
                    role = msg.get("role", "Unknown").upper()
                    content = msg.get("content", "")
                    f.write(f"[{role}]\n{content}\n\n")
                    f.write("-" * 50 + "\n\n")
            
            return True
        except Exception as e:
            print(f"Error saving chat: {e}")
            return False
    
    @staticmethod
    def load_chat_from_txt(filepath: str) -> Optional[Dict]:
        """Load chat from text file"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            
            lines = content.split('\n')
            model = "Unknown"
            messages = []
            current_role = None
            current_content = []
            
            # Parse the file
            for line in lines:
                if line.startswith("Model: "):
                    model = line.replace("Model: ", "").strip()
                elif line.startswith("[USER]"):
                    if current_role and current_content:
                        messages.append({
                            "role": current_role,
                            "content": '\n'.join(current_content).strip()
                        })
                    current_role = "user"
                    current_content = []
                elif line.startswith("[ASSISTANT]"):
                    if current_role and current_content:
                        messages.append({
                            "role": current_role,
                            "content": '\n'.join(current_content).strip()
                        })
                    current_role = "assistant"
                    current_content = []
                elif line.startswith("-" * 50):
                    if current_role and current_content:
                        messages.append({
                            "role": current_role,
                            "content": '\n'.join(current_content).strip()
                        })
                    current_role = None
                    current_content = []
                elif current_role and not line.startswith("===") and not line.startswith("Date:"):
                    current_content.append(line)
            
            # Add last message if exists
            if current_role and current_content:
                messages.append({
                    "role": current_role,
                    "content": '\n'.join(current_content).strip()
                })
            
            return {
                "model": model,
                "messages": messages,
                "name": Path(filepath).stem
            }
        except Exception as e:
            print(f"Error loading chat: {e}")
            return None


class ModelManagerDialog(wx.Dialog):
    """Dialog for managing Ollama models"""
    
    def __init__(self, parent):
        super().__init__(parent, title="Model Manager", size=(500, 400))
        self.init_ui()
        self.load_models()
    
    def init_ui(self):
        """Initialize UI components"""
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Title
        title = wx.StaticText(self, label="Installed Models")
        main_sizer.Add(title, 0, wx.ALL, 5)
        
        # Models list
        self.models_list = wx.ListBox(self, choices=[], name="Installed Models")
        self.models_list.SetToolTip("List of currently installed Ollama models")
        main_sizer.Add(self.models_list, 1, wx.EXPAND | wx.ALL, 5)
        
        # Download section
        download_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.model_input = wx.TextCtrl(self, name="Model name input")
        self.model_input.SetToolTip("Enter model name (e.g., llama2, mistral)")
        download_btn = wx.Button(self, label="Download Model")
        download_btn.Bind(wx.EVT_BUTTON, self.on_download)
        
        download_sizer.Add(self.model_input, 1, wx.EXPAND | wx.ALL, 5)
        download_sizer.Add(download_btn, 0, wx.ALL, 5)
        main_sizer.Add(download_sizer, 0, wx.EXPAND | wx.ALL, 5)
        
        # Progress
        self.progress = wx.Gauge(self, range=100, name="Download progress")
        main_sizer.Add(self.progress, 0, wx.EXPAND | wx.ALL, 5)
        
        self.progress_text = wx.StaticText(self, label="")
        main_sizer.Add(self.progress_text, 0, wx.EXPAND | wx.ALL, 5)
        
        # Buttons
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        refresh_btn = wx.Button(self, label="Refresh")
        refresh_btn.Bind(wx.EVT_BUTTON, lambda e: self.load_models())
        close_btn = wx.Button(self, wx.ID_CLOSE)
        close_btn.Bind(wx.EVT_BUTTON, lambda e: self.EndModal(wx.ID_CLOSE))
        
        btn_sizer.Add(refresh_btn, 0, wx.ALL, 5)
        btn_sizer.Add(close_btn, 0, wx.ALL, 5)
        main_sizer.Add(btn_sizer, 0, wx.CENTER | wx.ALL, 5)
        
        self.SetSizer(main_sizer)
    
    def load_models(self):
        """Load and display available models"""
        models = OllamaManager.get_models()
        self.models_list.Set(models)
        if models:
            self.progress_text.SetLabel(f"Found {len(models)} model(s)")
        else:
            self.progress_text.SetLabel("No models found. Download one to get started.")
    
    def on_download(self, event):
        """Handle model download"""
        model_name = self.model_input.GetValue().strip()
        if not model_name:
            wx.MessageBox("Please enter a model name", "Input Error", wx.OK | wx.ICON_ERROR)
            return
        
        self.progress.SetValue(0)
        self.progress_text.SetLabel(f"Downloading {model_name}...")
        
        def download_thread():
            OllamaManager.pull_model(model_name, self.update_progress)
            wx.CallAfter(self.load_models)
            wx.CallAfter(self.progress_text.SetLabel, f"Downloaded {model_name}")
        
        thread = threading.Thread(target=download_thread)
        thread.daemon = True
        thread.start()
    
    def update_progress(self, message):
        """Update progress during download"""
        try:
            data = json.loads(message) if isinstance(message, str) else message
            if "total" in data and "completed" in data:
                progress = int((data["completed"] / data["total"]) * 100)
                wx.CallAfter(self.progress.SetValue, progress)
        except:
            pass


class SettingsDialog(wx.Dialog):
    """Dialog for application settings"""
    
    def __init__(self, parent):
        super().__init__(parent, title="Settings", size=(400, 300))
        self.init_ui()
        self.load_settings()
    
    def init_ui(self):
        """Initialize UI components"""
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Ollama API URL
        api_sizer = wx.BoxSizer(wx.HORIZONTAL)
        api_label = wx.StaticText(self, label="Ollama API URL:")
        self.api_input = wx.TextCtrl(self, name="Ollama API URL")
        api_sizer.Add(api_label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        api_sizer.Add(self.api_input, 1, wx.EXPAND | wx.ALL, 5)
        main_sizer.Add(api_sizer, 0, wx.EXPAND | wx.ALL, 5)
        
        # Theme
        theme_sizer = wx.BoxSizer(wx.HORIZONTAL)
        theme_label = wx.StaticText(self, label="Theme:")
        self.theme_choice = wx.Choice(self, choices=["Light", "Dark"], name="Theme selection")
        theme_sizer.Add(theme_label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        theme_sizer.Add(self.theme_choice, 1, wx.EXPAND | wx.ALL, 5)
        main_sizer.Add(theme_sizer, 0, wx.EXPAND | wx.ALL, 5)
        
        # Auto-save
        self.autosave_cb = wx.CheckBox(self, label="Auto-save chats every 5 minutes", name="Auto-save setting")
        main_sizer.Add(self.autosave_cb, 0, wx.ALL, 5)
        
        # Buttons
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        save_btn = wx.Button(self, wx.ID_SAVE)
        save_btn.Bind(wx.EVT_BUTTON, self.on_save)
        close_btn = wx.Button(self, wx.ID_CLOSE)
        close_btn.Bind(wx.EVT_BUTTON, lambda e: self.EndModal(wx.ID_CLOSE))
        
        btn_sizer.Add(save_btn, 0, wx.ALL, 5)
        btn_sizer.Add(close_btn, 0, wx.ALL, 5)
        main_sizer.Add(btn_sizer, 0, wx.CENTER | wx.ALL, 5)
        
        self.SetSizer(main_sizer)
    
    def load_settings(self):
        """Load settings from config file"""
        try:
            if CONFIG_FILE.exists():
                with open(CONFIG_FILE, 'r') as f:
                    config = json.load(f)
                    self.api_input.SetValue(config.get("api_url", OLLAMA_API))
                    self.theme_choice.SetSelection(0 if config.get("theme", "Light") == "Light" else 1)
                    self.autosave_cb.SetValue(config.get("autosave", False))
            else:
                self.api_input.SetValue(OLLAMA_API)
                self.theme_choice.SetSelection(0)
        except Exception as e:
            print(f"Error loading settings: {e}")
    
    def on_save(self, event):
        """Save settings to config file"""
        try:
            config = {
                "api_url": self.api_input.GetValue(),
                "theme": self.theme_choice.GetStringSelection(),
                "autosave": self.autosave_cb.GetValue()
            }
            with open(CONFIG_FILE, 'w') as f:
                json.dump(config, f, indent=2)
            wx.MessageBox("Settings saved successfully", "Success", wx.OK | wx.ICON_INFORMATION)
        except Exception as e:
            wx.MessageBox(f"Error saving settings: {e}", "Error", wx.OK | wx.ICON_ERROR)


class ChatHistoryDialog(wx.Dialog):
    """Dialog for viewing and loading chat history"""
    
    def __init__(self, parent):
        super().__init__(parent, title="Chat History", size=(500, 400))
        self.parent_frame = parent
        self.init_ui()
        self.load_history()
    
    def init_ui(self):
        """Initialize UI components"""
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        
        title = wx.StaticText(self, label="Saved Chats")
        main_sizer.Add(title, 0, wx.ALL, 5)
        
        # Chat list
        self.chat_list = wx.ListBox(self, choices=[], name="Chat history list")
        self.chat_list.SetToolTip("Double-click to load a chat")
        self.chat_list.Bind(wx.EVT_LISTBOX_DCLICK, self.on_load_chat)
        main_sizer.Add(self.chat_list, 1, wx.EXPAND | wx.ALL, 5)
        
        # Buttons
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        load_btn = wx.Button(self, label="Load Selected")
        load_btn.Bind(wx.EVT_BUTTON, self.on_load_chat)
        delete_btn = wx.Button(self, label="Delete Selected")
        delete_btn.Bind(wx.EVT_BUTTON, self.on_delete_chat)
        close_btn = wx.Button(self, wx.ID_CLOSE)
        close_btn.Bind(wx.EVT_BUTTON, lambda e: self.EndModal(wx.ID_CLOSE))
        
        btn_sizer.Add(load_btn, 0, wx.ALL, 5)
        btn_sizer.Add(delete_btn, 0, wx.ALL, 5)
        btn_sizer.Add(close_btn, 0, wx.ALL, 5)
        main_sizer.Add(btn_sizer, 0, wx.CENTER | wx.ALL, 5)
        
        self.SetSizer(main_sizer)
    
    def load_history(self):
        """Load chat history from txt files"""
        self.chat_files = []
        if CHATS_DIR.exists():
            for chat_file in CHATS_DIR.glob("*.txt"):
                self.chat_files.append(chat_file)
        
        chat_names = [f.stem for f in self.chat_files]
        self.chat_list.Set(chat_names)
    
    def on_load_chat(self, event):
        """Load selected chat"""
        selection = self.chat_list.GetSelection()
        if selection != wx.NOT_FOUND and selection < len(self.chat_files):
            chat = ChatManager.load_chat_from_txt(str(self.chat_files[selection]))
            if chat:
                self.parent_frame.load_chat_data(chat)
                self.EndModal(wx.ID_OK)
    
    def on_delete_chat(self, event):
        """Delete selected chat"""
        selection = self.chat_list.GetSelection()
        if selection != wx.NOT_FOUND and selection < len(self.chat_files):
            dlg = wx.MessageDialog(
                self,
                f"Delete '{self.chat_files[selection].stem}'? This cannot be undone.",
                "Confirm Delete",
                wx.YES_NO | wx.ICON_QUESTION
            )
            if dlg.ShowModal() == wx.ID_YES:
                try:
                    self.chat_files[selection].unlink()
                    wx.MessageBox("Chat deleted successfully", "Success", wx.OK | wx.ICON_INFORMATION)
                    self.load_history()
                except Exception as e:
                    wx.MessageBox(f"Error deleting chat: {e}", "Error", wx.OK | wx.ICON_ERROR)
            dlg.Destroy()


class MainFrame(wx.Frame):
    """Main application window"""
    
    def __init__(self):
        super().__init__(None, title="Ollama Chat", size=(900, 700))
        self.current_chat_file = None
        self.is_saved = False
        self.messages = []
        self.init_ui()
        self.bind_shortcuts()
        self.load_models()
        self.Centre()
    
    def init_ui(self):
        """Initialize main UI"""
        # Main panel
        main_panel = wx.Panel(self)
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Title with role
        title = wx.StaticText(main_panel, label="Ollama Chat")
        title.SetToolTip("Main chat application window")
        main_sizer.Add(title, 0, wx.ALL, 10)
        
        # Model selection
        model_sizer = wx.BoxSizer(wx.HORIZONTAL)
        model_label = wx.StaticText(main_panel, label="Model:")
        self.model_choice = wx.Choice(main_panel, name="Model selection")
        self.model_choice.SetToolTip("Select an Ollama model. Ctrl+M to change")
        model_sizer.Add(model_label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        model_sizer.Add(self.model_choice, 1, wx.EXPAND | wx.ALL, 5)
        main_sizer.Add(model_sizer, 0, wx.EXPAND | wx.ALL, 5)
        
        # Chat display area
        chat_label = wx.StaticText(main_panel, label="Chat History")
        main_sizer.Add(chat_label, 0, wx.ALL, 5)
        
        self.chat_display = wx.TextCtrl(
            main_panel,
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_WORDWRAP,
            name="Chat display area"
        )
        self.chat_display.SetToolTip("Chat history display. Messages appear here.")
        main_sizer.Add(self.chat_display, 1, wx.EXPAND | wx.ALL, 5)
        
        # User input
        input_label = wx.StaticText(main_panel, label="Your Message")
        main_sizer.Add(input_label, 0, wx.ALL, 5)
        
        self.user_input = wx.TextCtrl(
            main_panel,
            style=wx.TE_MULTILINE | wx.TE_WORDWRAP,
            name="User message input"
        )
        self.user_input.SetToolTip("Enter your message here and press Ctrl+Enter to send")
        main_sizer.Add(self.user_input, 0, wx.EXPAND | wx.ALL, 5)
        
        # Buttons
        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        send_btn = wx.Button(main_panel, label="Send (Ctrl+Enter)")
        send_btn.Bind(wx.EVT_BUTTON, self.on_send_message)
        
        new_chat_btn = wx.Button(main_panel, label="New Chat (Ctrl+N)")
        new_chat_btn.Bind(wx.EVT_BUTTON, self.on_new_chat)
        
        save_chat_btn = wx.Button(main_panel, label="Save Chat (Ctrl+S)")
        save_chat_btn.Bind(wx.EVT_BUTTON, self.on_save_chat)
        
        open_chat_btn = wx.Button(main_panel, label="Open Chat (Ctrl+O)")
        open_chat_btn.Bind(wx.EVT_BUTTON, self.on_open_chat)
        
        copy_btn = wx.Button(main_panel, label="Copy Response (Ctrl+C)")
        copy_btn.Bind(wx.EVT_BUTTON, self.on_copy_response)
        
        button_sizer.Add(send_btn, 0, wx.ALL, 5)
        button_sizer.Add(new_chat_btn, 0, wx.ALL, 5)
        button_sizer.Add(save_chat_btn, 0, wx.ALL, 5)
        button_sizer.Add(open_chat_btn, 0, wx.ALL, 5)
        button_sizer.Add(copy_btn, 0, wx.ALL, 5)
        main_sizer.Add(button_sizer, 0, wx.CENTER | wx.ALL, 5)
        
        # Status bar
        self.status_bar = self.CreateStatusBar()
        self.status_bar.SetStatusText("Ready")
        
        main_panel.SetSizer(main_sizer)
        self.create_menu_bar()
    
    def create_menu_bar(self):
        """Create menu bar"""
        menubar = wx.MenuBar()
        
        # File menu
        file_menu = wx.Menu()
        file_menu.Append(wx.ID_NEW, "New Chat\tCtrl+N")
        file_menu.Append(wx.ID_OPEN, "Open Chat\tCtrl+O")
        file_menu.Append(wx.ID_SAVE, "Save Chat\tCtrl+S")
        file_menu.AppendSeparator()
        file_menu.Append(wx.ID_EXIT, "Exit\tAlt+F4")
        menubar.Append(file_menu, "&File")
        
        # Tools menu
        tools_menu = wx.Menu()
        tools_menu.Append(wx.ID_ANY, "Select Model\tCtrl+M")
        tools_menu.AppendSeparator()
        tools_menu.Append(wx.ID_ANY, "Options\tCtrl+Shift+O")
        menubar.Append(tools_menu, "&Tools")
        
        self.SetMenuBar(menubar)
        self.Bind(wx.EVT_MENU, self.on_new_chat, id=wx.ID_NEW)
        self.Bind(wx.EVT_MENU, self.on_open_chat, id=wx.ID_OPEN)
        self.Bind(wx.EVT_MENU, self.on_save_chat, id=wx.ID_SAVE)
        self.Bind(wx.EVT_MENU, self.on_exit, id=wx.ID_EXIT)
    
    def bind_shortcuts(self):
        """Bind keyboard shortcuts"""
        self.Bind(wx.EVT_CHAR_HOOK, self.on_char_hook)
    
    def on_char_hook(self, event):
        """Handle keyboard shortcuts"""
        key_code = event.GetKeyCode()
        ctrl_down = event.ControlDown()
        shift_down = event.ShiftDown()
        
        if ctrl_down and key_code == ord('N'):
            self.on_new_chat(None)
            return
        elif ctrl_down and key_code == ord('S'):
            self.on_save_chat(None)
            return
        elif ctrl_down and key_code == ord('O') and not shift_down:
            self.on_open_chat(None)
            return
        elif ctrl_down and shift_down and key_code == ord('O'):
            self.show_options_menu()
            return
        elif ctrl_down and key_code == ord('M'):
            self.on_select_model(None)
            return
        elif ctrl_down and key_code == ord('C'):
            self.on_copy_response(None)
            return
        elif ctrl_down and key_code == wx.WXK_RETURN:
            self.on_send_message(None)
            return
        
        event.Skip()
    
    def load_models(self):
        """Load available models"""
        def load_thread():
            models = OllamaManager.get_models()
            wx.CallAfter(self.update_models, models)
        
        thread = threading.Thread(target=load_thread)
        thread.daemon = True
        thread.start()
    
    def update_models(self, models):
        """Update model choice"""
        self.model_choice.Set(models)
        if models:
            self.model_choice.SetSelection(0)
            self.status_bar.SetStatusText(f"Loaded {len(models)} models")
        else:
            self.status_bar.SetStatusText("No models available. Download a model first.")
    
    def on_select_model(self, event):
        """Show model selection"""
        if self.model_choice.GetCount() > 0:
            self.model_choice.SetFocus()
    
    def on_send_message(self, event):
        """Send message to LLM"""
        message = self.user_input.GetValue().strip()
        if not message:
            wx.MessageBox("Please enter a message", "Input Error", wx.OK | wx.ICON_WARNING)
            return
        
        if self.model_choice.GetSelection() == wx.NOT_FOUND:
            wx.MessageBox("Please select a model first", "Model Error", wx.OK | wx.ICON_ERROR)
            return
        
        model = self.model_choice.GetStringSelection()
        
        # Add user message to display
        self.chat_display.AppendText(f"\nYou: {message}\n")
        self.messages.append({"role": "user", "content": message})
        self.user_input.Clear()
        self.status_bar.SetStatusText("Generating response...")
        
        # Generate response in thread
        def response_thread():
            response = OllamaManager.generate_response(model, message, self.append_response)
            wx.CallAfter(self.finalize_response, response)
        
        thread = threading.Thread(target=response_thread)
        thread.daemon = True
        thread.start()
    
    def append_response(self, text):
        """Append response text as it streams"""
        wx.CallAfter(self.chat_display.AppendText, text)
    
    def finalize_response(self, response):
        """Finalize response after generation"""
        self.messages.append({"role": "assistant", "content": response})
        self.chat_display.AppendText("\n")
        self.status_bar.SetStatusText("Ready")
        self.is_saved = False
    
    def on_new_chat(self, event):
        """Start new chat"""
        if self.messages and not self.is_saved:
            dlg = wx.MessageDialog(
                self,
                "Current chat is not saved. Save before starting a new chat?",
                "Unsaved Changes",
                wx.YES_NO | wx.CANCEL | wx.ICON_QUESTION
            )
            result = dlg.ShowModal()
            dlg.Destroy()
            
            if result == wx.ID_YES:
                self.on_save_chat(None)
            elif result == wx.ID_CANCEL:
                return
        
        self.chat_display.Clear()
        self.user_input.Clear()
        self.messages = []
        self.current_chat_file = None
        self.is_saved = False
        self.status_bar.SetStatusText("New chat started")
    
    def on_open_chat(self, event):
        """Open a saved chat file using native file dialog"""
        wildcard = "Text files (*.txt)|*.txt|All files (*.*)|*.*"
        dlg = wx.FileDialog(
            self,
            "Open Chat",
            defaultDir=str(CHATS_DIR),
            wildcard=wildcard,
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST
        )
        
        if dlg.ShowModal() == wx.ID_OK:
            filepath = dlg.GetPath()
            chat = ChatManager.load_chat_from_txt(filepath)
            
            if chat:
                # Ask if user wants to save current unsaved chat
                if self.messages and not self.is_saved:
                    save_dlg = wx.MessageDialog(
                        self,
                        "Current chat is not saved. Save before opening another chat?",
                        "Unsaved Changes",
                        wx.YES_NO | wx.CANCEL | wx.ICON_QUESTION
                    )
                    result = save_dlg.ShowModal()
                    save_dlg.Destroy()
                    
                    if result == wx.ID_YES:
                        self.on_save_chat(None)
                    elif result == wx.ID_CANCEL:
                        dlg.Destroy()
                        return
                
                self.load_chat_data(chat, filepath)
                self.status_bar.SetStatusText(f"Opened: {Path(filepath).name}")
            else:
                wx.MessageBox("Error loading chat file", "Error", wx.OK | wx.ICON_ERROR)
        
        dlg.Destroy()
    
    def on_save_chat(self, event):
        """Save current chat using native file dialog"""
        if not self.messages:
            wx.MessageBox("No messages to save", "Empty Chat", wx.OK | wx.ICON_WARNING)
            return
        
        if self.model_choice.GetSelection() == wx.NOT_FOUND:
            wx.MessageBox("Please select a model first", "Model Error", wx.OK | wx.ICON_ERROR)
            return
        
        # Use native file save dialog
        wildcard = "Text files (*.txt)|*.txt|All files (*.*)|*.*"
        dlg = wx.FileDialog(
            self,
            "Save Chat As",
            defaultDir=str(CHATS_DIR),
            defaultFile=f"chat_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            wildcard=wildcard,
            style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT
        )
        
        if dlg.ShowModal() == wx.ID_OK:
            filepath = dlg.GetPath()
            model = self.model_choice.GetStringSelection()
            
            if ChatManager.save_chat(filepath, self.messages, model):
                self.current_chat_file = filepath
                self.is_saved = True
                self.status_bar.SetStatusText(f"Chat saved: {Path(filepath).name}")
                wx.MessageBox("Chat saved successfully", "Success", wx.OK | wx.ICON_INFORMATION)
            else:
                wx.MessageBox("Error saving chat", "Error", wx.OK | wx.ICON_ERROR)
        
        dlg.Destroy()
    
    def load_chat_data(self, chat, filepath=None):
        """Load chat data into display"""
        self.chat_display.Clear()
        self.messages = chat.get("messages", [])
        self.current_chat_file = filepath
        self.is_saved = True
        
        # Set model if it's available
        model_name = chat.get("model", "Unknown")
        if model_name != "Unknown":
            index = self.model_choice.FindString(model_name)
            if index != wx.NOT_FOUND:
                self.model_choice.SetSelection(index)
        
        for msg in self.messages:
            role = msg.get("role", "Unknown").capitalize()
            content = msg.get("content", "")
            self.chat_display.AppendText(f"{role}: {content}\n\n")
        
        self.status_bar.SetStatusText(f"Loaded: {chat.get('name', 'Chat')}")
    
    def show_options_menu(self):
        """Show options menu"""
        # Create a popup menu
        menu = wx.Menu()
        
        settings_id = wx.NewId()
        manager_id = wx.NewId()
        history_id = wx.NewId()
        delete_id = wx.NewId()
        exit_id = wx.NewId()
        
        menu.Append(settings_id, "Settings")
        menu.Append(manager_id, "Model Manager")
        menu.Append(history_id, "Chat History")
        menu.Append(delete_id, "Delete Current Chat")
        menu.AppendSeparator()
        menu.Append(exit_id, "Exit")
        
        # Bind the events
        self.Bind(wx.EVT_MENU, lambda e: self.show_settings(), id=settings_id)
        self.Bind(wx.EVT_MENU, lambda e: self.show_model_manager(), id=manager_id)
        self.Bind(wx.EVT_MENU, lambda e: self.show_chat_history(), id=history_id)
        self.Bind(wx.EVT_MENU, lambda e: self.on_delete_current_chat(), id=delete_id)
        self.Bind(wx.EVT_MENU, lambda e: self.on_exit(None), id=exit_id)
        
        # Show the popup menu
        self.PopupMenu(menu)
        menu.Destroy()
    
    def show_settings(self):
        """Show settings dialog"""
        dlg = SettingsDialog(self)
        dlg.ShowModal()
        dlg.Destroy()
    
    def show_model_manager(self):
        """Show model manager dialog"""
        dlg = ModelManagerDialog(self)
        dlg.ShowModal()
        dlg.Destroy()
        self.load_models()
    
    def show_chat_history(self):
        """Show chat history dialog"""
        dlg = ChatHistoryDialog(self)
        dlg.ShowModal()
        dlg.Destroy()
    
    def on_delete_current_chat(self):
        """Delete current chat"""
        if not self.is_saved or not self.current_chat_file:
            wx.MessageBox(
                "The current chat has not been saved. Only saved chats can be deleted.",
                "Chat Not Saved",
                wx.OK | wx.ICON_ERROR
            )
            return
        
        dlg = wx.MessageDialog(
            self,
            f"Delete this chat? This cannot be undone.",
            "Confirm Delete",
            wx.YES_NO | wx.ICON_QUESTION
        )
        
        if dlg.ShowModal() == wx.ID_YES:
            try:
                Path(self.current_chat_file).unlink()
                self.on_new_chat(None)
                self.status_bar.SetStatusText("Chat deleted")
                wx.MessageBox("Chat deleted successfully", "Success", wx.OK | wx.ICON_INFORMATION)
            except Exception as e:
                wx.MessageBox(f"Error deleting chat: {e}", "Error", wx.OK | wx.ICON_ERROR)
            dlg.Destroy()
    
    def on_copy_response(self, event):
        """Copy assistant responses to clipboard"""
        assistant_messages = [msg.get("content", "") for msg in self.messages if msg.get("role") == "assistant"]
        
        if not assistant_messages:
            wx.MessageBox("No model responses to copy", "No Responses", wx.OK | wx.ICON_WARNING)
            return
        
        # Join all responses with separator
        copied_text = "\n" + "=" * 50 + "\n".join(assistant_messages)
        
        # Copy to clipboard
        if wx.TheClipboard.Open():
            wx.TheClipboard.SetData(wx.TextDataObject(copied_text))
            wx.TheClipboard.Close()
            self.status_bar.SetStatusText("Model responses copied to clipboard")
        else:
            wx.MessageBox("Failed to access clipboard", "Error", wx.OK | wx.ICON_ERROR)
    
    def on_exit(self, event):
        """Exit application"""
        if self.messages and not self.is_saved:
            dlg = wx.MessageDialog(
                self,
                "Unsaved changes. Exit without saving?",
                "Confirm Exit",
                wx.YES_NO | wx.ICON_QUESTION
            )
            result = dlg.ShowModal()
            dlg.Destroy()
            
            if result != wx.ID_YES:
                return
        
        self.Close(True)


class OllamaChatApp(wx.App):
    """Main application class"""
    
    def OnInit(self):
        """Initialize application"""
        self.frame = MainFrame()
        self.frame.Show()
        return True


def main():
    """Entry point"""
    app = OllamaChatApp()
    app.MainLoop()


if __name__ == "__main__":
        main()
