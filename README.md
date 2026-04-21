# 🎮 Bot do Celso — Sorteador de Times LoL

Bot de Discord para sortear times de League of Legends com IA, balanceamento por rank e Fearless Draft.

---

## Pré-requisitos

- Python 3.11+
- Token do bot Discord → [discord.com/developers](https://discord.com/developers/applications)
- Chave da API Gemini → [aistudio.google.com](https://aistudio.google.com/app/apikey)
- Chave da Riot API *(opcional, para rank e fearless automático)* → [developer.riot.games](https://developer.riot.games)

---

## Instalação

```bash
# 1. Instale as dependências
pip install -r requirements.txt

# 2. Configure as variáveis de ambiente
cp .env.example .env
# Edite o .env e preencha os tokens
```

**.env:**
```
DISCORD_TOKEN=seu_token_aqui
GEMINI_API_KEY=sua_chave_gemini_aqui
RIOT_API_KEY=sua_chave_riot_aqui   # opcional
```

```bash
# 3. Rode
python bot.py
```

---

## Comandos

### 🎮 Sorteio & Série
| Comando | Descrição |
|---|---|
| `!sortear rift` | Sorteia times para Summoner's Rift (com lanes). Times ficam **fixos** durante a série |
| `!sortear aram` | Sorteia times para ARAM (sem lanes) |
| `!mover` | Envia os jogadores do lobby para as calls do sorteio atual |
| `!proxjogo time1/time2` | Registra quem venceu o jogo e mostra placar + fearless |
| `!serie` | Mostra o placar e os times da série em andamento |
| `!resetar` | Devolve todos ao lobby e encerra a série |

### 🏆 Rank
| Comando | Descrição |
|---|---|
| `!registrar Nome#TAG` | Vincula seu Riot ID ao Discord (ex: `!registrar Faker#BR1`) |
| `!rank [@jogador]` | Mostra o rank de alguém |
| `!atualizar` | Atualiza seu rank via Riot API |

### 🚫 Fearless Draft
| Comando | Descrição |
|---|---|
| `!fearless start` | Inicia uma nova série fearless |
| `!fearless add Jinx Thresh` | Registra campeões manualmente |
| `!fearless sync` | Puxa campeões da última partida via Riot API |
| `!fearless status` | Mostra os campeões já banidos |
| `!fearless reset` | Zera a série |

### 🛠️ Moderação
| Comando | Descrição |
|---|---|
| `!limpar [n]` | Apaga as últimas N mensagens do canal (padrão: 10, máx: 100) |
| `!ajuda` | Lista todos os comandos |

---

## Fluxo de um MD3

```
!sortear rift       → sorteia os times e inicia a série (0×0)
!mover              → envia jogadores para as calls

  [jogo 1]

!proxjogo time1     → registra vitória do Time 1, placar: 1×0
!mover              → jogo 2

  [jogo 2]

!proxjogo time2     → placar: 1×1
!mover              → jogo 3

  [jogo 3]

!proxjogo time1     → Time 1 vence a série! 🏆 2×1
!resetar            → todos pro lobby, série encerrada
```

---

## Canais de voz esperados no Discord

| Canal | Uso |
|---|---|
| `🏠 Lobby` | Onde os jogadores ficam antes do sorteio |
| `🏳️Time 1 - 3x3` / `🏴Time 2 - 3x3` | Partidas 3v3 |
| `🏳️Time 1 - 4x4` / `🏴Time 2 - 4x4` | Partidas 4v4 |
| `🏳️Time 1 - 5x5` / `🏴Time 2 - 5x5` | Partidas 5v5 |
| `escalação` *(texto)* | Canal onde o resultado é enviado |


> Os nomes precisam ser **exatos**, incluindo os emojis.

---
## Permissões necessárias no Discord

Em **OAuth2 → Scopes**: `bot`

Em **Bot → Permissions**:
- `Move Members`
- `Send Messages`
- `Manage Messages`
- `Read Message History`

Em **Bot → Privileged Gateway Intents**:
- `Server Members Intent` ✅
- `Message Content Intent` ✅

---

## Estrutura do projeto

```
├── bot.py                  # Entry point
├── config.py               # Constantes (nomes de canais, cores, etc.)
├── requirements.txt
├── .env                    # Tokens (não suba para o git!)
├── .env.example            # Modelo do .env
├── data/
│   └── jogadores.json      # Riot IDs e rank cache dos jogadores
├── cogs/
│   ├── sorteio.py          # !sortear !mover !resetar !proxjogo !serie
│   ├── moderacao.py        # !limpar
│   └── rank.py             # !registrar !rank !atualizar !fearless
└── utils/
    ├── gemini.py           # Prompts e chamadas à IA
    ├── formatacao.py       # Discord Embeds
    ├── balanceamento.py    # Algoritmo de balanceamento por MMR
    └── riot.py             # Riot Games API
<<<<<<< HEAD
```
=======
```
>>>>>>> 100af19 (projeto semi-finalizado)
