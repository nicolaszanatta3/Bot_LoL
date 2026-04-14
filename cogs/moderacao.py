from discord.ext import commands


class Moderacao(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='limpar')
    @commands.has_permissions(manage_messages=True)
    async def limpar(self, ctx, quantidade: int = 10):
        if quantidade < 1 or quantidade > 100:
            await ctx.send('❌ Informe um número entre **1** e **100**.')
            return
        deletadas = await ctx.channel.purge(limit=quantidade + 1)
        aviso = await ctx.send(f'🧹 {len(deletadas) - 1} mensagem(ns) deletada(s).')
        await aviso.delete(delay=4)

    @limpar.error
    async def limpar_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send('❌ Você precisa da permissão **Gerenciar Mensagens** para usar isso.')
        elif isinstance(error, commands.BadArgument):
            await ctx.send('❌ Use: `!limpar 20` (número de mensagens, máx 100)')


async def setup(bot):
    await bot.add_cog(Moderacao(bot))
