import tkinter as tk
from tkinter import messagebox
import csv
import sys
import os

INPUT_FILE    = "data.txt"
OUTPUT_FILE   = "result.csv"
REJECTED_FILE = "rejected.csv"
AUTO_SAVE     = True
HEADER = ["слово", "значение_слова", "синоним", "значение_синонима"]

BTN_FONT = ("Arial", 13, "bold")
BTN_PADX = 14
BTN_PADY = 10


# ---------- данные ----------
def load_data(path):
    groups, order = {}, []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\r\n")
            if not line or line.startswith("#"):
                continue
            parts = line.split(";")
            if len(parts) < 4:
                continue
            word, meaning, syn, val = parts[0], parts[1], parts[2], ";".join(parts[3:])
            if val.strip() == "?":
                continue
            key = (word, meaning, syn)
            if key not in groups:
                groups[key] = []
                order.append(key)
            if val not in groups[key]:
                groups[key].append(val)
    return [(k, groups[k]) for k in order]


def read_csv_rows(path):
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        return []
    with open(path, encoding="utf-8", newline="") as f:
        reader = csv.reader(f, delimiter=";")
        next(reader, None)
        return [row for row in reader if row and any(c.strip() for c in row)]


def ensure_header(path):
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        with open(path, "w", encoding="utf-8", newline="") as f:
            csv.writer(f, delimiter=";").writerow(HEADER)


def append_row(path, row):
    with open(path, "a", encoding="utf-8", newline="") as f:
        csv.writer(f, delimiter=";").writerow(row)


def write_all(path, rows):
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(HEADER)
        for r in rows:
            w.writerow(r)


def load_processed_keys():
    keys = set()
    for path in (OUTPUT_FILE, REJECTED_FILE):
        for row in read_csv_rows(path):
            if len(row) >= 3:
                keys.add((row[0], row[1], row[2]))
    return keys


