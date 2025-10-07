import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import json
import requests
import sqlite3
from datetime import datetime, timedelta
import subprocess
import os
import webbrowser
from pathlib import Path
import threading
import shutil
from collections import defaultdict


# Try to import optional libraries
try:
    from matplotlib.figure import Figure
    from matplotlib.backend_tkagg import FigureCanvasTkAgg
    HAS_MATPLOTLIB = True
except:
    HAS_MATPLOTLIB = False



try:
    from fpdf import FPDF
    HAS_PDF = True
except:
    HAS_PDF = False




class HardwareEngineeringTool:
    def __init__(self, root):
        self.root = root
        self.root.title("Hardware Engineering Tool")
        self.root.geometry("1400x900")



        # Load Settings
        self.settings = self.load_settings

        # Init db
        self.init_database()

        # Auto-backup
        self.setup_auto_backup()

        # Color scheme
        self.appy_theme()

        # Status bar
        self.create_status_bar()

        # Create main interface
        self.create_menu()
        self.create_main_layout()

        # Keyboard shortcuts
        self.setup_shortcuts()

        # Check for updates on startup
        self.root.after(1000, self.startup_checks)



    def load_settings(self):
        # Load settings from JSON file
        default_settings = {
            "theme": "dark",
            "auto_backup": True,
            "backup_interval": 30,  # minutes
            "octopart_api_key": "",
            "jlcpcb_api_key": "",
            "currency": "USD",
            "default_markup": 1.0,
            "warn_obsolete": True,
            "warn_low_stock": True,
            "recent_projects": []
        }

        try:
            if os.path.exists("settings.json"):
                with open("settings.json", "r") as f:
                    loaded = json.load(f)
                    default_settings.update(loaded)
        except:
            pass



    def save_settings(self):
        # Save settings to JSON file
        try:
            with open("settings.json", "w") as f:
                json.dump(self.settings, f, indent=2)
        except Exception as e:
            print(f"Failed to save settings: {e}")



    def apply_theme(self):
        """Apply color theme"""
        if self.settings["theme"] == "dark":
            self.bg_dark = "#2b2b2b"
            self.bg_medium = "#3c3f41"
            self.bg_light = "#4e5254"
            self.accent = "#4a9eff"
            self.accent_green = "#5fb363"
            self.accent_red = "#e74856"
            self.accent_orange = "#f59b42"
            self.text_color = "#ffffff"
        else:  # light theme
            self.bg_dark = "#f0f0f0"
            self.bg_medium = "#e0e0e0"
            self.bg_light = "#d0d0d0"
            self.accent = "#0078d4"
            self.accent_green = "#107c10"
            self.accent_red = "#d13438"
            self.accent_orange = "#ff8c00"
            self.text_color = "#000000"
        
        self.root.configure(bg=self.bg_dark)


    def create_status_bar(self):
        # Create status bar at bottom
        self.status_bar = tk.Frame(self.root, bg=self.bg_medium, height=25)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        
        self.status_label = tk.Label(self.status_bar, text="Ready", bg=self.bg_medium, 
                                     fg=self.text_color, anchor=tk.W)
        self.status_label.pack(side=tk.LEFT, padx=10)
        
        self.progress = ttk.Progressbar(self.status_bar, mode='indeterminate', length=100)
        self.progress.pack(side=tk.RIGHT, padx=10)


    def set_status(self):
        # Update status bar
        self.status_label.config(text=message)
        if working:
            self.progress.start()
        else:
            self.progress.stop()
        self.root.update_idletasks()


    def setup_shortcuts(self):
        """Setup keyboard shortcuts"""
        self.root.bind('<Control-n>', lambda e: self.new_project())
        self.root.bind('<Control-o>', lambda e: self.import_bom())
        self.root.bind('<Control-s>', lambda e: self.export_components())
        self.root.bind('<Control-f>', lambda e: self.focus_search())
        self.root.bind('<F5>', lambda e: self.refresh_all())
        self.root.bind('<Control-comma>', lambda e: self.show_settings())


    def focus_search(self):
        """Focus on search box"""
        if hasattr(self, 'component_search'):
            self.component_search.focus()


    def refresh_all(self):
        """Refresh all views"""
        self.refresh_components()
        self.refresh_projects()
        self.update_dashboard_stats()
        self.set_status("Refreshed", False)


    def setup_auto_backup(self):
        """Setup automatic database backup"""
        if self.settings.get("auto_backup", True):
            interval = self.settings.get("backup_interval", 30) * 60000  # Convert to ms
            self.root.after(interval, self.auto_backup)


    def auto_backup(self):
        """Perform automatic backup"""
        try:
            backup_dir = "backups"
            os.makedirs(backup_dir, exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = f"{backup_dir}/hardware_workbench_{timestamp}.db"
            
            shutil.copy2("hardware_workbench.db", backup_file)
            
            # Keep only last 10 backups
            backups = sorted(Path(backup_dir).glob("*.db"))
            if len(backups) > 10:
                for old_backup in backups[:-10]:
                    old_backup.unlink()
            
            self.set_status(f"Auto-backup completed: {timestamp}", False)
        except Exception as e:
            print(f"Auto-backup failed: {e}")
        
        # Schedule next backup
        if self.settings.get("auto_backup", True):
            interval = self.settings.get("backup_interval", 30) * 60000
            self.root.after(interval, self.auto_backup)


    def init_database(self):
        """Initialize SQLite database with enhanced schema"""
        self.conn = sqlite3.connect('hardware_workbench.db')
        self.cursor = self.conn.cursor()
        
        # Components table (enhanced)
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS components (
                id INTEGER PRIMARY KEY,
                mpn TEXT UNIQUE,
                manufacturer TEXT,
                description TEXT,
                category TEXT,
                stock_qty INTEGER,
                min_stock INTEGER,
                unit_price REAL,
                lifecycle_status TEXT,
                last_checked TIMESTAMP,
                datasheet_url TEXT,
                notes TEXT,
                image_path TEXT,
                footprint TEXT,
                created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Price history table (NEW)
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS price_history (
                id INTEGER PRIMARY KEY,
                component_id INTEGER,
                price REAL,
                date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                source TEXT,
                FOREIGN KEY (component_id) REFERENCES components(id)
            )
        ''')
        
        # Suppliers table (NEW)
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS suppliers (
                id INTEGER PRIMARY KEY,
                name TEXT UNIQUE,
                website TEXT,
                contact TEXT,
                notes TEXT
            )
        ''')
        
        # Component-Supplier link (NEW)
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS component_suppliers (
                id INTEGER PRIMARY KEY,
                component_id INTEGER,
                supplier_id INTEGER,
                supplier_mpn TEXT,
                price REAL,
                moq INTEGER,
                lead_time_days INTEGER,
                last_updated TIMESTAMP,
                FOREIGN KEY (component_id) REFERENCES components(id),
                FOREIGN KEY (supplier_id) REFERENCES suppliers(id)
            )
        ''')
        
        # Projects table
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY,
                name TEXT UNIQUE,
                description TEXT,
                created_date TIMESTAMP,
                kicad_path TEXT,
                firmware_path TEXT,
                git_repo TEXT,
                last_opened TIMESTAMP
            )
        ''')
        
        # BOM table
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS bom (
                id INTEGER PRIMARY KEY,
                project_id INTEGER,
                component_id INTEGER,
                reference_designator TEXT,
                quantity INTEGER,
                do_not_populate INTEGER DEFAULT 0,
                FOREIGN KEY (project_id) REFERENCES projects(id),
                FOREIGN KEY (component_id) REFERENCES components(id)
            )
        ''')
        
        # Activity log (NEW)
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS activity_log (
                id INTEGER PRIMARY KEY,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                action TEXT,
                details TEXT
            )
        ''')
        
        self.conn.commit()



    def log_activity(self, action, details=""):
        """Log user activity"""
        try:
            self.cursor.execute(
                "INSERT INTO activity_log (action, details) VALUES (?, ?)",
                (action, details)
            )
            self.conn.commit()
        except:
            pass


    def create_menu(self):
        """Create enhanced menu bar"""
        menubar = tk.Menu(self.root, bg=self.bg_medium, fg=self.text_color)
        self.root.config(menu=menubar)
        
        # File menu
        file_menu = tk.Menu(menubar, tearoff=0, bg=self.bg_medium, fg=self.text_color)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="New Project (Ctrl+N)", command=self.new_project)
        file_menu.add_command(label="Import BOM (Ctrl+O)", command=self.import_bom)
        file_menu.add_command(label="Export Components (Ctrl+S)", command=self.export_components)
        file_menu.add_separator()
        file_menu.add_command(label="Backup Database", command=self.manual_backup)
        file_menu.add_command(label="Restore from Backup", command=self.restore_backup)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)
        
        # Edit menu
        edit_menu = tk.Menu(menubar, tearoff=0, bg=self.bg_medium, fg=self.text_color)
        menubar.add_cascade(label="Edit", menu=edit_menu)
        edit_menu.add_command(label="Settings (Ctrl+,)", command=self.show_settings)
        edit_menu.add_command(label="Suppliers", command=self.manage_suppliers)
        
        # View menu
        view_menu = tk.Menu(menubar, tearoff=0, bg=self.bg_medium, fg=self.text_color)
        menubar.add_cascade(label="View", menu=view_menu)
        view_menu.add_command(label="Refresh (F5)", command=self.refresh_all)
        view_menu.add_separator()
        view_menu.add_checkbutton(label="Dark Theme", command=self.toggle_theme)
        
        # Tools menu
        tools_menu = tk.Menu(menubar, tearoff=0, bg=self.bg_medium, fg=self.text_color)
        menubar.add_cascade(label="Tools", menu=tools_menu)
        tools_menu.add_command(label="Launch KiCad", command=lambda: self.launch_external("kicad"))
        tools_menu.add_command(label="Launch VS Code", command=lambda: self.launch_external("code"))
        tools_menu.add_command(label="Open Git GUI", command=lambda: self.launch_external("git-gui"))
        tools_menu.add_separator()
        tools_menu.add_command(label="Price Update (Octopart)", command=self.update_prices_octopart)
        tools_menu.add_command(label="Generate Report", command=self.generate_report)
        
        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0, bg=self.bg_medium, fg=self.text_color)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="Keyboard Shortcuts", command=self.show_shortcuts)
        help_menu.add_command(label="Documentation", command=self.show_help)
        help_menu.add_command(label="Check for Updates", command=self.check_updates)
        help_menu.add_separator()
        help_menu.add_command(label="About", command=self.show_about)


    def create_main_layout(self):
        # Create main tabbed interface
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('TNotebook', background=self.bg_dark)
        style.configure('TNotebook.Tab', background=self.bg_medium, foreground=self.text_color, padding=[20, 10])
        style.map('TNotebook.Tab', background=[('selected', self.accent)])
        
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Create tabs
        self.create_dashboard_tab()
        self.create_components_tab()
        self.create_bom_tab()
        self.create_projects_tab()
        self.create_analytics_tab()  # NEW
        self.create_tools_tab()
    
    
    def create_dashboard_tab(self):
        # Enhanced dashboard with recent projects and alerts
        dashboard = tk.Frame(self.notebook, bg=self.bg_dark)
        self.notebook.add(dashboard, text="📊 Dashboard")
        
        # Header
        header = tk.Label(dashboard, text="Hardware Engineering Workbench", 
                         font=("Arial", 24, "bold"), bg=self.bg_dark, fg=self.text_color)
        header.pack(pady=20)
        
        # Stats frame
        stats_frame = tk.Frame(dashboard, bg=self.bg_dark)
        stats_frame.pack(fill=tk.X, padx=20, pady=10)
        
        self.create_stat_card(stats_frame, "Projects", "0", 0)
        self.create_stat_card(stats_frame, "Components", "0", 1)
        self.create_stat_card(stats_frame, "Low Stock Alerts", "0", 2)
        self.create_stat_card(stats_frame, "Obsolete Parts", "0", 3)
        
        # Split view: Recent Projects + Alerts
        content_frame = tk.Frame(dashboard, bg=self.bg_dark)
        content_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # Recent Projects (LEFT)
        recent_frame = tk.LabelFrame(content_frame, text="📁 Recent Projects", 
                                     font=("Arial", 12, "bold"),
                                     bg=self.bg_dark, fg=self.text_color)
        recent_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        
        self.recent_projects_list = tk.Listbox(recent_frame, bg=self.bg_medium, 
                                               fg=self.text_color, font=("Arial", 10),
                                               height=8)
        self.recent_projects_list.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.recent_projects_list.bind('<Double-Button-1>', self.open_recent_project)
        
        # Alerts (RIGHT)
        alerts_frame = tk.LabelFrame(content_frame, text="⚠️ Alerts & Warnings", 
                                    font=("Arial", 12, "bold"),
                                    bg=self.bg_dark, fg=self.text_color)
        alerts_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(10, 0))
        
        self.alerts_text = tk.Text(alerts_frame, bg=self.bg_medium, fg=self.text_color,
                                   font=("Arial", 10), height=8, wrap=tk.WORD)
        self.alerts_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Quick actions
        actions_frame = tk.LabelFrame(dashboard, text="Quick Actions", font=("Arial", 12, "bold"),
                                     bg=self.bg_dark, fg=self.text_color)
        actions_frame.pack(fill=tk.X, padx=20, pady=20)
        
        self.create_action_button(actions_frame, "🆕 New Project", self.new_project, 0, 0)
        self.create_action_button(actions_frame, "📦 Add Component", self.add_component, 0, 1)
        self.create_action_button(actions_frame, "📋 Import BOM", self.import_bom, 0, 2)
        self.create_action_button(actions_frame, "💰 Cost Analysis", self.cost_analysis, 1, 0)
        self.create_action_button(actions_frame, "🔍 Find Alternatives", self.find_alternatives, 1, 1)
        self.create_action_button(actions_frame, "📊 Generate Report", self.generate_report, 1, 2)
        
        self.update_dashboard_stats()
        self.update_recent_projects()
        self.update_alerts()


    def create_stat_card(self, parent, title, value, column):
        """Create a stat card"""
        card = tk.Frame(parent, bg=self.bg_medium, relief=tk.RAISED, borderwidth=2)
        card.grid(row=0, column=column, padx=10, pady=10, sticky="nsew", ipadx=20, ipady=20)
        parent.columnconfigure(column, weight=1)
        
        tk.Label(card, text=title, font=("Arial", 12), bg=self.bg_medium, fg="#888888").pack()
        label = tk.Label(card, text=value, font=("Arial", 28, "bold"), bg=self.bg_medium, fg=self.accent)
        label.pack()
        
        setattr(self, f"stat_{title.lower().replace(' ', '_')}", label)


    def create_action_button(self, parent, text, command, row, col):
        """Create action button with tooltip"""
        btn = tk.Button(parent, text=text, command=command, font=("Arial", 12), 
                       bg=self.accent, fg=self.text_color, relief=tk.FLAT,
                       padx=20, pady=15, cursor="hand2")
        btn.grid(row=row, column=col, padx=15, pady=15, sticky="nsew")
        parent.columnconfigure(col, weight=1)
        parent.rowconfigure(row, weight=1)
        
        # Add hover effect
        btn.bind('<Enter>', lambda e: btn.config(bg=self.accent_green))
        btn.bind('<Leave>', lambda e: btn.config(bg=self.accent))


    def update_recent_projects(self):
        """Update recent projects list"""
        self.recent_projects_list.delete(0, tk.END)
        
        recent = self.cursor.execute('''
            SELECT name, last_opened FROM projects 
            WHERE last_opened IS NOT NULL
            ORDER BY last_opened DESC LIMIT 10
        ''').fetchall()
        
        for name, last_opened in recent:
            self.recent_projects_list.insert(tk.END, f"  {name}")


    def update_alerts(self):
        # Update alerts panel
        self.alerts_text.delete("1.0", tk.END)
        
        # Low stock alerts
        low_stock = self.cursor.execute('''
            SELECT mpn, stock_qty, min_stock FROM components 
            WHERE stock_qty < min_stock AND min_stock > 0
        ''').fetchall()
        
        if low_stock:
            self.alerts_text.insert(tk.END, "⚠️ LOW STOCK WARNINGS:\n", "warning")
            for mpn, qty, min_qty in low_stock:
                self.alerts_text.insert(tk.END, f"  • {mpn}: {qty} (min: {min_qty})\n")
            self.alerts_text.insert(tk.END, "\n")
        
        # Obsolete parts
        obsolete = self.cursor.execute('''
            SELECT mpn, lifecycle_status FROM components 
            WHERE lifecycle_status IN ('Obsolete', 'EOL', 'NRND')
        ''').fetchall()
        
        if obsolete:
            self.alerts_text.insert(tk.END, "🚫 LIFECYCLE ALERTS:\n", "error")
            for mpn, status in obsolete:
                self.alerts_text.insert(tk.END, f"  • {mpn}: {status}\n")
            self.alerts_text.insert(tk.END, "\n")
        
        # Price increases
        price_changes = self.cursor.execute('''
            SELECT c.mpn, ph1.price as old_price, ph2.price as new_price
            FROM components c
            JOIN price_history ph1 ON c.id = ph1.component_id
            JOIN price_history ph2 ON c.id = ph2.component_id
            WHERE ph2.date > ph1.date
            AND ph2.price > ph1.price * 1.1
            GROUP BY c.mpn
        ''').fetchall()
        
        if price_changes:
            self.alerts_text.insert(tk.END, "💰 PRICE INCREASES (>10%):\n", "info")
            for mpn, old, new in price_changes[:5]:
                change = ((new - old) / old) * 100
                self.alerts_text.insert(tk.END, f"  • {mpn}: ${old:.2f} → ${new:.2f} (+{change:.1f}%)\n")
        
        if not low_stock and not obsolete and not price_changes:
            self.alerts_text.insert(tk.END, "✓ All systems normal\nNo alerts at this time", "success")
        
        # Configure tags
        self.alerts_text.tag_config("warning", foreground=self.accent_orange, font=("Arial", 10, "bold"))
        self.alerts_text.tag_config("error", foreground=self.accent_red, font=("Arial", 10, "bold"))
        self.alerts_text.tag_config("info", foreground=self.accent, font=("Arial", 10, "bold"))
        self.alerts_text.tag_config("success", foreground=self.accent_green, font=("Arial", 10, "bold"))


    def open_recent_projects(self, event):



    def create_analytics_tab(self):



    def update_chart(self):



    def create_components_tab(self):



    def update_category_filter(self):



    def filter_components(self):



    def sort_components(self, column):



    def update_prices_octopart(self):



    def generate_report(self):



    def show_settings(self):



    def manage_suppliers(self):



    def toggle_theme(self):



    def startup_checks(self):



    def check_updates(self):



    def show_shortcuts(self):



    def manual_backup(self):



    def restore_backup(self):



    def create_bom_tab(self):



    def create_tools_tab(self):



    def add_component(self):



        def save():



    def new_project(self):



    def browse_folder(self, entry):



    def refresh_components(self):



    def refresh_projects(self):



    def refresh_projects_combo(self):



    def load_bom(self):



    def update_dashboard_stats(self):



    def import_bom(self):



        def do_import():



    def search_components(self):



    def launch_external(self, command):



    def check_lifecycle(self):



    def cost_analysis(self):



    def find_alternatives(self):



    def delete_project(self):



    def open_project(self, event):



    def open_folder(self, path):



    def edit_component(self, event):



    def show_component_context_menu(self, event):



    def view_datasheet(self):



    def delete_component(self):



    def export_components(self):



    def show_help(self):



    def show_about(self):



def main():
    root = tk.Tk()
    app = HardwareEngineeringTool(root)
    root.mainloop()



if __name__ == "__main__":
    main()