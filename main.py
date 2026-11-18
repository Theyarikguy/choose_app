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


# ---------- загрузка исходных данных ----------
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


# ---------- работа с csv ----------
def read_csv_rows(path):
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        return []
    with open(path, encoding="utf-8", newline="") as f:
        reader = csv.reader(f, delimiter=";")
        next(reader, None)                       # пропустить заголовок
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
    """Все (слово, значение, синоним), которые уже есть в любом из итоговых файлов."""
    keys = set()
    for path in (OUTPUT_FILE, REJECTED_FILE):
        for row in read_csv_rows(path):
            if len(row) >= 3:
                keys.add((row[0], row[1], row[2]))
    return keys


# ---------- строка с галочкой ----------
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
        if self.callback(self.index):           # callback вернул True — выбор принят
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


# ---------- основное приложение ----------
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

        self.header = tk.Label(root, font=("Arial", 14, "bold"),
                               anchor="w", justify="left", bg="#eef")
        self.header.pack(fill="x", padx=10, pady=(10, 2))

        self.subheader = tk.Label(root, font=("Arial", 12),
                                  anchor="w", justify="left", bg="#eef")
        self.subheader.pack(fill="x", padx=10, pady=(0, 8))

        self.frame = tk.Frame(root)
        self.frame.pack(fill="both", expand=True, padx=10, pady=5)

        self.progress = tk.Label(root, font=("Arial", 10), fg="#666")
        self.progress.pack(fill="x", padx=10)

        btn = tk.Frame(root)
        btn.pack(fill="x", padx=10, pady=8)
        tk.Button(btn, text="Пропустить синоним", font=("Arial", 11),
                  command=self.skip).pack(side="left")
        tk.Button(btn, text="Нет верного варианта", font=("Arial", 11),
                  command=self.reject).pack(side="left", padx=6)
        tk.Button(btn, text="Завершить и сохранить", font=("Arial", 11),
                  command=self.finish).pack(side="right")

        root.bind("<Configure>", self.on_resize)
        self.render()

    # -------- масштабирование --------
    def on_resize(self, event):
        if event.widget is not self.root:
            return
        if self._resize_job:
            self.root.after_cancel(self._resize_job)
        self._resize_job = self.root.after(200, self.render)

    def compute_font_size(self):
        w = max(self.root.winfo_width(), 400)
        h = max(self.root.winfo_height(), 300)
        return max(12, min(36, min(w // 45, h // 22)))

    # -------- отрисовка --------
    def render(self):
        self._resize_job = None
        if self.transitioning:
            return
        for w in self.frame.winfo_children():
            w.destroy()
        if self.idx >= len(self.items):
            self.finish()
            return

        (word, meaning, syn), values = self.items[self.idx]
        fs = self.compute_font_size()
        width = max(self.root.winfo_width(), 400)

        self.header.config(text=f"{word}; {meaning}",
                           font=("Arial", max(11, int(fs * 0.9)), "bold"),
                           wraplength=width - 30)
        self.subheader.config(text=f"Синоним: {syn}",
                              font=("Arial", max(10, int(fs * 0.8))),
                              wraplength=width - 30)
        done = self.skipped + self.idx
        self.progress.config(
            text=(f"{done + 1} из {self.total}"
                  f"  (уже обработано ранее: {self.skipped})"),
            font=("Arial", max(9, fs // 2)))

        wraplength = max(200, width - fs * 4)
        for i, v in enumerate(values):
            row = OptionRow(self.frame, v, i, self.on_select, fs)
            row.pack(fill="x", anchor="w", pady=4, padx=4)
            row.set_wraplength(wraplength)

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

    def _advance(self):
        self.transitioning = False
        self.render()

    def skip(self):
        if self.transitioning:
            return
        self.transitioning = True
        self.idx += 1
        self.root.after(100, self._advance)

    # -------- завершение --------
    def finish(self):
        if not self.auto_save:
            write_all(OUTPUT_FILE, self.results)
            write_all(REJECTED_FILE, self.rejected)

        msg = (f"Обработано в этой сессии:\n"
               f"  выбрано значений: {self.new_choices}\n"
               f"  отмечено «нет верного варианта»: {self.new_rejected}\n\n"
               f"Файлы:\n"
               f"  {OUTPUT_FILE} — выбранные значения\n"
               f"  {REJECTED_FILE} — без верного варианта")
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
    root.geometry("900x600")
    root.minsize(500, 400)
    root.update_idletasks()
    App(root, items, AUTO_SAVE, skipped=skipped, total=total)
    root.mainloop()


if __name__ == "__main__":
    main()