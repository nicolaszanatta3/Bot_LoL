import discord
from discord.ext import commands
from config import CANAL_LOBBY, CANAL_ESCALACAO, TAMANHOS
from utils.gemini import gerar_sorteio, gerar_sorteio_balanceado, gerar_campeoes
from utils.formatacao import embed_rift, embed_aram, embed_serie
from utils.balanceamento import montar_lista_mmr, balancear_times
from utils.riot import api_configurada
import json
import os

# ─── estado em memória ──────────────────────────────────────────────────────
_ultimo_sorteio: dict[int, dict] = {}
_serie:          dict[int, dict] = {}


def _normalizar(nome: str) -> str:
    return nome.strip().lower()


def _get_canais_times(guild, tamanho: str):
    nome_t1 = f'🏳️Time 1 - {tamanho}'
    nome_t2 = f'🏴Time 2 - {tamanho}'
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


# ─── View de Ready Check ──────────────────────────────────────────────────────

class ViewReadyCheck(discord.ui.View):
    def __init__(self, guild, sorteio: dict, autor_id: int):
        super().__init__(timeout=120)
        self.guild    = guild
        self.sorteio  = sorteio
        self.autor_id = autor_id
        self.prontos: set[str] = set()   # nomes normalizados que confirmaram
        self.message  = None

        lobby      = discord.utils.get(guild.voice_channels, name=CANAL_LOBBY)
        mapa_canal = sorteio.get('mapa_canal', {})

        # Jogadores válidos = estão no lobby E participaram do sorteio
        self.jogadores_validos: dict[str, discord.Member] = {}
        self.fora_do_sorteio: list[str] = []

        if lobby:
            for membro in lobby.members:
                nome_norm = _normalizar(membro.display_name)
                if nome_norm in mapa_canal:
                    self.jogadores_validos[nome_norm] = membro
                else:
                    self.fora_do_sorteio.append(membro.display_name)

    def _build_embed(self) -> discord.Embed:
        total   = len(self.jogadores_validos)
        prontos = len(self.prontos)

        todos_prontos = prontos >= total and total > 0

        embed = discord.Embed(
            title='🎮  READY CHECK',
            description='Clique em **✅ Estou Pronto!** para confirmar sua presença.',
            color=0x2ECC71 if todos_prontos else 0xF1C40F,
        )

        linhas = []
        for nome_norm, membro in self.jogadores_validos.items():
            icone = '✅' if nome_norm in self.prontos else '⬜'
            linhas.append(f'{icone}  **{membro.display_name}**')

        if not linhas:
            linhas.append('*Nenhum jogador do sorteio está no lobby.*')

        embed.add_field(
            name=f'Jogadores  ({prontos}/{total})',
            value='\n'.join(linhas),
            inline=False,
        )

        if self.fora_do_sorteio:
            embed.add_field(
                name='⚠️ Não participam deste sorteio',
                value='\n'.join(f'• {n}' for n in self.fora_do_sorteio),
                inline=False,
            )

        if todos_prontos:
            embed.set_footer(text='Todos prontos! Movendo para as calls...')
        else:
            embed.set_footer(text='Aguardando todos confirmarem... (2 min)')

        return embed

    @discord.ui.button(label='✅ Estou Pronto!', style=discord.ButtonStyle.success)
    async def pronto(self, interaction: discord.Interaction, _: discord.ui.Button):
        nome_norm = _normalizar(interaction.user.display_name)

        if nome_norm not in self.jogadores_validos:
            await interaction.response.send_message(
                '❌ Você não faz parte do sorteio atual.', ephemeral=True
            )
            return

        if nome_norm in self.prontos:
            await interaction.response.send_message(
                '✅ Você já confirmou presença!', ephemeral=True
            )
            return

        self.prontos.add(nome_norm)
        todos_prontos = len(self.prontos) >= len(self.jogadores_validos)

        await interaction.response.edit_message(
            embed=self._build_embed(),
            view=None if todos_prontos else self,
        )

        if todos_prontos:
            self.stop()
            await self._iniciar_jogo(interaction.channel)

    @discord.ui.button(label='🚀 Iniciar Agora', style=discord.ButtonStyle.danger)
    async def iniciar_agora(self, interaction: discord.Interaction, _: discord.ui.Button):
        is_admin = (
            interaction.user.guild_permissions.administrator
            or interaction.user.id == self.autor_id
        )
        if not is_admin:
            await interaction.response.send_message(
                '❌ Apenas o organizador ou um administrador pode forçar o início.',
                ephemeral=True,
            )
            return

        self.stop()
        await interaction.response.edit_message(embed=self._build_embed(), view=None)
        await self._iniciar_jogo(interaction.channel)

    async def _iniciar_jogo(self, channel):
        movidos, nao_movidos = await _mover_jogadores(self.guild, self.sorteio)

        embed = discord.Embed(
            title='🚀  O JOGO VAI COMEÇAR!',
            description='Todos os jogadores foram enviados para suas calls.\n**Boa sorte e bom jogo!** 🎮',
            color=0x2ECC71,
        )
        if movidos:
            embed.add_field(name='Movidos', value=str(movidos), inline=True)
        if nao_movidos:
            embed.add_field(
                name='⚠️ Não foi possível mover',
                value=', '.join(f'**{n}**' for n in nao_movidos),
                inline=False,
            )

        await channel.send(embed=embed)

    async def on_timeout(self):
        try:
            embed = self._build_embed()
            embed.color     = 0xE74C3C
            embed.set_footer(text='⏱️ Tempo esgotado. Use !mover novamente.')
            await self.message.edit(embed=embed, view=None)
        except Exception:
            pass


