import tkinter as tk
import customtkinter as ctk

class CodeEditor(ctk.CTkFrame):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        self.line_numbers = tk.Text(self, width=4, padx=5, takefocus=0, border=0,
                                    background="#1e1e1e", foreground="#858585",
                                    state="disabled", font=("Consolas", 11))
        self.line_numbers.grid(row=0, column=0, sticky="nsew")
        
        self.textbox_wrapper = ctk.CTkTextbox(self, font=("Consolas", 11), wrap="none")
        self.textbox_wrapper.grid(row=0, column=1, sticky="nsew")
        
        self.textbox = self.textbox_wrapper._textbox
        self.textbox.bind("<KeyRelease>", self._on_key_release)
        self.textbox.bind("<Configure>", self._on_configure)
        
        from snipglide.utils.helpers import create_context_menu
        create_context_menu(self.textbox)
        
        self.update_line_numbers()
        
    def get_text(self) -> str:
        return self.textbox_wrapper.get("1.0", "end-1c")
        
    def set_text(self, text: str):
        self.textbox_wrapper.delete("1.0", "end")
        self.textbox_wrapper.insert("1.0", text)
        self.update_line_numbers()
        
    def update_line_numbers(self):
        self.line_numbers.configure(state="normal")
        self.line_numbers.delete("1.0", "end")
        
        lines_count = int(self.textbox.index('end-1c').split('.')[0])
        lines_text = "\n".join(str(i) for i in range(1, lines_count + 1))
        
        self.line_numbers.insert("1.0", lines_text)
        self.line_numbers.configure(state="disabled")
        
    def _on_key_release(self, event):
        self.update_line_numbers()
        
    def _on_configure(self, event):
        self.update_line_numbers()

    def setup_highlight_tags(self):
        token_colors = {
            "Token.Keyword": ("#569cd6", "#0000ff"),
            "Token.String": ("#ce9178", "#a31515"),
            "Token.Comment": ("#6a9955", "#008000"),
            "Token.Number": ("#b5cea8", "#098658"),
            "Token.Name.Function": ("#dcdcaa", "#795e26"),
            "Token.Name.Class": ("#4ec9b0", "#267f99"),
            "Token.Operator": ("#d4d4d4", "#000000"),
        }
        self.is_dark = ctk.get_appearance_mode().lower() == "dark"
        for tag_name, colors in token_colors.items():
            color = colors[0] if self.is_dark else colors[1]
            self.textbox.tag_configure(tag_name, foreground=color)
            
    def highlight_code(self, lang: str):
        self.setup_highlight_tags()
        
        for tag in self.textbox.tag_names():
            if tag.startswith("Token."):
                self.textbox.tag_remove(tag, "1.0", "end")
                
        if lang == "Plain Text":
            return
            
        try:
            from pygments import lex
            from pygments.lexers import get_lexer_by_name
            lexer = get_lexer_by_name(lang.lower())
        except Exception:
            return
            
        code = self.get_text()
        tokens = list(lex(code, lexer))
        
        line = 1
        column = 0
        for token_type, value in tokens:
            start_idx = f"{line}.{column}"
            newlines = value.count("\n")
            if newlines > 0:
                parts = value.split("\n")
                line += newlines
                column = len(parts[-1])
            else:
                column += len(value)
            end_idx = f"{line}.{column}"
            
            t_str = str(token_type)
            for conf_tag in ["Token.Keyword", "Token.String", "Token.Comment", "Token.Number", "Token.Name.Function", "Token.Name.Class", "Token.Operator"]:
                if t_str.startswith(conf_tag):
                    self.textbox.tag_add(conf_tag, start_idx, end_idx)
                    break
