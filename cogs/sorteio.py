import discord
from discord.ext import commands
from config import CANAL_LOBBY, CANAL_ESCALACAO, TAMANHOS
from utils.gemini import gerar_sorteio, gerar_sorteio_balanceado
from utils.formatacao import embed_rift, embed_aram, embed_serie
from utils.balanceamento import montar_lista_mmr, balancear_times
from utils.riot import api_configurada
import json
import os

# ─── estado em memória ──────────────────────────────────────────────────────
# { guild_id: { "mapa_canal": {nome_norm: channel_id}, "tamanho": str,
#               "time1_nomes": [...], "time2_nomes": [...] } }
_ultimo_sorteio: dict[int, dict] = {}

# { guild_id: { "time1_wins": int, "time2_wins": int, "jogos": int } }
_serie: dict[int, dict] = {}


def _normalizar(nome: str) -> str:
    return nome.strip().lower()


def _get_canais_times(guild, tamanho: str):
    nome_t1 = f'🏳️ Time 1 - {tamanho}'
    nome_t2 = f'🏴 Time 2 - {tamanho}'
    return (
        discord.utils.get(guild.voice_channels, name=nome_t1),
        discord.utils.get(guild.voice_channels, name=nome_t2),
        nome_t1, nome_t2,
    )


def _carregar_jogadores() -> dict:
    path = os.path.join('data', 'jogadores.json')
    if os.path.exists(path):
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    return {}


def _mapa_nomes_rift(data, ch_time1, ch_time2) -> tuple[dict, list, list]:
    m, t1_nomes, t2_nomes = {}, [], []
    for info in data['time1'].values():
        nome = info.get('jogador', 'vazio')
        if nome != 'vazio':
            m[_normalizar(nome)] = ch_time1
            t1_nomes.append(nome)
    for info in data['time2'].values():
        nome = info.get('jogador', 'vazio')
        if nome != 'vazio':
            m[_normalizar(nome)] = ch_time2
            t2_nomes.append(nome)
    return m, t1_nomes, t2_nomes


def _mapa_nomes_aram(data, ch_time1, ch_time2) -> tuple[dict, list, list]:
    m, t1_nomes, t2_nomes = {}, [], []
    for entry in data.get('time1', []):
        m[_normalizar(entry['jogador'])] = ch_time1
        t1_nomes.append(entry['jogador'])
    for entry in data.get('time2', []):
        m[_normalizar(entry['jogador'])] = ch_time2
        t2_nomes.append(entry['jogador'])
    return m, t1_nomes, t2_nomes


async def _mover_jogadores(guild, sorteio: dict) -> tuple[int, list]:
    """Move jogadores do lobby para os canais salvos. Retorna (movidos, nao_movidos)."""
    lobby = discord.utils.get(guild.voice_channels, name=CANAL_LOBBY)
    if not lobby:
        return 0, []

    mapa_canal = sorteio['mapa_canal']
    movidos, nao_movidos = 0, []
    for membro in lobby.members:
        channel_id = mapa_canal.get(_normalizar(membro.display_name))
        if channel_id:
            canal_destino = guild.get_channel(channel_id)
            if canal_destino:
                await membro.move_to(canal_destino)
                movidos += 1
                continue
        nao_movidos.append(membro.display_name)
    return movidos, nao_movidos


