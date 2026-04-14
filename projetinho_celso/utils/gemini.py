from google import genai
import os
import json
import re

_client = genai.Client(api_key=os.getenv('GEMINI_API_KEY'))


def _limpar_json(texto: str) -> str:
    return re.sub(r'```(?:json)?\s*', '', texto).strip('`').strip()


def montar_prompt_rift(nomes: list) -> str:
    por_time = len(nomes) // 2
    return f"""Você é um narrador HILÁRIO e debochado de League of Legends. Sorteie 2 times de {por_time} jogadores para Summoner's Rift.

Jogadores (use EXATAMENTE esses nomes): {json.dumps(nomes, ensure_ascii=False)}

Regras:
- Divida aleatoriamente em 2 times equilibrados
- Atribua rotas: top, jungle, mid, bot, support (use "vazio" se faltar jogadores)
- Para cada jogador, escreva uma frase ENGRAÇADA e DEBOCHADA sobre ele naquela rota (português, máx 80 chars)
- Crie uma frase épica de rivalidade entre os dois times

Responda SOMENTE com JSON válido, sem markdown, sem texto extra:
{{
  "time1": {{
    "top":     {{"jogador": "nome", "comentario": "frase"}},
    "jungle":  {{"jogador": "nome", "comentario": "frase"}},
    "mid":     {{"jogador": "nome", "comentario": "frase"}},
    "bot":     {{"jogador": "nome", "comentario": "frase"}},
    "support": {{"jogador": "nome", "comentario": "frase"}}
  }},
  "time2": {{
    "top":     {{"jogador": "nome", "comentario": "frase"}},
    "jungle":  {{"jogador": "nome", "comentario": "frase"}},
    "mid":     {{"jogador": "nome", "comentario": "frase"}},
    "bot":     {{"jogador": "nome", "comentario": "frase"}},
    "support": {{"jogador": "nome", "comentario": "frase"}}
  }},
  "rivalidade": "frase épica aqui"
}}"""


def montar_prompt_rift_balanceado(time1: list, time2: list) -> str:
    """Usado quando os times já foram definidos pelo algoritmo de MMR.
    A IA só precisa atribuir rotas e gerar os comentários."""
    return f"""Você é um narrador HILÁRIO e debochado de League of Legends.
Os times já foram definidos. Agora atribua rotas e crie comentários.

Time 1: {json.dumps(time1, ensure_ascii=False)}
Time 2: {json.dumps(time2, ensure_ascii=False)}

Regras:
- Atribua uma rota para cada jogador: top, jungle, mid, bot, support (use "vazio" se faltar)
- Para cada jogador, escreva uma frase ENGRAÇADA e DEBOCHADA sobre ele naquela rota (português, máx 80 chars)
- Crie uma frase épica de rivalidade entre os dois times

Responda SOMENTE com JSON válido, sem markdown, sem texto extra:
{{
  "time1": {{
    "top":     {{"jogador": "nome", "comentario": "frase"}},
    "jungle":  {{"jogador": "nome", "comentario": "frase"}},
    "mid":     {{"jogador": "nome", "comentario": "frase"}},
    "bot":     {{"jogador": "nome", "comentario": "frase"}},
    "support": {{"jogador": "nome", "comentario": "frase"}}
  }},
  "time2": {{
    "top":     {{"jogador": "nome", "comentario": "frase"}},
    "jungle":  {{"jogador": "nome", "comentario": "frase"}},
    "mid":     {{"jogador": "nome", "comentario": "frase"}},
    "bot":     {{"jogador": "nome", "comentario": "frase"}},
    "support": {{"jogador": "nome", "comentario": "frase"}}
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


def gerar_sorteio(nomes: list, mapa: str) -> dict:
    if mapa == 'rift':
        prompt = montar_prompt_rift(nomes)
    else:
        prompt = montar_prompt_aram(nomes)

    response = _client.models.generate_content(model='gemini-1.5-flash', contents=prompt)
    return json.loads(_limpar_json(response.text.strip()))


def gerar_sorteio_balanceado(time1: list, time2: list) -> dict:
    """Para Rift quando os times já vêm do algoritmo de MMR."""
    prompt = montar_prompt_rift_balanceado(time1, time2)
    response = _client.models.generate_content(model='gemini-1.5-flash', contents=prompt)
    return json.loads(_limpar_json(response.text.strip()))
