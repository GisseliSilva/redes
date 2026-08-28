"""
========================================================================
 SERVIDOR - Jogo de Desenho e Adivinhação em Rede (estilo Pictionary)
========================================================================
Disciplina: Redes de Computadores
Trabalho: Interface de Programação de Rede (Sockets) - Cliente/Servidor
Linguagem: Python 3 (biblioteca padrão: socket, threading, json, random, time)

RESUMO DO FUNCIONAMENTO:
- O servidor abre um socket TCP e aceita várias conexões simultâneas,
  atendendo cada cliente em uma thread separada (multithreading).
- Um jogador por vez é sorteado para "desenhar" uma palavra secreta,
  escolhida de uma categoria aleatória (Animais, Comida, Objetos,
  Natureza, Lugares).
- Os traços que ele desenha no Canvas são enviados ao servidor e
  retransmitidos (broadcast) em tempo real para os demais clientes.
- Os outros jogadores tentam adivinhar a palavra pelo chat; quem acerta
  primeiro ganha pontos (proporcionais à dificuldade da palavra), e o
  desenhista também pontua.
- Um cronômetro visível conta o tempo da rodada em tempo real, e o
  servidor revela letras da palavra progressivamente conforme o tempo
  passa, para dar dicas extras.

------------------------------------------------------------------------
>>> NOVIDADES DESTA VERSÃO <<<
  1) Banco de palavras organizado por CATEGORIA, com dificuldade
     calculada automaticamente (fácil / médio / difícil) e pontuação
     proporcional (get_dificuldade / PONTOS_POR_DIFICULDADE).
  2) Cronômetro de rodada transmitido ao vivo para todos os clientes,
     usando uma thread dedicada (classe RoundTicker) que envia um
     evento "timer" a cada segundo.
  3) Sistema de dicas progressivas: em dois momentos da rodada, uma
     letra aleatória da palavra é revelada para todos (reveal_hint_letter).
  4) Contagem de rodada e placar mais completo, incluindo quem está
     desenhando no momento (para a interface mostrar uma coroa).
  5) Encerramento de rodada mais robusto: se o desenhista desconectar
     no meio da rodada, o jogo passa para o próximo automaticamente.


"""

import socket
import threading
import json
import random
import time

# ------------------------- CONFIGURAÇÕES BÁSICAS -------------------------
HOST = '0.0.0.0'   # escuta em todas as interfaces de rede da máquina
PORT = 5555          # porta TCP utilizada pela aplicação

ROUND_TIME = 75      # segundos de duração de cada rodada
PAUSA_ENTRE_RODADAS = 4  # segundos de pausa mostrando o resultado antes da próxima rodada

# MODIFICAÇÃO DO GRUPO: banco de palavras organizado por categoria
CATEGORIAS = {
    "Animais": [
        "gato", "cachorro", "elefante", "borboleta", "girafa", "tigre",
        "coruja", "tartaruga", "canguru", "polvo", "pinguim", "leao",
        "jacare", "abelha", "camelo", "morcego", "esquilo", "rinoceronte",
    ],
    "Comida": [
        "pizza", "sorvete", "hamburguer", "macarrao", "chocolate",
        "pipoca", "sushi", "salada", "bolo", "torta", "pastel",
        "feijoada", "brigadeiro", "coxinha", "lasanha", "waffle",
    ],
    "Objetos": [
        "computador", "bicicleta", "guardachuva", "telefone", "chapeu",
        "livro", "relogio", "mochila", "chave", "espelho", "violao",
        "oculos", "cadeira", "tesoura", "lampada", "cameraFotografica",
    ],
    "Natureza": [
        "montanha", "arvore", "estrela", "vulcao", "cachoeira",
        "deserto", "furacao", "arcoiris", "oceano", "girassol",
        "floresta", "vaga", "nuvem", "relampago", "iceberg",
    ],
    "Lugares": [
        "castelo", "aeroporto", "hospital", "biblioteca", "estadio",
        "fazenda", "praia", "cinema", "mercado", "farol", "cachoeira",
        "escola", "restaurante", "parque", "museu",
    ],
}

