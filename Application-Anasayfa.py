"""
PDF Atölyesi - PDF Birleştirici ve Sayfa Ayırıcı
=================================================
Geliştirici : Engin Arslan
Sürüm       : 1.0.4
Lisans      : MIT
"""

from __future__ import annotations

import os
import webbrowser

import tkinter as tk
from tkinter import filedialog, messagebox

import customtkinter as ctk
from PIL import Image

from pypdf import PdfReader, PdfWriter

try:
    import fitz
    FITZ_AVAILABLE = True
except ImportError:
    fitz = None
    FITZ_AVAILABLE = False


# ---------------------------------------------------------------------------
# SABİTLER
# ---------------------------------------------------------------------------
APP_NAME = "PDF Atölyesi"
APP_VERSION = "1.0.4"

THEMES = {
    "dark": {
        "bg":         "#0f172a",
        "surface":    "#1e293b",
        "surface_hi": "#334155",
        "border":     "#475569",
        "primary":    "#3b82f6",
        "primary_hi": "#2563eb",
        "success":    "#22c55e",
        "success_hi": "#16a34a",
        "danger":     "#ef4444",
        "danger_hi":  "#b91c1c",
        "warn":       "#f59e0b",
        "text":       "#f1f5f9",
        "text_dim":   "#94a3b8",
        "header":     "#1e293b",
        "footer":     "#1e293b",
    },
    "light": {
        "bg":         "#f1f5f9",
        "surface":    "#ffffff",
        "surface_hi": "#e2e8f0",
        "border":     "#cbd5e1",
        "primary":    "#2563eb",
        "primary_hi": "#1d4ed8",
        "success":    "#16a34a",
        "success_hi": "#15803d",
        "danger":     "#dc2626",
        "danger_hi":  "#b91c1c",
        "warn":       "#d97706",
        "text":       "#0f172a",
        "text_dim":   "#64748b",
        "header":     "#ffffff",
        "footer":     "#ffffff",
    },
}

SOCIAL_LINKS = [
    ("🐙", "GitHub",    "https://github.com/EnginArslan49?tab=repositories"),
    ("💼", "LinkedIn",  "https://www.linkedin.com/in/engin-arslan-49e04/"),
    ("📸", "Instagram", "https://www.instagram.com/49engn04"),
    ("🎥", "YouTube",   "https://www.youtube.com/@ramkafe"),
]


