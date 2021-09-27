from .foobltoobr import Foobltoobr
from redbot.core.bot import Red


async def setup(bot: Red) -> None:
    cog = Foobltoobr(bot)
    await cog.initialize()
    bot.add_cog(cog)
