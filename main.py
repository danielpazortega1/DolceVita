import customtkinter as ctk
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import sqlite3
import datetime
import os
import webbrowser

# --- CONFIGURACIÓN VISUAL ---
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

# Fuentes globales
FONT_TITLE = ("Roboto", 32, "bold")
FONT_HEADER = ("Roboto", 24, "bold")
FONT_TEXT = ("Roboto", 16)
FONT_BTN = ("Roboto", 16, "bold")
ROW_HEIGHT = 40

class DatabaseManager:
    def __init__(self, db_name="restaurante.db"):
        self.db_name = db_name
        self.init_db()

    def run_query(self, query, parameters=()):
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            try:
                result = cursor.execute(query, parameters)
                conn.commit()
                return result
            except sqlite3.Error as e:
                print(f"Error de BD: {e}")
                return None

    def init_db(self):
        # Crear Tablas
        self.run_query("""
            CREATE TABLE IF NOT EXISTS usuarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL UNIQUE,
                password TEXT NOT NULL,
                rol TEXT NOT NULL
            )
        """)
        self.run_query("""
            CREATE TABLE IF NOT EXISTS productos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL UNIQUE,
                precio_base REAL NOT NULL
            )
        """)
        self.run_query("""
            CREATE TABLE IF NOT EXISTS ventas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                correlativo INTEGER NOT NULL,
                fecha_hora TEXT NOT NULL,
                total REAL NOT NULL,
                usuario_responsable TEXT NOT NULL
            )
        """)
        self.run_query("""
            CREATE TABLE IF NOT EXISTS detalle_ventas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                id_venta INTEGER NOT NULL,
                producto TEXT NOT NULL,
                cantidad INTEGER NOT NULL,
                precio_unitario_aplicado REAL NOT NULL,
                subtotal REAL NOT NULL,
                FOREIGN KEY(id_venta) REFERENCES ventas(id)
            )
        """)
        
        # DATOS SEMILLA (Usuarios Actualizados)
        # Borramos admin previo para asegurar
        self.run_query("DELETE FROM usuarios WHERE rol='admin'") 
        
        # Lista de usuarios a crear
        # Lista de usuarios de prueba para GitHub
        usuarios_iniciales = [
            ("pruebagerente", "gerente123", "admin"),
            ("pruebamesero", "mesero123", "mesero")
        ]
        for u, p, r in usuarios_iniciales:
            self.run_query("INSERT OR IGNORE INTO usuarios (nombre, password, rol) VALUES (?, ?, ?)", (u, p, r))
        
        # Productos iniciales
        if not self.run_query("SELECT * FROM productos").fetchone():
            items = [("Cafe", 5.00), ("Pastel Chocolate", 20.00), 
                     ("Desayuno Chapin", 45.00), ("Licuado", 15.00), ("Coca Cola", 15.00)]
            for nombre, precio in items:
                self.run_query("INSERT OR IGNORE INTO productos (nombre, precio_base) VALUES (?, ?)", (nombre, precio))

    def login(self, user, pwd):
        res = self.run_query("SELECT nombre, rol FROM usuarios WHERE nombre=? AND password=?", (user, pwd))
        return res.fetchone()

    def get_products(self):
        return self.run_query("SELECT id, nombre, precio_base FROM productos").fetchall()

    def add_product(self, nombre, precio):
        try:
            self.run_query("INSERT INTO productos (nombre, precio_base) VALUES (?, ?)", (nombre, precio))
            return True
        except:
            return False

    def delete_product(self, id_prod):
        self.run_query("DELETE FROM productos WHERE id=?", (id_prod,))

    def get_next_correlative(self):
        res = self.run_query("SELECT MAX(correlativo) FROM ventas").fetchone()
        if res[0] is None: return 1
        return res[0] + 1

    # --- FUNCIONES DE EDICIÓN ---
    def get_sale_by_correlative(self, correlativo):
        venta = self.run_query("SELECT id, total, usuario_responsable, fecha_hora FROM ventas WHERE correlativo=?", (correlativo,)).fetchone()
        if not venta: return None
        id_venta = venta[0]
        detalles = self.run_query("SELECT producto, cantidad, precio_unitario_aplicado, subtotal FROM detalle_ventas WHERE id_venta=?", (id_venta,)).fetchall()
        items_list = [list(d) for d in detalles]
        return (id_venta, venta[1], venta[2], venta[3], items_list)

    def update_sale(self, id_venta, total, usuario, items):
        self.run_query("UPDATE ventas SET total=?, usuario_responsable=? WHERE id=?", (total, usuario, id_venta))
        self.run_query("DELETE FROM detalle_ventas WHERE id_venta=?", (id_venta,))
        for item in items:
            self.run_query("""
                INSERT INTO detalle_ventas (id_venta, producto, cantidad, precio_unitario_aplicado, subtotal)
                VALUES (?, ?, ?, ?, ?)
            """, (id_venta, item[0], item[1], item[2], item[3]))
        return True

    def registrar_venta(self, correlativo, total, usuario, items):
        fecha = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor = self.run_query("INSERT INTO ventas (correlativo, fecha_hora, total, usuario_responsable) VALUES (?, ?, ?, ?)",
                                (correlativo, fecha, total, usuario))
        id_venta = cursor.lastrowid
        for item in items:
            self.run_query("""
                INSERT INTO detalle_ventas (id_venta, producto, cantidad, precio_unitario_aplicado, subtotal)
                VALUES (?, ?, ?, ?, ?)
            """, (id_venta, item[0], item[1], item[2], item[3]))
        return True

    def delete_sale(self, correlativo):
        res = self.run_query("SELECT id FROM ventas WHERE correlativo=?", (correlativo,)).fetchone()
        if res:
            id_venta = res[0]
            self.run_query("DELETE FROM detalle_ventas WHERE id_venta=?", (id_venta,))
            self.run_query("DELETE FROM ventas WHERE id=?", (id_venta,))
            return True
        return False

    def get_ventas_reporte(self, filtro_hoy=False):
        query = "SELECT correlativo, fecha_hora, usuario_responsable, total FROM ventas"
        if filtro_hoy:
            hoy = datetime.datetime.now().strftime("%Y-%m-%d")
            query += f" WHERE substr(fecha_hora, 1, 10) = '{hoy}'"
        query += " ORDER BY correlativo DESC"
        return self.run_query(query).fetchall()


