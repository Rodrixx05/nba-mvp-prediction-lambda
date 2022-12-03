from datetime import datetime, date
import os
import re
import pickle

import pandas as pd
from sklearn.pipeline import Pipeline
from sqlalchemy import create_engine

import boto3

import utils.basketball_reference_rodrixx as brr
import utils.postprocessing_lib_rodrixx as post
import utils.preprocessing_lib_rodrixx as prep

models_bucket = os.environ['S3_BUCKET_MODELS']
season = int(os.environ['SEASON'])
conn_url = os.getenv('NBA_DB_CON')
s3 = boto3.resource("s3")

def handler(event, context):
    getter = brr.BasketballReferenceGetter()
    raw_df = getter.extract_player_stats_multiple(season, mvp = False, advanced = True, ranks = True)

    cols_tot = [col for col in raw_df.columns if '_tot' in col]
    cols_to_drop = ['Rk', 'G', 'GS', 'GT', 'Tm']
    cols_to_drop += cols_tot
    col_to_ohe = 'Pos'

    pipe_prep = Pipeline(steps = [
        ('DropPlayersMultiTeams', prep.DropPlayersMultiTeams()),
        ('SetIndex', prep.SetIndex()),
        ('OHE', prep.OHE(col_to_ohe)),
        ('DropColumns', prep.DropColumns(cols_to_drop)),
        ('DropPlayers', prep.DropPlayers()),
    ])

    pre_df = pipe_prep.fit_transform(raw_df)

    bucket = s3.Bucket(models_bucket)

    predictions_list = []

    for obj in bucket.objects.all():
        model = pickle.loads(obj.get()['Body'].read())
        prediction = model.predict(pre_df)
        model_type = re.match('^model_(.+)\.pkl$', obj.key).group(1)
        prediction_series = pd.Series(prediction, index = pre_df.index, name = f'PredShare_{model_type}')
        predictions_list.append(prediction_series)

    prediction_df = pd.concat(predictions_list, axis = 1)

    post_df = post.get_processed_prediction(prediction_df, pipe_prep['DropPlayers'].players_list)
    post_df['Datetime'] = date.today()

    final_df = pd.concat([post_df, pre_df], axis = 1)
    final_df = post.add_deleted_columns(final_df, pipe_prep['DropColumns'].drop_df, pipe_prep['OHE'].ohe_series)
    final_df.reset_index(inplace = True, drop = True)
    final_df.columns = map(post.format_column_name, final_df.columns)

    conn = create_engine(conn_url)

    final_df.to_sql(f'stats_predictions_{season}', conn, if_exists = 'append', index = False)