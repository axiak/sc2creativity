import click
import pickle
import glob
import typing
import pandas as pd
import numpy as np

from sc2creativity import utils
from sc2creativity import types

# Start everything at 1 hour
INFINITY = 60 * 60
START_COL = "{}_start"
WEIGHT_COL = "{}_weight"


SELF_NAME_COL = "self_name"
SELF_RACE_COL = "self_race_is_{}"

OPPONENT_NAME_COL = "opponent_name"
OPPONENT_RACE_COL = "opponent_race_is_{}"

START_TIME_COL = "game_start"
DURATION_COL = "game_duration"

RACES = ("protoss", "zerg", "terran")


@click.command()
def build_dataframes():
    for fname in glob.glob(utils.data_dir("interim", "summaries_*.pickle")):
        build_dataframe(fname)


def build_dataframe(fname):
    with open(fname, 'rb') as f:
        summaries: typing.List[types.ReplaySummary] = pickle.load(f)

    my_race = None
    all_action_names = set()
    for summary in summaries:
        my_race = summary.self.race
        for action in summary.actions:
            all_action_names.add(action.name)


    ### Create columns
    columns = []
    action_name_index = {}

    def _add_column(column_name):
        columns.append(column_name)
        action_name_index[columns[-1]] = len(columns) - 1

    _add_column(START_TIME_COL)
    _add_column(DURATION_COL)

    _add_column(SELF_NAME_COL)
    for race in RACES:
        _add_column(SELF_RACE_COL.format(race))

    _add_column(OPPONENT_NAME_COL)
    for race in RACES:
        _add_column(OPPONENT_RACE_COL.format(race))

    for action_name in sorted(all_action_names):
        _add_column(START_COL.format(action_name))
        _add_column(WEIGHT_COL.format(action_name))

    start_cols = [col for col in columns
                  if col.endswith("_start") and col != START_TIME_COL]

    ## Build data
    data = []
    replay_ids = []

    for summary in summaries:
        row_dict = {
            col: 0. for col in columns
        }
        for col in start_cols:
            row_dict[col] = INFINITY

        row_dict[START_TIME_COL] = summary.start_time
        row_dict[DURATION_COL] = summary.real_duration_seconds

        row_dict[SELF_NAME_COL] = summary.self.name
        row_dict[OPPONENT_NAME_COL] = summary.opponent.name

        row_dict[SELF_RACE_COL.format(summary.self.race)] = 1.
        row_dict[OPPONENT_RACE_COL.format(summary.opponent.race)] = 1.

        for action in summary.actions:
            row_dict[WEIGHT_COL.format(action.name)] = action.event_weight
            row_dict[START_COL.format(action.name)] = action.first_event_time

        for col in start_cols:
            row_dict[col] = INFINITY / (row_dict[col] or 0.1)

        data.append([
            row_dict[col] for col in columns
        ])
        replay_ids.append(summary.replay_id)

    df = pd.DataFrame(columns=columns, data=data, index=replay_ids)
    print(df.head())
    df.to_hdf(utils.data_dir("processed", "summaries_{}.hdf".format(my_race)), "summaries")