PONTOS_POR_DIFICULDADE = {"facil": 5, "medio": 10, "dificil": 15}


def get_dificuldade(palavra):
    """MODIFICAÇÃO DO GRUPO: classifica a palavra pelo tamanho, já que
    palavras maiores tendem a ser mais difíceis de desenhar/adivinhar."""
    tamanho = len(palavra)
    if tamanho <= 5:
        return "facil"
    if tamanho <= 8:
        return "medio"
    return "dificil"


# ------------------------- ESTADO GLOBAL DO JOGO -------------------------
clients_lock = threading.Lock()   # protege as estruturas compartilhadas
clients = {}            # socket -> {"name": str, "score": int}
turn_order = []          # ordem de rodízio dos jogadores (lista de sockets)
current_drawer = None    # socket do jogador que está desenhando agora
current_word = None      # palavra secreta da rodada atual
current_category = None  # categoria da rodada atual
current_difficulty = None
revealed_indices = set()  # posições da palavra já reveladas como dica
round_number = 0
game_started = False

round_ticker = None       # instância de RoundTicker em andamento
hint_timers = []          # threading.Timer(s) agendados para revelar letras
next_round_timer = None   # threading.Timer que agenda a próxima rodada


# ------------------------- FUNÇÕES DE COMUNICAÇÃO -------------------------
def send_json(conn, obj):
    """Envia um dicionário Python como uma linha JSON terminada por \\n.
    Usamos \\n como delimitador de mensagens porque o TCP trabalha como
    um fluxo contínuo de bytes (stream), sem separar mensagens sozinho."""
    try:
        data = (json.dumps(obj) + "\n").encode("utf-8")
        conn.sendall(data)
    except Exception:
        pass  # cliente pode ter desconectado nesse meio-tempo


def broadcast(obj, exclude=None):
    """Envia a mesma mensagem para todos os clientes conectados,
    exceto (opcionalmente) para um socket específico."""
    with clients_lock:
        destinos = list(clients.keys())
    for c in destinos:
        if c is exclude:
            continue
        send_json(c, obj)


def broadcast_scoreboard():
    """MODIFICAÇÃO DO GRUPO: placar agora também informa quem está
    desenhando no momento, para a interface exibir uma coroa/destaque."""
    with clients_lock:
        scores = {
            info["name"]: {
                "score": info["score"],
                "drawing": (conn == current_drawer),
            }
            for conn, info in clients.items()
        }
    broadcast({"type": "scoreboard", "scores": scores})


def build_hint(word, revealed):
    return " ".join(ch if i in revealed else "_" for i, ch in enumerate(word))


# ------------------- MODIFICAÇÃO DO GRUPO: CRONÔMETRO AO VIVO -------------------
class RoundTicker(threading.Thread):
    """Thread dedicada que conta o tempo da rodada em segundos e transmite
    o valor restante para todos os clientes a cada tique, permitindo que
    a interface mostre um cronômetro visual em tempo real."""

    def __init__(self, seconds, on_timeout):
        super().__init__(daemon=True)
        self.total = seconds
        self.seconds_left = seconds
        self.on_timeout = on_timeout
        self._stop_event = threading.Event()

    def run(self):
        while self.seconds_left > 0 and not self._stop_event.is_set():
            broadcast({
                "type": "timer",
                "seconds_left": self.seconds_left,
                "total": self.total,
            })
            time.sleep(1)
            self.seconds_left -= 1
        if not self._stop_event.is_set():
            broadcast({"type": "timer", "seconds_left": 0, "total": self.total})
            self.on_timeout()

    def stop(self):
        self._stop_event.set()


def cancel_round_helpers():
    """Cancela o cronômetro e os timers de dica da rodada atual, se houver."""
    global round_ticker, hint_timers
    if round_ticker:
        round_ticker.stop()
        round_ticker = None
    for t in hint_timers:
        t.cancel()
    hint_timers = []


