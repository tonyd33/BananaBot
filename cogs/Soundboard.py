import discord
from discord.ext import commands, tasks
import asyncio
import os
import re

from config import PREFIX

class SoundBoard(commands.Cog):

    def __init__(self, client):
        self.client = client
        self.description = "A soundboard"

    @commands.Cog.listener()
    async def on_ready(self):
        print('SoundBoard activated.')

    @commands.command(aliases=['lsb'],
                      brief="Lists sounds",
                      description="List sounds",
                      usage=f"PATH")
    @commands.guild_only()
    async def listSounds(self, ctx, *args):
        # this gives a wonky path if args is like "path/to/directory" rather than "path to directory", need check
        path = '/'.join(args)
        msg = self._rlistSounds(path)
        if msg is None:
            await ctx.send("Sorry, I couldn't find your path")
            return
        await ctx.send(msg)

    def _rlistSounds(self, path, depth=0):
        """
        Given a path relative to ./cogs/soundboard/, return a formatted message displaying all subdirectories and files
        recursively
        """
        root = './cogs/soundboard/'
        rel = os.path.join(root, path)
        if not os.path.exists(rel):
            return None
        msg = ''
        for item in os.listdir(rel):
            rel_item_path = os.path.join(rel, item)
            if os.path.isdir(rel_item_path):
                msg += f"{'  ' * depth}/{item}\n"
                msg += self._rlistSounds(os.path.join(path, item), depth=depth + 1)
            else:
                regex = '([^.]*).[^.]*'
                basename = os.path.basename(rel_item_path)
                match = re.search(regex, basename)
                if match is not None:
                    msg += f"{'  ' * depth}-{match.group(1)}\n"
        return msg

    @commands.command(aliases=['sb', 'sound'],
                      brief="Plays a sound",
                      help="Plays a sound",
                      usage=f"[PATHTOSOUND...]")
    @commands.guild_only()
    async def soundboard(self, ctx, *args):
        """
        Takes in a space separated path to a sound and plays it.
        """
        path = '/'.join(args)
        root = './cogs/soundboard/'
        relpath = os.path.join(root, f'{path}.mp3')
        if not os.path.exists(relpath):
            await ctx.send("Couldn't find the sound.")
            return

        voice = ctx.guild.voice_client
        author = ctx.author

        def leave(err):
            # asyncio.run_coroutine_threadsafe(voice.disconnect(), self.client.loop)
            pass

        if voice and voice.channel and not voice.is_playing():
            voice.play(discord.FFmpegPCMAudio(relpath), after=None)
            voice.source = discord.PCMVolumeTransformer(voice.source)
            voice.source.volume = 1
        elif author.voice is not None and author.voice.channel is not None:
            voice = await author.voice.channel.connect(timeout=30, reconnect=True)
            voice.play(discord.FFmpegPCMAudio(relpath), after=None)
            voice.source = discord.PCMVolumeTransformer(voice.source)
            voice.source.volume = 1

        await self.timeoutleave(voice)

    async def timeoutleave(self, voice, timeout=300):
        """
        Waits timeout amount of seconds before leaving the voice channel
        """
        if not voice:
            return
        while voice.is_playing():
            await asyncio.sleep(1)
        else:
            await asyncio.sleep(timeout)
            while voice.is_playing():
                break
            else:
                await voice.disconnect()

    @commands.command(brief="Makes Banana disconnect from the channel",
                      description="Makes Banana disconnect from the channel")
    @commands.guild_only()
    async def leave(self, ctx):
        voice = ctx.guild.voice_client
        if voice is None:
            await ctx.send("I'm not in a channel!")
            return
        # maybe have it play a cute sound before leaving or something idk lol
        await voice.disconnect()


def setup(client):
    client.add_cog(SoundBoard(client))