async def _executar_sorteio(ctx, mapa: str, membros, tamanho: str,
                             ch_time1, ch_time2, quarta_rota: str | None = None,
                             formato: str = 'md3'):
    """Lógica central de sorteio — chamada pelo comando e pelos botões do 4x4."""
    guild        = ctx.guild
    ch_escalacao = discord.utils.get(guild.text_channels, name=CANAL_ESCALACAO)

    try:
        mmr_diff   = None
        dados_rank = _carregar_jogadores()
        tem_ranks  = bool(dados_rank.get(str(guild.id)))

        if mapa == 'rift' and api_configurada() and tem_ranks:
            lista_mmr                = montar_lista_mmr(membros, dados_rank, guild.id)
            t1_mmr, t2_mmr, mmr_diff = balancear_times(lista_mmr)
            data = gerar_sorteio_balanceado(
                [j['nome'] for j in t1_mmr], [j['nome'] for j in t2_mmr],
                quarta_rota=quarta_rota,
            )
        else:
            nomes = [m.display_name for m in membros]
            data  = gerar_sorteio(nomes, mapa, quarta_rota=quarta_rota)

        if mapa == 'rift':
            emb                            = embed_rift(data, tamanho, mmr_diff)
            mapa_canal, t1_nomes, t2_nomes = _mapa_nomes_rift(data, ch_time1, ch_time2)
        else:
            emb                            = embed_aram(data, tamanho)
            mapa_canal, t1_nomes, t2_nomes = _mapa_nomes_aram(data, ch_time1, ch_time2)

        canal_resultado = ch_escalacao or ctx.channel
        await canal_resultado.send(embed=emb)

        # Guarda rotas de cada jogador para uso no !campeoes
        rotas_jogadores = {}
        if mapa == 'rift':
            for rota, info in data['time1'].items():
                nome = info.get('jogador', 'vazio')
                if nome != 'vazio':
                    rotas_jogadores[nome] = rota
            for rota, info in data['time2'].items():
                nome = info.get('jogador', 'vazio')
                if nome != 'vazio':
                    rotas_jogadores[nome] = rota

        _ultimo_sorteio[guild.id] = {
            'mapa_canal':       {nome: canal.id for nome, canal in mapa_canal.items()},
            'tamanho':          tamanho,
            'time1_nomes':      t1_nomes,
            'time2_nomes':      t2_nomes,
            'rotas_jogadores':  rotas_jogadores,
            'pick_mode':        None,
        }
        wins_needed = 3 if formato == 'md5' else 2
        _serie[guild.id] = {
            'time1_wins':  0,
            'time2_wins':  0,
            'jogos':       0,
            'formato':     formato.upper(),
            'wins_needed': wins_needed,
        }

        await ctx.send(
            '✅ Sorteio salvo! Times fixos para toda a série.\n'
            'Use `!mover` para enviar os jogadores, `!proxjogo` para registrar resultados.'
        )

        if mapa == 'rift':
            view = ViewModoPick(guild.id, ctx)
            msg  = await ctx.send('🏆 **Como vão ser escolhidos os campeões?**', view=view)
            view.message = msg
    except Exception as e:
        await ctx.send(f'❌ Erro: {e}')


