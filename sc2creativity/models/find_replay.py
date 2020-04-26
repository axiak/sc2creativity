import glob
import hashlib
import multiprocessing
import os
import shutil
import tempfile
import zipfile
import random

import click
import sc2reader

from sc2creativity import utils

CPUS = max(1, multiprocessing.cpu_count() - 2)
MAX_REPLAYS = 100000


@click.command()
@click.option("--replay-id")
@click.option("--output-directory")
def find_replay(replay_id, output_directory):
    replay_id, player_id = replay_id.split('_')
    player_id = int(player_id)
    garbage = []
    try:
        all_replays = []
        for source_file in glob.glob(utils.data_dir("raw", "replays", "*")):
            all_replays.extend(replay_files(source_file, garbage))
        random.shuffle(all_replays)
        print("  !! Searching {} replays.".format(len(all_replays)))
        with multiprocessing.Pool(CPUS) as p:
            args = [(replay_id, player_id, fname) for fname in all_replays]
            for i, (found_fname, found_player) in enumerate(p.imap_unordered(search_file, args)):
                if found_fname is not None:
                    target_file = os.path.join(
                        output_directory,
                        "{}-{}.SC2Replay".format(
                            replay_id, found_player
                        )
                    )
                    print("  !! Found replay. Placing in {}".format(target_file))
                    shutil.copy(found_fname, target_file)
                    return
                if i > 0 and i % 10 == 0:
                    print("  !! Completed {} replays.".format(i))
                if i > MAX_REPLAYS:
                    break
    finally:
        cleanup_garbage(garbage)


def search_file(args):
    replay_id, player_id, fname = args
    replay = sc2reader.load_replay(fname)

    if replay.type == '1v1' and \
            replay_id == build_replay_id(replay):
        player = "{}".format(replay.player[player_id + 1])
        return fname, player
    else:
        return None, None


def build_replay_id(replay):
    hasher = hashlib.sha256()
    hasher.update(replay.release_string.encode("utf8"))
    hasher.update(
        "{0} on {1} at {2}".format(replay.type, replay.map_name, replay.start_time).encode("utf8")
    )
    for team in replay.teams:
        for player in team.players:
            hasher.update("{0}".format(player).encode("utf8"))
    return hasher.hexdigest()


def cleanup_garbage(garbage):
    for fname in garbage:
        try:
            os.unlink(fname)
        except:
            pass


def replay_files(source_file, garbage=None):
    if source_file.lower().endswith(".sc2replay"):
        yield source_file
        return
    elif not source_file.lower().endswith(".zip"):
        return
    with zipfile.ZipFile(source_file) as zf:
        for member in zf.namelist():
            if not member.lower().endswith(".sc2replay"):
                continue
            tf = tempfile.NamedTemporaryFile(suffix=os.path.basename(member), delete=False)
            garbage.append(tf.name)
            with zf.open(member) as source, \
                    open(tf.name, "wb") as of:
                shutil.copyfileobj(source, of)
            yield tf.name

