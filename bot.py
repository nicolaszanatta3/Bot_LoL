import asyncio
import discord
from discord.ext import commands
import os
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

if not DISCORD_TOKEN:
    raise RuntimeError('DISCORD_TOKEN não definido no .env')
if not GEMINI_API_KEY:
    raise RuntimeError('GEMINI_API_KEY não definido no .env')

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.voice_states = True

bot = commands.Bot(command_prefix='!', intents=intents)

COGS = [
    'cogs.sorteio',
    'cogs.moderacao',
    'cogs.rank',
]
@bot.event
async def on_ready():
    print(f'✅ Bot {bot.user} online!')
    print(f'   Servidores: {len(bot.guilds)}')


@bot.command(name='ajuda')
async def ajuda(ctx):
    embed = discord.Embed(
        title='📖  Comandos do Bot',
        color=0xC89B3C,
    )
    embed.add_field(
        name='🎮  Sorteio & Série',
        value=(
            '`!sortear rift` — Sorteia times para Rift (times ficam fixos na série)\n'
            '`!sortear aram` — Sorteia times para ARAM\n'
            '`!mover`        — Envia jogadores do lobby para as calls\n'
            '`!proxjogo time1/time2` — Registra vencedor e mostra placar + fearless\n'
            '`!serie`        — Mostra placar e times da série atual\n'
            '`!resetar`      — Devolve todos ao lobby e encerra a série'
        ),
        inline=False,
    )
    embed.add_field(
        name='🏆  Rank',
        value=(
            '`!registrar Nome#TAG` — Vincula seu Riot ID\n'
            '`!rank [@jogador]`    — Mostra o rank\n'
            '`!atualizar`         — Atualiza seu rank via Riot API'
        ),
        inline=False,
    )
    embed.add_field(
        name='🚫  Fearless Draft',
        value=(
            '`!fearless start`  — Inicia uma nova série\n'
            '`!fearless add`    — Registra campeões manualmente\n'
            '`!fearless sync`   — Puxa campeões da última partida (Riot API)\n'
            '`!fearless status` — Mostra campeões banidos\n'
            '`!fearless reset`  — Zera a série'
        ),
        inline=False,
    )
    embed.add_field(
        name='🛠️  Moderação',
        value='`!limpar [n]` — Apaga as últimas N mensagens (padrão: 10, máx: 100)',
        inline=False,
    )
    embed.set_footer(text='Jogadores suportados: 6 (3x3) · 8 (4x4) · 10 (5x5)')
    await ctx.send(embed=embed)


async def main():
    async with bot:
        for cog in COGS:
            await bot.load_extension(cog)
            print(f'   Cog carregada: {cog}')
        await bot.start(DISCORD_TOKEN)


if __name__ == '__main__':
    asyncio.run(main())