# ---------------------------------------------------------------------------
# YARDIMCILAR
# ---------------------------------------------------------------------------
def human_size(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def parse_page_ranges(range_str: str, total: int) -> list[int]:
    if not range_str.strip():
        raise ValueError("Sayfa aralığı boş olamaz.")
    pages: list[int] = []
    for part in range_str.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            s, e = int(a.strip()), int(b.strip())
            if s > e:
                raise ValueError(f"Geçersiz aralık: '{part}'")
            pages.extend(range(s, e + 1))
        else:
            pages.append(int(part))
    for p in pages:
        if p < 1 or p > total:
            raise ValueError(f"Sayfa {p} mevcut değil (toplam: {total})")
    seen, out = set(), []
    for p in pages:
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out


def render_pdf_page(pdf_path, page_index: int, max_w: int = 520, max_h: int = 640):
    if not FITZ_AVAILABLE:
        return None
    doc = fitz.open(pdf_path)
    try:
        page = doc.load_page(page_index)
        rect = page.rect
        zoom = min(max_w / rect.width, max_h / rect.height)
        pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
        return Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    finally:
        doc.close()


def get_page_count(pdf_path) -> int:
    if FITZ_AVAILABLE:
        doc = fitz.open(pdf_path)
        try:
            return doc.page_count
        finally:
            doc.close()
    return len(PdfReader(pdf_path).pages)


# ---------------------------------------------------------------------------
# ANA UYGULAMA
# ---------------------------------------------------------------------------
class PDFAtolyesi(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title(f"{APP_NAME}  •  v{APP_VERSION}")
        self.geometry("1280x820")
        self.minsize(1080, 720)

        ctk.set_default_color_theme("blue")

        self.update_idletasks()
        w, h = 1280, 820
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")

        self._theme_name = "dark"
        ctk.set_appearance_mode(self._theme_name)

        self._merge_files: list[str] = []
        self._preview_path: str | None = None
        self._preview_page: int = 0
        self._preview_total: int = 0
        self._preview_img_ref = None
        self._thumb_refs: list = []
        self._split_path: str | None = None
        self._split_total: int = 0
        self._split_selected: set[int] = set()
        self._current_mode: str | None = None

        self._apply_theme()

        # === LAYOUT ===
        self._header = ctk.CTkFrame(self, fg_color=self.C["header"],
                                    corner_radius=0, height=72)
        self._header.pack(side="top", fill="x")
        self._header.pack_propagate(False)

        self._footer = ctk.CTkFrame(self, fg_color=self.C["footer"],
                                    corner_radius=0, height=60)
        self._footer.pack(side="bottom", fill="x")
        self._footer.pack_propagate(False)

        self._content = ctk.CTkFrame(self, fg_color=self.C["bg"], corner_radius=0)
        self._content.pack(side="top", fill="both", expand=True,
                           padx=16, pady=12)

        self._build_header()
        self._build_footer()
        self._show_welcome()

        if not FITZ_AVAILABLE:
            self.after(500, self._show_fitz_warning)

    # ------------------------------------------------------------------
    def _apply_theme(self):
        self.C = THEMES[self._theme_name]
        self.configure(fg_color=self.C["bg"])

    def _toggle_theme(self):
        self._theme_name = "light" if self._theme_name == "dark" else "dark"
        ctk.set_appearance_mode(self._theme_name)
        self._apply_theme()

        for child in self._header.winfo_children():
            child.destroy()
        for child in self._footer.winfo_children():
            child.destroy()
        self._header.configure(fg_color=self.C["header"])
        self._footer.configure(fg_color=self.C["footer"])
        self._content.configure(fg_color=self.C["bg"])
        self._build_header()
        self._build_footer()

        if self._current_mode:
            self._enter_mode(self._current_mode)
        else:
            self._show_welcome()

    def _show_fitz_warning(self):
        messagebox.showwarning(
            "Önizleme Devre Dışı",
            "PyMuPDF (fitz) yüklü değil.\n\n"
            "Önizleme ve küçük resim özellikleri devre dışı.\n"
            "Birleştirme ve ayırma işlemleri sorunsuz çalışmaya devam eder.\n\n"
            "Kurulum için terminalde:\n\n    pip install pymupdf",
            parent=self,
        )

    # ==================================================================
    # HEADER — logo + başlıklar HER ZAMAN sol yaslı, görünür
    # ==================================================================
    def _build_header(self):
        C = self.C
        self._header.grid_columnconfigure(1, weight=1)

        # SOL: logo + iki satır başlık — artık HİÇ GİZLENMİYOR
        self._logo_block = ctk.CTkFrame(self._header, fg_color="transparent")
        self._logo_block.grid(row=0, column=0, sticky="w", padx=(20, 0), pady=10)

        logo_inner = ctk.CTkFrame(self._logo_block, fg_color="transparent")
        logo_inner.pack(side="left")

        ctk.CTkLabel(logo_inner, text="📄", font=ctk.CTkFont(size=26)
                     ).pack(side="left", padx=(0, 10))

        title_box = ctk.CTkFrame(logo_inner, fg_color="transparent")
        title_box.pack(side="left")

        row = ctk.CTkFrame(title_box, fg_color="transparent")
        row.pack(anchor="w")
        ctk.CTkLabel(row, text=APP_NAME,
                     font=ctk.CTkFont(size=18, weight="bold"),
                     text_color=C["text"]).pack(side="left")
        ctk.CTkLabel(row, text=f"  v{APP_VERSION}",
                     font=ctk.CTkFont(size=10),
                     text_color=C["text_dim"]).pack(side="left", pady=(4, 0))

        ctk.CTkLabel(
            title_box,
            text="PDF Birleştirici & Sayfa Ayırıcı  •  💡 Tamamen ücretsiz",
            font=ctk.CTkFont(size=9),
            text_color=C["text_dim"],
        ).pack(anchor="w")

        # ORTA: mod etiketi (workspace'te dolar)
        self._header_mode_lbl = ctk.CTkLabel(
            self._header, text="",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=C["primary"],
        )
        self._header_mode_lbl.grid(row=0, column=1, sticky="w", padx=20)

        # SAĞ: [Yardım] [Ana Sayfa] [Tema]
        right = ctk.CTkFrame(self._header, fg_color="transparent")
        right.grid(row=0, column=2, sticky="e", padx=(0, 20), pady=10)

        self._help_btn = ctk.CTkButton(
            right, text="❓  Nasıl Kullanılır?", width=150, height=34,
            fg_color=C["primary"], hover_color=C["primary_hi"],
            text_color="white", font=ctk.CTkFont(size=11, weight="bold"),
            command=self._open_help,
        )
        self._help_btn.pack(side="left", padx=(0, 8))
        self._help_btn.pack_forget()

        self._home_btn = ctk.CTkButton(
            right, text="🏠  Ana Sayfa", width=120, height=34,
            fg_color=C["surface_hi"], hover_color=C["border"],
            text_color=C["text"], font=ctk.CTkFont(size=11, weight="bold"),
            command=self._show_welcome,
        )
        self._home_btn.pack(side="left", padx=(0, 8))
        self._home_btn.pack_forget()

        theme_icon = "☀️" if self._theme_name == "dark" else "🌙"
        self._theme_btn = ctk.CTkButton(
            right, text=theme_icon, width=42, height=34,
            fg_color=C["surface_hi"], hover_color=C["border"],
            text_color=C["text"], font=ctk.CTkFont(size=15),
            command=self._toggle_theme,
        )
        self._theme_btn.pack(side="left")

    # ==================================================================
    # FOOTER
    # ==================================================================
    def _build_footer(self):
        C = self.C
        self._footer.grid_columnconfigure(1, weight=1)

        left = ctk.CTkFrame(self._footer, fg_color="transparent")
        left.grid(row=0, column=0, sticky="w", padx=(20, 12), pady=10)
        ctk.CTkLabel(left, text="👤  Geliştirici: ",
                     font=ctk.CTkFont(size=11), text_color=C["text_dim"]
                     ).pack(side="left")
        ctk.CTkLabel(left, text="Engin Arslan",
                     font=ctk.CTkFont(size=11, weight="bold"),
                     text_color=C["text"]).pack(side="left")

        mid = ctk.CTkFrame(self._footer, fg_color="transparent")
        mid.grid(row=0, column=1, sticky="w", padx=8, pady=10)
        for emoji, name, url in SOCIAL_LINKS:
            ctk.CTkButton(
                mid, text=f"{emoji} {name}", width=100, height=30,
                fg_color="transparent", hover_color=C["surface_hi"],
                text_color=C["primary"],
                font=ctk.CTkFont(size=11),
                border_width=1, border_color=C["border"],
                command=lambda u=url: webbrowser.open_new_tab(u),
            ).pack(side="left", padx=4)

        right = ctk.CTkFrame(self._footer, fg_color="transparent")
        right.grid(row=0, column=2, sticky="e", padx=(8, 20), pady=10)

        self._status_lbl = ctk.CTkLabel(
            right, text="Hazır.", font=ctk.CTkFont(size=10),
            text_color=C["text_dim"],
        )
        self._status_lbl.pack(side="left", padx=(0, 6))

    def _set_status(self, msg: str):
        if hasattr(self, "_status_lbl"):
            self._status_lbl.configure(text=msg)

    # ==================================================================
    # KARŞILAMA — artık başlık YOK, sadece soru + kartlar
    # ==================================================================
    def _clear_content(self):
        for w in self._content.winfo_children():
            w.destroy()
        for i in range(4):
            try:
                self._content.grid_rowconfigure(i, weight=0)
            except Exception:
                pass
        for i in range(3):
            try:
                self._content.grid_columnconfigure(i, weight=0)
            except Exception:
                pass

    def _show_welcome(self):
        self._current_mode = None
        self._header_mode_lbl.configure(text="")
        self._home_btn.pack_forget()
        self._help_btn.pack_forget()
        # ARTIK logo_block gizlenmiyor — header her sayfada görünür

        self._clear_content()
        C = self.C

        self._content.grid_rowconfigure(0, weight=1)
        self._content.grid_columnconfigure(0, weight=1)

        wrap = ctk.CTkFrame(self._content, fg_color="transparent")
        wrap.grid(row=0, column=0, sticky="nsew")
        wrap.grid_rowconfigure(1, weight=1)
        wrap.grid_columnconfigure(0, weight=1)

        title_box = ctk.CTkFrame(wrap, fg_color="transparent")
        title_box.grid(row=0, column=0, pady=(50, 24))

        # Başlık artık header'da — burada sadece soru
        ctk.CTkLabel(title_box, text="Ne yapmak istersiniz?",
                     font=ctk.CTkFont(size=22, weight="bold"),
                     text_color=C["text"]).pack()
        ctk.CTkLabel(title_box,
                     text="Başlamak için aşağıdaki işlemlerden birini seçin.",
                     font=ctk.CTkFont(size=12),
                     text_color=C["text_dim"]).pack(pady=(6, 0))

        cards = ctk.CTkFrame(wrap, fg_color="transparent")
        cards.grid(row=1, column=0, pady=(10, 40))
        cards.grid_columnconfigure((0, 1), weight=1, uniform="card")

        self._welcome_card(
            cards, col=0,
            icon="🔗", title="PDF Birleştir",
            desc="Birden fazla PDF'i tek dosyada birleştirin.",
            color=C["primary"], hover=C["primary_hi"],
            on_start=lambda: self._enter_mode("merge"),
        )
        self._welcome_card(
            cards, col=1,
            icon="✂️", title="Sayfa Ayır",
            desc="Sayfa aralığı belirterek PDF'ten ayıklayın.",
            color=C["success"], hover=C["success_hi"],
            on_start=lambda: self._enter_mode("split"),
        )

    def _welcome_card(self, parent, col, icon, title, desc, color, hover, on_start):
        C = self.C
        card = ctk.CTkFrame(
            parent, fg_color=C["surface"], corner_radius=14,
            border_width=1, border_color=C["border"], width=320, height=230,
        )
        card.grid(row=0, column=col, padx=14, pady=4, sticky="nsew")
        card.grid_propagate(False)

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(expand=True, fill="both", padx=22, pady=18)

        ctk.CTkLabel(inner, text=icon,
                     font=ctk.CTkFont(size=42)).pack(pady=(0, 6))
        ctk.CTkLabel(inner, text=title,
                     font=ctk.CTkFont(size=18, weight="bold"),
                     text_color=C["text"]).pack()
        ctk.CTkLabel(inner, text=desc,
                     font=ctk.CTkFont(size=11),
                     text_color=C["text_dim"],
                     justify="center", wraplength=270).pack(pady=(4, 16))

        ctk.CTkButton(
            inner, text="▶  Başla", width=160, height=38,
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=color, hover_color=hover, corner_radius=8,
            command=on_start,
        ).pack()

        def _enter(_e):
            card.configure(border_color=color)
        def _leave(_e):
            card.configure(border_color=C["border"])
        card.bind("<Enter>", _enter)
        card.bind("<Leave>", _leave)

    # ==================================================================
    # MOD GEÇİŞİ
    # ==================================================================
    def _enter_mode(self, mode: str):
        self._current_mode = mode
        self._clear_content()

        # Ana Sayfa + Yardım butonları görünür
        self._home_btn.pack(side="left", padx=(0, 8), before=self._theme_btn)
        self._help_btn.pack(side="left", padx=(0, 8), before=self._home_btn)

        if mode == "merge":
            self._header_mode_lbl.configure(text="🔗  PDF Birleştirme Modu")
            self._build_merge_workspace(self._content)
        else:
            self._header_mode_lbl.configure(text="✂️  Sayfa Ayırma Modu")
            self._build_split_workspace(self._content)

    # ==================================================================
    # BİRLEŞTİRME
    # ==================================================================
    def _build_merge_workspace(self, parent):
        C = self.C
        parent.grid_rowconfigure(0, weight=1)
        parent.grid_columnconfigure(0, weight=3, minsize=380)
        parent.grid_columnconfigure(1, weight=4)

        left = ctk.CTkFrame(parent, fg_color=C["surface"], corner_radius=10)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        left.grid_rowconfigure(2, weight=1)
        left.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(left, text="📚  Birleştirilecek Dosyalar",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=C["text"]).grid(row=0, column=0, sticky="w", padx=12, pady=(12, 4))
        self._merge_count_lbl = ctk.CTkLabel(left, text="Henüz dosya eklenmedi",
                                             font=ctk.CTkFont(size=10),
                                             text_color=C["text_dim"])
        self._merge_count_lbl.grid(row=1, column=0, sticky="w", padx=12, pady=(0, 6))

        lb_frame = ctk.CTkFrame(left, fg_color=C["bg"], corner_radius=8)
        lb_frame.grid(row=2, column=0, sticky="nsew", padx=12, pady=(0, 6))
        lb_frame.grid_rowconfigure(0, weight=1)
        lb_frame.grid_columnconfigure(0, weight=1)

        self._merge_listbox = tk.Listbox(
            lb_frame, bg=C["bg"], fg=C["text"],
            selectbackground=C["primary"], selectforeground="white",
            highlightthickness=0, borderwidth=0, activestyle="none",
            font=("Segoe UI", 10), height=14,
        )
        self._merge_listbox.grid(row=0, column=0, sticky="nsew", padx=6, pady=6)
        self._merge_listbox.bind("<<ListboxSelect>>", self._on_merge_select)

        msb = ctk.CTkScrollbar(lb_frame, command=self._merge_listbox.yview)
        msb.grid(row=0, column=1, sticky="ns", padx=(0, 6), pady=6)
        self._merge_listbox.configure(yscrollcommand=msb.set)

        btns = ctk.CTkFrame(left, fg_color="transparent")
        btns.grid(row=3, column=0, sticky="ew", padx=12, pady=(0, 6))
        for i in range(3):
            btns.grid_columnconfigure(i, weight=1)

        ctk.CTkButton(btns, text="➕ Ekle", height=32, fg_color=C["primary"],
                      hover_color=C["primary_hi"], command=self._merge_add
                      ).grid(row=0, column=0, sticky="ew", padx=(0, 4))
        ctk.CTkButton(btns, text="⬆️", height=32, width=44, fg_color=C["surface_hi"],
                      hover_color=C["border"], command=self._merge_up
                      ).grid(row=0, column=1, padx=2)
        ctk.CTkButton(btns, text="⬇️", height=32, width=44, fg_color=C["surface_hi"],
                      hover_color=C["border"], command=self._merge_down
                      ).grid(row=0, column=2, padx=2)
        ctk.CTkButton(btns, text="❌ Kaldır", height=32, fg_color=C["danger"],
                      hover_color=C["danger_hi"], command=self._merge_remove
                      ).grid(row=1, column=0, sticky="ew", padx=(0, 4), pady=(6, 0))
        ctk.CTkButton(btns, text="🗑️ Temizle", height=32, fg_color=C["surface_hi"],
                      hover_color=C["border"], command=self._merge_clear
                      ).grid(row=1, column=1, columnspan=2, sticky="ew", padx=(2, 0), pady=(6, 0))

        ctk.CTkButton(left, text="🚀  PDF'leri Birleştir ve Kaydet", height=44,
                      font=ctk.CTkFont(size=13, weight="bold"),
                      fg_color=C["success"], hover_color=C["success_hi"],
                      command=self._merge_execute
                      ).grid(row=4, column=0, sticky="ew", padx=12, pady=(0, 12))

        right = ctk.CTkFrame(parent, fg_color=C["surface"], corner_radius=10)
        right.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        right.grid_rowconfigure(2, weight=1)
        right.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(right, text="🖼️  Canlı Önizleme",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=C["text"]).grid(row=0, column=0, sticky="w", padx=12, pady=(12, 4))

        nav = ctk.CTkFrame(right, fg_color="transparent")
        nav.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 6))
        ctk.CTkButton(nav, text="◀", width=36, height=30, fg_color=C["surface_hi"],
                      hover_color=C["border"],
                      command=lambda: self._preview_goto(self._preview_page - 1)).pack(side="left")
        self._page_entry = ctk.CTkEntry(nav, width=64, height=30, justify="center",
                                        fg_color=C["bg"], border_color=C["border"],
                                        text_color=C["text"])
        self._page_entry.pack(side="left", padx=6)
        self._page_entry.insert(0, "0")
        self._page_entry.bind("<Return>", self._on_page_entry)
        self._page_total_lbl = ctk.CTkLabel(nav, text="/ 0", font=ctk.CTkFont(size=11),
                                            text_color=C["text_dim"])
        self._page_total_lbl.pack(side="left")
        ctk.CTkButton(nav, text="▶", width=36, height=30, fg_color=C["surface_hi"],
                      hover_color=C["border"],
                      command=lambda: self._preview_goto(self._preview_page + 1)).pack(side="left", padx=(6, 0))
        self._preview_name_lbl = ctk.CTkLabel(nav, text="—", font=ctk.CTkFont(size=10),
                                              text_color=C["text_dim"])
        self._preview_name_lbl.pack(side="right")

        self._preview_container = ctk.CTkFrame(right, fg_color=C["bg"], corner_radius=8)
        self._preview_container.grid(row=2, column=0, sticky="nsew", padx=12, pady=(0, 12))
        self._preview_container.grid_rowconfigure(0, weight=1)
        self._preview_container.grid_columnconfigure(0, weight=1)

        initial = ("📄\n\nBir PDF seçtiğinizde\nburada önizleme görünür"
                   if FITZ_AVAILABLE else "⚠️\n\nÖnizleme için PyMuPDF gerekli\n\npip install pymupdf")
        self._preview_label = ctk.CTkLabel(self._preview_container, text=initial,
                                           font=ctk.CTkFont(size=13),
                                           text_color=C["text_dim"], justify="center")
        self._preview_label.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

    # ==================================================================
    # AYIRMA
    # ==================================================================
    def _build_split_workspace(self, parent):
        C = self.C
        parent.grid_rowconfigure(2, weight=1)
        parent.grid_columnconfigure(0, weight=1)

        top = ctk.CTkFrame(parent, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", pady=(0, 4))
        top.grid_columnconfigure(1, weight=1)

        ctk.CTkButton(top, text="📂  PDF Seç", width=130, fg_color=C["primary"],
                      hover_color=C["primary_hi"], command=self._split_pick
                      ).grid(row=0, column=0, padx=(0, 12))
        self._split_file_lbl = ctk.CTkLabel(top, text="Henüz dosya seçilmedi",
                                            font=ctk.CTkFont(size=12),
                                            text_color=C["text"], anchor="w")
        self._split_file_lbl.grid(row=0, column=1, sticky="ew")
        self._split_pages_lbl = ctk.CTkLabel(top, text="Toplam sayfa: —",
                                             font=ctk.CTkFont(size=12, weight="bold"),
                                             text_color=C["primary"])
        self._split_pages_lbl.grid(row=0, column=2, sticky="e")

        range_row = ctk.CTkFrame(parent, fg_color=C["surface"], corner_radius=8)
        range_row.grid(row=1, column=0, sticky="ew", pady=6)
        range_row.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(range_row, text="Sayfa Aralığı:",
                     font=ctk.CTkFont(size=12, weight="bold"),
                     text_color=C["text"]).grid(row=0, column=0, padx=(12, 8), pady=10)
        self._split_range = ctk.CTkEntry(range_row, placeholder_text="örn: 1-3,5,8-10",
                                         fg_color=C["bg"], border_color=C["border"],
                                         text_color=C["text"])
        self._split_range.grid(row=0, column=1, sticky="ew", padx=(0, 8), pady=10)
        ctk.CTkButton(range_row, text="✂️  Ayır ve Kaydet", width=160, height=34,
                      fg_color=C["success"], hover_color=C["success_hi"],
                      font=ctk.CTkFont(size=12, weight="bold"),
                      command=self._split_execute
                      ).grid(row=0, column=2, padx=(0, 12), pady=10)

        grid_wrap = ctk.CTkFrame(parent, fg_color=C["surface"], corner_radius=8)
        grid_wrap.grid(row=2, column=0, sticky="nsew", pady=(6, 0))
        grid_wrap.grid_rowconfigure(0, weight=1)
        grid_wrap.grid_columnconfigure(0, weight=1)

        self._thumb_scroll = ctk.CTkScrollableFrame(grid_wrap, fg_color=C["bg"],
                                                    scrollbar_button_color=C["surface_hi"])
        self._thumb_scroll.grid(row=0, column=0, sticky="nsew", padx=6, pady=6)

        placeholder = ("📄\n\nPDF seçtikten sonra sayfa küçük resimleri burada görünür.\n"
                       "Küçük resimlere tıklayarak sayfa seçebilirsiniz."
                       if FITZ_AVAILABLE else
                       "⚠️  Küçük resimler için PyMuPDF gerekli.\n\npip install pymupdf\n\n"
                       "Dilerseniz aralık kutusuna doğrudan 1-3,5-8-10 gibi yazabilirsiniz.")
        ctk.CTkLabel(self._thumb_scroll, text=placeholder, font=ctk.CTkFont(size=12),
                     text_color=C["text_dim"], justify="center").pack(pady=40)

    # ==================================================================
    # BİRLEŞTİRME MANTIĞI
    # ==================================================================
    def _on_merge_select(self, _evt=None):
        sel = self._merge_listbox.curselection()
        if not sel:
            return
        self._load_preview(self._merge_files[sel[0]])

    def _merge_add(self):
        files = filedialog.askopenfilenames(
            title="Birleştirilecek PDF'leri seçin",
            filetypes=[("PDF dosyaları", "*.pdf")],
        )
        if not files:
            return
        added = 0
        for f in files:
            if f not in self._merge_files:
                self._merge_files.append(f)
                added += 1
        self._refresh_merge_list()
        if added and not self._preview_path:
            self._merge_listbox.selection_set(0)
            self._on_merge_select()
        self._set_status(f"{added} dosya eklendi. Toplam: {len(self._merge_files)}")

    def _merge_up(self):
        sel = self._merge_listbox.curselection()
        if not sel or sel[0] == 0:
            return
        i = sel[0]
        self._merge_files[i - 1], self._merge_files[i] = self._merge_files[i], self._merge_files[i - 1]
        self._refresh_merge_list()
        self._merge_listbox.selection_set(i - 1)

    def _merge_down(self):
        sel = self._merge_listbox.curselection()
        if not sel or sel[0] >= len(self._merge_files) - 1:
            return
        i = sel[0]
        self._merge_files[i + 1], self._merge_files[i] = self._merge_files[i], self._merge_files[i + 1]
        self._refresh_merge_list()
        self._merge_listbox.selection_set(i + 1)

    def _merge_remove(self):
        sel = self._merge_listbox.curselection()
        if not sel:
            return
        del self._merge_files[sel[0]]
        self._refresh_merge_list()
        if self._merge_files:
            idx = min(sel[0], len(self._merge_files) - 1)
            self._merge_listbox.selection_set(idx)
            self._on_merge_select()
        else:
            self._clear_preview()

    def _merge_clear(self):
        self._merge_files.clear()
        self._refresh_merge_list()
        self._clear_preview()

    def _refresh_merge_list(self):
        C = self.C
        self._merge_listbox.configure(bg=C["bg"], fg=C["text"])
        self._merge_listbox.delete(0, "end")
        for i, f in enumerate(self._merge_files, 1):
            self._merge_listbox.insert("end", f"  {i:02d}.  {os.path.basename(f)}")
        n = len(self._merge_files)
        self._merge_count_lbl.configure(text=f"{n} dosya" if n else "Henüz dosya eklenmedi")

    def _merge_execute(self):
        if len(self._merge_files) < 2:
            messagebox.showwarning("Yetersiz Dosya",
                                   "Birleştirme için en az 2 PDF eklemelisiniz.", parent=self)
            return
        out = filedialog.asksaveasfilename(
            title="Birleştirilmiş PDF'i kaydet", defaultextension=".pdf",
            filetypes=[("PDF dosyası", "*.pdf")], initialfile="birlestirilmis.pdf",
        )
        if not out:
            return
        try:
            writer = PdfWriter()
            for pdf in self._merge_files:
                reader = PdfReader(pdf)
                for page in reader.pages:
                    writer.add_page(page)
            with open(out, "wb") as f:
                writer.write(f)
            size = human_size(os.path.getsize(out))
            messagebox.showinfo("Başarılı ✅",
                                f"Birleştirme tamamlandı.\n\n{out}\n\nBoyut: {size}", parent=self)
            self._set_status(f"Birleştirildi → {os.path.basename(out)} ({size})")
        except Exception as e:
            messagebox.showerror("Hata ❌", f"Birleştirme hatası:\n{e}", parent=self)

    # ==================================================================
    # ÖNİZLEME
    # ==================================================================
    def _load_preview(self, path: str):
        self._preview_path = path
        self._preview_page = 0
        self._preview_name_lbl.configure(text=os.path.basename(path))
        if not FITZ_AVAILABLE:
            try:
                self._preview_total = get_page_count(path)
                self._page_total_lbl.configure(text=f"/ {self._preview_total}")
            except Exception:
                self._preview_total = 0
            self._preview_label.configure(image="",
                                          text="⚠️  Önizleme için PyMuPDF gerekli\n\npip install pymupdf")
            return
        try:
            self._preview_total = get_page_count(path)
        except Exception as e:
            self._clear_preview()
            self._set_status(f"Önizleme hatası: {e}")
            return
        self._page_total_lbl.configure(text=f"/ {self._preview_total}")
        self._render_preview()

    def _render_preview(self):
        if not self._preview_path or not FITZ_AVAILABLE:
            return
        try:
            img = render_pdf_page(self._preview_path, self._preview_page)
            if img is None:
                return
            self._preview_container.update_idletasks()
            cw = max(300, self._preview_container.winfo_width() - 20)
            ch = max(300, self._preview_container.winfo_height() - 20)
            img.thumbnail((cw, ch), Image.LANCZOS)
            ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=img.size)
            self._preview_img_ref = ctk_img
            self._preview_label.configure(image=ctk_img, text="")
            self._page_entry.delete(0, "end")
            self._page_entry.insert(0, str(self._preview_page + 1))
        except Exception as e:
            self._set_status(f"Render hatası: {e}")

    def _preview_goto(self, idx: int):
        if not self._preview_path:
            return
        if 0 <= idx < self._preview_total:
            self._preview_page = idx
            self._render_preview()

    def _on_page_entry(self, _evt=None):
        try:
            n = int(self._page_entry.get())
            self._preview_goto(n - 1)
        except ValueError:
            pass

    def _clear_preview(self):
        self._preview_path = None
        self._preview_page = 0
        self._preview_total = 0
        txt = ("📄\n\nBir PDF seçtiğinizde\nburada önizleme görünür"
               if FITZ_AVAILABLE else "⚠️\n\nÖnizleme için PyMuPDF gerekli\n\npip install pymupdf")
        self._preview_label.configure(image="", text=txt)
        self._preview_name_lbl.configure(text="—")
        self._page_total_lbl.configure(text="/ 0")
        self._page_entry.delete(0, "end")
        self._page_entry.insert(0, "0")

    # ==================================================================
    # AYIRMA MANTIĞI
    # ==================================================================
    def _split_pick(self):
        path = filedialog.askopenfilename(
            title="Ayırılacak PDF'i seçin",
            filetypes=[("PDF dosyaları", "*.pdf")],
        )
        if not path:
            return
        try:
            total = get_page_count(path)
        except Exception as e:
            messagebox.showerror("Hata", f"PDF açılamadı:\n{e}", parent=self)
            return
        self._split_path = path
        self._split_total = total
        self._split_selected.clear()
        self._split_file_lbl.configure(text=os.path.basename(path))
        self._split_pages_lbl.configure(text=f"Toplam: {total} sayfa")
        if FITZ_AVAILABLE:
            doc = fitz.open(path)
            try:
                self._render_thumbnails(doc)
            finally:
                doc.close()
        else:
            for w in self._thumb_scroll.winfo_children():
                w.destroy()
            ctk.CTkLabel(self._thumb_scroll,
                         text="⚠️  Küçük resimler için PyMuPDF gerekli\npip install pymupdf\n\n"
                              "Aşağıdaki aralık kutusunu kullanabilirsiniz.",
                         font=ctk.CTkFont(size=12), text_color=self.C["warn"],
                         justify="center").pack(pady=40)
        self._set_status(f"{os.path.basename(path)} yüklendi ({total} sayfa).")

    def _render_thumbnails(self, doc):
        C = self.C
        for w in self._thumb_scroll.winfo_children():
            w.destroy()
        self._thumb_refs.clear()
        cols = 6
        for i in range(doc.page_count):
            page = doc.load_page(i)
            rect = page.rect
            zoom = min(150 / rect.width, 190 / rect.height)
            pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
            img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            thumb = ctk.CTkImage(light_image=img, dark_image=img, size=img.size)
            self._thumb_refs.append(thumb)

            cell = ctk.CTkFrame(self._thumb_scroll, fg_color="transparent")
            cell.grid(row=i // cols, column=i % cols, padx=6, pady=6)
            btn = ctk.CTkButton(cell, image=thumb, text="", width=img.width + 4,
                                height=img.height + 4, fg_color=C["surface_hi"],
                                hover_color=C["primary"], border_width=2,
                                border_color=C["border"],
                                command=lambda p=i: self._toggle_thumb(p))
            btn.pack()
            lbl = ctk.CTkLabel(cell, text=str(i + 1), font=ctk.CTkFont(size=10, weight="bold"),
                               text_color=C["text_dim"])
            lbl.pack()
            cell._btn = btn
            cell._lbl = lbl

    def _toggle_thumb(self, page_idx: int):
        C = self.C
        page_no = page_idx + 1
        parent = self._thumb_scroll.winfo_children()[page_idx]
        btn = parent._btn
        lbl = parent._lbl
        if page_no in self._split_selected:
            self._split_selected.remove(page_no)
            btn.configure(border_color=C["border"], fg_color=C["surface_hi"])
            lbl.configure(text_color=C["text_dim"])
        else:
            self._split_selected.add(page_no)
            btn.configure(border_color=C["success"], fg_color=C["primary"])
            lbl.configure(text_color=C["success"])
        self._refresh_range_entry()

    def _refresh_range_entry(self):
        if not self._split_selected:
            self._split_range.delete(0, "end")
            return
        pages = sorted(self._split_selected)
        parts = []
        start = prev = pages[0]
        for p in pages[1:]:
            if p == prev + 1:
                prev = p
                continue
            parts.append(f"{start}-{prev}" if start != prev else f"{start}")
            start = prev = p
        parts.append(f"{start}-{prev}" if start != prev else f"{start}")
        self._split_range.delete(0, "end")
        self._split_range.insert(0, ",".join(parts))

    def _split_execute(self):
        if not self._split_path:
            messagebox.showwarning("Dosya Yok", "Önce bir PDF seçin.", parent=self)
            return
        try:
            pages = parse_page_ranges(self._split_range.get(), self._split_total)
        except ValueError as e:
            messagebox.showerror("Geçersiz Aralık", str(e), parent=self)
            return
        out = filedialog.asksaveasfilename(
            title="Ayırılmış PDF'i kaydet", defaultextension=".pdf",
            filetypes=[("PDF dosyası", "*.pdf")], initialfile="ayrilmis.pdf",
        )
        if not out:
            return
        try:
            reader = PdfReader(self._split_path)
            writer = PdfWriter()
            for p in pages:
                writer.add_page(reader.pages[p - 1])
            with open(out, "wb") as f:
                writer.write(f)
            size = human_size(os.path.getsize(out))
            messagebox.showinfo("Başarılı ✅",
                                f"{len(pages)} sayfa ayıklandı.\n\n{out}\n\nBoyut: {size}", parent=self)
            self._set_status(f"Ayrıldı → {os.path.basename(out)} ({size})")
        except Exception as e:
            messagebox.showerror("Hata ❌", f"Ayırma hatası:\n{e}", parent=self)

    # ==================================================================
    # YARDIM
    # ==================================================================
    def _open_help(self):
        HelpWindow(self, context=self._current_mode, theme=self._theme_name)


# ---------------------------------------------------------------------------
# YARDIM PENCERESİ
# ---------------------------------------------------------------------------
class HelpWindow(ctk.CTkToplevel):
    def __init__(self, master, context: str | None = None, theme: str = "dark"):
        super().__init__(master)
        self._C = THEMES[theme]
        self.title("Nasıl Kullanılır? — PDF Atölyesi")
        self.geometry("780x660")
        self.configure(fg_color=self._C["bg"])
        self.transient(master)
        self.grab_set()

        self.update_idletasks()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"780x660+{(sw-780)//2}+{(sh-660)//2}")

        container = ctk.CTkScrollableFrame(
            self, fg_color=self._C["bg"], corner_radius=0,
            scrollbar_button_color=self._C["surface_hi"],
        )
        container.pack(fill="both", expand=True, padx=16, pady=16)

        title_box = ctk.CTkFrame(container, fg_color="transparent")
        title_box.pack(fill="x", pady=(0, 12))

        if context == "merge":
            header = "🔗  PDF Birleştirme — Nasıl Kullanılır?"
        elif context == "split":
            header = "✂️  Sayfa Ayırma — Nasıl Kullanılır?"
        else:
            header = "❓  PDF Atölyesi — Nasıl Kullanılır?"

        ctk.CTkLabel(title_box, text=header,
                     font=ctk.CTkFont(size=20, weight="bold"),
                     text_color=self._C["text"]).pack(anchor="w")
        ctk.CTkLabel(title_box, text="Aşağıdaki adımları takip edin.",
                     font=ctk.CTkFont(size=12),
                     text_color=self._C["text_dim"]).pack(anchor="w")

        if context == "merge":
            self._card(container, "🔗  PDF Birleştirme Adımları", [
                "1. ➕ Ekle butonuyla PDF dosyalarınızı seçin.",
                "   (Birden fazla dosyayı aynı anda seçebilirsiniz.)",
                "",
                "2. Listeden bir dosyaya tıklayın → sağ taraftaki önizleme",
                "   panelinde o dosyanın ilk sayfası görünür.",
                "",
                "3. ⬆️ / ⬇️ butonlarıyla dosyaların sırasını değiştirin.",
                "   ❌ Kaldır ile listeden çıkarabilirsiniz.",
                "",
                "4. ◀ ▶ butonlarıyla sayfalar arasında gezinin veya üstteki",
                "   kutuya sayfa numarası yazıp Enter'a basın.",
                "",
                "5. Her şey hazır olduğunda 🚀 PDF'leri Birleştir ve Kaydet",
                "   butonuna tıklayın.",
                "",
                "6. Açılan pencerede dosya adı ve konumu belirleyin → Kaydet.",
            ])
            self._card(container, "💡  İpuçları", [
                "• Orijinal dosyalarınız asla değiştirilmez;",
                "  her işlem yeni bir kopya oluşturur.",
                "• Birleştirme için en az 2 PDF gerekir.",
                "• Çıktı boyutu işlem sonrası bildirimde gösterilir.",
            ])

        elif context == "split":
            self._card(container, "✂️  Sayfa Ayırma Adımları", [
                "1. 📂 PDF Seç butonuyla ayırmak istediğiniz PDF'i yükleyin.",
                "",
                "2. Tüm sayfalar küçük resim olarak ekranda listelenir.",
                "",
                "3. Küçük resimlere tıklayarak istediğiniz sayfaları seçin.",
                "   Seçili sayfalar mavi kenarlıklı ve yeşil numaralı olur.",
                "",
                "4. Seçtiğiniz sayfalar Sayfa Aralığı kutusuna otomatik",
                "   yazılır (örn. 1-3,5,8-10).",
                "",
                "5. İsterseniz bu kutuya doğrudan kendi aralığınızı da",
                "   yazabilirsiniz.",
                "",
                "6. ✂️ Ayır ve Kaydet butonuna tıklayın → dosya adı ve",
                "   konum belirleyip kaydedin.",
            ])
            self._card(container, "📐  Sayfa Aralığı Sözdizimi", [
                "Tek sayfa:   5      → sadece 5. sayfa",
                "Aralık:      1-3    → 1, 2 ve 3. sayfalar",
                "Karışık:     1-3,5,8-10  → 1,2,3,5,8,9,10",
                "",
                "Not: Sayfalar 1'den başlar. Geçersiz veya aralık dışı",
                "bir sayfa yazarsanız uyarı alırsınız.",
            ])

        else:
            self._card(container, "🎯  Genel Bakış", [
                "PDF Atölyesi iki temel işlem yapar: PDF Birleştirme",
                "ve Sayfa Ayırma.",
                "",
                "Başlangıç ekranında iki kart görürsünüz. İşlem seçtikten",
                "sonra üst sağdaki ❓ Nasıl Kullanılır? butonuyla",
                "o işleme özel rehberi açabilirsiniz.",
                "",
                "Tüm işlemler tamamen yerel olarak çalışır — hiçbir veri",
                "internete gönderilmez. Orijinal dosyalarınız asla",
                "değiştirilmez; her işlem yeni bir kopya oluşturur.",
            ])

        self._card(container, "🛠️  Gereksinimler & Sorun Giderme", [
            "Zorunlu: pypdf, customtkinter, pillow",
            "Önizleme için: pymupdf",
            "",
            "Kurulum:",
            "    pip install pypdf pymupdf customtkinter pillow",
            "",
            "Sık karşılaşılan hatalar:",
            "• ModuleNotFoundError: No module named 'fitz'",
            "  → pip install pymupdf  (fitz değil!)",
            "• PermissionError → dosyayı açık tutan programı kapatın.",
            "• Şifreli PDF'ler desteklenmez.",
        ])

        ctk.CTkButton(container, text="Kapat", height=42,
                      font=ctk.CTkFont(size=13, weight="bold"),
                      fg_color=self._C["primary"], hover_color=self._C["primary_hi"],
                      command=self.destroy).pack(fill="x", padx=4, pady=(12, 8))

    def _card(self, parent, title, lines):
        C = self._C
        card = ctk.CTkFrame(parent, fg_color=C["surface"], corner_radius=10)
        card.pack(fill="x", pady=6)
        ctk.CTkLabel(card, text=title,
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=C["primary"]).pack(anchor="w", padx=14, pady=(12, 4))
        for line in lines:
            ctk.CTkLabel(card, text=line if line.strip() else " ",
                         font=ctk.CTkFont(size=12), text_color=C["text"],
                         justify="left", anchor="w", wraplength=700
                         ).pack(anchor="w", padx=14, pady=0)
        ctk.CTkFrame(card, height=1, fg_color=C["surface_hi"]).pack(
            fill="x", padx=14, pady=(8, 8))


# ---------------------------------------------------------------------------
# GİRİŞ
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    PDFAtolyesi().mainloop()