def reveal_hint_letter():
    """MODIFICAÇÃO DO GRUPO: revela uma letra aleatória (ainda não revelada)
    da palavra secreta e avisa todos os clientes com a dica atualizada."""
    global revealed_indices
    if not current_word:
        return
    faltando = [i for i in range(len(current_word)) if i not in revealed_indices]
    if not faltando:
        return
    revealed_indices.add(random.choice(faltando))
    broadcast({"type": "hint_update", "hint": build_hint(current_word, revealed_indices)})


# ------------------- LÓGICA DE TURNOS -------------------
def start_next_round():
    """Escolhe o próximo desenhista (rodízio), sorteia categoria/palavra e
    inicia o cronômetro + as dicas progressivas da nova rodada."""
    global current_drawer, current_word, current_category, current_difficulty
    global game_started, turn_order, revealed_indices, round_number

    cancel_round_helpers()

    with clients_lock:
        active = list(clients.keys())

    if len(active) < 2:
        game_started = False
        current_drawer = None
        broadcast({"type": "system", "text": "Aguardando mais jogadores para iniciar a partida..."})
        broadcast_scoreboard()
        return

    game_started = True

    # atualiza a fila de rodízio caso alguém tenha entrado/saído da sala
    turn_order = [c for c in turn_order if c in active]
    for c in active:
        if c not in turn_order:
            turn_order.append(c)

    if current_drawer in turn_order:
        idx = (turn_order.index(current_drawer) + 1) % len(turn_order)
    else:
        idx = 0

    current_drawer = turn_order[idx]
    current_category = random.choice(list(CATEGORIAS.keys()))
    current_word = random.choice(CATEGORIAS[current_category])
    current_difficulty = get_dificuldade(current_word)
    revealed_indices = set()
    round_number += 1

    with clients_lock:
        drawer_name = clients[current_drawer]["name"]

    broadcast({"type": "clear"})  # limpa o quadro de todos para a nova rodada
    broadcast({
        "type": "turn_started",
        "drawer": drawer_name,
        "hint": build_hint(current_word, revealed_indices),
        "category": current_category,
        "difficulty": current_difficulty,
        "round": round_number,
        "seconds": ROUND_TIME,
    })
    # a palavra secreta só é revelada ao desenhista, em mensagem individual
    send_json(current_drawer, {
        "type": "your_turn",
        "word": current_word,
        "category": current_category,
        "difficulty": current_difficulty,
        "round": round_number,
        "seconds": ROUND_TIME,
    })
    broadcast({
        "type": "system",
        "text": f"Rodada {round_number}: {drawer_name} está desenhando! "
                f"Categoria: {current_category} ({len(current_word)} letras).",
    })
    broadcast_scoreboard()

    # MODIFICAÇÃO DO GRUPO: agenda revelação progressiva de letras e o
    # cronômetro visível, ambos cancelados automaticamente se a rodada
    # terminar antes (acerto ou desconexão do desenhista)
    global round_ticker, hint_timers
    round_ticker = RoundTicker(ROUND_TIME, end_round_by_timeout)
    round_ticker.start()

    if len(current_word) > 3:
        t1 = threading.Timer(ROUND_TIME * 0.4, reveal_hint_letter)
        t2 = threading.Timer(ROUND_TIME * 0.7, reveal_hint_letter)
        t1.daemon = True
        t2.daemon = True
        t1.start()
        t2.start()
        hint_timers = [t1, t2]


def end_round_by_timeout():
    """Chamada automaticamente quando o tempo da rodada acaba."""
    broadcast({"type": "system", "text": f"Tempo esgotado! A palavra era: {current_word}"})
    start_next_round()


