from itertools import combinations

# Pontuação base por tier
TIER_BASE = {
    'IRON':        0,
    'BRONZE':      400,
    'SILVER':      800,
    'GOLD':        1200,
    'PLATINUM':    1600,
    'EMERALD':     2000,
    'DIAMOND':     2400,
    'MASTER':      2800,
    'GRANDMASTER': 3200,
    'CHALLENGER':  3600,
}

# Pontuação adicional por divisão
RANK_BONUS = {'IV': 0, 'III': 100, 'II': 200, 'I': 300}

# MMR padrão para jogadores sem rank cadastrado
MMR_UNRANKED = 600


def rank_para_mmr(tier: str, rank: str, lp: int) -> int:
    base  = TIER_BASE.get(tier.upper(), 0)
    bonus = RANK_BONUS.get(rank.upper(), 0)
    return base + bonus + lp


def balancear_times(jogadores: list[dict]) -> tuple[list[dict], list[dict], int]:
    """
    Recebe lista de dicts: [{'nome': str, 'mmr': int}, ...]
    Retorna (time1, time2, diferenca_mmr) com os times mais equilibrados possíveis.

    Para N=10 testa C(10,5)=252 combinações — instantâneo.
    """
    n    = len(jogadores)
    meio = n // 2

    melhor_t1  = None
    melhor_t2  = None
    menor_diff = float('inf')

    indices = list(range(n))
    for combo in combinations(indices, meio):
        conjunto = set(combo)
        t1   = [jogadores[i] for i in combo]
        t2   = [jogadores[i] for i in indices if i not in conjunto]
        diff = abs(sum(j['mmr'] for j in t1) - sum(j['mmr'] for j in t2))
        if diff < menor_diff:
            menor_diff = diff
            melhor_t1  = t1
            melhor_t2  = t2

    return melhor_t1, melhor_t2, menor_diff


def montar_lista_mmr(membros, dados_jogadores: dict, guild_id: int) -> list[dict]:
    """
    Cruza membros do Discord com os dados de rank salvos.
    Jogadores sem cadastro recebem MMR_UNRANKED.
    """
    guild_data = dados_jogadores.get(str(guild_id), {})
    resultado  = []

    for membro in membros:
        uid   = str(membro.id)
        info  = guild_data.get(uid, {})
        rank  = info.get('rank')

        if rank and rank.get('tier'):
            mmr = rank_para_mmr(rank['tier'], rank.get('rank', 'IV'), rank.get('lp', 0))
        else:
            mmr = MMR_UNRANKED

        resultado.append({'nome': membro.display_name, 'mmr': mmr})

    return resultado
