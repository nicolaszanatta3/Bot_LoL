import discord
from config import ROTAS_DISPLAY, COR_ESCALACAO, COR_INFO, COR_SUCESSO


def embed_rift(data: dict, tamanho: str, mmr_diff: int | None = None) -> discord.Embed:
    embed = discord.Embed(
        title=f'🎮  ESCALAÇÃO  ·  SUMMONER\'S RIFT  ·  {tamanho}',
        color=COR_ESCALACAO,
    )

    t1_linhas = []
    for rota, display in ROTAS_DISPLAY.items():
        info    = data['time1'].get(rota, {})
        jogador = info.get('jogador', 'vazio')
        coment  = info.get('comentario', '')
        if jogador != 'vazio':
            t1_linhas.append(f'{display}\n**{jogador}**\n*{coment}*')

    t2_linhas = []
    for rota, display in ROTAS_DISPLAY.items():
        info    = data['time2'].get(rota, {})
        jogador = info.get('jogador', 'vazio')
        coment  = info.get('comentario', '')
        if jogador != 'vazio':
            t2_linhas.append(f'{display}\n**{jogador}**\n*{coment}*')

    embed.add_field(name='🏳️  Time 1', value='\n\n'.join(t1_linhas) or '—', inline=True)
    embed.add_field(name='🏴  Time 2', value='\n\n'.join(t2_linhas) or '—', inline=True)

    footer = data.get('rivalidade', '')
    if mmr_diff is not None:
        footer = f'⚖️ Diferença de MMR: {mmr_diff} pts  ·  ⚔️ {footer}'
    elif footer:
        footer = f'⚔️  {footer}'

    if footer:
        embed.set_footer(text=footer)

    return embed


def embed_aram(data: dict, tamanho: str) -> discord.Embed:
    embed = discord.Embed(
        title=f'🎮  ESCALAÇÃO  ·  ARAM  ·  {tamanho}',
        color=COR_ESCALACAO,
    )

    t1_linhas = [
        f'• **{e["jogador"]}**\n*{e["comentario"]}*'
        for e in data.get('time1', [])
    ]
    t2_linhas = [
        f'• **{e["jogador"]}**\n*{e["comentario"]}*'
        for e in data.get('time2', [])
    ]

    embed.add_field(name='🏳️  Time 1', value='\n\n'.join(t1_linhas) or '—', inline=True)
    embed.add_field(name='🏴  Time 2', value='\n\n'.join(t2_linhas) or '—', inline=True)

    if data.get('rivalidade'):
        embed.set_footer(text=f'⚔️  {data["rivalidade"]}')

    return embed


def embed_rank(discord_nome: str, riot_id: str, rank_info: dict) -> discord.Embed:
    tier   = rank_info.get('tier', 'UNRANKED').capitalize()
    rank   = rank_info.get('rank', '')
    lp     = rank_info.get('lp', 0)
    mmr    = rank_info.get('mmr', 0)
    wins   = rank_info.get('wins', 0)
    losses = rank_info.get('losses', 0)
    total  = wins + losses
    winrate = round(wins / total * 100) if total else 0

    embed = discord.Embed(
        title=f'🏆  {discord_nome}',
        description=f'`{riot_id}`',
        color=COR_INFO,
    )
    embed.add_field(name='Rank',    value=f'**{tier} {rank}**' if rank else '**Unranked**', inline=True)
    embed.add_field(name='LP',      value=f'**{lp}**', inline=True)
    embed.add_field(name='MMR',     value=f'**{mmr}** pts', inline=True)
    embed.add_field(name='Vitórias', value=f'**{wins}**', inline=True)
    embed.add_field(name='Derrotas', value=f'**{losses}**', inline=True)
    embed.add_field(name='Winrate', value=f'**{winrate}%**', inline=True)
    return embed


def embed_serie(sorteio: dict, serie: dict, fearless: dict | None = None) -> discord.Embed:
    t1_wins = serie.get('time1_wins', 0)
    t2_wins = serie.get('time2_wins', 0)
    jogos   = serie.get('jogos', 0)

    # Cor muda conforme quem está vencendo
    if t1_wins > t2_wins:
        cor = 0x3498DB   # azul — Time 1 na frente
    elif t2_wins > t1_wins:
        cor = 0xE74C3C   # vermelho — Time 2 na frente
    else:
        cor = COR_ESCALACAO  # empate

    embed = discord.Embed(
        title=f'⚔️  SÉRIE  ·  Jogo {jogos + 1}',
        color=cor,
    )

    t1_nomes = sorteio.get('time1_nomes', [])
    t2_nomes = sorteio.get('time2_nomes', [])

    embed.add_field(
        name=f'🏳️  Time 1  —  {t1_wins} vitória(s)',
        value='\n'.join(f'• {n}' for n in t1_nomes) or '—',
        inline=True,
    )
    embed.add_field(
        name=f'🏴  Time 2  —  {t2_wins} vitória(s)',
        value='\n'.join(f'• {n}' for n in t2_nomes) or '—',
        inline=True,
    )

    # Placar visual
    placar = f'**{t1_wins}  ×  {t2_wins}**'
    embed.add_field(name='Placar', value=placar, inline=False)

    # Fearless bans se ativo
    if fearless and fearless.get('usados'):
        usados = fearless['usados']
        bans   = '  '.join(f'~~{c}~~' for c in sorted(usados))
        embed.add_field(
            name=f'🚫  Fearless — {len(usados)} banido(s)',
            value=bans,
            inline=False,
        )

    embed.set_footer(text='Use !proxjogo time1 ou !proxjogo time2 para registrar o resultado.')
    return embed


def embed_status_fearless(usados: list[str], serie: int) -> discord.Embed:
    embed = discord.Embed(
        title=f'🚫  Fearless Draft  ·  Série #{serie}',
        color=COR_ESCALACAO,
    )
    if usados:
        lista = '\n'.join(f'• {c}' for c in sorted(usados))
        embed.add_field(name=f'{len(usados)} campeão(s) banido(s)', value=lista, inline=False)
    else:
        embed.description = '*Nenhum campeão banido ainda. Boa sorte!*'
    embed.set_footer(text='Campeões já jogados não podem ser repetidos na série.')
    return embed
