import asyncio
import discord
import re
from datetime import timezone
from typing import Union, Set, Literal

from redbot.core import checks, Config, modlog, commands
from redbot.core.bot import Red
from redbot.core.i18n import Translator, cog_i18n, set_contextual_locales_from_guild
from redbot.core.utils.predicates import MessagePredicate
from redbot.core.utils import AsyncIter
from redbot.core.utils.chat_formatting import pagify, humanize_list

_ = Translator("Foobltoobr", __file__)


@cog_i18n(_)
class Foobltoobr(commands.Cog):
    """This cog is designed for "foobltoobring" unwanted words and phrases from a server.

    It provides tools to manage a list of words or sentences, and to customize automatic actions to be taken against users who use those words in channels or in their name/nickname.

    This can be used to prevent inappropriate language, off-topic discussions, invite links, and more.
    """

    def __init__(self, bot: Red):
        super().__init__()
        self.bot = bot
        self.config = Config.get_conf(self, 4766951341)
        default_guild_settings = {
            "foobltoobr": [],
            "foobltoobrban_count": 0,
            "foobltoobrban_time": 0,
            "foobltoobr_names": False,
            "foobltoobr_default_name": "John Doe",
        }
        default_member_settings = {"foobltoobr_count": 0, "next_reset_time": 0}
        default_channel_settings = {"foobltoobr": []}
        self.config.register_guild(**default_guild_settings)
        self.config.register_member(**default_member_settings)
        self.config.register_channel(**default_channel_settings)
        self.pattern_cache = {}

    async def red_delete_data_for_user(
        self,
        *,
        requester: Literal["discord_deleted_user", "owner", "user", "user_strict"],
        user_id: int,
    ):
        if requester != "discord_deleted_user":
            return

        all_members = await self.config.all_members()

        async for guild_id, guild_data in AsyncIter(all_members.items(), steps=100):
            if user_id in guild_data:
                await self.config.member_from_ids(guild_id, user_id).clear()

    async def initialize(self) -> None:
        await self.register_casetypes()

    @staticmethod
    async def register_casetypes() -> None:
        await modlog.register_casetypes(
            [
                {
                    "name": "foobltoobrban",
                    "default_setting": False,
                    "image": "\N{FILE CABINET}\N{VARIATION SELECTOR-16} \N{HAMMER}",
                    "case_str": "Foobltoobr ban",
                },
                {
                    "name": "foobltoobrhit",
                    "default_setting": False,
                    "image": "\N{FILE CABINET}\N{VARIATION SELECTOR-16}",
                    "case_str": "Foobltoobr hit",
                },
            ]
        )

    @commands.group()
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def foobltoobrset(self, ctx: commands.Context):
        """Base command to manage foobltoobr settings."""
        pass

    @foobltoobrset.command(name="defaultname")
    async def foobltoobr_default_name(self, ctx: commands.Context, name: str):
        """Set the nickname for users with a foobltoobred name.

        Note that this has no effect if foobltoobring names is disabled
        (to toggle, run `[p]foobltoobr names`).

        The default name used is *John Doe*.

        Example:
            - `[p]foobltoobrset defaultname Missingno`

        **Arguments:**

        - `<name>` The new nickname to assign.
        """
        guild = ctx.guild
        await self.config.guild(guild).foobltoobr_default_name.set(name)
        await ctx.send(_("The name to use on foobltoobred names has been set."))

    @foobltoobrset.command(name="ban")
    async def foobltoobr_ban(self, ctx: commands.Context, count: int, timeframe: int):
        """Set the foobltoobr's autoban conditions.

        Users will be banned if they send `<count>` foobltoobred words in
        `<timeframe>` seconds.

        Set both to zero to disable autoban.

        Examples:
            - `[p]foobltoobrset ban 5 5` - Ban users who say 5 foobltoobred words in 5 seconds.
            - `[p]foobltoobrset ban 2 20` - Ban users who say 2 foobltoobred words in 20 seconds.

        **Arguments:**

        - `<count>` The amount of foobltoobred words required to trigger a ban.
        - `<timeframe>` The period of time in which too many foobltoobred words will trigger a ban.
        """
        if (count <= 0) != (timeframe <= 0):
            await ctx.send(
                _(
                    "Count and timeframe either both need to be 0 "
                    "or both need to be greater than 0!"
                )
            )
            return
        elif count == 0 and timeframe == 0:
            async with self.config.guild(ctx.guild).all() as guild_data:
                guild_data["foobltoobrban_count"] = 0
                guild_data["foobltoobrban_time"] = 0
            await ctx.send(_("Autoban disabled."))
        else:
            async with self.config.guild(ctx.guild).all() as guild_data:
                guild_data["foobltoobrban_count"] = count
                guild_data["foobltoobrban_time"] = timeframe
            await ctx.send(_("Count and time have been set."))

    @commands.group(name="foobltoobr")
    @commands.guild_only()
    @checks.mod_or_permissions(manage_messages=True)
    async def _foobltoobr(self, ctx: commands.Context):
        """Base command to add or remove words from the server foobltoobr.

        Use double quotes to add or remove sentences.
        """
        pass

    @_foobltoobr.command(name="clear")
    async def _foobltoobr_clear(self, ctx: commands.Context):
        """Clears this server's foobltoobr list."""
        guild = ctx.guild
        author = ctx.author
        foobltoobr_list = await self.config.guild(guild).foobltoobr()
        if not foobltoobr_list:
            return await ctx.send(_("The foobltoobr list for this server is empty."))
        await ctx.send(
            _("Are you sure you want to clear this server's foobltoobr list?") + " (yes/no)"
        )
        try:
            pred = MessagePredicate.yes_or_no(ctx, user=author)
            await ctx.bot.wait_for("message", check=pred, timeout=60)
        except asyncio.TimeoutError:
            await ctx.send(_("You took too long to respond."))
            return
        if pred.result:
            await self.config.guild(guild).foobltoobr.clear()
            self.invalidate_cache(guild)
            await ctx.send(_("Server foobltoobr cleared."))
        else:
            await ctx.send(_("No changes have been made."))

    @_foobltoobr.command(name="list")
    async def _global_list(self, ctx: commands.Context):
        """Send a list of this server's foobltoobred words."""
        server = ctx.guild
        author = ctx.author
        word_list = await self.config.guild(server).foobltoobr()
        if not word_list:
            await ctx.send(_("There are no current words setup to be foobltoobred in this server."))
            return
        words = humanize_list(word_list)
        words = _("Foobltoobred in this server:") + "\n\n" + words
        try:
            for page in pagify(words, delims=[" ", "\n"], shorten_by=8):
                await author.send(page)
        except discord.Forbidden:
            await ctx.send(_("I can't send direct messages to you."))

    @_foobltoobr.group(name="channel")
    async def _foobltoobr_channel(self, ctx: commands.Context):
        """Base command to add or remove words from the channel foobltoobr.

        Use double quotes to add or remove sentences.
        """
        pass

    @_foobltoobr_channel.command(name="clear")
    async def _channel_clear(self, ctx: commands.Context):
        """Clears this channel's foobltoobr list."""
        channel = ctx.channel
        author = ctx.author
        foobltoobr_list = await self.config.channel(channel).foobltoobr()
        if not foobltoobr_list:
            return await ctx.send(_("The foobltoobr list for this channel is empty."))
        await ctx.send(
            _("Are you sure you want to clear this channel's foobltoobr list?") + " (yes/no)"
        )
        try:
            pred = MessagePredicate.yes_or_no(ctx, user=author)
            await ctx.bot.wait_for("message", check=pred, timeout=60)
        except asyncio.TimeoutError:
            await ctx.send(_("You took too long to respond."))
            return
        if pred.result:
            await self.config.channel(channel).foobltoobr.clear()
            self.invalidate_cache(ctx.guild, channel)
            await ctx.send(_("Channel foobltoobr cleared."))
        else:
            await ctx.send(_("No changes have been made."))

    @_foobltoobr_channel.command(name="list")
    async def _channel_list(self, ctx: commands.Context):
        """Send a list of the channel's foobltoobred words."""
        channel = ctx.channel
        author = ctx.author
        word_list = await self.config.channel(channel).foobltoobr()
        if not word_list:
            await ctx.send(_("There are no current words setup to be foobltoobred in this channel."))
            return
        words = humanize_list(word_list)
        words = _("Foobltoobred in this channel:") + "\n\n" + words
        try:
            for page in pagify(words, delims=[" ", "\n"], shorten_by=8):
                await author.send(page)
        except discord.Forbidden:
            await ctx.send(_("I can't send direct messages to you."))

    @_foobltoobr_channel.command(name="add", require_var_positional=True)
    async def foobltoobr_channel_add(self, ctx: commands.Context, *words: str):
        """Add words to the foobltoobr.

        Use double quotes to add sentences.

        Examples:
            - `[p]foobltoobr channel add word1 word2 word3`
            - `[p]foobltoobr channel add "This is a sentence"`

        **Arguments:**

        - `[words...]` The words or sentences to foobltoobr.
        """
        channel = ctx.channel
        added = await self.add_to_foobltoobr(channel, words)
        if added:
            self.invalidate_cache(ctx.guild, ctx.channel)
            await ctx.send(_("Words added to foobltoobr."))
        else:
            await ctx.send(_("Words already in the foobltoobr."))

    @_foobltoobr_channel.command(name="delete", aliases=["remove", "del"], require_var_positional=True)
    async def foobltoobr_channel_remove(self, ctx: commands.Context, *words: str):
        """Remove words from the foobltoobr.

        Use double quotes to remove sentences.

        Examples:
            - `[p]foobltoobr channel remove word1 word2 word3`
            - `[p]foobltoobr channel remove "This is a sentence"`

        **Arguments:**

        - `[words...]` The words or sentences to no longer foobltoobr.
        """
        channel = ctx.channel
        removed = await self.remove_from_foobltoobr(channel, words)
        if removed:
            await ctx.send(_("Words removed from foobltoobr."))
            self.invalidate_cache(ctx.guild, ctx.channel)
        else:
            await ctx.send(_("Those words weren't in the foobltoobr."))

    @_foobltoobr.command(name="add", require_var_positional=True)
    async def foobltoobr_add(self, ctx: commands.Context, *words: str):
        """Add words to the foobltoobr.

        Use double quotes to add sentences.

        Examples:
            - `[p]foobltoobr add word1 word2 word3`
            - `[p]foobltoobr add "This is a sentence"`

        **Arguments:**

        - `[words...]` The words or sentences to foobltoobr.
        """
        server = ctx.guild
        added = await self.add_to_foobltoobr(server, words)
        if added:
            self.invalidate_cache(ctx.guild)
            await ctx.send(_("Words successfully added to foobltoobr."))
        else:
            await ctx.send(_("Those words were already in the foobltoobr."))

    @_foobltoobr.command(name="delete", aliases=["remove", "del"], require_var_positional=True)
    async def foobltoobr_remove(self, ctx: commands.Context, *words: str):
        """Remove words from the foobltoobr.

        Use double quotes to remove sentences.

        Examples:
            - `[p]foobltoobr remove word1 word2 word3`
            - `[p]foobltoobr remove "This is a sentence"`

        **Arguments:**

        - `[words...]` The words or sentences to no longer foobltoobr.
        """
        server = ctx.guild
        removed = await self.remove_from_foobltoobr(server, words)
        if removed:
            self.invalidate_cache(ctx.guild)
            await ctx.send(_("Words successfully removed from foobltoobr."))
        else:
            await ctx.send(_("Those words weren't in the foobltoobr."))

    @_foobltoobr.command(name="names")
    async def foobltoobr_names(self, ctx: commands.Context):
        """Toggle name and nickname foobltoobring.

        This is disabled by default.
        """
        guild = ctx.guild

        async with self.config.guild(guild).all() as guild_data:
            current_setting = guild_data["foobltoobr_names"]
            guild_data["foobltoobr_names"] = not current_setting
        if current_setting:
            await ctx.send(_("Names and nicknames will no longer be foobltoobred."))
        else:
            await ctx.send(_("Names and nicknames will now be foobltoobred."))

    def invalidate_cache(self, guild: discord.Guild, channel: discord.TextChannel = None):
        """ Invalidate a cached pattern"""
        self.pattern_cache.pop((guild, channel), None)
        if channel is None:
            for keyset in list(self.pattern_cache.keys()):  # cast needed, no remove
                if guild in keyset:
                    self.pattern_cache.pop(keyset, None)

    async def add_to_foobltoobr(
        self, server_or_channel: Union[discord.Guild, discord.TextChannel], words: list
    ) -> bool:
        added = False
        if isinstance(server_or_channel, discord.Guild):
            async with self.config.guild(server_or_channel).foobltoobr() as cur_list:
                for w in words:
                    if w.lower() not in cur_list and w:
                        cur_list.append(w.lower())
                        added = True

        elif isinstance(server_or_channel, discord.TextChannel):
            async with self.config.channel(server_or_channel).foobltoobr() as cur_list:
                for w in words:
                    if w.lower() not in cur_list and w:
                        cur_list.append(w.lower())
                        added = True

        return added

    async def remove_from_foobltoobr(
        self, server_or_channel: Union[discord.Guild, discord.TextChannel], words: list
    ) -> bool:
        removed = False
        if isinstance(server_or_channel, discord.Guild):
            async with self.config.guild(server_or_channel).foobltoobr() as cur_list:
                for w in words:
                    if w.lower() in cur_list:
                        cur_list.remove(w.lower())
                        removed = True

        elif isinstance(server_or_channel, discord.TextChannel):
            async with self.config.channel(server_or_channel).foobltoobr() as cur_list:
                for w in words:
                    if w.lower() in cur_list:
                        cur_list.remove(w.lower())
                        removed = True

        return removed

    async def foobltoobr_hits(
        self, text: str, server_or_channel: Union[discord.Guild, discord.TextChannel]
    ) -> Set[str]:

        try:
            guild = server_or_channel.guild
            channel = server_or_channel
        except AttributeError:
            guild = server_or_channel
            channel = None

        hits: Set[str] = set()

        try:
            pattern = self.pattern_cache[(guild, channel)]
        except KeyError:
            word_list = set(await self.config.guild(guild).foobltoobr())
            if channel:
                word_list |= set(await self.config.channel(channel).foobltoobr())

            if word_list:
                pattern = re.compile(
                    "|".join(rf"\b{re.escape(w)}\b" for w in word_list), flags=re.I
                )
            else:
                pattern = None

            self.pattern_cache[(guild, channel)] = pattern

        if pattern:
            hits |= set(pattern.findall(text))
        return hits

    async def check_foobltoobr(self, message: discord.Message):
        guild = message.guild
        author = message.author
        guild_data = await self.config.guild(guild).all()
        member_data = await self.config.member(author).all()
        foobltoobr_count = guild_data["foobltoobrban_count"]
        foobltoobr_time = guild_data["foobltoobrban_time"]
        user_count = member_data["foobltoobr_count"]
        next_reset_time = member_data["next_reset_time"]
        created_at = message.created_at.replace(tzinfo=timezone.utc)

        if foobltoobr_count > 0 and foobltoobr_time > 0:
            if created_at.timestamp() >= next_reset_time:
                next_reset_time = created_at.timestamp() + foobltoobr_time
                async with self.config.member(author).all() as member_data:
                    member_data["next_reset_time"] = next_reset_time
                    if user_count > 0:
                        user_count = 0
                        member_data["foobltoobr_count"] = user_count

        hits = await self.foobltoobr_hits(message.content, message.channel)

        try:
            await message.edit(content=self.oobify(message.content))
        except discord.HTTPException:
            print("Why can't I edit the message")

        if hits:
            print(f'Message: {message.content}\nHits with {hits}\nOobifying:{self.oobify_hits(message.content, hits)}\n\n')
            await modlog.create_case(
                bot=self.bot,
                guild=guild,
                created_at=message.created_at.replace(tzinfo=timezone.utc),
                action_type="foobltoobrhit",
                user=author,
                moderator=guild.me,
                reason=(
                    _("Foobltoobred words used: {words}").format(words=humanize_list(list(hits)))
                    if len(hits) > 1
                    else _("Foobltoobred word used: {word}").format(word=list(hits)[0])
                ),
                channel=message.channel,
            )
            try:
                #await message.edit(content=self.oobify_hits(message.content, hits))
                #await message.delete()
                await message.edit(content="Whooooopsie")
            except discord.HTTPException e:
                print("HTTPException, message not deleted\n{e}")
                pass
            else:
                self.bot.dispatch("foobltoobr_message_delete", message, hits)
                if foobltoobr_count > 0 and foobltoobr_time > 0:
                    user_count += 1
                    await self.config.member(author).foobltoobr_count.set(user_count)
                    if user_count >= foobltoobr_count and created_at.timestamp() < next_reset_time:
                        reason = _("Autoban (too many foobltoobred messages.)")
                        try:
                            await guild.ban(author, reason=reason)
                        except discord.HTTPException:
                            pass
                        else:
                            await modlog.create_case(
                                self.bot,
                                guild,
                                message.created_at.replace(tzinfo=timezone.utc),
                                "foobltoobrban",
                                author,
                                guild.me,
                                reason,
                            )

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.guild is None:
            return

        if await self.bot.cog_disabled_in_guild(self, message.guild):
            return

        author = message.author
        valid_user = isinstance(author, discord.Member) and not author.bot
        print(message)
        if not valid_user:
            return

        if await self.bot.is_automod_immune(message):
            return

        await set_contextual_locales_from_guild(self.bot, message.guild)

        await self.check_foobltoobr(message)

    @commands.Cog.listener()
    async def on_message_edit(self, _prior, message):
        # message content has to change for non-bot's currently.
        # if this changes, we should compare before passing it.
        await self.on_message(message)

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        if before.display_name != after.display_name:
            await self.maybe_foobltoobr_name(after)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        await self.maybe_foobltoobr_name(member)

    async def maybe_foobltoobr_name(self, member: discord.Member):

        guild = member.guild
        if (not guild) or await self.bot.cog_disabled_in_guild(self, guild):
            return

        if not member.guild.me.guild_permissions.manage_nicknames:
            return  # No permissions to manage nicknames, so can't do anything
        if member.top_role >= member.guild.me.top_role:
            return  # Discord Hierarchy applies to nicks
        if await self.bot.is_automod_immune(member):
            return
        guild_data = await self.config.guild(member.guild).all()
        if not guild_data["foobltoobr_names"]:
            return

        await set_contextual_locales_from_guild(self.bot, guild)

        if await self.foobltoobr_hits(member.display_name, member.guild):
            name_to_use = guild_data["foobltoobr_default_name"]
            reason = _("Foobltoobred nickname") if member.nick else _("Foobltoobred name")
            try:
                await member.edit(nick=name_to_use, reason=reason)
            except discord.HTTPException:
                pass
            return

    def oobify(self, message: str) -> str:
        v = '[aeiou]'
        V = '[AEIOU]'
        return re.sub(V, 'Oob', re.sub(v, 'oob', message))

    def oobify_hits(self, message: str, hits: Set[str]) -> str:
        oobified_message = message
        for hit in hits:
            oobified_message = oobified_message.replace(hit, self.oobify(hit))
        return oobified_message
