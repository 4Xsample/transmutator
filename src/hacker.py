"""
Hacker terminal animation content for phase transitions.

Mix of real technical output and iconic movie/TV quotes.
"""

import random
from typing import List, Dict, Any


QUOTES = [
    '"Shall we play a game?" — WOPR, WarGames (1983)',
    '"HACK THE PLANET!" — Dade Murphy, Hackers (1995)',
    '"I\'m in." — Every hacker movie ever',
    '"The Matrix has you..." — The Matrix (1999)',
    '"It\'s a Unix system! I know this!" — Lex Murphy, Jurassic Park (1993)',
    '"Stay frosty." — Cpl. Hicks, Aliens (1986)',
    '"Game over, man! Game over!" — Pvt. Hudson, Aliens (1986)',
    '"Hello, friend." — Elliot Alderson, Mr. Robot (2015)',
    '"Never send a human to do a machine\'s job." — Agent Smith, The Matrix (1999)',
    '"Mess with the best, die like the rest." — Crash Override, Hackers (1995)',
    '"Do. Or do not. There is no try." — Yoda (1980)',
    '"I\'ll be back." — T-800, The Terminator (1984)',
    '"Have you tried turning it off and on again?" — Roy, The IT Crowd',
    '"I see dead pixels." — Every sysadmin',
    '"sudo make me a sandwich" — xkcd #149',
    '"There is no spoon." — The Matrix (1999)',
    '"Wanna play a game?" — Q*bert, probably',
    '"Trust the process." — Ancient DevOps Proverb',
]


def _tech_lines_transform(ctx: Dict[str, Any]) -> List[str]:
    fc = ctx.get("files_count", 0)
    vc = ctx.get("video_count", 0)
    ac = ctx.get("audio_count", 0)
    preset = ctx.get("video_preset", "4Xmovie")
    bitrate = ctx.get("audio_bitrate", "320k")
    return [
        "> Inicialitzant matriu de transcodificació...",
        "> Carregant configuració de codecs...",
        f"> Fitxers detectats: {fc}",
        f">   Vídeo: {vc} fitxer(s)",
        f">   Àudio: {ac} fitxer(s)",
        "> Verificant HandBrakeCLI... OK",
        "> Verificant FFmpeg... OK",
        f"> Preset vídeo: {preset}",
        "> Resolució objectiu: 1080p (Fast Decode)",
        "> Codec: H.265/HEVC → H.264/AVC",
        f"> Bitrate àudio: {bitrate} CBR",
        "> Codec àudio: FLAC/WAV → MP3 (libmp3lame)",
        "> Allocating transcode buffer... 2048 MB",
        "> Validant integritat dels streams...",
        "> Pipeline ready.",
    ]


def _tech_lines_load(ctx: Dict[str, Any]) -> List[str]:
    fc = ctx.get("files_count", 0)
    return [
        "> Inicialitzant transferència a Plex...",
        "> Verificant connectivitat de xarxa...",
        "> Muntatge SMB/NFS: OK",
        f"> Fitxers a transferir: {fc}",
        "> Configurant rsync --remove-source-files...",
        "> Verificant espai al destí...",
        "> Destí: /mnt/PlexMedia/Downloads/",
        "> Pipeline de càrrega ready.",
    ]


def generate_animation(ctx: Dict[str, Any], num_quotes: int = 3) -> List[str]:
    """Return a list of ``(line, delay_s)`` for the hacker animation."""
    phase = ctx.get("phase", "transform")
    if phase == "load":
        tech = _tech_lines_load(ctx)
    else:
        tech = _tech_lines_transform(ctx)

    quotes = random.sample(QUOTES, min(num_quotes, len(QUOTES)))

    # Interleave quotes at roughly even intervals
    result: List[str] = []
    step = max(1, len(tech) // (num_quotes + 1))
    qi = 0
    for i, line in enumerate(tech):
        result.append(line)
        if qi < len(quotes) and (i + 1) % step == 0:
            result.append(f">  {quotes[qi]}")
            qi += 1

    result.append("> Començant processament...")
    return result