class Sorteio(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ── !sortear ─────────────────────────────────────────────────────────────

    @commands.command(name='sortear')
    async def sortear(self, ctx, mapa: str = 'rift'):
        mapa = mapa.lower()
        if mapa not in ('rift', 'aram'):
            await ctx.send('❌ Mapa inválido!\nUse `!sortear rift` ou `!sortear aram`')
            return

        guild        = ctx.guild
        lobby        = discord.utils.get(guild.voice_channels, name=CANAL_LOBBY)
        ch_escalacao = discord.utils.get(guild.text_channels,  name=CANAL_ESCALACAO)

        if not lobby:
            await ctx.send(f'❌ Canal de voz **{CANAL_LOBBY}** não encontrado!')
            return

        membros = lobby.members
        n       = len(membros)

        if n < 2:
            await ctx.send(f'❌ Precisa de pelo menos **2 jogadores** no lobby! Atualmente: **{n}**')
            return
        if n % 2 != 0:
            await ctx.send(f'❌ Precisa de número **par** de jogadores! Atualmente: **{n}**')
            return

        tamanho = TAMANHOS.get(n)
        if not tamanho:
            suportados = ' / '.join(str(k) for k in TAMANHOS)
            await ctx.send(f'❌ **{n}** jogadores não suportado. Aceitos: **{suportados}**')
            return

        ch_time1, ch_time2, nome_t1, nome_t2 = _get_canais_times(guild, tamanho)
        if not ch_time1:
            await ctx.send(f'❌ Canal **{nome_t1}** não encontrado!')
            return
        if not ch_time2:
            await ctx.send(f'❌ Canal **{nome_t2}** não encontrado!')
            return

        await ctx.send(f'⏳ Sorteando times para **{mapa.upper()} {tamanho}**...')

        try:
            mmr_diff   = None
            dados_rank = _carregar_jogadores()
            tem_ranks  = bool(dados_rank.get(str(guild.id)))

            if mapa == 'rift' and api_configurada() and tem_ranks:
                lista_mmr            = montar_lista_mmr(membros, dados_rank, guild.id)
                t1_mmr, t2_mmr, mmr_diff = balancear_times(lista_mmr)
                data                 = gerar_sorteio_balanceado(
                    [j['nome'] for j in t1_mmr], [j['nome'] for j in t2_mmr]
                )
            else:
                nomes = [m.display_name for m in membros]
                data  = gerar_sorteio(nomes, mapa)

            if mapa == 'rift':
                emb                       = embed_rift(data, tamanho, mmr_diff)
                mapa_canal, t1_nomes, t2_nomes = _mapa_nomes_rift(data, ch_time1, ch_time2)
            else:
                emb                       = embed_aram(data, tamanho)
                mapa_canal, t1_nomes, t2_nomes = _mapa_nomes_aram(data, ch_time1, ch_time2)

            canal_resultado = ch_escalacao or ctx.channel
            await canal_resultado.send(embed=emb)

            # Salva o sorteio e inicia a série
            _ultimo_sorteio[guild.id] = {
                'mapa_canal':  {nome: canal.id for nome, canal in mapa_canal.items()},
                'tamanho':     tamanho,
                'time1_nomes': t1_nomes,
                'time2_nomes': t2_nomes,
            }
            _serie[guild.id] = {'time1_wins': 0, 'time2_wins': 0, 'jogos': 0}

            await ctx.send(
                '✅ Sorteio salvo! Os times ficam **fixos durante toda a série**.\n'
                'Use `!mover` para enviar os jogadores, `!proxjogo` para registrar resultados.'
            )

        except Exception as e:
            await ctx.send(f'❌ Erro: {e}')

    # ── !mover ────────────────────────────────────────────────────────────────

    @commands.command(name='mover')
    async def mover(self, ctx):
        sorteio = _ultimo_sorteio.get(ctx.guild.id)
        if not sorteio:
            await ctx.send('❌ Nenhum sorteio salvo! Use `!sortear` primeiro.')
            return

        lobby = discord.utils.get(ctx.guild.voice_channels, name=CANAL_LOBBY)
        if not lobby or not lobby.members:
            await ctx.send(f'❌ Nenhum jogador no **{CANAL_LOBBY}** para mover.')
            return

        movidos, nao_movidos = await _mover_jogadores(ctx.guild, sorteio)

        if movidos:
            await ctx.send(f'✅ {movidos} jogador(es) enviado(s) para as calls!')
        if nao_movidos:
            lista = ', '.join(f'**{n}**' for n in nao_movidos)
            await ctx.send(f'⚠️ Não foi possível mover: {lista}')

    # ── !proxjogo ─────────────────────────────────────────────────────────────

    @commands.command(name='proxjogo')
    async def proxjogo(self, ctx, vencedor: str = ''):
        """Registra o vencedor do jogo anterior e prepara o próximo.
        Uso: !proxjogo time1  |  !proxjogo time2  |  !proxjogo (sem registrar)
        """
        guild   = ctx.guild
        sorteio = _ultimo_sorteio.get(guild.id)

        if not sorteio:
            await ctx.send('❌ Nenhuma série em andamento. Use `!sortear` primeiro.')
            return

        serie = _serie.setdefault(guild.id, {'time1_wins': 0, 'time2_wins': 0, 'jogos': 0})

        # Registra o vencedor se informado
        if vencedor.lower() in ('time1', 'time 1', '1'):
            serie['time1_wins'] += 1
            serie['jogos']      += 1
        elif vencedor.lower() in ('time2', 'time 2', '2'):
            serie['time2_wins'] += 1
            serie['jogos']      += 1
        elif vencedor:
            await ctx.send('❌ Use `!proxjogo time1` ou `!proxjogo time2`')
            return

        # Pega fearless do cog de rank
        rank_cog     = self.bot.cogs.get('Rank')
        fearless_info = None
        if rank_cog:
            estado = rank_cog._fearless.get(guild.id)
            if estado:
                fearless_info = estado

        emb = embed_serie(sorteio, serie, fearless_info)
        ch_escalacao = discord.utils.get(guild.text_channels, name=CANAL_ESCALACAO)
        canal = ch_escalacao or ctx.channel
        await canal.send(embed=emb)

        # Verifica se a série foi decidida (MD3 = primeiro a 2)
        if serie['time1_wins'] >= 2:
            await canal.send('🏆 **Time 1 venceu a série!** GG WP\nUse `!resetar` para voltar ao lobby.')
        elif serie['time2_wins'] >= 2:
            await canal.send('🏆 **Time 2 venceu a série!** GG WP\nUse `!resetar` para voltar ao lobby.')

    # ── !serie ────────────────────────────────────────────────────────────────

    @commands.group(name='serie', invoke_without_command=True)
    async def serie(self, ctx):
        guild   = ctx.guild
        sorteio = _ultimo_sorteio.get(guild.id)

        if not sorteio:
            await ctx.send('❌ Nenhuma série em andamento. Use `!sortear` primeiro.')
            return

        serie        = _serie.get(guild.id, {'time1_wins': 0, 'time2_wins': 0, 'jogos': 0})
        rank_cog     = self.bot.cogs.get('Rank')
        fearless_info = rank_cog._fearless.get(guild.id) if rank_cog else None

        emb = embed_serie(sorteio, serie, fearless_info)
        await ctx.send(embed=emb)

    # ── !resetar ──────────────────────────────────────────────────────────────

    @commands.command(name='resetar')
    async def resetar(self, ctx):
        guild = ctx.guild
        lobby = discord.utils.get(guild.voice_channels, name=CANAL_LOBBY)

        if not lobby:
            await ctx.send(f'❌ Canal **{CANAL_LOBBY}** não encontrado!')
            return

        membros_para_mover = []
        for tamanho in TAMANHOS.values():
            for prefixo in ('🏳️ Time 1', '🏴 Time 2'):
                canal = discord.utils.get(guild.voice_channels, name=f'{prefixo} - {tamanho}')
                if canal:
                    membros_para_mover.extend(canal.members)

        if not membros_para_mover:
            await ctx.send('ℹ️ Nenhum jogador nos canais dos times para resetar.')
            return

        movidos = 0
        for membro in membros_para_mover:
            try:
                await membro.move_to(lobby)
                movidos += 1
            except Exception:
                pass

        # Limpa o estado da série
        _ultimo_sorteio.pop(guild.id, None)
        _serie.pop(guild.id, None)

        await ctx.send(f'✅ {movidos} jogador(es) de volta ao **{CANAL_LOBBY}**! Série encerrada.')


async def setup(bot):
    await bot.add_cog(Sorteio(bot))
