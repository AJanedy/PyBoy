#!/usr/bin/env python3
#
# License: See LICENSE.md file
# GitHub: https://github.com/Baekalfen/PyBoy
#

import argparse
import copy
import os
import time

import pyboy
from pyboy import PyBoy
from pyboy.plugins.manager import parser_arguments
from pyboy.pyboy import defaults
from pyboy.utils import PyBoyInvalidInputException
import numpy as np
from moviepy.video.io.ImageSequenceClip import ImageSequenceClip
from moviepy.audio.AudioClip import AudioArrayClip


logger = pyboy.logging.get_logger(__name__)

INTERNAL_LOADSTATE = "INTERNAL_LOADSTATE_TOKEN"


def color_tuple(string):
    color_palette = [int(c.strip(), 16) for c in string.split(",")]
    if not (len(color_palette) == 4):
        raise PyBoyInvalidInputException(f"Not the correct amount of colors! Expected four, got {len(color_palette)}")
    return color_palette


def cgb_color_tuple(string):
    color_palette = [int(c.strip(), 16) for c in string.split(",")]
    if not (len(color_palette) == 12):
        raise PyBoyInvalidInputException(f"Not the correct amount of colors! Expected twelve, got {len(color_palette)}")
    return [color_palette[0:4], color_palette[4:8], color_palette[8:12]]


def valid_file_path(path):
    if not path == INTERNAL_LOADSTATE and not os.path.isfile(path):
        logger.error("Filepath '%s' couldn't be found, or isn't a file!", path)
        exit(1)
    return path


def valid_volume(vol):
    if isinstance(vol, bool):
        return 100 if vol else 0
    elif vol.isnumeric() and (0 <= int(vol) <= 100):
        return int(vol)
    else:
        raise ValueError("Invalid volume")


def valid_sample_rate(freq):
    if freq.isnumeric() and int(freq) % 60 == 0:
        return int(freq)
    else:
        raise ValueError("Invalid sample rate")


""" ########################### MODIFIED CODE: ANDREW JANEDY ###################################################### """


def get_video_frame(emulator):
    frame_np = np.array(emulator.screen.image)
    if frame_np.shape != (144, 160, 4):
        frame_np = np.resize(frame_np, (144, 160, 4))

    return frame_np


def sanitize_game_title(gamerom):

    file_name = os.path.splitext(os.path.basename(gamerom))[0]
    cleaned_file_name = file_name.replace(" - ", "_").replace(" ", "_")

    return cleaned_file_name


def merge_av(audio_frames, video_frames, file_path):

    video_frames = [frame[:, :, :3] for frame in video_frames]
    video = ImageSequenceClip(video_frames, fps=60)

    sample_rate = 48000

    audio = np.vstack(audio_frames)  # Stack frames into large array

    if audio.dtype != np.float32 and audio.dtype != np.float64:
        audio = audio.astype(np.float32)

    max_val = np.max(np.abs(audio))
    if max_val > 1:
        audio = audio / max_val * 0.5

    audio_clip = AudioArrayClip(audio, fps=sample_rate)

    video = video.with_audio(audio_clip)

    video.write_videofile(file_path, codec="libx264", audio_codec="aac")


""" ############################ END MODIFIED CODE ################################################################# """

parser = argparse.ArgumentParser(
    description="PyBoy -- Game Boy emulator written in Python",
    epilog="Warning: Features marked with (internal use) might be subject to change.",
)
parser.add_argument("ROM", type=valid_file_path, help="Path to a Game Boy compatible ROM file")

""" ########################### MODIFIED CODE: ANDREW JANEDY ###################################################### """

parser.add_argument("-k", "--keybinds", type=str, help="JSON string of key bind map")
# parser.add_argument("-sr", "--screen_record", action='store_true', help="Enable screen recording")

parser.add_argument(
    "-sr", "--screen_record",
    nargs="?",
    const=True,      # If user just does -sr, it sets to True
    default=False,   # If user omits -sr entirely, it's False
    help="Enable screen recording. Optionally specify a filename."
)

""" ############################ END MODIFIED CODE ################################################################# """

parser.add_argument("-b", "--bootrom", dest="bootrom", type=valid_file_path, help="Path to a boot-ROM file")
parser.add_argument("--no-input", action="store_true", help="Disable all user-input (mostly for autonomous testing)")
parser.add_argument(
    "--log-level",
    default=defaults["log_level"],
    type=str,
    choices=["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"],
    help="Set logging level",
)
parser.add_argument(
    "--color-palette",
    type=color_tuple,
    default=defaults["color_palette"],
    help=('Four comma seperated, hexadecimal, RGB values for colors (i.e. "FFFFFF,999999,555555,000000")'),
)
parser.add_argument(
    "--cgb-color-palette",
    type=cgb_color_tuple,
    default=defaults["cgb_color_palette"],
    help=(
        'Three sets of four comma seperated, hexadecimal, RGB values for colors in the order of: background, obj0, obj1 (i.e. "FFFFFF,7BFF31,0063C5,000000,FFFFFF,FF8484,FF8484,000000,FFFFFF,FF8484,FF8484,000000")'
    ),
)
parser.add_argument(
    "-l",
    "--loadstate",
    nargs="?",
    default=None,
    const=INTERNAL_LOADSTATE,
    type=valid_file_path,
    help=(
        "Load state from file. If filepath is specified, it will load the given path. Otherwise, it will automatically "
        "locate a saved state next to the ROM file."
    ),
)
parser.add_argument(
    "-w",
    "--window",
    default=defaults["window"],
    type=str,
    choices=["SDL2", "OpenGL", "null"],
    help="Specify window-type to use",
)
parser.add_argument("-s", "--scale", default=defaults["scale"], type=int, help="The scaling multiplier for the window")
parser.add_argument("--no-renderer", action="store_true", help="Disable rendering (internal use)")
parser.add_argument(
    "--gameshark",
    type=str,
    help="Add GameShark cheats on start-up. Add multiple by comma separation (i.e. '010138CD, 01033CD1')",
)

