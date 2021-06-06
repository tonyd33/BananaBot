from discord import FFmpegAudio
from discord.opus import Encoder as OpusEncoder
from discord.ext import commands

import time

from config import PREFIX

class FFmpegPulseAudio(FFmpegAudio):
    def __init__(self, source, *, executable='ffmpeg', args, **subprocess_kwargs):
        super().__init__(source, executable=executable, args=args, **subprocess_kwargs)
        time.sleep(1)

    def read(self):
        ret = self._stdout.read(OpusEncoder.FRAME_SIZE)
        if len(ret) != OpusEncoder.FRAME_SIZE:
            return b''
        return ret

    def is_opus(self):
        return False

# TODO: Media controls, possibly remove Soundboard and integrate it here
class Radio(commands.Cog):
    """
    A multipurpose cog for playing and controlling audio through Banana's PulseAudio sink.
    """
    def __init__(self, client):
        self.client = client
        self.description = "BananaRadio"

    @commands.Cog.listener()
    async def on_ready(self):
        print('Radio activated.')

    @commands.command()
    async def radioctl(self, ctx, *commands):
        """
        COMMANDS
            connect
                Connect to channel that the user is in
            start
                Start audio stream
            spotify QUERY_OR_URL
                Plays a spotify song based on a query or Spotify URL
        """
        index = 0
        while index < len(commands):
            try:
                command = commands[index]
                if 'connect' in command:
                    await self.connect_to_channel(ctx)
                elif 'start' in command:
                    self.start_audio_stream(ctx)
                elif 'spotify' in command:
                    query_or_url = commands[index + 1]
                    # TODO: implement
                index += 1
            except IndexError as e:
                await ctx.send("Expected additional arguments")


    async def connect_to_channel(self, ctx):
        voice = ctx.guild.voice_client
        author = ctx.author

        if voice and voice.channel:
            await ctx.send("I'm already in a channel!")
            return False
        if author.voice is not None and author.voice.channel is not None:
            await author.voice.channel.connect(timeout=30, reconnect=True)
            return True
        return False

    def start_audio_stream(self, ctx):
        voice = ctx.guild.voice_client

        if voice and voice.channel and not voice.is_playing():
            # TODO: Get correct sink, audio_rate, audio_channels or get from config
            sink = '0'
            audio_rate = '44100'
            audio_channels = '2'
            args = []
            input_args = f'-f pulse -i {sink} -ar {audio_rate} -ac {audio_channels}'.split(' ')
            output_args = '-f s16le -ar 48000 -ac 2 -loglevel warning pipe:1'.split(' ')
            args.extend(input_args)
            args.extend(output_args)
            voice.play(FFmpegPulseAudio(sink, args=args), after=None)
            return True
        return False

def setup(client):
    client.add_cog(Radio(client))