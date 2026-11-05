# -*- coding: utf-8 -*-
"""
MecatroniCar - Interface Gráfica Nativa Desktop (CustomTkinter)
Uma opção 100% nativa em Python caso prefira não utilizar o navegador.
"""
import os
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk

import config
import cache
import parser

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")

class OficinaApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("MecatroniCar - Histórico de Visitas e Serviços")
        self.geometry("1100x750")
        self.minsize(900, 600)

        self.cfg = config.load_config(BASE_DIR)
        self.db_path = cache.get_db_path(BASE_DIR)

        self.current_folder = self.cfg.get("spreadsheet_folder", "")
        self.all_cars = []

        self.create_widgets()
        self.load_initial_data()

    def create_widgets(self):
        # Top Frame: Folder selector and stats
        self.top_frame = ctk.CTkFrame(self, corner_radius=10)
        self.top_frame.pack(fill="x", padx=15, pady=(15, 10))

        self.folder_label = ctk.CTkLabel(
            self.top_frame, 
            text=f"📁 Pasta: {self.current_folder or 'Nenhuma pasta selecionada'}", 
            font=ctk.CTkFont(size=12, weight="bold"),
            anchor="w"
        )
        self.folder_label.pack(side="left", padx=15, pady=10, fill="x", expand=True)

        self.btn_change_folder = ctk.CTkButton(
            self.top_frame, 
            text="📂 Alterar Pasta", 
            width=120, 
            command=self.on_change_folder
        )
        self.btn_change_folder.pack(side="right", padx=(5, 15), pady=10)

        self.btn_reindex = ctk.CTkButton(
            self.top_frame, 
            text="🔄 Atualizar Lista", 
            width=120, 
            fg_color="#334155", 
            command=self.on_reindex
        )
        self.btn_reindex.pack(side="right", padx=5, pady=10)

        # Search Frame
        self.search_frame = ctk.CTkFrame(self, corner_radius=10)
        self.search_frame.pack(fill="x", padx=15, pady=(0, 10))

        self.search_entry = ctk.CTkEntry(
            self.search_frame, 
            placeholder_text="🔍 Digite a placa (ex: FNB 1A77) ou nome do cliente (ex: Danilo, Natanael)...",
            height=40,
            font=ctk.CTkFont(size=14)
        )
        self.search_entry.pack(side="left", fill="x", expand=True, padx=15, pady=12)
        self.search_entry.bind("<KeyRelease>", self.on_search_key)

        self.btn_clear = ctk.CTkButton(
            self.search_frame, 
            text="✕ Limpar", 
            width=80, 
            fg_color="#64748b",
            command=self.on_clear_search
        )
        self.btn_clear.pack(side="right", padx=15, pady=12)

        # Main Content Panes (Split: Left list of cars, Right detail of visits)
        self.paned_frame = ctk.CTkFrame(self, corner_radius=10)
        self.paned_frame.pack(fill="both", expand=True, padx=15, pady=(0, 15))

        # Left: Cars list
        self.left_frame = ctk.CTkFrame(self.paned_frame, width=320, corner_radius=8)
        self.left_frame.pack(side="left", fill="y", padx=10, pady=10)
        self.left_frame.pack_propagate(False)

        self.left_title = ctk.CTkLabel(
            self.left_frame, 
            text="Veículos Cadastrados", 
            font=ctk.CTkFont(size=14, weight="bold")
        )
        self.left_title.pack(padx=10, pady=(10, 5), anchor="w")

        self.cars_scroll = ctk.CTkScrollableFrame(self.left_frame)
        self.cars_scroll.pack(fill="both", expand=True, padx=5, pady=5)

        # Right: Vehicle visits details
        self.right_frame = ctk.CTkFrame(self.paned_frame, corner_radius=8)
        self.right_frame.pack(side="right", fill="both", expand=True, padx=(0, 10), pady=10)

        # Right Header Banner
        self.banner_frame = ctk.CTkFrame(self.right_frame, fg_color="#f1f5f9", corner_radius=8)
        self.banner_frame.pack(fill="x", padx=10, pady=10)

        self.banner_plate = ctk.CTkLabel(
            self.banner_frame, 
            text="Selecione um veículo", 
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color="#1e293b"
        )
        self.banner_plate.pack(anchor="w", padx=15, pady=(10, 2))

        self.banner_info = ctk.CTkLabel(
            self.banner_frame, 
            text="Use a busca acima ou clique em um veículo ao lado para ver o histórico de serviços.",
            font=ctk.CTkFont(size=12),
            text_color="#64748b"
        )
        self.banner_info.pack(anchor="w", padx=15, pady=(0, 10))

        # Visits scroll area
        self.visits_scroll = ctk.CTkScrollableFrame(self.right_frame)
        self.visits_scroll.pack(fill="both", expand=True, padx=10, pady=(0, 10))

    def load_initial_data(self):
        if self.current_folder and os.path.isdir(self.current_folder):
            threading.Thread(target=self.index_and_refresh, daemon=True).start()
        else:
            self.refresh_cars_list([])

    def index_and_refresh(self):
        cache.scan_and_index_folder(self.current_folder, self.db_path)
        cars = cache.get_all_cars(self.db_path)
        self.after(0, lambda: self.refresh_cars_list(cars))

    def refresh_cars_list(self, cars):
        self.all_cars = cars
        for widget in self.cars_scroll.winfo_children():
            widget.destroy()

        if not cars:
            lbl = ctk.CTkLabel(self.cars_scroll, text="Nenhum carro encontrado.", text_color="#94a3b8")
            lbl.pack(pady=20)
            return

        for car in cars:
            btn = ctk.CTkButton(
                self.cars_scroll,
                text=f"{car.get('plate_display', car.get('plate_clean'))}\n{car.get('car_model', '')} ({car.get('visit_count', 1)} vis.)",
                font=ctk.CTkFont(size=12, weight="bold"),
                fg_color="#f8fafc",
                text_color="#1e293b",
                hover_color="#e2e8f0",
                anchor="w",
                height=50,
                command=lambda p=car.get('plate_clean'): self.show_car_history(p)
            )
            btn.pack(fill="x", padx=5, pady=4)

    def on_change_folder(self):
        folder = filedialog.askdirectory(
            initialdir=self.current_folder or os.path.expanduser("~"),
            title="Selecione a pasta das planilhas da oficina"
        )
        if folder:
            self.current_folder = os.path.normpath(folder)
            self.cfg["spreadsheet_folder"] = self.current_folder
            config.save_config(self.cfg, BASE_DIR)
            self.folder_label.configure(text=f"📁 Pasta: {self.current_folder}")
            threading.Thread(target=self.index_and_refresh, daemon=True).start()

    def on_reindex(self):
        if not self.current_folder or not os.path.isdir(self.current_folder):
            messagebox.showwarning("Aviso", "Selecione uma pasta válida primeiro.")
            return
        threading.Thread(target=self.index_and_refresh, daemon=True).start()

    def on_search_key(self, event=None):
        q = self.search_entry.get().strip()
        if not q:
            self.refresh_cars_list(self.all_cars)
            return

        results = cache.search_files(q, self.db_path)
        # Unique plates
        seen = set()
        matched_cars = []
        for r in results:
            p = r.get("plate_clean")
            if p and p not in seen:
                seen.add(p)
                matched_cars.append({
                    "plate_clean": p,
                    "plate_display": r.get("plate_display", p),
                    "car_model": r.get("car_model", ""),
                    "visit_count": 1
                })
        self.refresh_cars_list(matched_cars)
        if len(matched_cars) == 1:
            self.show_car_history(matched_cars[0]["plate_clean"])

    def on_clear_search(self):
        self.search_entry.delete(0, "end")
        self.refresh_cars_list(self.all_cars)

    def show_car_history(self, plate):
        visits = cache.get_car_history(plate, self.db_path)
        for widget in self.visits_scroll.winfo_children():
            widget.destroy()

        if not visits:
            return

        latest = visits[0]
        details = latest.get("details", {})

        self.banner_plate.configure(text=f"🚗 {latest.get('plate_display', plate)}")
        info_str = f"Cliente: {latest.get('client_name', 'N/I')}  |  Modelo: {latest.get('car_model', 'N/I')}  |  Ano: {latest.get('car_year', 'N/I')}  |  Cor: {latest.get('car_color', 'N/I')}"
        if details.get("phone"):
            info_str += f"  |  Celular: {details.get('phone')}"
        self.banner_info.configure(text=info_str)

        # Render visits
        for visit in visits:
            v_frame = ctk.CTkFrame(self.visits_scroll, fg_color="#ffffff", corner_radius=8, border_width=1, border_color="#e2e8f0")
            v_frame.pack(fill="x", padx=5, pady=8)

            # Header of visit
            v_head = ctk.CTkFrame(v_frame, fg_color="#f8fafc", corner_radius=6)
            v_head.pack(fill="x", padx=8, pady=(8, 4))

            date_str = visit.get("entry_date") or "Data N/I"
            km_str = f"{visit.get('odometer', '')} km" if visit.get('odometer') else "KM N/I"
            v_num = f"Visita #{visit.get('visit_num')}" if visit.get('visit_num') else ""

            lbl_v = ctk.CTkLabel(
                v_head, 
                text=f"📅 {date_str}   ⏱️ {km_str}   {v_num}", 
                font=ctk.CTkFont(size=13, weight="bold"),
                text_color="#1e293b"
            )
            lbl_v.pack(side="left", padx=10, pady=6)

            btn_open_excel = ctk.CTkButton(
                v_head,
                text="📂 Abrir no Excel",
                width=110,
                height=26,
                fg_color="#15803d",
                hover_color="#166534",
                font=ctk.CTkFont(size=11, weight="bold"),
                command=lambda fp=visit.get("file_path"): self.open_excel_file(fp)
            )
            btn_open_excel.pack(side="right", padx=10, pady=6)

            # Complaint
            if visit.get("complaint"):
                c_lbl = ctk.CTkLabel(
                    v_frame, 
                    text=f"⚠️ Queixa: {visit.get('complaint')}", 
                    font=ctk.CTkFont(size=12, weight="bold"),
                    text_color="#92400e",
                    anchor="w"
                )
                c_lbl.pack(fill="x", padx=12, pady=(2, 4))

            # Items
            items = visit.get("details", {}).get("items", [])
            for it in items:
                it_frame = ctk.CTkFrame(
                    v_frame, 
                    fg_color=it.get("color") or "#ffffff", 
                    corner_radius=4,
                    border_width=0
                )
                it_frame.pack(fill="x", padx=10, pady=2)

                text_col = it.get("text_color") or "#1e293b"

                desc_text = f"• [{it.get('section', 'Item')}] {it.get('description', '')}"
                if it.get("quantity"):
                    desc_text += f" (Qtd: {it.get('quantity')})"
                if it.get("total_price") and it.get("total_price") != "R$ 0,00":
                    desc_text += f" - Total: {it.get('total_price')}"

                it_lbl = ctk.CTkLabel(
                    it_frame,
                    text=desc_text,
                    font=ctk.CTkFont(size=12),
                    text_color=text_col,
                    anchor="w"
                )
                it_lbl.pack(side="left", padx=8, pady=3, fill="x", expand=True)

                if it.get("comment"):
                    btn_note = ctk.CTkButton(
                        it_frame,
                        text="📝 Ver Nota",
                        width=70,
                        height=22,
                        fg_color="#ef4444",
                        hover_color="#dc2626",
                        font=ctk.CTkFont(size=10, weight="bold"),
                        command=lambda n=it.get("comment"), d=it.get("description"): self.show_note_dialog(d, n)
                    )
                    btn_note.pack(side="right", padx=6, pady=3)

            # Totals
            sub = visit.get("details", {}).get("subtotal")
            tot = visit.get("details", {}).get("total")
            if (sub and sub != "R$ 0,00") or (tot and tot != "R$ 0,00"):
                f_lbl = ctk.CTkLabel(
                    v_frame,
                    text=f"Total da Visita: {tot or sub}",
                    font=ctk.CTkFont(size=12, weight="bold"),
                    text_color="#0f172a",
                    anchor="e"
                )
                f_lbl.pack(fill="x", padx=12, pady=(4, 8))

    def show_note_dialog(self, title, comment):
        dlg = ctk.CTkToplevel(self)
        dlg.title("Observação / Nota Técnica")
        dlg.geometry("600x450")
        dlg.attributes("-topmost", True)

        lbl = ctk.CTkLabel(dlg, text=f"Item: {title}", font=ctk.CTkFont(size=14, weight="bold"))
        lbl.pack(padx=15, pady=(15, 5), anchor="w")

        txt = ctk.CTkTextbox(dlg, font=ctk.CTkFont(family="Consolas", size=12))
        txt.pack(fill="both", expand=True, padx=15, pady=10)
        txt.insert("1.0", comment)
        txt.configure(state="disabled")

        btn = ctk.CTkButton(dlg, text="Fechar", command=dlg.destroy)
        btn.pack(pady=(0, 15))

    def open_excel_file(self, fpath):
        if fpath and os.path.exists(fpath):
            try:
                os.startfile(fpath)
            except Exception as e:
                messagebox.showerror("Erro", f"Não foi possível abrir o arquivo:\n{e}")
        else:
            messagebox.showerror("Erro", "Arquivo não encontrado no disco.")

def main():
    app = OficinaApp()
    app.mainloop()

if __name__ == "__main__":
    main()
