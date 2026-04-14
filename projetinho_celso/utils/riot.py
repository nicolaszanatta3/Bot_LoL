"""
Riot Games API — integração com rank e partidas.
Requer RIOT_API_KEY no .env (developer.riot.games).
"""
import aiohttp
import os

RIOT_API_KEY = os.getenv('RIOT_API_KEY', '')
REGION       = 'br1'       # servidor BR
REGIONAL     = 'americas'  # rota regional para Account API


def _headers() -> dict:
    return {'X-Riot-Token': RIOT_API_KEY}


async def buscar_puuid(riot_id: str) -> str | None:
    """Recebe 'Nome#TAG' e retorna o PUUID do jogador."""
    if '#' not in riot_id:
        return None
    nome, tag = riot_id.split('#', 1)
    url = (
        f'https://{REGIONAL}.api.riotgames.com'
        f'/riot/account/v1/accounts/by-riot-id/{nome}/{tag}'
    )
    async with aiohttp.ClientSession() as s:
        async with s.get(url, headers=_headers()) as r:
            if r.status != 200:
                return None
            data = await r.json()
            return data.get('puuid')


async def buscar_rank(puuid: str) -> dict | None:
    """Retorna {'tier', 'rank', 'lp', 'wins', 'losses'} da fila solo/duo, ou None."""
    url = f'https://{REGION}.api.riotgames.com/lol/league/v4/entries/by-puuid/{puuid}'

    async with aiohttp.ClientSession() as s:
        async with s.get(url, headers=_headers()) as r:
            if r.status != 200:
                return None
            entries = await r.json()

    for entry in entries:
        if entry.get('queueType') == 'RANKED_SOLO_5x5':
            return {
                'tier':   entry['tier'],
                'rank':   entry['rank'],
                'lp':     entry['leaguePoints'],
                'wins':   entry.get('wins', 0),
                'losses': entry.get('losses', 0),
            }
    return None  # jogador sem rank na fila solo


async def buscar_campeoes_ultima_partida(puuid: str) -> list[str]:
    """Retorna lista de nomes de campeões da última partida customizada do jogador."""
    url_match = (
        f'https://{REGIONAL}.api.riotgames.com'
        f'/lol/match/v5/matches/by-puuid/{puuid}/ids?count=1&queue=0'
    )
    async with aiohttp.ClientSession() as s:
        async with s.get(url_match, headers=_headers()) as r:
            if r.status != 200:
                return []
            match_ids = await r.json()

        if not match_ids:
            return []

        url_detail = (
            f'https://{REGIONAL}.api.riotgames.com'
            f'/lol/match/v5/matches/{match_ids[0]}'
        )
        async with s.get(url_detail, headers=_headers()) as r:
            if r.status != 200:
                return []
            detail = await r.json()

    participantes = detail.get('info', {}).get('participants', [])
    return [p['championName'] for p in participantes]


def api_configurada() -> bool:
    return bool(RIOT_API_KEY)