# ─── View de modo de pick de campeões ────────────────────────────────────────

async def _enviar_picks(ctx, guild_id: int):
    """Gera e envia os picks aleatórios da IA."""
    sorteio = _ultimo_sorteio.get(guild_id, {})
    rotas   = sorteio.get('rotas_jogadores', {})

    rank_cog = ctx.bot.cogs.get('Rank')
    banidos  = []
    if rank_cog:
        banidos = rank_cog._fearless.get(guild_id, {}).get('usados', [])

    picks = gerar_campeoes(rotas, banidos)

    t1_nomes = sorteio.get('time1_nomes', [])
    t2_nomes = sorteio.get('time2_nomes', [])

    embed = discord.Embed(title='🎲  PICKS ALEATÓRIOS', color=0xC89B3C)
    embed.add_field(
        name='🏳️  Time 1',
        value='\n'.join(
            f'**{n}** → {picks.get(n, {}).get("campeao", "?")}  *{picks.get(n, {}).get("comentario", "")}*'
            for n in t1_nomes if n in picks
        ) or '—',
        inline=False,
    )
    embed.add_field(
        name='🏴  Time 2',
        value='\n'.join(
            f'**{n}** → {picks.get(n, {}).get("campeao", "?")}  *{picks.get(n, {}).get("comentario", "")}*'
            for n in t2_nomes if n in picks
        ) or '—',
        inline=False,
    )
    if banidos:
        embed.set_footer(text=f'🚫 Fearless: {", ".join(banidos)}')

    ch_escalacao = discord.utils.get(ctx.guild.text_channels, name=CANAL_ESCALACAO)
    await (ch_escalacao or ctx.channel).send(embed=embed)


class ViewModoPick(discord.ui.View):
    def __init__(self, guild_id: int, ctx):
        super().__init__(timeout=60)
        self.guild_id = guild_id
        self.ctx      = ctx

    @discord.ui.button(label='🎲 Aleatório (IA)', style=discord.ButtonStyle.primary)
    async def aleatorio(self, interaction: discord.Interaction, _: discord.ui.Button):
        _ultimo_sorteio.get(self.guild_id, {})['pick_mode'] = 'aleatorio'
        self.stop()
        await interaction.response.edit_message(content='⏳ Sorteando campeões...', view=None)
        try:
            await _enviar_picks(self.ctx, self.guild_id)
        except Exception as e:
            await interaction.followup.send(f'❌ Erro ao sortear campeões: {e}')

    @discord.ui.button(label='⚔️ Draft manual', style=discord.ButtonStyle.secondary)
    async def manual(self, interaction: discord.Interaction, _: discord.ui.Button):
        _ultimo_sorteio.get(self.guild_id, {})['pick_mode'] = 'manual'
        self.stop()
        await interaction.response.edit_message(
            content='⚔️ **Draft manual!**  Cheque `!fearless status` antes de entrar na seleção.',
            view=None,
        )

    async def on_timeout(self):
        _ultimo_sorteio.get(self.guild_id, {})['pick_mode'] = 'manual'
        try:
            await self.message.edit(content='⏱️ Sem resposta — assumindo **draft manual**.', view=None)
        except Exception:
            pass


# ─── View de botões para escolha da 4ª rota (4x4) ───────────────────────────

