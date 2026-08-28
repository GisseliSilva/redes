"""
========================================================================
 CLIENTE - Jogo de Desenho e Adivinhação em Rede (estilo Gartic)
 LAYOUT: Microsoft Paint clássico (Windows) + cara de jogo de adivinhação
========================================================================
Disciplina: Redes de Computadores
Trabalho: Interface de Programação de Rede (Sockets) - Cliente/Servidor
Linguagem: Python 3 (bibliotecas padrão: socket, threading, json, tkinter)

RESUMO DO FUNCIONAMENTO:
- Toda a camada de REDE é idêntica à versão anterior: conecta via socket
  TCP, manda/recebe JSON delimitado por "\n", uma thread cuida do recv()
  enquanto a thread principal cuida da interface gráfica.
- O que mudou foi só a INTERFACE (Tkinter), que agora imita a "moldura"
  do Microsoft Paint clássico do Windows (menu, barra de ferramentas,
  paleta em grade, barra de status) só que com uma "casca" de jogo de
  adivinhação por cima (estilo Gartic): faixa colorida com o cronômetro,
  a dica da palavra e o placar com coroa para quem está desenhando.

------------------------------------------------------------------------
>>> O QUE MUDOU NESTA VERSÃO (LAYOUT PAINT + GARTIC) <<<
  1) Barra de menu no topo (Arquivo / Editar / Ver / Ajuda) — visual do
     Windows clássico, com alguns comandos realmente funcionais.
  2) Barra de ferramentas com "botões-ícone" em relevo (relief=RAISED),
     imitando a caixa de ferramentas do Paint (lápis, borracha, balde
     de "limpar tudo", seletor de espessura).
  3) Paleta de cores em grade retangular na parte inferior da janela,
     com indicador de cor primária sobreposto — igual ao Paint clássico.
  4) Barra de status embaixo mostrando a posição do cursor no canvas,
     como no Paint original.
  5) Por cima dessa "moldura cinza" do Windows, uma faixa de jogo estilo
     Gartic: cronômetro grande e colorido, dica da palavra em caixas
     tipo "forca", categoria/dificuldade, chat em bolhas e placar com
     avatares + coroa para quem está desenhando.
  6) Paleta de cinzas do Windows 95/98 (#C0C0C0, #808080, #DFDFDF) para
     toda a moldura, mantendo cores vivas só na parte "de jogo".
------------------------------------------------------------------------
"""

import socket
import threading
import json
import queue
import tkinter as tk
from tkinter import font as tkfont

# ------------------------- PALETA "MOLDURA" (ESTILO WINDOWS/PAINT) -------------------------
WIN_GRAY = "#C0C0C0"        # cinza clássico de fundo de janela
WIN_GRAY_LIGHT = "#DFDFDF"
WIN_GRAY_DARK = "#808080"
WIN_BLACK = "#000000"
WIN_WHITE = "#FFFFFF"
TITLE_BLUE = "#000080"      # azul de barra de título estilo Windows 98

# ------------------------- PALETA "DE JOGO" (ESTILO GARTIC) -------------------------
GARTIC_PURPLE = "#5B2A86"
GARTIC_PURPLE_DARK = "#421D63"
GARTIC_PINK = "#FF5C8D"
GARTIC_YELLOW = "#FFD23F"
GARTIC_GREEN = "#3DDC97"
GARTIC_ORANGE = "#F2994A"
GARTIC_RED = "#EB5757"
TEXT_DARK = "#24272E"
TEXT_MUTED = "#6B7280"
CARD_BG = "#FFFFFF"
CARD_BORDER = "#D8DAE8"

# Paleta de cores do "balde de tinta" (grade estilo Paint clássico)
PALETA_CORES = [
    "#000000", "#7F7F7F", "#880015", "#ED1C24", "#FF7F27", "#FFF200",
    "#22B14C", "#00A2E8", "#3F48CC", "#A349A4", "#FFFFFF", "#C3C3C3",
    "#B97A57", "#FFAEC9", "#FFC90E", "#EFE4B0", "#B5E61D", "#99D9EA",
    "#7092BE", "#C8BFE7",
]

