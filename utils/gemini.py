from google import genai
import os
import json
import re

_client = genai.Client(api_key=os.getenv('GEMINI_API_KEY'))


def _limpar_json(texto: str) -> str:
    texto = re.sub(r'```(?:json)?\s*', '', texto).strip('`').strip()
    # Remove trailing commas antes de } ou ] (JSON inválido que a IA às vezes gera)
    texto = re.sub(r',\s*([}\]])', r'\1', texto)
    return texto


def _rotas_para_tamanho(n_jogadores: int, quarta_rota: str | None = None) -> list[str]:
    """Retorna as rotas ativas conforme o número de jogadores por time."""
    por_time = n_jogadores // 2
    if por_time <= 3:
        return ['top', 'mid', 'bot']
    if por_time == 4:
        quarta = quarta_rota or 'jungle'
        return ['top', 'mid', 'bot', quarta]
    return ['top', 'jungle', 'mid', 'bot', 'support']


def montar_prompt_rift(nomes: list, quarta_rota: str | None = None) -> str:
    por_time = len(nomes) // 2
    rotas    = _rotas_para_tamanho(len(nomes), quarta_rota)
    rotas_str = ', '.join(rotas)

    campos_json = ',\n'.join(
        f'    "{r}": {{"jogador": "nome", "comentario": "frase"}}'
        for r in rotas
    )

    return f"""Você é um narrador HILÁRIO e debochado de League of Legends. Sorteie 2 times de {por_time} jogadores para Summoner's Rift.

Jogadores (use EXATAMENTE esses nomes): {json.dumps(nomes, ensure_ascii=False)}

Regras:
- Divida aleatoriamente em 2 times equilibrados
- Atribua SOMENTE estas rotas: {rotas_str}
- Para cada jogador, escreva uma frase ENGRAÇADA e DEBOCHADA sobre ele naquela rota (português, máx 80 chars)
- Crie uma frase épica de rivalidade entre os dois times

Responda SOMENTE com JSON válido, sem markdown, sem texto extra:
{{
  "time1": {{
{campos_json}
  }},
  "time2": {{
{campos_json}
  }},
  "rivalidade": "frase épica aqui"
}}"""


def montar_prompt_rift_balanceado(time1: list, time2: list, quarta_rota: str | None = None) -> str:
    """Usado quando os times já foram definidos pelo algoritmo de MMR.
    A IA só precisa atribuir rotas e gerar os comentários."""
    n_total   = len(time1) + len(time2)
    rotas     = _rotas_para_tamanho(n_total, quarta_rota)
    rotas_str = ', '.join(rotas)

    campos_json = ',\n'.join(
        f'    "{r}": {{"jogador": "nome", "comentario": "frase"}}'
        for r in rotas
    )

    return f"""Você é um narrador HILÁRIO e debochado de League of Legends.
Os times já foram definidos. Agora atribua rotas e crie comentários.

Time 1: {json.dumps(time1, ensure_ascii=False)}
Time 2: {json.dumps(time2, ensure_ascii=False)}

Regras:
- Atribua SOMENTE estas rotas: {rotas_str}
- Para cada jogador, escreva uma frase ENGRAÇADA e DEBOCHADA sobre ele naquela rota (português, máx 80 chars)
- Crie uma frase épica de rivalidade entre os dois times

Responda SOMENTE com JSON válido, sem markdown, sem texto extra:
{{
  "time1": {{
{campos_json}
  }},
  "time2": {{
{campos_json}
  }},
  "rivalidade": "frase épica aqui"
}}"""


def montar_prompt_aram(nomes: list) -> str:
    por_time = len(nomes) // 2
    return f"""Você é um narrador HILÁRIO e debochado de League of Legends. Sorteie 2 times de {por_time} jogadores para ARAM.

Jogadores (use EXATAMENTE esses nomes): {json.dumps(nomes, ensure_ascii=False)}

Regras:
- Divida aleatoriamente em 2 times equilibrados
- Para cada jogador, escreva uma frase ENGRAÇADA e DEBOCHADA sobre ele no ARAM (português, máx 80 chars)
- Crie uma frase épica de rivalidade entre os dois times

Responda SOMENTE com JSON válido, sem markdown, sem texto extra:
{{
  "time1": [
    {{"jogador": "nome", "comentario": "frase"}}
  ],
  "time2": [
    {{"jogador": "nome", "comentario": "frase"}}
  ],
  "rivalidade": "frase épica aqui"
}}"""


def gerar_campeoes(rotas_jogadores: dict, banidos: list[str]) -> dict:
    """
    rotas_jogadores: {'NomeJogador': 'rota', ...}
    banidos: lista de campeões já usados no fearless
    Retorna: {'NomeJogador': {'campeao': str, 'comentario': str}, ...}
    """
    jogadores_str = json.dumps(rotas_jogadores, ensure_ascii=False)
    banidos_str   = ', '.join(banidos) if banidos else 'nenhum'

    prompt = f"""Você é um narrador HILÁRIO de League of Legends.
Atribua um campeão aleatório para cada jogador conforme sua rota.

Jogadores e rotas: {jogadores_str}
Campeões PROIBIDOS (Fearless): {banidos_str}

Regras:
- Escolha um campeão diferente e VÁLIDO para a rota de cada jogador
- NÃO use nenhum campeão da lista de proibidos
- Para cada pick, escreva uma frase ENGRAÇADA sobre a escolha (português, máx 70 chars)
- Use nomes de campeões em inglês exatamente como no jogo

Responda SOMENTE com JSON válido, sem markdown:
{{
  "NomeJogador": {{"campeao": "ChampionName", "comentario": "frase"}},
  ...
}}"""

    response = _client.models.generate_content(model='gemini-2.5-flash-lite', contents=prompt)
    return json.loads(_limpar_json(response.text.strip()))


def rotas_ativas(n_jogadores: int, quarta_rota: str | None = None) -> list[str]:
    """Exposto para uso externo (formatação, etc.)."""
    return _rotas_para_tamanho(n_jogadores, quarta_rota)


def gerar_sorteio(nomes: list, mapa: str, quarta_rota: str | None = None) -> dict:
    if mapa == 'rift':
        prompt = montar_prompt_rift(nomes, quarta_rota)
    else:
        prompt = montar_prompt_aram(nomes)

    response = _client.models.generate_content(model='gemini-2.5-flash-lite', contents=prompt)
    return json.loads(_limpar_json(response.text.strip()))


def gerar_sorteio_balanceado(time1: list, time2: list, quarta_rota: str | None = None) -> dict:
    """Para Rift quando os times já vêm do algoritmo de MMR."""
    prompt = montar_prompt_rift_balanceado(time1, time2, quarta_rota)
    response = _client.models.generate_content(model='gemini-2.5-flash-lite', contents=prompt)
    return json.loads(_limpar_json(response.text.strip()))
