# -*- coding: utf-8 -*-
import discord
from discord.ext import commands

import json
from typing import *

from Utilities import retrieve_embed_field_index
from config import PREFIX, MIN_MATCH

ATTENDING_STRING = "Attending"
NOT_ATTENDING_STRING = "Not attending"
DELIMITER = ", "
BANANAWHISPERER = "Banana whisperer"


def add_user_to_embed_field(
    embed: discord.Embed, field: str, user: discord.User, options: Optional[Dict] = None
) -> bool:
    """
    Adds user to an embed field for a Banana atsub message. Returns True iff successful.
    Precondition: The desired field has value of the form "User1{DELIMITER}User2, ..."
    :param embed: discord.Embed
    :param field: str
    :param user: discord.User
    :param options: Dict
    :return: bool
    """
    # Currently no use of options in this function, but I imagine there might be uses in the future
    if not options:
        options = {}
    user_name = user.display_name
    index = retrieve_embed_field_index(field, embed)
    if index == -1:
        return False
    going_field = embed.fields[index]
    going_field_value_array = going_field.value.split(DELIMITER)
    if user_name in going_field_value_array:
        return False
    going_field_value_array.append(user_name)
    going_field_value_formatted = DELIMITER.join(going_field_value_array)
    embed.set_field_at(index=index, name=field, value=going_field_value_formatted)
    return True


def remove_user_from_embed_field(
    embed: discord.Embed, field: str, user: discord.User, options: Optional[Dict] = None
):
    """
    Removes a user to an embed field for a Banana atsub message. Returns True iff successful.
    Precondition: The desired field has value of the form "User1{DELIMITER}User2, ..."
    :param embed: discord.Embed
    :param field: str
    :param user: discord.User
    :param options: Dict
    :return: bool
    """
    if not options:
        options = {}
    ignores = options.pop("ignores", [])
    user_name = user.display_name
    if user_name in ignores:
        return False
    index = retrieve_embed_field_index(field, embed)
    if index == -1:
        return False
    going_field = embed.fields[index]
    user_name = user.display_name
    going_field_value_array = going_field.value.split(DELIMITER)
    if user_name not in going_field_value_array:
        return False
    going_field_value_array.remove(user_name)
    going_field_value_formatted = DELIMITER.join(going_field_value_array)
    embed.set_field_at(index=index, name=field, value=going_field_value_formatted)
    return True