DIFICULDADE_COR = {"facil": GARTIC_GREEN, "medio": GARTIC_ORANGE, "dificil": GARTIC_RED}
DIFICULDADE_LABEL = {"facil": "FÁCIL", "medio": "MÉDIO", "dificil": "DIFÍCIL"}

AVATAR_CORES = [GARTIC_PURPLE, GARTIC_PINK, GARTIC_GREEN, "#9B51E0",
                 "#00BCD4", GARTIC_ORANGE, GARTIC_RED, "#2F80ED"]


def cor_avatar(nome):
    """Gera sempre a mesma cor para o mesmo nome (hash simples pela soma
    dos códigos dos caracteres)."""
    indice = sum(ord(c) for c in nome) % len(AVATAR_CORES)
    return AVATAR_CORES[indice]


class GameClient:
    def __init__(self):
        self.sock = None
        self.msg_queue = queue.Queue()
        self.is_drawer = False
        self.current_color = "#000000"
        self.secondary_color = "#FFFFFF"
        self.brush_size = 3
        self.erasing = False
        self.last_x = None
        self.last_y = None
        self.color_swatches = []
        self.round_total_time = 75

        self.root = tk.Tk()
        self.root.configure(bg=WIN_GRAY)
        self.root.withdraw()  # esconde a janela principal até conectar
        self.connect_dialog()

    # ------------------------- TELA DE CONEXÃO -------------------------
    def connect_dialog(self):
        top = tk.Toplevel()
        top.title("Conectar ao servidor")
        top.geometry("420x520")
        top.minsize(380, 480)
        top.resizable(True, True)
        top.configure(bg=WIN_GRAY)

        # "Barra de título" falsa, estilo Windows 98, só pra dar o clima
        titlebar = tk.Frame(top, bg=TITLE_BLUE, height=28)
        titlebar.pack(fill=tk.X)
        tk.Label(titlebar, text="🖌 Drawize - Conexão", bg=TITLE_BLUE, fg="white",
                 font=("Segoe UI", 10, "bold")).pack(side=tk.LEFT, padx=8, pady=4)

        header_font = tkfont.Font(family="Comic Sans MS", size=18, weight="bold")
        label_font = tkfont.Font(family="Segoe UI", size=9, weight="bold")
        entry_font = tkfont.Font(family="Segoe UI", size=11)

        header = tk.Frame(top, bg=GARTIC_PURPLE)
        header.pack(fill=tk.X)
        tk.Label(header, text="Drawize", bg=GARTIC_PURPLE, fg="white",
                 font=header_font, wraplength=380, justify="center").pack(pady=(18, 4))
        tk.Label(header, text="jogo de desenho em", bg=GARTIC_PURPLE,
                 fg=GARTIC_YELLOW, font=("Segoe UI", 9, "italic")).pack(pady=(0, 16))

        card = tk.Frame(top, bg=WIN_GRAY_LIGHT, padx=22, pady=20,
                         relief=tk.GROOVE, bd=3)
        card.pack(padx=24, pady=18, fill=tk.BOTH, expand=True)

        entries = {}

        def campo(rotulo, valor_padrao):
            tk.Label(card, text=rotulo, bg=WIN_GRAY_LIGHT, fg=TEXT_DARK, font=label_font,
                     anchor="w").pack(fill=tk.X, pady=(8, 3))
            e = tk.Entry(card, font=entry_font, bg="white", relief=tk.SUNKEN, bd=2)
            e.insert(0, valor_padrao)
            e.pack(fill=tk.X, ipady=5)
            e.bind("<Return>", lambda ev: do_connect())
            return e

        entries["ip"] = campo("IP DO SERVIDOR", "172.18.10.51")
        entries["port"] = campo("PORTA", "5555")
        entries["name"] = campo("SEU NOME", "")

        status_lbl = tk.Label(card, text="", fg=GARTIC_RED, bg=WIN_GRAY_LIGHT,
                               font=("Segoe UI", 9, "bold"), wraplength=330, justify="left")
        status_lbl.pack(pady=(10, 0), fill=tk.X)

        def do_connect():
            ip = entries["ip"].get().strip()
            try:
                port = int(entries["port"].get().strip())
            except ValueError:
                status_lbl.config(text="Porta inválida.")
                return
            name = entries["name"].get().strip() or "Jogador"

            try:
                self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.sock.settimeout(5)
                self.sock.connect((ip, port))
                self.sock.settimeout(None)
                self.send_json({"type": "join", "name": name})

                top.destroy()
                self.root.deiconify()
                self.build_game_window(name)

                threading.Thread(target=self.receive_loop, daemon=True).start()
                self.root.after(50, self.process_queue)
            except Exception as e:
                status_lbl.config(text=f"Erro ao conectar: {e}")

        connect_btn = tk.Button(
            card, text="CONECTAR ➤", command=do_connect, bg=GARTIC_PINK, fg="white",
            activebackground=GARTIC_PURPLE, activeforeground="white",
            font=("Segoe UI", 11, "bold"), relief=tk.RAISED, bd=3, cursor="hand2",
        )
        connect_btn.pack(fill=tk.X, ipady=9, pady=(18, 4), side=tk.BOTTOM)

        top.protocol("WM_DELETE_WINDOW", lambda: (top.destroy(), self.root.destroy()))
        top.grab_set()
        entries["name"].focus_set()
        self.root.wait_window(top)

    # ------------------------- REDE (sem mudanças) -------------------------
    def send_json(self, obj):
        try:
            data = (json.dumps(obj) + "\n").encode("utf-8")
            self.sock.sendall(data)
        except Exception:
            pass

    def receive_loop(self):
        buffer = ""
        while True:
            try:
                chunk = self.sock.recv(4096)
                if not chunk:
                    break
                buffer += chunk.decode("utf-8")
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    if line.strip():
                        self.msg_queue.put(json.loads(line))
            except Exception:
                break
        self.msg_queue.put({"type": "system", "text": "Conexão com o servidor perdida."})

    def process_queue(self):
        try:
            while True:
                msg = self.msg_queue.get_nowait()
                self.handle_message(msg)
        except queue.Empty:
            pass
        self.root.after(50, self.process_queue)

    def handle_message(self, msg):
        mtype = msg.get("type")

        if mtype == "draw":
            self.canvas.create_line(
                msg["x1"], msg["y1"], msg["x2"], msg["y2"],
                fill=msg.get("color", "black"), width=msg.get("width", 3),
                capstyle=tk.ROUND, smooth=True
            )
        elif mtype == "clear":
            self.canvas.delete("all")
        elif mtype == "chat":
            self.add_chat_bubble(msg["name"], msg["text"], correct=msg.get("correct", False))
        elif mtype == "system":
            self.add_system_line(msg["text"])
        elif mtype == "timer":
            self.round_total_time = msg.get("total", self.round_total_time)
            self.update_timer_display(msg.get("seconds_left", 0))
        elif mtype == "hint_update":
            self.update_hint(msg["hint"])
        elif mtype == "turn_started":
            self.is_drawer = False
            self.current_word_hint = msg["hint"]
            self.update_round_header(
                round_no=msg.get("round"), drawer=msg["drawer"],
                category=msg.get("category"), difficulty=msg.get("difficulty"),
                is_drawer=False,
            )
            self.update_hint(msg["hint"])
            self.set_drawing_enabled(False)
        elif mtype == "your_turn":
            self.is_drawer = True
            self.update_round_header(
                round_no=msg.get("round"), drawer="Você", category=msg.get("category"),
                difficulty=msg.get("difficulty"), is_drawer=True, word=msg.get("word"),
            )
            self.set_drawing_enabled(True)
        elif mtype == "scoreboard":
            self.update_scoreboard(msg["scores"])

    # ------------------------- HEADER / DICA / TIMER (estilo Gartic) -------------------------
    def update_round_header(self, round_no, drawer, category, difficulty, is_drawer, word=None):
        self.round_label.config(text=f"RODADA {round_no}" if round_no else "")
        cor_dif = DIFICULDADE_COR.get(difficulty, TEXT_MUTED)
        texto_dif = DIFICULDADE_LABEL.get(difficulty, "")
        self.badge_label.config(
            text=f"  {category or ''} · {texto_dif}  ", bg=cor_dif, fg="white"
        )
        if is_drawer:
            self.status_label.config(
                text=f"SUA VEZ DE DESENHAR!    Palavra: {word}",
                bg=GARTIC_PINK, fg="white",
            )
        else:
            self.status_label.config(
                text=f"Vez de: {drawer}  — tente adivinhar!", bg=GARTIC_PURPLE, fg="white",
            )

    def update_hint(self, hint):
        # exibe a dica em "caixinhas" tipo jogo da forca, espaçando as letras
        espacado = "  ".join(hint.split(" "))
        self.hint_label.config(text=espacado)

    def update_timer_display(self, seconds_left):
        total = max(self.round_total_time, 1)
        frac = seconds_left / total
        if frac > 0.5:
            cor = GARTIC_GREEN
        elif frac > 0.2:
            cor = GARTIC_ORANGE
        else:
            cor = GARTIC_RED
        self.timer_label.config(text=f"⏱ {seconds_left}s", fg=cor)

    # ------------------------- PLACAR -------------------------
    def update_scoreboard(self, scores):
        for w in self.score_inner.winfo_children():
            w.destroy()
        ranking = sorted(scores.items(), key=lambda x: -x[1]["score"])
        for nome, info in ranking:
            linha = tk.Frame(self.score_inner, bg=CARD_BG)
            linha.pack(fill=tk.X, pady=3)

            av = tk.Canvas(linha, width=26, height=26, bg=CARD_BG, highlightthickness=0)
            av.create_oval(0, 0, 26, 26, fill=cor_avatar(nome), outline="")
            iniciais = "".join([p[0] for p in nome.split()[:2]]).upper() or "?"
            av.create_text(13, 13, text=iniciais, fill="white", font=("Segoe UI", 9, "bold"))
            av.pack(side=tk.LEFT, padx=(2, 8))

            rotulo = nome + ("👑" if info.get("drawing") else "")
            tk.Label(linha, text=rotulo, bg=CARD_BG, fg=TEXT_DARK,
                     font=("Segoe UI", 9, "bold"), anchor="w").pack(side=tk.LEFT, fill=tk.X, expand=True)
            tk.Label(linha, text=f"{info['score']} pts", bg=CARD_BG, fg=TEXT_MUTED,
                     font=("Segoe UI", 9)).pack(side=tk.RIGHT)

    # ------------------------- CHAT -------------------------
    def add_chat_bubble(self, nome, texto, correct=False):
        self.chat_text.config(state=tk.NORMAL)
        tag_nome = "chat_correct_name" if correct else "chat_name"
        tag_msg = "chat_correct_msg" if correct else "chat_msg"
        prefixo = "✔ " if correct else ""
        self.chat_text.insert(tk.END, f"{prefixo}{nome}", tag_nome)
        self.chat_text.insert(tk.END, f"  {texto}\n", tag_msg)
        self.chat_text.see(tk.END)
        self.chat_text.config(state=tk.DISABLED)

    def add_system_line(self, texto):
        self.chat_text.config(state=tk.NORMAL)
        self.chat_text.insert(tk.END, f"✦ {texto}\n", "chat_system")
        self.chat_text.see(tk.END)
        self.chat_text.config(state=tk.DISABLED)

    def set_drawing_enabled(self, enabled):
        state = tk.NORMAL if enabled else tk.DISABLED
        self.clear_btn.config(state=state, cursor="hand2" if enabled else "arrow")
        self.pencil_btn.config(state=state, cursor="hand2" if enabled else "arrow")
        self.eraser_btn.config(state=state, cursor="hand2" if enabled else "arrow")
        self.brush_scale.config(state=state)
        for swatch in self.color_swatches:
            swatch.config(state=state, cursor="hand2" if enabled else "arrow")

    # ------------------------- INTERFACE GRÁFICA -------------------------
    def build_game_window(self, name):
        self.root.title(f"Drawize — {name}")
        self.root.configure(bg=WIN_GRAY)
        self.root.minsize(1000, 700)

        # ================= BARRA DE MENU (estilo Windows/Paint) =================
        menubar = tk.Menu(self.root)
        menu_arquivo = tk.Menu(menubar, tearoff=0)
        menu_arquivo.add_command(label="Sair", command=self.on_close)
        menubar.add_cascade(label="Arquivo", menu=menu_arquivo)

        menu_editar = tk.Menu(menubar, tearoff=0)
        menu_editar.add_command(label="Limpar tela", command=self.clear_canvas)
        menubar.add_cascade(label="Editar", menu=menu_editar)

        menu_ajuda = tk.Menu(menubar, tearoff=0)
        menu_ajuda.add_command(
            label="Como jogar",
            command=lambda: self.add_system_line(
                "Quando for sua vez, desenhe a palavra secreta. Os demais tentam adivinhar pelo chat!"
            ),
        )
        menubar.add_cascade(label="Ajuda", menu=menu_ajuda)
        self.root.config(menu=menubar)

        # ================= BARRA DE FERRAMENTAS (estilo Paint) =================
        toolbar = tk.Frame(self.root, bg=WIN_GRAY_LIGHT, relief=tk.RAISED, bd=2)
        toolbar.pack(fill=tk.X)

        self.pencil_btn = tk.Button(
            toolbar, text="✏ Lápis", command=self.use_pencil, relief=tk.RAISED, bd=2,
            bg=WIN_GRAY_LIGHT, activebackground=WIN_GRAY, font=("Segoe UI", 9), cursor="hand2",
        )
        self.pencil_btn.pack(side=tk.LEFT, padx=3, pady=3, ipadx=4)

        self.eraser_btn = tk.Button(
            toolbar, text="🧽 Borracha", command=self.toggle_eraser, relief=tk.RAISED, bd=2,
            bg=WIN_GRAY_LIGHT, activebackground=WIN_GRAY, font=("Segoe UI", 9), cursor="hand2",
        )
        self.eraser_btn.pack(side=tk.LEFT, padx=3, pady=3, ipadx=4)

        self.clear_btn = tk.Button(
            toolbar, text="🗑 Limpar Tudo", command=self.clear_canvas, relief=tk.RAISED, bd=2,
            bg=WIN_GRAY_LIGHT, activebackground=WIN_GRAY, font=("Segoe UI", 9), cursor="hand2",
        )
        self.clear_btn.pack(side=tk.LEFT, padx=3, pady=3, ipadx=4)

        tk.Frame(toolbar, bg=WIN_GRAY_DARK, width=2).pack(side=tk.LEFT, fill=tk.Y, padx=8, pady=4)

        tk.Label(toolbar, text="Espessura:", bg=WIN_GRAY_LIGHT, font=("Segoe UI", 9)).pack(side=tk.LEFT)
        self.brush_scale = tk.Scale(
            toolbar, from_=1, to=15, orient=tk.HORIZONTAL, length=110, bg=WIN_GRAY_LIGHT,
            fg=TEXT_DARK, highlightthickness=0, troughcolor=WIN_GRAY,
            command=lambda v: setattr(self, "brush_size", int(v)),
        )
        self.brush_scale.set(3)
        self.brush_scale.pack(side=tk.LEFT, padx=(4, 6), pady=2)

        # ================= FAIXA DE JOGO ESTILO GARTIC =================
        game_bar = tk.Frame(self.root, bg=GARTIC_PURPLE)
        game_bar.pack(fill=tk.X)

        info_row = tk.Frame(game_bar, bg=GARTIC_PURPLE)
        info_row.pack(fill=tk.X, padx=16, pady=(8, 0))
        self.round_label = tk.Label(info_row, text="", bg=GARTIC_PURPLE, fg=GARTIC_YELLOW,
                                     font=("Segoe UI", 10, "bold"))
        self.round_label.pack(side=tk.LEFT)
        self.timer_label = tk.Label(info_row, text="⏱ --", bg=GARTIC_PURPLE, fg=GARTIC_GREEN,
                                     font=("Segoe UI", 13, "bold"))
        self.timer_label.pack(side=tk.RIGHT)
        self.badge_label = tk.Label(info_row, text="", bg=TEXT_MUTED, fg="white",
                                     font=("Segoe UI", 9, "bold"))
        self.badge_label.pack(side=tk.RIGHT, padx=12)

        self.status_label = tk.Label(
            game_bar, text="Aguardando início da partida...",
            font=("Segoe UI", 13, "bold"), bg=GARTIC_PURPLE_DARK, fg="white", pady=8,
        )
        self.status_label.pack(fill=tk.X, pady=(6, 0))

        self.hint_label = tk.Label(
            game_bar, text="", font=("Consolas", 22, "bold"), bg=GARTIC_PURPLE_DARK,
            fg=GARTIC_YELLOW, pady=10,
        )
        self.hint_label.pack(fill=tk.X)

        # ================= CORPO PRINCIPAL =================
        main_frame = tk.Frame(self.root, bg=WIN_GRAY, padx=10, pady=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # ---- Coluna esquerda: paleta de cores em grade (estilo Paint) ----
        left_col = tk.Frame(main_frame, bg=WIN_GRAY)
        left_col.grid(row=0, column=0, sticky="n", padx=(0, 8))

        # indicador de cor primária/secundária, igual Paint clássico
        color_indicator = tk.Frame(left_col, bg=WIN_GRAY, width=50, height=50)
        color_indicator.pack(pady=(0, 6))
        color_indicator.pack_propagate(False)
        self.primary_swatch = tk.Frame(color_indicator, bg=self.current_color, relief=tk.SUNKEN, bd=2,
                                        width=32, height=32)
        self.primary_swatch.place(x=0, y=0)
        self.secondary_swatch = tk.Frame(color_indicator, bg=self.secondary_color, relief=tk.SUNKEN, bd=2,
                                          width=32, height=32)
        self.secondary_swatch.place(x=16, y=16)

        palette_frame = tk.Frame(left_col, bg=WIN_GRAY_LIGHT, relief=tk.SUNKEN, bd=2)
        palette_frame.pack()
        self.color_swatches = []
        for i, c in enumerate(PALETA_CORES):
            row, col = divmod(i, 2)
            sw = tk.Button(
                palette_frame, bg=c, width=2, height=1, relief=tk.RAISED, bd=1,
                activebackground=c, cursor="hand2",
                command=lambda c=c: self.set_color(c),
            )
            sw.grid(row=row, column=col, padx=1, pady=1)
            self.color_swatches.append(sw)

        # ---- Centro: canvas de desenho ----
        canvas_col = tk.Frame(main_frame, bg=WIN_GRAY)
        canvas_col.grid(row=0, column=1, sticky="n")

        canvas_card = tk.Frame(canvas_col, bg=WIN_WHITE, relief=tk.SUNKEN, bd=3)
        canvas_card.pack()
        self.canvas = tk.Canvas(canvas_card, width=560, height=420, bg="white",
                                 cursor="pencil", highlightthickness=0)
        self.canvas.pack()
        self.canvas.bind("<Button-1>", self.on_mouse_down)
        self.canvas.bind("<B1-Motion>", self.on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_mouse_up)
        self.canvas.bind("<Motion>", self.on_mouse_move)

        # ---- Barra de status (estilo Paint) ----
        self.status_bar = tk.Label(
            canvas_col, text="Pronto.", bg=WIN_GRAY_LIGHT, fg=TEXT_DARK,
            font=("Segoe UI", 8), relief=tk.SUNKEN, bd=1, anchor="w",
        )
        self.status_bar.pack(fill=tk.X, pady=(4, 0), ipady=2)

        # ---- Coluna direita: placar + chat (estilo Gartic) ----
        side = tk.Frame(main_frame, bg=WIN_GRAY, width=260)
        side.grid(row=0, column=2, sticky="n", padx=(10, 0))

        tk.Label(side, text="PLACAR", bg=WIN_GRAY, fg=TEXT_MUTED,
                 font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(0, 4))
        score_card = tk.Frame(side, bg=CARD_BG, relief=tk.GROOVE, bd=2)
        score_card.pack(fill=tk.X, pady=(0, 14))
        self.score_inner = tk.Frame(score_card, bg=CARD_BG)
        self.score_inner.pack(fill=tk.BOTH, padx=8, pady=8)

        tk.Label(side, text="CHAT / PALPITES", bg=WIN_GRAY, fg=TEXT_MUTED,
                 font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(0, 4))
        chat_card = tk.Frame(side, bg=CARD_BG, relief=tk.GROOVE, bd=2)
        chat_card.pack(fill=tk.BOTH, expand=True)

        self.chat_text = tk.Text(
            chat_card, height=15, bd=0, relief=tk.FLAT, bg=CARD_BG, fg=TEXT_DARK,
            font=("Segoe UI", 9), wrap=tk.WORD, state=tk.DISABLED, padx=8, pady=8,
        )
        self.chat_text.pack(fill=tk.BOTH, expand=True)
        self.chat_text.tag_config("chat_name", font=("Segoe UI", 9, "bold"), foreground=GARTIC_PURPLE)
        self.chat_text.tag_config("chat_msg", foreground=TEXT_DARK)
        self.chat_text.tag_config("chat_correct_name", font=("Segoe UI", 9, "bold"), foreground=GARTIC_GREEN)
        self.chat_text.tag_config("chat_correct_msg", foreground=GARTIC_GREEN, font=("Segoe UI", 9, "bold"))
        self.chat_text.tag_config("chat_system", foreground=GARTIC_PINK, font=("Segoe UI", 8, "italic"))

        # ================= BARRA INFERIOR: ENVIO DE PALPITES =================
        bottom_frame = tk.Frame(self.root, bg=GARTIC_PURPLE, pady=8, padx=12)
        bottom_frame.pack(fill=tk.X, side=tk.BOTTOM)
        self.guess_entry = tk.Entry(
            bottom_frame, font=("Segoe UI", 11), relief=tk.SUNKEN, bd=2,
        )
        self.guess_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=5, padx=(0, 8))
        self.guess_entry.bind("<Return>", lambda e: self.send_guess())
        tk.Button(
            bottom_frame, text="Enviar ➤", command=self.send_guess,
            bg=GARTIC_PINK, fg="white", activebackground=GARTIC_PURPLE_DARK, activeforeground="white",
            relief=tk.RAISED, bd=2, font=("Segoe UI", 10, "bold"), cursor="hand2", padx=14,
        ).pack(side=tk.LEFT, ipady=5)

        self.set_drawing_enabled(False)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    # ------------------------- FERRAMENTAS DE DESENHO -------------------------
    def use_pencil(self):
        self.erasing = False
        self.pencil_btn.config(relief=tk.SUNKEN)
        self.eraser_btn.config(relief=tk.RAISED)

    def set_color(self, c):
        self.erasing = False
        self.pencil_btn.config(relief=tk.SUNKEN)
        self.eraser_btn.config(relief=tk.RAISED)
        self.current_color = c
        self.primary_swatch.config(bg=c)

    def toggle_eraser(self):
        self.erasing = not self.erasing
        self.eraser_btn.config(relief=tk.SUNKEN if self.erasing else tk.RAISED)
        self.pencil_btn.config(relief=tk.RAISED if self.erasing else tk.SUNKEN)

    # ------------------------- EVENTOS DE DESENHO -------------------------
    def on_mouse_down(self, event):
        if not self.is_drawer:
            return
        self.last_x, self.last_y = event.x, event.y

    def on_mouse_drag(self, event):
        if not self.is_drawer or self.last_x is None:
            return
        x, y = event.x, event.y
        cor = "#FFFFFF" if self.erasing else self.current_color
        largura = self.brush_size * 3 if self.erasing else self.brush_size
        self.canvas.create_line(
            self.last_x, self.last_y, x, y,
            fill=cor, width=largura, capstyle=tk.ROUND, smooth=True
        )
        self.send_json({
            "type": "draw",
            "x1": self.last_x, "y1": self.last_y,
            "x2": x, "y2": y,
            "color": cor, "width": largura,
        })
        self.last_x, self.last_y = x, y

    def on_mouse_up(self, event):
        self.last_x, self.last_y = None, None

    def on_mouse_move(self, event):
        self.status_bar.config(text=f"  x: {event.x}   y: {event.y}")

    def clear_canvas(self):
        if self.is_drawer:
            self.canvas.delete("all")
            self.send_json({"type": "clear"})

    # ------------------------- CHAT / PALPITES -------------------------
    def send_guess(self):
        text = self.guess_entry.get().strip()
        if text:
            self.send_json({"type": "guess", "text": text})
            self.guess_entry.delete(0, tk.END)

    def on_close(self):
        try:
            self.sock.close()
        except Exception:
            pass
        self.root.destroy()

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    client = GameClient()
    client.run()