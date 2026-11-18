import tkinter as tk
from tkinter import messagebox
import csv
import sys

INPUT_FILE  = "data.txt"
OUTPUT_FILE = "result.csv"
AUTO_SAVE   = True   # True — сохранять каждую запись сразу в файл


# ---------- загрузка ----------
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


# ---------- одна строка с галочкой ----------
class OptionRow(tk.Frame):
    def __init__(self, parent, text, index, callback, font_size):
        super().__init__(parent, bg="white", relief="groove", bd=2,
                         cursor="hand2")
        self.index    = index
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
        if not self.selected:
            self.selected = True
            self.box.config(text="☑")
            self.callback(self.index)

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
    def __init__(self, root, items, auto_save):
        self.root = root
        self.items = items
        self.idx = 0
        self.results = []
        self.auto_save = auto_save
        self.transitioning = False
        self._resize_job = None

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
        tk.Button(btn, text="Завершить и сохранить", font=("Arial", 11),
                  command=self.finish).pack(side="right")

        if self.auto_save:
            with open(OUTPUT_FILE, "w", encoding="utf-8", newline="") as f:
                csv.writer(f, delimiter=";").writerow(
                    ["слово", "значение_слова", "синоним", "значение_синонима"])

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
        self.progress.config(text=f"{self.idx + 1} из {len(self.items)}",
                             font=("Arial", max(9, fs // 2)))

        wraplength = max(200, width - fs * 4)
        for i, v in enumerate(values):
            row = OptionRow(self.frame, v, i, self.on_select, fs)
            row.pack(fill="x", anchor="w", pady=4, padx=4)
            row.set_wraplength(wraplength)

    # -------- выбор --------
    def on_select(self, i):
        if self.transitioning:
            return
        self.transitioning = True
        (word, meaning, syn), values = self.items[self.idx]
        row_data = [word, meaning, syn, values[i]]
        self.results.append(row_data)

        if self.auto_save:
            with open(OUTPUT_FILE, "a", encoding="utf-8", newline="") as f:
                csv.writer(f, delimiter=";").writerow(row_data)

        self.idx += 1
        self.root.after(300, self._advance)

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
        if not self.auto_save and self.results:
            with open(OUTPUT_FILE, "w", encoding="utf-8", newline="") as f:
                w = csv.writer(f, delimiter=";")
                w.writerow(["слово", "значение_слова", "синоним",
                            "значение_синонима"])
                for r in self.results:
                    w.writerow(r)

        extra = " (по ходу)" if self.auto_save else ""
        messagebox.showinfo("Готово",
                            f"Обработано записей: {len(self.results)}\n"
                            f"Файл: {OUTPUT_FILE}{extra}")
        self.root.destroy()


# ---------- запуск ----------
def main():
    path = sys.argv[1] if len(sys.argv) > 1 else INPUT_FILE
    try:
        items = load_data(path)
    except FileNotFoundError:
        root = tk.Tk(); root.withdraw()
        messagebox.showerror("Ошибка", f"Файл не найден: {path}")
        return

    if not items:
        root = tk.Tk(); root.withdraw()
        messagebox.showinfo("Пусто", "Нет данных для обработки.")
        return

    root = tk.Tk()
    root.title("Выбор значений синонимов")
    root.geometry("900x600")
    root.minsize(500, 400)
    root.update_idletasks()      # чтобы при первом render winfo_width() был реальный
    App(root, items, AUTO_SAVE)
    root.mainloop()


if __name__ == "__main__":
    main()