class Subscription(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.description = "A way to mention a group of people without extra roles"

    # Adds BananaBot's server ids to subscriptions.json
    @commands.Cog.listener()
    async def on_ready(self):
        self._initialize_sub_data()
        print("Subscriptions activated.")

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction: discord.Reaction, user: discord.User):
        message = reaction.message
        # Check it's not Banana reacting
        if user == self.client.user or message.author != self.client.user:
            return
        # Check if the message sent is an atsub message
        if "Calling all" in message.embeds[0].title:
            embed = message.embeds[0]
            if reaction.emoji == "✅":
                # Nesting the if for code clarity in case future handlers continue the if block
                if add_user_to_embed_field(embed, ATTENDING_STRING, user):
                    await message.edit(embed=embed)
            elif reaction.emoji == "❌":
                pass

    @commands.Cog.listener()
    async def on_reaction_remove(self, reaction, user):
        message = reaction.message
        # Check it's not Banana reacting
        if user == self.client.user or message.author != self.client.user:
            return
        # Check if the message sent is an atsub message
        if "Calling all" in message.embeds[0].title:
            embed = message.embeds[0]
            if reaction.emoji == "✅":
                if remove_user_from_embed_field(
                    embed, ATTENDING_STRING, user, options={"ignores": [embed.author]}
                ):
                    await message.edit(embed=embed)
            elif reaction.emoji == "❌":
                pass

    async def _validate_user(self, ctx):
        is_banana_whisperer = any(
            role.name == BANANAWHISPERER for role in ctx.message.author.roles
        )
        is_admin = ctx.message.author.guild_permissions.administrator
        if not is_banana_whisperer and not is_admin:
            await ctx.send("Hey, you're not a Banana whisperer...")
            return False
        return True

    @commands.command(
        aliases=["mksub"],
        brief="Makes a subscription",
        description="Makes a subscription",
        usage=f"SUBSCRIPTION",
    )
    @commands.guild_only()
    async def makesub(self, ctx, sub_name):
        if not self._validate_user(ctx):
            return
        if len(sub_name) <= MIN_MATCH:
            await ctx.send(
                f"This name is too short! Please make this name at least {MIN_MATCH} characters long."
            )
            return
        sub_data = self._load_sub_data()
        server_id = str(ctx.guild.id)

        if server_id in sub_data:
            sub_dict = sub_data[server_id]
            if self._match_sub(sub_dict, sub_name) is not None:
                await ctx.send(
                    f"Subscription '{sub_name}' already exists. Please choose a different name."
                )
                return
            else:
                sub_dict[sub_name] = []
        else:
            sub_data[server_id] = {sub_name: []}

        self._write_sub_data(sub_data)
        await ctx.send(f"Subscription  '{sub_name}' successfully created.")

    @commands.command(
        aliases=["rmsub"],
        brief="Removes a subscription",
        description="Removes a subscription",
        usage=f"SUBSCRIPTION",
    )
    @commands.guild_only()
    async def removesub(self, ctx, sub_name):
        if not self._validate_user(ctx):
            return
        sub_data = self._load_sub_data()
        server_id = str(ctx.guild.id)
        if not self._sub_exists(server_id, sub_name, match_exact=True):
            await ctx.send(
                f"{sub_name} doesn't exist. Note this command is case sensitive!"
            )
            return
        sub_dict = sub_data[server_id]
        sub_dict.pop(sub_name)

        self._write_sub_data(sub_data)
        await ctx.send(f"Subscription  '{sub_name}' successfully removed.")

    """
    Takes in a subscription name and subscribes the message sender to sub_name. If there are additional arguments,
    then it instead subscribes all of the mentioned user in the message to sub_name
    """

    @commands.command(
        aliases=["sub"],
        brief="Subscribe",
        description="Subscribe",
        usage=f"SUBSCRIPTION",
    )
    @commands.guild_only()
    async def subscribe(self, ctx, sub_name, *args):
        json_file = self._load_sub_data()
        server_id = str(ctx.guild.id)
        if not self._sub_exists(server_id, sub_name, match_exact=True):
            await ctx.send(
                f"{sub_name} doesn't exist. You can check the subscriptions using `{PREFIX}lsub all`. "
                f"Note this command is case sensitive!"
            )
            return

        sub_dict = json_file[server_id]
        if len(args) > 0:
            if not ctx.author.guild_permissions.administrator:
                await ctx.send("You must be an administrator to do this")
                return

            for user in ctx.message.mentions:
                sub_dict[sub_name].append(str(user.id))

            await ctx.send(
                f"Subscribed {len(ctx.message.mentions)} users to {sub_name}"
            )
        else:
            if str(ctx.author.id) in sub_dict[sub_name]:
                await ctx.send(f"You've already subscribed to '{sub_name}'!")
            else:
                sub_dict[sub_name].append(str(ctx.author.id))
                await ctx.send(f"Subscribed to '{sub_name}' successfully")

        self._write_sub_data(json_file)

    @commands.command(
        aliases=["unsub"],
        brief="Unsubscribe",
        description="Unsubscribe",
        usage=f"SUBSCRIPTION",
    )
    @commands.guild_only()
    async def unsubscribe(self, ctx, sub_name, *args):
        json_file = self._load_sub_data()
        server_id = str(ctx.guild.id)
        if not self._sub_exists(server_id, sub_name, match_exact=True):
            await ctx.send(
                f"{sub_name} doesn't exist. Note this command is case sensitive!"
            )
            return

        sub_dict = json_file[server_id]
        if len(args) > 0:
            if not ctx.author.guild_permissions.administrator:
                await ctx.send("You must be an administrator to do this")
                return
            missed_msg = "Couldn't remove:\n"
            missed_num = 0
            for user in ctx.message.mentions:
                user_id = str(user.id)
                if user_id in sub_dict[sub_name]:
                    sub_dict[sub_name].remove(user_id)
                else:
                    missed_num += 1
                    missed_msg += f"{str(user.name)}\n"
            if missed_num > 0:
                await ctx.send(missed_msg)
            await ctx.send(
                f"Unsubscribed {len(ctx.message.mentions) - missed_num} users from {sub_name}"
            )
        else:
            user_id = str(ctx.author.id)
            if user_id not in sub_dict[sub_name]:
                await ctx.send(f"You're not in {sub_name}")
                return
            sub_dict[sub_name].remove(user_id)
            await ctx.send(f"Unsubscribed from {sub_name}")

        self._write_sub_data(json_file)

    """
    General command to list subscriptions. Formatting is as follows:
    lsu <opts>
    where opts is in 'all', 'subscribers', 'me' and may be input in any order.
    If 'subscribers' is in args, then the succeeding argument must be a sub name.
    """

    @commands.command(
        aliases=["lsub"],
        brief="List subscriptions",
        description="List subscriptions",
        usage=f"all|subscribers|me",
    )
    @commands.guild_only()
    async def listsubs(self, ctx, *args):
        json_file = self._load_sub_data()
        server_id = str(ctx.guild.id)
        if server_id not in json_file:
            await ctx.send("There are no subscriptions for this server.")
            return

        sub_dict = json_file[server_id]
        message = ""
        if "subscribers" in args:
            index = args.index("subscribers")
            sub_name = args[index + 1]
            if not self._sub_exists(server_id, sub_name, match_exact=True):
                await ctx.send(
                    f"Subscription '{sub_name}' does not exist. Note this command is case sensitive!"
                )
                return

            user_ids = sub_dict[sub_name]
            users = [await ctx.guild.fetch_member(i) for i in user_ids]
            message = f"{sub_name} members:\n"
            for user in users:
                message += f"    - {user.name}\n"

        if "me" in args:
            message += f"{ctx.author.name}, you are in:\n"
            num_subs = 0
            for sub in sub_dict:
                if str(ctx.author.id) in sub_dict[sub]:
                    message += f"    - {sub}\n"
                    num_subs += 1
            if num_subs == 0:
                message += f"No subs!\nCall `{PREFIX}sub sub_name` to subscribe.\n"

        if "all" in args or len(args) == 0:
            message += f"All {ctx.guild.name} subscriptions:\n"
            for sub_name in sub_dict.keys():
                message += f"    - {sub_name}\n"

        await ctx.send(message)

    @commands.command(
        brief="@'s users of a sub",
        description="@'s users of a sub",
        usage=f"SUBSCRIPTION",
        aliases=["@", "at", "a"],
    )
    @commands.guild_only()
    async def atsub(self, ctx, sub_name):
        async with ctx.typing():
            sub_data = self._load_sub_data()
            server_id = str(ctx.guild.id)

            if not self._sub_exists(server_id, sub_name, match_exact=False):
                await ctx.send(
                    f"{sub_name} doesn't exist, call `{PREFIX}mksub {sub_name}`"
                )
                return

            server_subs = sub_data.get(server_id)
            matched_server_subs = self._match_sub(server_subs, sub_name)

            # Multiple matches? We already guaranteed at least 1 match in the _sub_exists call
            if len(matched_server_subs) > 1:
                message_text = (
                    "There were multiple subscriptions that matched your query:\n"
                )
                for sub in matched_server_subs.keys():
                    message_text += f"    - {sub}\n"
                message_text += f"Try sending a more specific query"
                await ctx.send(message_text)
                return

            matched_sub_name = list(matched_server_subs.keys())[0]
            user_ids = matched_server_subs[matched_sub_name]

            if not user_ids:
                await ctx.send(
                    f"There are no users in {matched_sub_name}, you can sub to it with "
                    f"`{PREFIX}sub {matched_sub_name}`!"
                )
                return

            users = [await ctx.guild.fetch_member(user_id) for user_id in user_ids]
            embed = discord.Embed(
                title=f"**Calling all {matched_sub_name} members!**",
                description=f"If you don't want to be mentioned in this, call `{PREFIX}unsub "
                f"{matched_sub_name}`. \nNote that unsub is case sensitive!",
                color=0xFFFF00,
            )
            embed.set_author(
                name=ctx.author.display_name, icon_url=ctx.author.avatar_url
            )
            embed.add_field(name=ATTENDING_STRING, value=ctx.author.display_name)
            message_text = "||"
            for user in users:
                message_text += f"{user.mention}"
            message_text += "||"
            message = await ctx.send(message_text, embed=embed)
            await message.add_reaction("✅")
            await message.add_reaction("❌")

    """
    Given a dictionary of sub names to lists of users, match parameter sub_name and return the entries in the
    dictionary that match or None if none was found
    """

    def _match_sub(self, subs, sub_search):
        matched = {}
        sub_search = sub_search.lower()
        for sub, users in subs.items():
            sub_lower = sub.lower()
            match_length = max(MIN_MATCH, len(sub_search))
            if sub_lower[:match_length] == sub_search:
                matched[sub] = users
                if sub_lower == sub_search:
                    return matched
        if len(matched) == 0:
            return None
        return matched

    def _initialize_sub_data(self):
        json_file = self._load_sub_data()
        for server in self.client.guilds:
            server_id = str(server.id)
            if server_id not in json_file:
                json_file[server_id] = {}

        self._write_sub_data(json_file)

    def _load_sub_data(self):
        file = open("./cogs/subscription/subscriptions.json", mode="r")
        json_file = json.load(file)
        file.close()
        return json_file

    def _write_sub_data(self, json_file):
        file = open("./cogs/subscription/subscriptions.json", mode="w")
        json.dump(json_file, file, indent=4)
        file.close()

    def _sub_exists(self, server_id, sub_name, match_exact=True):
        json_file = self._load_sub_data()
        server_id = str(server_id)
        if match_exact:
            return server_id in json_file and sub_name in json_file[server_id]
        return (
            server_id in json_file
            and self._match_sub(json_file[server_id], sub_name) is not None
        )


def setup(client):
    client.add_cog(Subscription(client))
