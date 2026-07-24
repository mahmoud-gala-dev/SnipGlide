import customtkinter as ctk
from snipglide.models.group import Group
from snipglide.models.snippet import Snippet
from snipglide.database.group_repo import add_group, get_group_by_name
from snipglide.database.snippet_repo import add_snippet, get_snippet_by_shortcut

class Marketplace(ctk.CTkFrame):
    def __init__(self, parent, toast_callback, refresh_callback, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)
        self.toast_callback = toast_callback
        self.refresh_callback = refresh_callback
        
        self.title_label = ctk.CTkLabel(self, text="Snippet Marketplace", font=ctk.CTkFont(size=24, weight="bold"))
        self.title_label.pack(pady=(20, 10), anchor="w", padx=20)
        
        self.sub_label = ctk.CTkLabel(self, text="Download template packs to boost your workflow.", font=ctk.CTkFont(size=12), text_color="gray")
        self.sub_label.pack(pady=(0, 20), anchor="w", padx=20)
        
        self.packs_frame = ctk.CTkScrollableFrame(self)
        self.packs_frame.pack(fill="both", expand=True, padx=20, pady=10)
        
        self.packs = [
            {
                "name": "Developer Boilerplates",
                "category": "Programming",
                "icon": "💻",
                "desc": "A set of standard loops, class builders, and mock templates.",
                "snippets": [
                    {"shortcut": "#for", "replacement": "for i in range(10):\n    print(i)", "language": "Python"},
                    {"shortcut": "#main", "replacement": "if __name__ == '__main__':\n    main()", "language": "Python"}
                ]
            },
            {
                "name": "Customer Support Pack",
                "category": "Customer Support",
                "icon": "💬",
                "desc": "Standard greeting templates and template emails for fast replies.",
                "snippets": [
                    {"shortcut": "#hi", "replacement": "Hello {{form:Client Name}},\n\nThank you for reaching out. How can I assist you?", "language": "Plain Text"},
                    {"shortcut": "#bye", "replacement": "Best regards,\n{{username}}", "language": "Plain Text"}
                ]
            },
            {
                "name": "Medical Records Shortcuts",
                "category": "Medical",
                "icon": "🩺",
                "desc": "Quick shortcuts for patient diagnostics, logs, and prescriptions.",
                "snippets": [
                    {"shortcut": "#diag", "replacement": "Chief Complaint: {{form:Complaint}}\nHistory: {{form:History}}\nPlan: {{form:Plan}}", "language": "Plain Text"}
                ]
            }
        ]
        
        for pack in self.packs:
            self._create_pack_card(pack)
            
    def _create_pack_card(self, pack: dict):
        card = ctk.CTkFrame(self.packs_frame, fg_color=("gray90", "gray15"))
        card.pack(fill="x", pady=8, padx=10)
        
        info_frame = ctk.CTkFrame(card, fg_color="transparent")
        info_frame.pack(side="left", padx=15, pady=10, fill="both", expand=True)
        
        ctk.CTkLabel(info_frame, text=f"{pack['icon']} {pack['name']}", font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w")
        ctk.CTkLabel(info_frame, text=f"Category: {pack['category']} • {len(pack['snippets'])} snippets", text_color="#3b82f6", font=ctk.CTkFont(size=12)).pack(anchor="w", pady=2)
        ctk.CTkLabel(info_frame, text=pack['desc'], text_color="gray", font=ctk.CTkFont(size=12)).pack(anchor="w")
        
        install_btn = ctk.CTkButton(
            card,
            text="Install Pack",
            width=100,
            command=lambda p=pack: self._install_pack(p)
        )
        install_btn.pack(side="right", padx=15, pady=15)
        
    def _install_pack(self, pack: dict):
        g = get_group_by_name(pack['category'])
        if g:
            g_id = g.id
        else:
            g_id = add_group(Group(name=pack['category'], icon=pack['icon']))
            
        installed = 0
        skipped = 0
        
        for s in pack['snippets']:
            existing = get_snippet_by_shortcut(s['shortcut'])
            if existing:
                skipped += 1
                continue
                
            add_snippet(Snippet(
                shortcut=s['shortcut'],
                replacement=s['replacement'],
                group_id=g_id,
                language=s['language'],
                description="Imported from Marketplace"
            ))
            installed += 1
            
        msg = f"Installed {installed} snippets."
        if skipped > 0:
            msg += f" (Skipped {skipped} duplicates)"
            
        self.toast_callback(msg)
        self.refresh_callback()