class View4x4(discord.ui.View):
    def __init__(self, ctx, membros, tamanho, ch_time1, ch_time2, formato: str):
        super().__init__(timeout=30)
        self.ctx       = ctx
        self.membros   = membros
        self.tamanho   = tamanho
        self.ch_time1  = ch_time1
        self.ch_time2  = ch_time2
        self.formato   = formato

    async def _sortear(self, interaction: discord.Interaction, quarta_rota: str):
        await interaction.response.edit_message(
            content=f'⏳ Sorteando com **Top · Mid · ADC · {quarta_rota.capitalize()}**...',
            view=None,
        )
        await _executar_sorteio(
            self.ctx, 'rift', self.membros, self.tamanho,
            self.ch_time1, self.ch_time2,
            quarta_rota=quarta_rota, formato=self.formato,
        )

    @discord.ui.button(label='🌿 Jungle', style=discord.ButtonStyle.primary)
    async def jungle(self, interaction: discord.Interaction, _: discord.ui.Button):
        await self._sortear(interaction, 'jungle')

    @discord.ui.button(label='🛡️ Support', style=discord.ButtonStyle.secondary)
    async def support(self, interaction: discord.Interaction, _: discord.ui.Button):
        await self._sortear(interaction, 'support')

    async def on_timeout(self):
        try:
            await self.message.edit(content='⏱️ Tempo esgotado. Use `!sortear rift` de novo.', view=None)
        except Exception:
            pass


# ─── Cog ─────────────────────────────────────────────────────────────────────

