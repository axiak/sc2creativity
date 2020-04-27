import collections
import glob
import hashlib
import multiprocessing
import os
import pickle
import shutil
import tempfile
import typing
import zipfile

import click
import sc2reader
from sc2reader import events as sc2events

from sc2creativity import types
from sc2creativity import utils

BANNED_ABILITIES = set("""
CreepTumor
ToOverseer
""".split())


WEIGHT_DECAY_HALF_LIFE_SECONDS = 120.
MAX_INITIAL_TIME = 7.5 * 60
CPUS = max(1, multiprocessing.cpu_count() - 2)
MAX_REPLAYS = 10000
RACES = ("terran", "protoss", "zerg")


@click.command()
def build_summaries():
    garbage = []
    try:
        summaries_by_race = collections.defaultdict(list)
        all_replays = []
        for source_file in glob.glob(utils.data_dir("raw", "replays", "*")):
            all_replays.extend(replay_files(source_file, garbage))
        print("  !! Processing {} replays.".format(len(all_replays)))
        with multiprocessing.Pool(CPUS) as p:
            for i, summaries in enumerate(p.imap_unordered(summaries_for_replay, all_replays)):
                for summary in summaries:
                    summaries_by_race[summary.self.race].append(summary)
                if i > 0 and i % 10 == 0:
                    print("  !! Completed {} replays.".format(i))
                if i > MAX_REPLAYS:
                    break
        print("  !! Writing summaries to data dir.")
        for race, summaries in summaries_by_race.items():
            write_race(race, summaries)
    finally:
        cleanup_garbage(garbage)


def write_race(race, summaries):
    fname = utils.data_dir("interim", "summaries_{}.pickle".format(race.lower()))
    all_summaries = summaries

    old_summaries = load_old_summaries(fname)
    if old_summaries is not None:
        all_summaries = old_summaries
        ignore_ids = set(summary.replay_id for summary in all_summaries)
        for summary in summaries:
            if summary.replay_id not in ignore_ids:
                all_summaries.append(summary)
    with open(fname, 'wb+') as of:
        pickle.dump(all_summaries, of)
    print("Wrote {}".format(fname))


def load_old_summaries(fname):
    if os.path.exists(fname):
        with open(fname, 'rb') as f:
            try:
                return pickle.load(f)
            except:
                pass


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


def summaries_for_replay(fname):
    replay = sc2reader.load_replay(fname)
    if replay.type != '1v1':
        return []
    summaries = []
    replay_id = build_replay_id(replay)
    for player in range(2):
        summary = summarize_replay(replay, player, "{}_{}".format(
            replay_id, player
        ))
        if summary is not None:
            summaries.append(summary)
    return summaries


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


def summarize_replay(replay, player_id_zero_idx, replay_id) -> typing.Optional[types.ReplaySummary]:
    other_player = 1 - player_id_zero_idx
    self_race = _get_race(replay, player_id_zero_idx + 1)
    opponent_race = _get_race(replay, other_player + 1)
    if self_race is None or opponent_race is None:
        return
    actions = {}
    for event in get_build_events(replay, player_id_zero_idx + 1):
        accumulator = actions.get(event.target_name)
        if accumulator is None and event.second <= MAX_INITIAL_TIME:
            accumulator = actions[event.target_name] = types.ActionEvents(
                name=event.target_name,
                all_event_times=[]
            )
        if accumulator is not None:
            accumulator.all_event_times.append(event.second)


    action_rollups = []
    for action in actions.values():
        times = sorted(action.all_event_times)
        start = times[0]

        action_rollups.append(types.ActionRollup(
            name=action.name,
            first_event_time=start,
            event_weight=sum(
                0.5 ** ((time - start) / float(WEIGHT_DECAY_HALF_LIFE_SECONDS))
                for time in times
            )))
    action_rollups.sort(key=lambda x: x.name)
    return types.ReplaySummary(
        self=types.ReplayPlayer(
            name=replay.player[player_id_zero_idx + 1].name,
            winner=replay.player[player_id_zero_idx + 1].result == 'Win',
            race=self_race
        ),
        opponent=types.ReplayPlayer(
            name=replay.player[other_player + 1].name,
            winner=replay.player[other_player + 1].result == 'Win',
            race=opponent_race
        ),
        actions=action_rollups,
        start_time=replay.start_time,
        replay_id=replay_id,
        real_duration_seconds=int(replay.real_length.total_seconds())
    )


def _get_race(replay, player_id):
    race = replay.player[player_id].play_race.lower()
    if race not in RACES:
        print("  !! Invalid race: {}".format(race))
        return None
    else:
        return race


def get_build_events(replay, player_id) -> typing.Iterable[types.BuildEvent]:
    for event in replay.player[player_id].events:
        if not isinstance(event, sc2events.CommandEvent):
            continue
        if not event.has_ability:
            continue
        for prefix in ('Train', 'Build', 'Morph', 'Upgrade', 'Research'):
            if event.ability_name and event.ability_name.startswith(prefix):
                name = event.ability_name[len(prefix):]
                if name in BANNED_ABILITIES:
                    continue
                yield types.BuildEvent(
                    second=event.second,
                    target_name=name
                )

