# Jogo de Desenho e Adivinhação em Rede (estilo Pictionary)

Trabalho de Redes de Computadores — Interface de Programação de Rede (Sockets)
Cliente/Servidor desenvolvido em **Python 3**, usando apenas bibliotecas
padrão da linguagem: `socket`, `threading`, `json` e `tkinter` (interface
gráfica). **Não é necessário instalar nada com pip.**

## Arquivos

- `servidor.py` — servidor TCP multithread. Gerencia jogadores, turnos,
  sorteio de palavras, pontuação e retransmissão dos desenhos.
- `cliente.py` — cliente com interface gráfica em **Tkinter**. Não precisa
  instalar nada além do Python padrão.
  instalar a biblioteca pygame (veja abaixo).
- `requirements.txt` — dependência necessária apenas para a versão Pygame.

**As duas versões de cliente falam o mesmo protocolo e usam o mesmo
`servidor.py` — não precisa rodar o servidor de forma diferente para
cada uma, e dá até para misturar: alguns jogadores usando `cliente.py`
e outros usando `cliente_pygame.py` ao mesmo tempo, na mesma partida.**

## Como executar

### 1. Pré-requisitos
Python 3.8 ou superior instalado (o Tkinter já vem incluso na instalação
padrão do Python no Windows/Mac; no Linux, se necessário: `sudo apt install python3-tk`).

### 2. Iniciar o servidor
Em uma máquina (pode ser o próprio notebook usado na apresentação):

```bash
python3 servidor.py
```

O terminal deve mostrar:
```
[SERVIDOR] Aguardando conexões em 0.0.0.0:5555 ...
```

### 3. Iniciar os clientes
Abra um terminal para cada jogador (pode ser na mesma máquina, para
demonstração, ou em máquinas diferentes na mesma rede):

**Versão Tkinter (sem instalar nada extra):**
```bash
python3 cliente.py
```

**Versão Pygame (visual mais rico — precisa instalar a dependência uma vez):**
```bash
pip install -r requirements.txt
python3 cliente_pygame.py
```

Na tela de conexão, informe:
- **IP do servidor**: `127.0.0.1` se for na mesma máquina, ou o IP da
  máquina onde o `servidor.py` está rodando (ex.: `192.168.0.10`)
- **Porta**: `5555` (padrão, já vem preenchido)
- **Nome**: nome do jogador

É necessário **pelo menos 2 clientes conectados** para a partida começar.

### 4. Jogando
- O jogador sorteado como "desenhista" vê a palavra secreta e desenha no
  Canvas com o mouse.
- Os demais jogadores digitam palpites no campo de chat.
- Quem acertar primeiro ganha pontos, e a vez passa automaticamente para
  o próximo jogador.
- Cada rodada tem 60 segundos; se ninguém acertar, a palavra é revelada
  e a próxima rodada começa.

## Arquitetura / Protocolo

A comunicação usa **sockets TCP** com um protocolo próprio de aplicação:
cada mensagem é um objeto **JSON** seguido por uma quebra de linha (`\n`),
usada como delimitador entre mensagens no fluxo de bytes do TCP.

Tipos de mensagem trocados:

| Tipo            | Direção            | Finalidade                                  |
|-----------------|---------------------|----------------------------------------------|
| `join`          | cliente → servidor  | Entrar na sala com um nome                   |
| `draw`          | ambos                | Coordenadas de um traço desenhado            |
| `clear`         | ambos                | Limpar o quadro de desenho                   |
| `guess`         | cliente → servidor  | Enviar um palpite / mensagem de chat         |
| `chat`          | servidor → cliente  | Mensagem de chat retransmitida               |
| `system`        | servidor → cliente  | Avisos do sistema (entrou, saiu, acertou...) |
| `turn_started`  | servidor → cliente  | Início de rodada (para quem não desenha)     |
| `your_turn`     | servidor → cliente  | Início de rodada (revela a palavra ao desenhista) |
| `scoreboard`    | servidor → cliente  | Atualização do placar                        |

## Inovação do grupo

O material pesquisado como referência (ver PDF de apresentação) trazia
apenas um exemplo básico de **chat de texto** cliente/servidor. A partir
desse conceito, o grupo desenvolveu um **jogo colaborativo em tempo real**,
adicionando: protocolo estruturado em JSON, transmissão de desenho ao
vivo, sistema de turnos com rodízio automático, verificação de palpites
e pontuação no servidor, e temporizador de rodada. Os trechos de código
correspondentes a cada uma dessas adições estão comentados no código-fonte
com a marcação `MODIFICAÇÃO DO GRUPO`.
