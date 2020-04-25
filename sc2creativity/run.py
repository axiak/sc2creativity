import glob
import os
import typing


try:
    from sc2creativity import models
except ImportError:
    import models

import sc2reader
from sc2reader import events as sc2events

BANNED_ABILITIES = set("""
CreepTumor
ToOverseer
""".split())


WEIGHT_DECAY_HALF_LIFE_SECONDS = 120.
MAX_INITIAL_TIME = 600.


def main():
    folder = '/home/axiak/Documents/Games/battlenet/drive_c/users/axiak/My Documents/StarCraft II/Accounts/77567716/1-S2-1-3269512/Replays/Multiplayer'
    for replay_fname in glob.glob(os.path.join(folder, 'Zen*.SC2Replay')):
        handle_replay(replay_fname)


def handle_replay(fname):
    replay = sc2reader.load_replay(fname)
    if replay.type != '1v1':
        return
    for player in range(2):
        summary = summarize_replay(replay, player)
        print(summary)


def summarize_replay(replay, player_id_zero_idx) -> models.ReplaySummary:
    other_player = 1 - player_id_zero_idx
    self_race = replay.player[player_id_zero_idx + 1].play_race
    opponent_race = replay.player[other_player + 1].play_race
    actions = {}
    for event in get_build_events(replay, player_id_zero_idx + 1):
        accumulator = actions.get(event.target_name)
        if accumulator is None and event.second <= MAX_INITIAL_TIME:
            accumulator = actions[event.target_name] = models.ActionEvents(
                name=event.target_name,
                all_event_times=[]
            )
        if accumulator is not None:
            accumulator.all_event_times.append(event.second)
    action_rollups = []
    for action in actions.values():
        times = sorted(action.all_event_times)
        start = times[0]

        action_rollups.append(models.ActionRollup(
            name=action.name,
            first_event_time=start,
            event_weight=sum(
                0.5 ** ((time - start) / float(WEIGHT_DECAY_HALF_LIFE_SECONDS))
                for time in times
            )))
    action_rollups.sort(key=lambda x: x.name)
    return models.ReplaySummary(
        self_race=self_race,
        opponent_race=opponent_race,
        actions=action_rollups
    )


def get_build_events(replay, player_id) -> typing.Iterable[models.BuildEvent]:
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
                yield models.BuildEvent(
                    second=event.second,
                    target_name=name
                )


if __name__ == '__main__':
    main()