def handle_correct_guess(guesser_conn, guesser_name):
    """MODIFICAÇÃO DO GRUPO: pontuação proporcional à dificuldade da
    palavra. Quem acerta ganha o dobro dos pontos-base; o desenhista
    ganha os pontos-base como bônus."""
    global next_round_timer
    pontos_base = PONTOS_POR_DIFICULDADE.get(current_difficulty, 10)

    with clients_lock:
        clients[guesser_conn]["score"] += pontos_base * 2
        if current_drawer in clients:
            clients[current_drawer]["score"] += pontos_base

    cancel_round_helpers()

    broadcast({
        "type": "chat",
        "name": guesser_name,
        "text": f"acertou a palavra! Era \"{current_word}\" (+{pontos_base * 2} pts)",
        "correct": True,
    })
    broadcast_scoreboard()

    if next_round_timer:
        next_round_timer.cancel()
    next_round_timer = threading.Timer(PAUSA_ENTRE_RODADAS, start_next_round)
    next_round_timer.daemon = True
    next_round_timer.start()


# ------------------------- THREAD DE ATENDIMENTO POR CLIENTE -------------------------
def handle_client(conn, addr):
    """Cada cliente conectado é atendido em uma thread própria, permitindo
    que o servidor converse com vários clientes ao mesmo tempo sem que um
    bloqueie o atendimento do outro."""
    buffer = ""
    try:
        while True:
            chunk = conn.recv(4096)
            if not chunk:
                break  # cliente fechou a conexão
            buffer += chunk.decode("utf-8")

            # um recv() pode trazer mais de uma mensagem (ou uma mensagem
            # incompleta); por isso separamos por linha (\n)
            while "\n" in buffer:
                line, buffer = buffer.split("\n", 1)
                if not line.strip():
                    continue
                msg = json.loads(line)
                mtype = msg.get("type")

                if mtype == "join":
                    name = (msg.get("name") or f"Jogador{addr[1]}").strip()[:20]
                    with clients_lock:
                        clients[conn] = {"name": name, "score": 0}
                    broadcast({"type": "system", "text": f"{name} entrou na sala."})
                    broadcast_scoreboard()
                    if not game_started:
                        start_next_round()

                elif mtype == "draw":
                    # só o desenhista da vez pode transmitir traços -> impede trapaça
                    if conn == current_drawer:
                        broadcast(msg, exclude=conn)

                elif mtype == "clear":
                    if conn == current_drawer:
                        broadcast({"type": "clear"})

                elif mtype == "guess":
                    text = msg.get("text", "")
                    with clients_lock:
                        guesser_name = clients[conn]["name"]

                    if conn == current_drawer:
                        # o próprio desenhista só usa o campo como bate-papo
                        broadcast({"type": "chat", "name": guesser_name, "text": text})
                        continue

                    if current_word and text.strip().lower() == current_word.lower():
                        handle_correct_guess(conn, guesser_name)
                    else:
                        broadcast({"type": "chat", "name": guesser_name, "text": text})

    except (ConnectionResetError, json.JSONDecodeError):
        pass
    finally:
        era_desenhista = (conn == current_drawer)
        with clients_lock:
            if conn in clients:
                left_name = clients[conn]["name"]
                del clients[conn]
                broadcast({"type": "system", "text": f"{left_name} saiu da sala."})
        if conn in turn_order:
            turn_order.remove(conn)
        conn.close()
        broadcast_scoreboard()
        print(f"[SERVIDOR] Conexão encerrada: {addr}")

        # MODIFICAÇÃO DO GRUPO: se quem desconectou era o desenhista da
        # vez, a rodada não pode continuar travada esperando ele -> pula
        if era_desenhista:
            cancel_round_helpers()
            start_next_round()


def main():
    servidor_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    servidor_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    servidor_socket.bind((HOST, PORT))
    servidor_socket.listen()
    print(f"[SERVIDOR] Aguardando conexões em {HOST}:{PORT} ...")

    try:
        while True:
            conn, addr = servidor_socket.accept()
            print(f"[SERVIDOR] Nova conexão de {addr}")
            threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()
    except KeyboardInterrupt:
        print("\n[SERVIDOR] Encerrando servidor...")
    finally:
        servidor_socket.close()


if __name__ == "__main__":
    main()
    