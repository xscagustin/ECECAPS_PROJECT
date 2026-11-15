import customtkinter as ctk

class SideTabView(ctk.CTkFrame):
    """Reusable custom widget for vertical side-tabs in CustomTkinter."""
    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # 1. Left Vertical Sidebar (Tab Bar Container)
        self.sidebar = ctk.CTkFrame(self, width=130, corner_radius=6)
        self.sidebar.grid(row=0, column=0, sticky="nsew", padx=(0, 10))

        self.pages = {}
        self.buttons = {}
        self.active_tab = None

    def add(self, name: str) -> ctk.CTkFrame:
        """Adds a tab page and returns its parent frame reference."""
        # Create container frame for tab content
        page_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.pages[name] = page_frame

        # Create vertical side tab button
        btn = ctk.CTkButton(
            self.sidebar,
            text=name,
            anchor="w",
            fg_color="transparent",
            text_color=("gray10", "gray90"),
            command=lambda n=name: self.set(n)
        )
        btn.pack(fill="x", padx=5, pady=4)
        self.buttons[name] = btn

        # Auto-select first added tab
        if self.active_tab is None:
            self.set(name)

        return page_frame

    def tab(self, name: str) -> ctk.CTkFrame:
        """Returns reference to the tab frame."""
        return self.pages[name]

    def set(self, name: str):
        """Switch active tab panel."""
        if name not in self.pages:
            return

        # Hide active frame and reset button highlight
        if self.active_tab and self.active_tab in self.pages:
            self.pages[self.active_tab].grid_forget()
            self.buttons[self.active_tab].configure(fg_color="transparent")

        # Show target tab frame and apply active highlight button state
        self.pages[name].grid(row=0, column=1, sticky="nsew")
        self.buttons[name].configure(fg_color=("gray75", "gray30"))
        self.active_tab = name


# --- Usage Example ---
class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.geometry("600x400")
        self.title("Custom Vertical Side Tabs")

        # Create the side tabview instance
        self.tabview = SideTabView(self)
        self.tabview.pack(fill="both", expand=True, padx=15, pady=15)

        # Add tabs
        self.tabview.add("Dashboard")
        self.tabview.add("Settings")
        self.tabview.add("Console")

        # Add widgets to tabs
        ctk.CTkLabel(self.tabview.tab("Dashboard"), text="Dashboard Panel", font=("Helvetica", 16)).pack(pady=20)
        ctk.CTkLabel(self.tabview.tab("Settings"), text="Settings Panel", font=("Helvetica", 16)).pack(pady=20)
        ctk.CTkLabel(self.tabview.tab("Console"), text="Console Log Output Panel", font=("Helvetica", 16)).pack(pady=20)

if __name__ == "__main__":
    app = App()
    app.mainloop()