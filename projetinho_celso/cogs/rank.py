import discord
from discord.ext import commands
from utils import riot
from utils.balanceamento import rank_para_mmr
from utils.formatacao import embed_rank, embed_status_fearless
import json
import os

DATA_PATH = os.path.join('data', 'jogadores.json')


def _carregar() -> dict:
    if os.path.exists(DATA_PATH):
        with open(DATA_PATH, encoding='utf-8') as f:
            return json.load(f)
    return {}


def _salvar(dados: dict):
    os.makedirs('data', exist_ok=True)
    with open(DATA_PATH, 'w', encoding='utf-8') as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)


class Rank(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ── !registrar ───────────────────────────────────────────────────────────

    @commands.command(name='registrar')
    async def registrar(self, ctx, *, riot_id: str = ''):
        """Vincula seu Discord ao seu Riot ID (ex: !registrar Faker#BR1)"""
        if not riot_id or '#' not in riot_id:
            await ctx.send('❌ Use: `!registrar NomeDeInvocador#TAG`\nEx: `!registrar Faker#BR1`')
            return

        if not riot.api_configurada():
            await ctx.send('⚠️ A Riot API ainda não está configurada. Aguarde!')
            return

        await ctx.send(f'⏳ Buscando dados de **{riot_id}**...')

        puuid = await riot.buscar_puuid(riot_id)
        if not puuid:
            await ctx.send(f'❌ Riot ID **{riot_id}** não encontrado. Verifique o nome e a tag.')
            return

        rank_info = await riot.buscar_rank(puuid)

        dados = _carregar()
        guild_key = str(ctx.guild.id)
        user_key  = str(ctx.author.id)

        if guild_key not in dados:
            dados[guild_key] = {}

        dados[guild_key][user_key] = {
            'riot_id': riot_id,
            'puuid':   puuid,
            'rank':    rank_info,
        }
        _salvar(dados)

        if rank_info:
            mmr = rank_para_mmr(rank_info['tier'], rank_info.get('rank', 'IV'), rank_info.get('lp', 0))
            rank_info['mmr'] = mmr
            emb = embed_rank(ctx.author.display_name, riot_id, rank_info)
            await ctx.send(f'✅ **{ctx.author.display_name}** registrado!', embed=emb)
        else:
            await ctx.send(
                f'✅ **{ctx.author.display_name}** registrado como **{riot_id}**.\n'
                f'ℹ️ Sem rank na fila solo/duo — será tratado como Unranked no sorteio.'
            )

    # ── !rank ─────────────────────────────────────────────────────────────────

    @commands.command(name='rank')
    async def ver_rank(self, ctx, membro: discord.Member = None):
        """Mostra o rank de um jogador registrado."""
        alvo = membro or ctx.author
        dados = _carregar()
        info  = dados.get(str(ctx.guild.id), {}).get(str(alvo.id))

        if not info:
            quem = 'Você não está' if alvo == ctx.author else f'**{alvo.display_name}** não está'
            await ctx.send(f'❌ {quem} registrado. Use `!registrar NomeDeInvocador#TAG`')
            return

        rank_info = info.get('rank')
        riot_id   = info.get('riot_id', '?')

        if not rank_info:
            await ctx.send(f'ℹ️ **{alvo.display_name}** (`{riot_id}`) está sem rank na fila solo/duo.')
            return

        mmr = rank_para_mmr(rank_info['tier'], rank_info.get('rank', 'IV'), rank_info.get('lp', 0))
        rank_info['mmr'] = mmr
        emb = embed_rank(alvo.display_name, riot_id, rank_info)
        await ctx.send(embed=emb)

    # ── !atualizar ────────────────────────────────────────────────────────────

    @commands.command(name='atualizar')
    async def atualizar(self, ctx):
        """Atualiza seu rank na Riot API."""
        if not riot.api_configurada():
            await ctx.send('⚠️ A Riot API ainda não está configurada.')
            return

        dados = _carregar()
        info  = dados.get(str(ctx.guild.id), {}).get(str(ctx.author.id))

        if not info:
            await ctx.send('❌ Você não está registrado. Use `!registrar NomeDeInvocador#TAG`')
            return

        await ctx.send('⏳ Atualizando rank...')
        rank_info = await riot.buscar_rank(info['puuid'])
        info['rank'] = rank_info
        _salvar(dados)

        if rank_info:
            mmr = rank_para_mmr(rank_info['tier'], rank_info.get('rank', 'IV'), rank_info.get('lp', 0))
            rank_info['mmr'] = mmr
            emb = embed_rank(ctx.author.display_name, info['riot_id'], rank_info)
            await ctx.send('✅ Rank atualizado!', embed=emb)
        else:
            await ctx.send('✅ Atualizado — sem rank na fila solo/duo.')

    # ── Fearless Draft ────────────────────────────────────────────────────────
    # Estado: { guild_id: { "serie": int, "usados": [str] } }
    _fearless: dict[int, dict] = {}

    @commands.group(name='fearless', invoke_without_command=True)
    async def fearless(self, ctx):
        await ctx.send(
            '**Subcomandos do Fearless Draft:**\n'
            '`!fearless start`   — Inicia uma nova série\n'
            '`!fearless add NomeCampeão NomeCampeão2 ...` — Registra campeões manualmente\n'
            '`!fearless sync`    — Puxa campeões da última partida via Riot API\n'
            '`!fearless status`  — Mostra campeões já banidos\n'
            '`!fearless reset`   — Zera a série atual'
        )

    @fearless.command(name='start')
    async def fearless_start(self, ctx):
        serie_anterior = self._fearless.get(ctx.guild.id, {}).get('serie', 0)
        self._fearless[ctx.guild.id] = {'serie': serie_anterior + 1, 'usados': []}
        await ctx.send(f'🎮 Fearless Draft iniciado! **Série #{serie_anterior + 1}** começando.')

    @fearless.command(name='add')
    async def fearless_add(self, ctx, *campeoes: str):
        if not campeoes:
            await ctx.send('❌ Informe ao menos um campeão. Ex: `!fearless add Jinx Thresh`')
            return
        estado = self._fearless.setdefault(ctx.guild.id, {'serie': 1, 'usados': []})
        novos  = [c.capitalize() for c in campeoes if c.capitalize() not in estado['usados']]
        estado['usados'].extend(novos)
        emb = embed_status_fearless(estado['usados'], estado['serie'])
        await ctx.send(f'✅ {len(novos)} campeão(s) adicionado(s)!', embed=emb)

    @fearless.command(name='sync')
    async def fearless_sync(self, ctx):
        if not riot.api_configurada():
            await ctx.send('⚠️ Riot API não configurada. Use `!fearless add` manualmente.')
            return

        dados  = _carregar()
        guild  = dados.get(str(ctx.guild.id), {})
        estado = self._fearless.setdefault(ctx.guild.id, {'serie': 1, 'usados': []})

        await ctx.send('⏳ Buscando última partida dos jogadores registrados...')

        encontrados = []
        for user_data in guild.values():
            puuid = user_data.get('puuid')
            if puuid:
                camps = await riot.buscar_campeoes_ultima_partida(puuid)
                for c in camps:
                    if c not in estado['usados'] and c not in encontrados:
                        encontrados.append(c)

        if not encontrados:
            await ctx.send('ℹ️ Nenhum campeão novo encontrado na última partida.')
            return

        estado['usados'].extend(encontrados)
        emb = embed_status_fearless(estado['usados'], estado['serie'])
        await ctx.send(f'✅ {len(encontrados)} campeão(s) adicionado(s) via Riot API!', embed=emb)

    @fearless.command(name='status')
    async def fearless_status(self, ctx):
        estado = self._fearless.get(ctx.guild.id, {'serie': 1, 'usados': []})
        emb    = embed_status_fearless(estado['usados'], estado['serie'])
        await ctx.send(embed=emb)

    @fearless.command(name='reset')
    async def fearless_reset(self, ctx):
        self._fearless.pop(ctx.guild.id, None)
        await ctx.send('🔄 Série resetada! Use `!fearless start` para começar uma nova.')


async def setup(bot):
    await bot.add_cog(Rank(bot))