class LoginFrame(ctk.CTkFrame):
    def __init__(self, master, login_callback):
        super().__init__(master)
        self.login_callback = login_callback
        self.place(relx=0.5, rely=0.5, anchor="center")

        ctk.CTkLabel(self, text="DOLCE VITA", font=FONT_TITLE).pack(pady=30, padx=60)
        self.user_entry = ctk.CTkEntry(self, placeholder_text="Usuario", font=FONT_TEXT, height=40, width=300)
        self.user_entry.pack(pady=15)
        self.pass_entry = ctk.CTkEntry(self, placeholder_text="Contraseña", show="*", font=FONT_TEXT, height=40, width=300)
        self.pass_entry.pack(pady=15)
        ctk.CTkButton(self, text="INGRESAR", command=self.attempt_login, font=FONT_BTN, height=50, width=300).pack(pady=30)
        ctk.CTkLabel(self, text="", text_color="gray").pack(pady=10)

    def attempt_login(self):
        u = self.user_entry.get()
        p = self.pass_entry.get()
        self.login_callback(u, p)


class SalesFrame(ctk.CTkFrame):
    def __init__(self, master, user_info, db: DatabaseManager, logout_cb):
        super().__init__(master)
        self.pack(fill="both", expand=True, padx=10, pady=10)
        self.user_info = user_info
        self.db = db
        self.logout_cb = logout_cb
        self.cart_items = [] 
        
        self.is_editing = False
        self.editing_id = None
        self.editing_correlative = None

        # --- Header ---
        header = ctk.CTkFrame(self, height=60)
        header.pack(fill="x", pady=5)
        
        # Info Usuario y Selector Mesero
        ctk.CTkLabel(header, text="Atiende:", font=FONT_TEXT).pack(side="left", padx=(20, 5))
        
        # LISTA ACTUALIZADA DE MESEROS
        lista_meseros = ["ELDER", "ANA", "ALEJANDRA", "VARIOS"]
        
        self.waiter_var = tk.StringVar(value="Seleccionar Mesero")
        self.combo_waiter = ctk.CTkComboBox(header, values=lista_meseros, variable=self.waiter_var,
                                            state="readonly", font=FONT_BTN, width=200, height=35)
        self.combo_waiter.pack(side="left", padx=5)

        # Botón Modificar Ticket
        ctk.CTkButton(header, text="✏️ Modificar", fg_color="#FBC02D", text_color="black", hover_color="#F9A825",
                      font=FONT_BTN, width=120, command=self.start_edit_ticket).pack(side="left", padx=20)
        
        self.lbl_next_correlative = ctk.CTkLabel(header, text="Ticket #: ...", font=("Roboto", 20, "bold"), text_color="#00E676")
        self.lbl_next_correlative.pack(side="left", padx=30)

        ctk.CTkButton(header, text="Cerrar Sesión", width=120, height=40, fg_color="#D32F2F", font=FONT_BTN, command=logout_cb).pack(side="right", padx=20)

        # --- Layout Principal ---
        content = ctk.CTkFrame(self)
        content.pack(fill="both", expand=True)
        content.columnconfigure(0, weight=1) 
        content.columnconfigure(1, weight=3) 

        # Panel Izquierdo (Inputs)
        left_panel = ctk.CTkFrame(content)
        left_panel.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

        self.lbl_mode = ctk.CTkLabel(left_panel, text="Nuevo Pedido", font=FONT_HEADER)
        self.lbl_mode.pack(pady=20)

        self.products_raw = self.db.get_products()
        self.prod_names = [p[1] for p in self.products_raw]
        
        ctk.CTkLabel(left_panel, text="Buscar (Nombre o ID):", font=FONT_TEXT).pack(pady=(10,0), anchor="w", padx=20)
        self.cb_products = ctk.CTkComboBox(left_panel, values=self.prod_names, command=self.on_prod_select, 
                                           font=FONT_TEXT, height=40, width=250)
        self.cb_products.pack(pady=5, padx=20)
        self.cb_products.set("") 
        self.cb_products.bind("<Return>", self.on_smart_search)

        self.var_price = tk.DoubleVar()
        self.var_qty = tk.IntVar(value=1)

        ctk.CTkLabel(left_panel, text="Precio (Q):", font=FONT_TEXT).pack(pady=(15,0), anchor="w", padx=20)
        self.entry_price = ctk.CTkEntry(left_panel, textvariable=self.var_price, font=FONT_TEXT, height=40)
        self.entry_price.pack(pady=5, padx=20, fill="x")

        ctk.CTkLabel(left_panel, text="Cantidad:", font=FONT_TEXT).pack(pady=(15,0), anchor="w", padx=20)
        self.entry_qty = ctk.CTkEntry(left_panel, textvariable=self.var_qty, font=FONT_TEXT, height=40)
        self.entry_qty.pack(pady=5, padx=20, fill="x")
        self.entry_qty.bind("<Return>", lambda event: self.add_to_cart())

        ctk.CTkButton(left_panel, text="AGREGAR (+)", command=self.add_to_cart, font=FONT_BTN, height=50).pack(pady=30, padx=20, fill="x")
        
        self.btn_cancel_edit = ctk.CTkButton(left_panel, text="Cancelar Edición", fg_color="gray", command=self.cancel_edit_mode)

        # Panel Derecho (Tabla)
        right_panel = ctk.CTkFrame(content)
        right_panel.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview", background="#2b2b2b", fieldbackground="#2b2b2b", foreground="white", 
                        font=("Roboto", 14), rowheight=ROW_HEIGHT)
        style.configure("Treeview.Heading", background="#3a3a3a", foreground="white", relief="flat", font=("Roboto", 14, "bold"))
        style.map("Treeview", background=[("selected", "#1f538d")])

        self.tree = ttk.Treeview(right_panel, columns=("Prod", "Cant", "Precio", "Subtotal"), show="headings", height=15)
        self.tree.heading("Prod", text="Producto")
        self.tree.heading("Cant", text="Cant")
        self.tree.heading("Precio", text="Precio")
        self.tree.heading("Subtotal", text="Subtotal")
        
        self.tree.column("Prod", width=300)
        self.tree.column("Cant", width=100, anchor="center")
        self.tree.column("Precio", width=150, anchor="e")
        self.tree.column("Subtotal", width=150, anchor="e")
        
        self.tree.pack(fill="both", expand=True, padx=5, pady=5)
        self.tree.bind("<Double-1>", self.delete_cart_item)

        # Footer con DOS BOTONES
        footer = ctk.CTkFrame(right_panel, height=100)
        footer.pack(fill="x", pady=5)
        
        self.lbl_total = ctk.CTkLabel(footer, text="TOTAL: Q0.00", font=("Roboto", 40, "bold"), text_color="#00E676")
        self.lbl_total.pack(side="left", padx=30)
        
        btn_frame = ctk.CTkFrame(footer, fg_color="transparent")
        btn_frame.pack(side="right", padx=20)

        ctk.CTkButton(btn_frame, text="SOLO GUARDAR\n(Sin Imprimir)", height=60, width=150, font=("Roboto", 14, "bold"), 
                      fg_color="#1976D2", hover_color="#1565C0", 
                      command=lambda: self.finish_sale(print_ticket=False)).pack(side="left", padx=10)

        self.btn_finish = ctk.CTkButton(btn_frame, text="COBRAR E\nIMPRIMIR", height=60, width=180, font=("Roboto", 16, "bold"), 
                      fg_color="#00C853", hover_color="#009624", 
                      command=lambda: self.finish_sale(print_ticket=True))
        self.btn_finish.pack(side="left", padx=10)

        self.update_next_correlative()

    def update_next_correlative(self):
        if self.is_editing:
            self.lbl_next_correlative.configure(text=f"Editando: #{self.editing_correlative}", text_color="#FBC02D")
        else:
            siguiente = self.db.get_next_correlative()
            self.lbl_next_correlative.configure(text=f"Siguiente Ticket: #{siguiente}", text_color="#00E676")

    def on_prod_select(self, choice):
        for p in self.products_raw:
            if p[1] == choice:
                self.var_price.set(p[2])
                break

    def on_smart_search(self, event):
        inp = self.cb_products.get().strip()
        if not inp: return
        found_product = None
        if inp.isdigit():
            search_id = int(inp)
            for p in self.products_raw:
                if p[0] == search_id:
                    found_product = p
                    break
        else:
            for p in self.products_raw:
                if p[1].lower().startswith(inp.lower()):
                    found_product = p
                    break
        if found_product:
            self.cb_products.set(found_product[1])
            self.var_price.set(found_product[2])
            self.entry_qty.focus_set()
            self.entry_qty.select_range(0, tk.END)
        else:
            messagebox.showwarning("No encontrado", f"No existe producto con ID o Nombre: '{inp}'")

    def add_to_cart(self):
        prod = self.cb_products.get()
        if prod not in self.prod_names:
            self.on_smart_search(None)
            prod = self.cb_products.get()
            if prod not in self.prod_names: return

        try:
            qty = self.var_qty.get()
            price = self.var_price.get()
        except:
            messagebox.showerror("Error", "Cantidad o Precio inválidos")
            return

        if qty <= 0: return

        found_in_cart = False
        for index, item in enumerate(self.cart_items):
            if item[0] == prod and item[2] == price:
                new_qty = item[1] + qty
                new_sub = round(new_qty * price, 2)
                self.cart_items[index] = [prod, new_qty, price, new_sub]
                found_in_cart = True
                break
        
        if not found_in_cart:
            subtotal = round(qty * price, 2)
            self.cart_items.append([prod, qty, price, subtotal])

        self.refresh_cart()
        self.cb_products.set("")
        self.var_qty.set(1)
        self.cb_products.focus_set()

    def delete_cart_item(self, event):
        sel = self.tree.selection()
        if sel:
            idx = self.tree.index(sel[0])
            del self.cart_items[idx]
            self.refresh_cart()

    def refresh_cart(self):
        for i in self.tree.get_children():
            self.tree.delete(i)
        total_gral = 0
        for item in self.cart_items:
            self.tree.insert("", "end", values=item)
            total_gral += item[3]
        self.lbl_total.configure(text=f"TOTAL: Q{total_gral:.2f}")

    # --- LÓGICA DE EDICIÓN ---
    def start_edit_ticket(self):
        corr_str = simpledialog.askstring("Modificar Ticket", "Ingrese el Número de Ticket (Correlativo):")
        if not corr_str or not corr_str.isdigit(): return
        corr = int(corr_str)
        data = self.db.get_sale_by_correlative(corr)
        if not data:
            messagebox.showerror("No encontrado", f"El ticket #{corr} no existe.")
            return

        self.editing_id = data[0]
        usuario_responsable = data[2]
        self.cart_items = data[4]
        
        self.is_editing = True
        self.editing_correlative = corr
        
        self.lbl_mode.configure(text=f"EDITANDO TICKET #{corr}", text_color="#FBC02D")
        self.btn_finish.configure(text="GUARDAR CAMBIOS", fg_color="#FBC02D", hover_color="#F9A825", text_color="black")
        self.btn_cancel_edit.pack(pady=10, fill="x")
        self.update_next_correlative()
        
        # Selección de mesero en edición
        lista_meseros = ["ELDER", "ANA", "ALEJANDRA", "VARIOS"]
        if usuario_responsable in lista_meseros:
            self.waiter_var.set(usuario_responsable)
        else:
            self.waiter_var.set("Seleccionar Mesero")
            
        self.refresh_cart()
        messagebox.showinfo("Modo Edición", f"Ticket #{corr} cargado.")

    def cancel_edit_mode(self):
        self.is_editing = False
        self.editing_id = None
        self.editing_correlative = None
        self.cart_items = []
        self.refresh_cart()
        
        self.lbl_mode.configure(text="Nuevo Pedido", text_color=["#DCE4EE", "#DCE4EE"])
        self.btn_finish.configure(text="COBRAR E\nIMPRIMIR", fg_color="#00C853", hover_color="#009624", text_color="white")
        self.btn_cancel_edit.pack_forget()
        self.waiter_var.set("Seleccionar Mesero")
        self.update_next_correlative()

    def finish_sale(self, print_ticket=True):
        mesero_actual = self.waiter_var.get()
        if mesero_actual == "Seleccionar Mesero":
            messagebox.showwarning("Atención", "Por favor selecciona quién atendió la mesa.")
            return

        if not self.cart_items:
            messagebox.showwarning("Vacío", "No hay items en el carrito")
            return
        
        total = sum(item[3] for item in self.cart_items)
        
        if self.is_editing:
            if self.db.update_sale(self.editing_id, total, mesero_actual, self.cart_items):
                messagebox.showinfo("Actualizado", f"Ticket #{self.editing_correlative} modificado correctamente.")
                if print_ticket:
                    self.generate_html_ticket(self.editing_correlative, total, mesero_actual, reprint=True)
                self.cancel_edit_mode() 
            else:
                messagebox.showerror("Error", "No se pudo actualizar la venta.")
        else:
            correlativo = self.db.get_next_correlative()
            if self.db.registrar_venta(correlativo, total, mesero_actual, self.cart_items):
                if print_ticket:
                    self.generate_html_ticket(correlativo, total, mesero_actual)
                else:
                    messagebox.showinfo("Guardado", f"Venta #{correlativo} guardada (Sin imprimir).")
                
                self.cart_items = []
                self.refresh_cart()
                self.update_next_correlative()
            else:
                messagebox.showerror("Error", "No se pudo guardar la venta en BD")

    def generate_html_ticket(self, correlative, total, mesero_nombre, reprint=False):
        filename = f"ticket_{correlative}.html"
        file_path = os.path.abspath(filename)
        titulo = "TICKET MODIFICADO" if reprint else "DOLCE VITA"
        
        # --- AQUÍ ESTÁ EL ARREGLO ---
        # Borré "margin: 0;" y puse "margin-left: 8mm;"
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ 
                    font-family: 'Arial', sans-serif; 
                    width: 44mm;      /* Ancho para que quepa bien */
                    margin-left: 8mm; /* ESTO ES LO QUE EMPUJA EL TEXTO A LA DERECHA */
                    padding: 0; 
                    background-color: white;
                    font-weight: bold; 
                    font-size: 13px;
                }}
                h2 {{ text-align: center; margin: 0; font-size: 16px; margin-bottom: 5px; }}
                .info {{ text-align: center; font-size: 12px; margin-bottom: 8px; }}
                table {{ width: 100%; border-collapse: collapse; }}
                th {{ border-bottom: 2px solid black; text-align: left; font-size: 12px; }}
                td {{ padding: 3px 0; font-size: 12px; }}
                .num {{ text-align: right; }}
                .total {{ 
                    border-top: 2px solid black; 
                    font-weight: 900; 
                    font-size: 16px; 
                    margin-top: 5px; 
                    text-align: right; 
                }}
                .footer {{ text-align: center; margin-top: 15px; font-size: 11px; }}
                
                @media print {{
                    @page {{ margin: 0; size: auto; }}
                    body {{ margin-left: 8mm; }} /* Forzar margen al imprimir */
                }}
            </style>
        </head>
        <body>
            <br>
            <h2>{titulo}</h2>
            <div class="info">
                #{correlative} <br>
                {datetime.datetime.now().strftime("%d/%m/%y %H:%M")}<br>
                Atiende: {mesero_nombre.upper()}
            </div>
            <table>
                <tr><th width="50%">PROD</th><th width="10%">C.</th><th class="num">TOT</th></tr>
        """
        
        for item in self.cart_items:
            # Nombre cortado a 10 caracteres
            nombre_corto = (item[0][:10] + '.') if len(item[0]) > 10 else item[0]
            html_content += f"<tr><td>{nombre_corto}</td><td style='text-align:center'>{item[1]}</td><td class='num'>Q{item[3]:.2f}</td></tr>"

        html_content += f"""
            </table>
            <div class="total">TOTAL: Q{total:.2f}</div>
            <div class="footer">¡GRACIAS POR SU VISITA!</div>
            <br>
            <div style="text-align: center;">.</div>
            <script>window.onload = function() {{ window.print(); }}</script>
        </body>
        </html>
        """
        
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        webbrowser.open_new_tab(file_path)


class ManagerFrame(ctk.CTkFrame):
    def __init__(self, master, db: DatabaseManager, logout_cb):
        super().__init__(master)
        self.pack(fill="both", expand=True)
        self.db = db
        
        header = ctk.CTkFrame(self, height=60)
        header.pack(fill="x")
        ctk.CTkLabel(header, text=f"ADMINISTRACIÓN (Carlos)", font=FONT_HEADER).pack(side="left", padx=20)
        ctk.CTkButton(header, text="Cerrar Sesión", fg_color="#D32F2F", width=150, command=logout_cb).pack(side="right", padx=20)

        self.tabs = ctk.CTkTabview(self)
        self.tabs.pack(fill="both", expand=True, padx=20, pady=20)
        
        self.tab_prods = self.tabs.add("Productos")
        self.tab_reports = self.tabs.add("Reportes")
        self.setup_products_tab()
        self.setup_reports_tab()

    def setup_products_tab(self):
        form_frame = ctk.CTkFrame(self.tab_prods)
        form_frame.pack(fill="x", pady=10, padx=10)
        
        self.entry_p_name = ctk.CTkEntry(form_frame, placeholder_text="Nombre Producto", font=FONT_TEXT, width=200)
        self.entry_p_name.pack(side="left", padx=10)
        self.entry_p_price = ctk.CTkEntry(form_frame, placeholder_text="Precio (Q)", font=FONT_TEXT, width=100)
        self.entry_p_price.pack(side="left", padx=10)
        
        ctk.CTkButton(form_frame, text="Crear Producto", command=self.create_prod, font=FONT_BTN).pack(side="left", padx=10)
        ctk.CTkButton(form_frame, text="Eliminar Seleccionado", fg_color="#D32F2F", command=self.delete_prod, font=FONT_BTN).pack(side="right", padx=10)
        
        self.tree_prod = ttk.Treeview(self.tab_prods, columns=("ID", "Nombre", "Precio"), show="headings", height=12)
        self.tree_prod.heading("ID", text="ID")
        self.tree_prod.heading("Nombre", text="Nombre")
        self.tree_prod.heading("Precio", text="Precio Base")
        self.tree_prod.pack(fill="both", expand=True, padx=10, pady=10)
        self.load_products()

    def load_products(self):
        for i in self.tree_prod.get_children():
            self.tree_prod.delete(i)
        for p in self.db.get_products():
            self.tree_prod.insert("", "end", values=p)

    def create_prod(self):
        try:
            nom = self.entry_p_name.get()
            pre = float(self.entry_p_price.get())
            if nom:
                if self.db.add_product(nom, pre):
                    self.load_products()
                    self.entry_p_name.delete(0, 'end')
                    self.entry_p_price.delete(0, 'end')
                else: messagebox.showerror("Error", "Ese producto ya existe.")
        except ValueError: messagebox.showerror("Error", "Precio inválido")

    def delete_prod(self):
        sel = self.tree_prod.selection()
        if sel:
            item = self.tree_prod.item(sel[0])
            self.db.delete_product(item['values'][0])
            self.load_products()

    def setup_reports_tab(self):
        ctrl_frame = ctk.CTkFrame(self.tab_reports)
        ctrl_frame.pack(fill="x", pady=10, padx=10)
        
        self.switch_hoy = ctk.CTkSwitch(ctrl_frame, text="Solo Ventas de HOY", font=FONT_TEXT, command=self.load_reports)
        self.switch_hoy.pack(side="left", padx=20)
        
        ctk.CTkButton(ctrl_frame, text="ANULAR VENTA", fg_color="#D32F2F", font=FONT_BTN, command=self.anular_venta).pack(side="left", padx=20)

        self.lbl_sum_total = ctk.CTkLabel(ctrl_frame, text="Total Vendido: Q0.00", font=FONT_HEADER, text_color="#00E676")
        self.lbl_sum_total.pack(side="right", padx=20)

        self.tree_rep = ttk.Treeview(self.tab_reports, columns=("Corr", "Fecha", "Usuario", "Total"), show="headings")
        self.tree_rep.heading("Corr", text="# Ticket")
        self.tree_rep.heading("Fecha", text="Fecha/Hora")
        self.tree_rep.heading("Usuario", text="Mesero")
        self.tree_rep.heading("Total", text="Monto")
        self.tree_rep.pack(fill="both", expand=True, padx=10, pady=10)
        self.load_reports()

    def load_reports(self):
        for i in self.tree_rep.get_children():
            self.tree_rep.delete(i)
        solo_hoy = True if self.switch_hoy.get() == 1 else False
        data = self.db.get_ventas_reporte(filtro_hoy=solo_hoy)
        suma = 0
        for row in data:
            self.tree_rep.insert("", "end", values=row)
            suma += row[3]
        self.lbl_sum_total.configure(text=f"Total Vendido: Q{suma:.2f}")

    def anular_venta(self):
        sel = self.tree_rep.selection()
        if not sel:
            messagebox.showwarning("Selección", "Selecciona una venta para anular.")
            return
        item = self.tree_rep.item(sel[0])
        correlativo = item['values'][0]
        if messagebox.askyesno("Confirmar", f"¿Eliminar venta #{correlativo}?"):
            if self.db.delete_sale(correlativo):
                self.load_reports()

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Sistema POS - Dolce Vita")
        self.geometry("1024x768")
        self.db = DatabaseManager()
        self.current_frame = None
        self.show_login()

    def switch_frame(self, frame_class, **kwargs):
        if self.current_frame: self.current_frame.destroy()
        self.current_frame = frame_class(self, **kwargs)

    def show_login(self):
        self.switch_frame(LoginFrame, login_callback=self.verify_login)

    def verify_login(self, username, password):
        user = self.db.login(username, password)
        if user:
            user_data = {'nombre': user[0], 'rol': user[1]}
            if user[1] == 'admin': self.show_manager(user_data)
            else: self.show_sales(user_data)
        else: messagebox.showerror("Error", "Credenciales incorrectas")

    def show_sales(self, user_data):
        self.switch_frame(SalesFrame, user_info=user_data, db=self.db, logout_cb=self.show_login)

    def show_manager(self, user_data):
        self.switch_frame(ManagerFrame, db=self.db, logout_cb=self.show_login)

if __name__ == "__main__":
    app = App()
    app.mainloop()