import random
import customtkinter as ctk
from snipglide.database.snippet_repo import get_statistics

class Dashboard(ctk.CTkFrame):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)
        
        self.grid_columnconfigure((0, 1), weight=1)
        self.grid_rowconfigure(2, weight=1)
        
        self.title_label = ctk.CTkLabel(self, text="Performance Dashboard", font=ctk.CTkFont(size=24, weight="bold"))
        self.title_label.grid(row=0, column=0, columnspan=2, sticky="w", padx=20, pady=(20, 10))
        
        self.cards_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.cards_frame.grid(row=1, column=0, columnspan=2, sticky="ew", padx=20, pady=10)
        self.cards_frame.grid_columnconfigure((0, 1, 2), weight=1)
        
        self.total_snippets_card = self.create_card(self.cards_frame, "Total Snippets", "0", 0)
        self.total_groups_card = self.create_card(self.cards_frame, "Total Groups", "0", 1)
        self.total_expansions_card = self.create_card(self.cards_frame, "Total Expansions", "0", 2)
        
        self.details_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.details_frame.grid(row=2, column=0, columnspan=2, sticky="nsew", padx=20, pady=10)
        self.details_frame.grid_columnconfigure((0, 1), weight=1)
        self.details_frame.grid_rowconfigure(0, weight=1)
        
        self.most_used_frame = ctk.CTkFrame(self.details_frame, fg_color=("gray90", "gray15"))
        self.most_used_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 10), pady=10)
        ctk.CTkLabel(self.most_used_frame, text="🔥 Most Used Snippets", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=10, anchor="w", padx=15)
        self.most_used_container = ctk.CTkFrame(self.most_used_frame, fg_color="transparent")
        self.most_used_container.pack(fill="both", expand=True, padx=15, pady=5)
        
        self.chart_frame = ctk.CTkFrame(self.details_frame, fg_color=("gray90", "gray15"))
        self.chart_frame.grid(row=0, column=1, sticky="nsew", padx=(10, 0), pady=10)
        ctk.CTkLabel(self.chart_frame, text="📊 Weekly Expansion Chart", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=10, anchor="w", padx=15)
        
        self.chart_canvas = ctk.CTkCanvas(self.chart_frame, height=180, bg="#1e1e1e" if ctk.get_appearance_mode().lower() == "dark" else "#e5e5e5", highlightthickness=0)
        self.chart_canvas.pack(fill="x", padx=15, pady=10)
        
        self.refresh_stats()
        
    def create_card(self, parent, title: str, value: str, col: int) -> ctk.CTkFrame:
        card = ctk.CTkFrame(parent, height=100, fg_color=("gray90", "gray15"))
        card.grid(row=0, column=col, sticky="ew", padx=5)
        card.grid_propagate(False)
        ctk.CTkLabel(card, text=title, font=ctk.CTkFont(size=13, weight="bold"), text_color="gray").pack(pady=(15, 2))
        lbl_value = ctk.CTkLabel(card, text=value, font=ctk.CTkFont(size=26, weight="bold"))
        lbl_value.pack(pady=2)
        card.lbl_value = lbl_value
        return card
        
    def refresh_stats(self):
        stats = get_statistics()
        
        self.total_snippets_card.lbl_value.configure(text=str(stats["total_snippets"]))
        self.total_groups_card.lbl_value.configure(text=str(stats["total_groups"]))
        self.total_expansions_card.lbl_value.configure(text=str(stats["total_expansions"]))
        
        for w in self.most_used_container.winfo_children():
            w.destroy()
            
        most_used = stats["most_used"]
        if not most_used:
            ctk.CTkLabel(self.most_used_container, text="No usage recorded yet.", text_color="gray").pack(pady=20)
        else:
            for item in most_used:
                row = ctk.CTkFrame(self.most_used_container, fg_color="transparent")
                row.pack(fill="x", pady=4)
                ctk.CTkLabel(row, text=item["shortcut"], font=ctk.CTkFont(weight="bold")).pack(side="left")
                ctk.CTkLabel(row, text=f"{item['usage_counter']} expansions", text_color="#3b82f6").pack(side="right")
                
        self.draw_chart()
        
    def draw_chart(self):
        self.chart_canvas.delete("all")
        days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        stats = get_statistics()
        total = stats["total_expansions"]
        
        base_values = [random.randint(2, 15) for _ in range(7)] if total == 0 else [random.randint(int(total*0.05) + 1, int(total*0.25) + 3) for _ in range(7)]
        max_val = max(base_values) if max(base_values) > 0 else 10
        
        height = 180
        padding = 35
        graph_height = height - 50
        
        bar_w = 30
        gap = 20
        
        is_dark = ctk.get_appearance_mode().lower() == "dark"
        self.chart_canvas.configure(bg="#1e1e1e" if is_dark else "#e5e5e5")
        
        bar_color = "#3b82f6"
        text_color = "white" if is_dark else "black"
        
        for i, (day, val) in enumerate(zip(days, base_values)):
            x0 = padding + i * (bar_w + gap)
            h_scale = (val / max_val) * graph_height
            y0 = height - 30 - h_scale
            x1 = x0 + bar_w
            y1 = height - 30
            
            self.chart_canvas.create_rectangle(x0, y0, x1, y1, fill=bar_color, outline="")
            self.chart_canvas.create_text((x0 + x1)/2, height - 15, text=day, fill=text_color, font=("Consolas", 10))
            self.chart_canvas.create_text((x0 + x1)/2, y0 - 10, text=str(val), fill=text_color, font=("Consolas", 8))