gameboy_type_parser = parser.add_mutually_exclusive_group()
gameboy_type_parser.add_argument(
    "--dmg", action="store_const", const=False, dest="cgb", help="Force emulator to run as original Game Boy (DMG)"
)
gameboy_type_parser.add_argument(
    "--cgb", action="store_const", const=True, dest="cgb", help="Force emulator to run as Game Boy Color"
)

# NOTE: Inverted logic on variable
parser.add_argument(
    "--no-sound-emulation",
    default=True,
    action="store_false",
    dest="sound_emulated",
    help="Disables sound emulation (not just muted!)",
)

sound_parser = parser.add_mutually_exclusive_group()

sound_parser.add_argument(
    "--sound",
    action="store_const",
    const=100,
    dest="sound_volume",
    help="Deprecated setting. Now sets sound volume to 100%%. See '--sound-volume'",
)
sound_parser.add_argument(
    "--sound-volume",
    default=100,
    type=valid_volume,
    help="Set sound volume in percent (0-100)",
)
parser.set_defaults(sound_volume=100)

parser.add_argument(
    "--sound-sample-rate",
    default=None,
    type=valid_sample_rate,
    help="Set sound sample rate. Has to be divisible in 60.",
)

for arguments in parser_arguments():
    for a in arguments:
        *args, kwargs = a
        if args[0] not in parser._option_string_actions:
            parser.add_argument(*args, **kwargs)


def main():
    argv = parser.parse_args()

    print(
        """
The Game Boy controls are as follows:

| Keyboard key | GameBoy equivalant |
| ---          | ---                |
| Up           | Up                 |
| Down         | Down               |
| Left         | Left               |
| Right        | Right              |
| A            | A                  |
| S            | B                  |
| Return       | Start              |
| Backspace    | Select             |

The other controls for the emulator:

| Keyboard key | Emulator function       |
| ---          | ---                     |
| F11          | Toggle fullscreen       |
| Escape       | Quit                    |
| D            | Debug                   |
| Space        | Unlimited FPS           |
| Z            | Save state              |
| X            | Load state              |
| I            | Toggle screen recording |
| O            | Save screenshot         |
| ,            | Rewind backwards        |
| .            | Rewind forward          |
| J            | Memory Window + 0x100   |
| K            | Memory Window - 0x100   |
| Shift + J    | Memory Window + 0x1000  |
| Shift + K    | Memory Window - 0x1000  |

See "pyboy --help" for how to enable rewind and other awesome features!
"""
    )
    # Start PyBoy and run loop
    kwargs = copy.deepcopy(vars(argv))
    kwargs.pop("ROM", None)
    kwargs.pop("loadstate", None)
    kwargs.pop("no_renderer", None)
    kwargs.pop("screen_record", None)  # MODIFIED CODE: ANDREW JANEDY
    if hasattr(argv, 'keybinds') and argv.keybinds is not None:
        kwargs['keybinds'] = argv.keybinds  # MODIFIED CODE: ANDREW JANEDY
    pyboy = PyBoy(argv.ROM, **kwargs)

    if argv.loadstate is not None:
        if argv.loadstate == INTERNAL_LOADSTATE:
            state_path = argv.ROM + ".state"
        else:
            state_path = argv.loadstate

        valid_file_path(state_path)
        with open(state_path, "rb") as f:
            pyboy.load_state(f)

    """ ########################### MODIFIED CODE: ANDREW JANEDY ################################################### """

    video_frames = []
    audio_frames = []
    mp4_file_path = None
    scrn_rec_fold = os.path.join(os.path.dirname(__file__), '..', 'pyboy_gui', 'screen_recordings')

    if argv.screen_record:
        cleaned_game_title = sanitize_game_title(pyboy.gamerom)
        timestamp = time.strftime("%m.%d.%Y_%H.%M.%S")
        file_name = f"{cleaned_game_title}_{timestamp}"
        mp4_file_path = os.path.join(scrn_rec_fold, file_name + ".mp4")

    while pyboy.tick():
        if argv.screen_record:
            video_frames.append(np.array(pyboy.screen.image))
            audio_frames.append(pyboy.sound.ndarray.copy())

    pyboy.stop()

    if argv.screen_record:
        merge_av(audio_frames, video_frames, mp4_file_path)
    """ #################################### END MODIFIED CODE ##################################################### """


if __name__ == "__main__":
    main()