class Sorteio(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='sortear')
    async def sortear(self, ctx, mapa: str = 'rift', formato: str = 'md3'):
        mapa    = mapa.lower()
        formato = formato.lower()
        if mapa not in ('rift', 'aram'):
            await ctx.send('❌ Mapa inválido!\nUse `!sortear rift` ou `!sortear aram`')
            return
        if formato not in ('md3', 'md5'):
            await ctx.send('❌ Formato inválido!\nUse `md3` ou `md5`. Ex: `!sortear rift md5`')
            return

        guild   = ctx.guild
        lobby   = discord.utils.get(guild.voice_channels, name=CANAL_LOBBY)

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

        # 3x3 → top, mid, adc (direto)
        if tamanho == '3x3':
            await ctx.send(f'⏳ Sorteando times para **RIFT 3x3 {formato.upper()}** (Top · Mid · ADC)...')
            await _executar_sorteio(ctx, mapa, membros, tamanho, ch_time1, ch_time2, formato=formato)

        # 4x4 → pergunta a 4ª rota com botões
        elif tamanho == '4x4' and mapa == 'rift':
            view = View4x4(ctx, membros, tamanho, ch_time1, ch_time2, formato=formato)
            msg = await ctx.send(
                '**4x4 detectado!** Qual será a **4ª rota**?\n'
                'Rotas fixas: Top · Mid · ADC  +',
                view=view,
            )
            view.message = msg

        # 5x5 ou aram → sorteio normal
        else:
            await ctx.send(f'⏳ Sorteando times para **{mapa.upper()} {tamanho} {formato.upper()}**...')
            await _executar_sorteio(ctx, mapa, membros, tamanho, ch_time1, ch_time2, formato=formato)

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

        view = ViewReadyCheck(ctx.guild, sorteio, ctx.author.id)

        if not view.jogadores_validos:
            await ctx.send(
                f'❌ Nenhum jogador do sorteio está no **{CANAL_LOBBY}**.\n'
                'Certifique-se de que os jogadores estão na call antes de usar `!mover`.'
            )
            return

        msg        = await ctx.send(embed=view._build_embed(), view=view)
        view.message = msg

    @commands.command(name='campeoes')
    async def campeoes(self, ctx):
        sorteio = _ultimo_sorteio.get(ctx.guild.id)

        if not sorteio:
            await ctx.send('❌ Nenhum sorteio ativo. Use `!sortear rift` primeiro.')
            return

        if sorteio.get('pick_mode') != 'aleatorio':
            await ctx.send('❌ O modo de pick desta série é **draft manual**.\nPara usar picks aleatórios, inicie uma nova série e escolha 🎲 Aleatório.')
            return

        rotas = sorteio.get('rotas_jogadores', {})
        if not rotas:
            await ctx.send('❌ Rotas não encontradas. Refaça o sorteio.')
            return

        rank_cog = self.bot.cogs.get('Rank')
        banidos  = []
        if rank_cog:
            estado  = rank_cog._fearless.get(ctx.guild.id, {})
            banidos = estado.get('usados', [])

        await ctx.send('⏳ Sorteando campeões...')

        try:
            picks = gerar_campeoes(rotas, banidos)

            t1_nomes = sorteio.get('time1_nomes', [])
            t2_nomes = sorteio.get('time2_nomes', [])

            embed = discord.Embed(title='🎲  PICKS ALEATÓRIOS', color=0xC89B3C)

            t1_txt = '\n'.join(
                f'**{n}** → {picks.get(n, {}).get("campeao", "?")}  *{picks.get(n, {}).get("comentario", "")}*'
                for n in t1_nomes if n in picks
            )
            t2_txt = '\n'.join(
                f'**{n}** → {picks.get(n, {}).get("campeao", "?")}  *{picks.get(n, {}).get("comentario", "")}*'
                for n in t2_nomes if n in picks
            )

            embed.add_field(name='🏳️  Time 1', value=t1_txt or '—', inline=False)
            embed.add_field(name='🏴  Time 2', value=t2_txt or '—', inline=False)

            if banidos:
                embed.set_footer(text=f'🚫 Fearless: {", ".join(banidos)}')

            ch_escalacao = discord.utils.get(ctx.guild.text_channels, name=CANAL_ESCALACAO)
            await (ch_escalacao or ctx.channel).send(embed=embed)

        except Exception as e:
            await ctx.send(f'❌ Erro ao gerar picks: {e}')

    @commands.command(name='proxjogo')
    async def proxjogo(self, ctx, vencedor: str = ''):
        guild   = ctx.guild
        sorteio = _ultimo_sorteio.get(guild.id)

        if not sorteio:
            await ctx.send('❌ Nenhuma série em andamento. Use `!sortear` primeiro.')
            return

        serie = _serie.setdefault(guild.id, {'time1_wins': 0, 'time2_wins': 0, 'jogos': 0})

        if vencedor.lower() in ('time1', 'time 1', '1'):
            serie['time1_wins'] += 1
            serie['jogos']      += 1
        elif vencedor.lower() in ('time2', 'time 2', '2'):
            serie['time2_wins'] += 1
            serie['jogos']      += 1
        elif vencedor:
            await ctx.send('❌ Use `!proxjogo time1` ou `!proxjogo time2`')
            return

        rank_cog      = self.bot.cogs.get('Rank')
        fearless_info = rank_cog._fearless.get(guild.id) if rank_cog else None

        emb = embed_serie(sorteio, serie, fearless_info)
        ch_escalacao = discord.utils.get(guild.text_channels, name=CANAL_ESCALACAO)
        await (ch_escalacao or ctx.channel).send(embed=emb)

        wins_needed = serie.get('wins_needed', 2)
        if serie['time1_wins'] >= wins_needed:
            await ctx.send('🏆 **Time 1 venceu a série!** GG WP\nUse `!resetar` para voltar ao lobby.')
        elif serie['time2_wins'] >= wins_needed:
            await ctx.send('🏆 **Time 2 venceu a série!** GG WP\nUse `!resetar` para voltar ao lobby.')

    @commands.group(name='serie', invoke_without_command=True)
    async def serie(self, ctx):
        sorteio = _ultimo_sorteio.get(ctx.guild.id)
        if not sorteio:
            await ctx.send('❌ Nenhuma série em andamento. Use `!sortear` primeiro.')
            return

        serie         = _serie.get(ctx.guild.id, {'time1_wins': 0, 'time2_wins': 0, 'jogos': 0})
        rank_cog      = self.bot.cogs.get('Rank')
        fearless_info = rank_cog._fearless.get(ctx.guild.id) if rank_cog else None

        await ctx.send(embed=embed_serie(sorteio, serie, fearless_info))

    @commands.command(name='resetar')
    async def resetar(self, ctx):
        guild = ctx.guild
        lobby = discord.utils.get(guild.voice_channels, name=CANAL_LOBBY)

        if not lobby:
            await ctx.send(f'❌ Canal **{CANAL_LOBBY}** não encontrado!')
            return

        membros_para_mover = []
        for tamanho in TAMANHOS.values():
            for prefixo in ('🏳️Time 1', '🏴Time 2'):
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

        _ultimo_sorteio.pop(guild.id, None)
        _serie.pop(guild.id, None)

        await ctx.send(f'✅ {movidos} jogador(es) de volta ao **{CANAL_LOBBY}**! Série encerrada.')


async def setup(bot):
    await bot.add_cog(Sorteio(bot))