# ---------- строка-вариант ----------
class OptionRow(tk.Frame):
    def __init__(self, parent, text, index, callback, font_size):
        super().__init__(parent, bg="white", relief="groove", bd=2, cursor="hand2")
        self.index = index
        self.callback = callback
        self.selected = False
        pad = max(6, font_size // 3)

        self.box = tk.Label(self, text="☐", font=("Arial", font_size),
                            bg="white", cursor="hand2")
        self.box.pack(side="left", padx=(pad, pad // 2), pady=pad)

        self.label = tk.Label(self, text=text, font=("Arial", font_size),
                              bg="white", anchor="w", justify="left",
                              wraplength=300, cursor="hand2")
        self.label.pack(side="left", fill="x", expand=True,
                        padx=(0, pad), pady=pad)

        for w in (self, self.box, self.label):
            w.bind("<Button-1>", self.on_click)
            w.bind("<Enter>", self.on_enter)
            w.bind("<Leave>", self.on_leave)

    def on_click(self, _):
        if self.selected:
            return
        if self.callback(self.index):
            self.selected = True
            self.box.config(text="☑")

    def set_wraplength(self, wl):
        self.label.config(wraplength=wl)

    def on_enter(self, _):
        if not self.selected:
            self._bg("#f0f8ff")

    def on_leave(self, _):
        if not self.selected:
            self._bg("white")

    def _bg(self, color):
        for w in (self, self.box, self.label):
            w.config(bg=color)


# ---------- приложение ----------
class App:
    def __init__(self, root, items, auto_save, skipped=0, total=0):
        self.root = root
        self.items = items
        self.idx = 0
        self.auto_save = auto_save
        self.transitioning = False
        self._resize_job = None
        self.skipped = skipped
        self.total = total or len(items)
        self.current_fs = None

        if auto_save:
            ensure_header(OUTPUT_FILE)
            ensure_header(REJECTED_FILE)
            self.results = []
            self.rejected = []
        else:
            self.results = read_csv_rows(OUTPUT_FILE)
            self.rejected = read_csv_rows(REJECTED_FILE)

        self.new_choices = 0
        self.new_rejected = 0

        # ============ Layout ============
        root.configure(bg="#f5f5f5")

        # 1. Кнопки — сначала, side="bottom", чтобы всегда были видны
        btn_frame = tk.Frame(root, bg="#e0e0e0", bd=1, relief="ridge")
        btn_frame.pack(side="bottom", fill="x", padx=10, pady=(5, 10))

        tk.Button(btn_frame, text="Пропустить", font=BTN_FONT,
                  command=self.skip, padx=BTN_PADX, pady=BTN_PADY,
                  bg="#eeeeee").pack(side="left", padx=(8, 4), pady=6)

        tk.Button(btn_frame, text="Нет верного варианта", font=BTN_FONT,
                  command=self.reject, padx=BTN_PADX, pady=BTN_PADY,
                  bg="#ffd8d8").pack(side="left", padx=4, pady=6)

        tk.Button(btn_frame, text="Завершить", font=BTN_FONT,
                  command=self.finish, padx=BTN_PADX, pady=BTN_PADY,
                  bg="#d8f0d8").pack(side="right", padx=(4, 8), pady=6)

        # 2. Прогресс — над кнопками
        self.progress = tk.Label(root, font=("Arial", 10), fg="#666", bg="#f5f5f5")
        self.progress.pack(side="bottom", fill="x", padx=10, pady=(0, 2))

        # 3. Заголовки — сверху
        self.header_word = tk.Label(root, font=("Arial", 16, "bold"),
                                    anchor="w", justify="left",
                                    bg="#eef4ff", fg="#002244")
        self.header_word.pack(side="top", fill="x", padx=10, pady=(10, 0))

        self.header_meaning = tk.Label(root, font=("Arial", 13),
                                       anchor="w", justify="left",
                                       bg="#eef4ff", fg="#334455")
        self.header_meaning.pack(side="top", fill="x", padx=10, pady=(2, 0))

        self.header_syn = tk.Label(root, font=("Arial", 13, "bold"),
                                   anchor="w", justify="left",
                                   bg="#eef4ff", fg="#0055aa")
        self.header_syn.pack(side="top", fill="x", padx=10, pady=(6, 6))

        # 4. Прокручиваемая область с вариантами
        container = tk.Frame(root, bg="white", relief="sunken", bd=1)
        container.pack(side="top", fill="both", expand=True, padx=10, pady=(0, 5))

        self.canvas = tk.Canvas(container, bg="white", highlightthickness=0)
        self.scrollbar = tk.Scrollbar(container, orient="vertical",
                                      command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)

        self.inner = tk.Frame(self.canvas, bg="white")
        self.canvas_window = self.canvas.create_window((0, 0),
                                                       window=self.inner,
                                                       anchor="nw")
        self.inner.bind("<Configure>", self._on_inner_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)

        # колесо мыши — глобально
        for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            root.bind_all(seq, self._on_mousewheel)

        root.bind("<Configure>", self.on_resize)
        root.after(10, self.render)   # первичный рендер, когда окно уже видно

    # -------- скроллбар и прокрутка --------
    def _on_inner_configure(self, _):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        self._toggle_scrollbar()

    def _on_canvas_configure(self, e):
        self.canvas.itemconfig(self.canvas_window, width=e.width)
        self._toggle_scrollbar()

    def _toggle_scrollbar(self):
        bbox = self.canvas.bbox("all")
        if not bbox:
            return
        content_h = bbox[3] - bbox[1]
        view_h = self.canvas.winfo_height()
        need = content_h > view_h + 2

        if need and not self.scrollbar.winfo_ismapped():
            self.scrollbar.pack(side="right", fill="y")
        elif not need and self.scrollbar.winfo_ismapped():
            self.scrollbar.pack_forget()
            self.canvas.yview_moveto(0)

    def _on_mousewheel(self, e):
        if not self.scrollbar.winfo_ismapped():
            return
        if e.num == 4:
            self.canvas.yview_scroll(-1, "units")
        elif e.num == 5:
            self.canvas.yview_scroll(1, "units")
        else:
            self.canvas.yview_scroll(int(-e.delta / 120), "units")

    # -------- ресайз --------
    def on_resize(self, event):
        if event.widget is not self.root:
            return
        if self._resize_job:
            self.root.after_cancel(self._resize_job)
        self._resize_job = self.root.after(200, self._maybe_rerender)

    def _maybe_rerender(self):
        self._resize_job = None
        if self.compute_font_size() != self.current_fs:
            self.render(keep_scroll=True)

    def compute_font_size(self):
        w = max(self.root.winfo_width(), 400)
        return max(12, min(32, w // 45))

    # -------- отрисовка --------
    def render(self, keep_scroll=False):
        if self.transitioning:
            return
        old_scroll = self.canvas.yview()[0] if keep_scroll else 0.0

        for w in self.inner.winfo_children():
            w.destroy()
        if self.idx >= len(self.items):
            self.finish()
            return

        (word, meaning, syn), values = self.items[self.idx]
        fs = self.compute_font_size()
        self.current_fs = fs
        width = max(self.root.winfo_width(), 400)
        wrap = width - 30

        self.header_word.config(
            text=word,
            font=("Arial", max(14, int(fs * 1.1)), "bold"),
            wraplength=wrap)
        self.header_meaning.config(
            text=meaning,
            font=("Arial", max(11, int(fs * 0.85))),
            wraplength=wrap)
        self.header_syn.config(
            text=f"Синоним: {syn}",
            font=("Arial", max(11, int(fs * 0.85)), "bold"),
            wraplength=wrap)

        done = self.skipped + self.idx
        self.progress.config(
            text=(f"{done + 1} из {self.total}"
                  f"  (уже обработано ранее: {self.skipped})"),
            font=("Arial", max(9, fs // 2)))

        row_wrap = max(200, width - fs * 4 - 40)
        for i, v in enumerate(values):
            row = OptionRow(self.inner, v, i, self.on_select, fs)
            row.pack(fill="x", anchor="w", pady=4, padx=6)
            row.set_wraplength(row_wrap)

        self.root.after_idle(lambda: self.canvas.yview_moveto(old_scroll))
        self.root.after(10, self._toggle_scrollbar)

    # -------- действия --------
    def on_select(self, i):
        if self.transitioning:
            return False
        self.transitioning = True
        (word, meaning, syn), values = self.items[self.idx]
        row = [word, meaning, syn, values[i]]
        if self.auto_save:
            append_row(OUTPUT_FILE, row)
        else:
            self.results.append(row)
        self.new_choices += 1
        self.idx += 1
        self.root.after(300, self._advance)
        return True

    def reject(self):
        if self.transitioning:
            return
        self.transitioning = True
        (word, meaning, syn), _ = self.items[self.idx]
        row = [word, meaning, syn, ""]
        if self.auto_save:
            append_row(REJECTED_FILE, row)
        else:
            self.rejected.append(row)
        self.new_rejected += 1
        self.idx += 1
        self.root.after(150, self._advance)

    def skip(self):
        if self.transitioning:
            return
        self.transitioning = True
        self.idx += 1
        self.root.after(100, self._advance)

    def _advance(self):
        self.transitioning = False
        self.render()

    # -------- завершение --------
    def finish(self):
        if not self.auto_save:
            write_all(OUTPUT_FILE, self.results)
            write_all(REJECTED_FILE, self.rejected)

        msg = (f"Обработано в этой сессии:\n"
               f"  выбрано значений: {self.new_choices}\n"
               f"  отмечено «нет верного варианта»: {self.new_rejected}\n\n"
               f"Файлы:\n"
               f"  {OUTPUT_FILE}\n"
               f"  {REJECTED_FILE}")
        messagebox.showinfo("Готово", msg)
        self.root.destroy()


# ---------- запуск ----------
def main():
    path = sys.argv[1] if len(sys.argv) > 1 else INPUT_FILE
    try:
        all_items = load_data(path)
    except FileNotFoundError:
        root = tk.Tk(); root.withdraw()
        messagebox.showerror("Ошибка", f"Файл не найден: {path}")
        return

    total = len(all_items)
    processed = load_processed_keys()
    items = [it for it in all_items if it[0] not in processed]
    skipped = total - len(items)

    if not items:
        root = tk.Tk(); root.withdraw()
        messagebox.showinfo(
            "Готово",
            f"Все {total} записей уже обработаны.\n"
            f"Чтобы начать заново — удалите {OUTPUT_FILE} и {REJECTED_FILE}.")
        return

    root = tk.Tk()
    root.title("Выбор значений синонимов")
    root.geometry("950x700")
    root.minsize(650, 450)
    root.update_idletasks()
    App(root, items, AUTO_SAVE, skipped=skipped, total=total)
    root.mainloop()


if __name__ == "__main__":
    main()