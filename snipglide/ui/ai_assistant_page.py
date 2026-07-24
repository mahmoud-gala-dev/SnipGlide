import customtkinter as ctk
import threading
from snipglide.services.ai import call_ai_completion
from snipglide.models.snippet import Snippet
from snipglide.database.snippet_repo import add_snippet, get_snippet_by_shortcut

class AIAssistantPage(ctk.CTkFrame):
    def __init__(self, parent, toast_callback, settings_provider, refresh_callback, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)
        self.toast_callback = toast_callback
        self.settings_provider = settings_provider
        self.refresh_callback = refresh_callback
        
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=20, pady=(20, 10))
        ctk.CTkLabel(header, text="🤖 AI Assistant & Prompt Builder", font=ctk.CTkFont(size=22, weight="bold")).pack(anchor="w")
        ctk.CTkLabel(header, text="Draft templates and prompt expansions using Gemini AI.", font=ctk.CTkFont(size=12), text_color="gray").pack(anchor="w", pady=2)
        
        content = ctk.CTkFrame(self)
        content.grid(row=1, column=0, sticky="nsew", padx=20, pady=10)
        content.grid_columnconfigure((0, 1), weight=1)
        content.grid_rowconfigure(0, weight=1)
        
        left = ctk.CTkFrame(content, fg_color="transparent")
        left.grid(row=0, column=0, sticky="nsew", padx=15, pady=15)
        left.grid_columnconfigure(0, weight=1)
        left.grid_rowconfigure(1, weight=1)
        
        ctk.CTkLabel(left, text="Enter your prompt / instructions:", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, sticky="w", pady=5)
        
        preset_frame = ctk.CTkFrame(left, fg_color="transparent")
        preset_frame.grid(row=1, column=0, sticky="ew", pady=5)
        ctk.CTkLabel(preset_frame, text="Prompt Preset:").pack(side="left", padx=(0, 5))
        self.preset_var = ctk.StringVar(value="Custom")
        self.preset_menu = ctk.CTkOptionMenu(
            preset_frame,
            variable=self.preset_var,
            values=["Custom", "Professional Reschedule", "Friendly Follow-up", "Code Explainer", "SQL Query Builder"],
            command=self._on_preset_change
        )
        self.preset_menu.pack(side="left", fill="x", expand=True)
        
        self.prompt_text = ctk.CTkTextbox(left, height=220)
        self.prompt_text.grid(row=2, column=0, sticky="nsew", pady=5)
        self.prompt_text.insert("1.0", "Write a professional email template asking for a reschedule, including fields for {{form:New Date}} and {{form:Reason}}.")
        
        self.gen_btn = ctk.CTkButton(left, text="✨ Generate Snippet Text", command=self._generate)
        self.gen_btn.grid(row=3, column=0, sticky="ew", pady=10)
        
        right = ctk.CTkFrame(content, fg_color="transparent")
        right.grid(row=0, column=1, sticky="nsew", padx=15, pady=15)
        right.grid_columnconfigure(0, weight=1)
        right.grid_rowconfigure(1, weight=1)
        
        ctk.CTkLabel(right, text="Generated Snippet Preview:", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, sticky="w", pady=5)
        self.output_text = ctk.CTkTextbox(right, height=220)
        self.output_text.grid(row=1, column=0, sticky="nsew", pady=5)
        
        save_frame = ctk.CTkFrame(right, fg_color="transparent")
        save_frame.grid(row=2, column=0, sticky="ew", pady=10)
        
        ctk.CTkLabel(save_frame, text="Shortcut:", font=ctk.CTkFont(size=11, weight="bold")).pack(side="left", padx=5)
        self.shortcut_entry = ctk.CTkEntry(save_frame, placeholder_text="e.g. #resched", width=120)
        self.shortcut_entry.pack(side="left", padx=5)
        
        self.save_btn = ctk.CTkButton(save_frame, text="💾 Save Snippet", command=self._save_snippet)
        self.save_btn.pack(side="left", fill="x", expand=True, padx=5)
        
        from snipglide.utils.helpers import create_context_menu
        for attr in [self.prompt_text, self.output_text, self.shortcut_entry]:
            create_context_menu(attr)
            
    def _on_preset_change(self, preset: str):
        self.prompt_text.delete("1.0", "end")
        if preset == "Professional Reschedule":
            self.prompt_text.insert("1.0", "Write a professional email template asking for a meeting reschedule. Include fields for {{form:Original Date}}, {{form:Suggested New Date}}, and {{form:Reason for change}}.")
        elif preset == "Friendly Follow-up":
            self.prompt_text.insert("1.0", "Write a friendly, polite follow-up email template asking for feedback on a proposal. Include {{form:Proposal Name}}.")
        elif preset == "Code Explainer":
            self.prompt_text.insert("1.0", "Write a snippet template that explains how a piece of code works in clean bullet points. Include {{form:Language}}.")
        elif preset == "SQL Query Builder":
            self.prompt_text.insert("1.0", "Write a query template to SELECT data from a table based on user criteria. Include {{form:Table Name}} and {{form:Where Condition}}.")
        else:
            self.prompt_text.insert("1.0", "")
        
    def _generate(self):
        prompt = self.prompt_text.get("1.0", "end-1c").strip()
        if not prompt:
            self.toast_callback("Prompt text cannot be empty.", error=True)
            return
            
        settings = self.settings_provider()
        api_key = settings.get("ai_api_key", "")
        provider = settings.get("ai_provider", "gemini")
        temperature = float(settings.get("ai_temperature", 0.7))
        
        self.toast_callback("AI generating content...")
        self.gen_btn.configure(state="disabled", text="Generating...")
        
        def run():
            try:
                result = call_ai_completion(prompt, api_key, provider, temperature=temperature)
                self.after(0, lambda: self.output_text.delete("1.0", "end"))
                self.after(0, lambda: self.output_text.insert("1.0", result))
                self.after(0, lambda: self.toast_callback("Generation complete!"))
            except Exception as e:
                self.after(0, lambda: self.toast_callback(f"Failed to generate: {e}", error=True))
            finally:
                self.after(0, lambda: self.gen_btn.configure(state="normal", text="✨ Generate Snippet Text"))
                
        threading.Thread(target=run, daemon=True).start()
        
    def _save_snippet(self):
        shortcut = self.shortcut_entry.get().strip()
        replacement = self.output_text.get("1.0", "end-1c").strip()
        
        if not shortcut or not replacement:
            self.toast_callback("Shortcut and replacement text are required.", error=True)
            return
            
        existing = get_snippet_by_shortcut(shortcut)
        if existing:
            self.toast_callback("Shortcut already exists.", error=True)
            return
            
        try:
            add_snippet(Snippet(
                shortcut=shortcut,
                replacement=replacement,
                group_id=1,
                description="Generated by AI Assistant"
            ))
            self.toast_callback("Snippet saved successfully!")
            self.refresh_callback()
            self.shortcut_entry.delete(0, "end")
        except Exception as e:
            self.toast_callback(f"Failed to save: {e}", error=True)
