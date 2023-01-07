# Data updater for NBA MVP Prediction APP

This repository stores the container image files for the *AWS Lambda* function that updates the data on the NBA MVP Prediction App. The main repository containing the app files is hosted [here](https://github.com/Rodrixx05/nba-mvp-prediction-app-aws)

## Structure

This *AWS Lambda* function executes the following tasks:

1. Webscraping is used to extract individual stats (both standard and advanced) from each NBA player from [Basketball Reference](https://www.basketball-reference.com). To do that, the function uses a custom module (named basketball_reference_rodrixx) created to extract the stats from the website using *BeautifulSoup4* library. This same module does also some data cleaning and parses the information into a DataFrame.
2. The stats are pre-procesed so that the ML models can ingest them. This is achieved using a *Scikit-Learn* pipeline and several custom transformers defined in a custom module (named preprocessing_lib_rodrixx). The pipeline drops player rows which are repeated because of a team switch during the leage, sets indexes, encodes categorical data and drops some columns.
3. The processed stats are passed to the ML models and the MVP results are predicted. The models in pickle format are saved in an *AWS S3* bucket, so that the lambda function can load them in the execution process. These models are explained in more detail in [this section](#ml-models)
4. The output of the model is post-processed in order to extract additional metrics (votes, adjusted share and rank), and also deleted columns that were not used by the model are added again to the dataset. Column names are formatted so that the database can handle them. A custom module is used for this part of the process (named postprocessing_lib_rodrixx).
5. Post-processed data is finally appended to the corresponding PostgreSQL table using the *SQLalchemy* module.

### ML Models

The 3 machine learning models that are currently used by the app are based on the following methods:

- **Random Forest Regressor**: it combines the output of multiple decision trees to reach a single result.
- **XGBoost Regressor**: it implements the gradient boosting algorithm, adding one decision tree at a time to the ensemble and fit to correct the prediction errors made by prior models.
- **Ensemble Regressor**: it combines both previous methods using a voting regressor to obtain the final result.

All the models have been trained using individual stats (both standard and advanced stats) as predictors and the MVP voting share as the target, from the seasons between years 1982 and 2015. They have also been validated using data from seasons between 2015 and 2022. 

The output of the models is served in 4 different forms:

- **Predicted Share**: it's the percentage of votes received over the maximum votes a player can get. It's the target of the ML models, and it can be considered the "raw output" as no restrictions are applied in terms of total votes given. So if this perecentage was multiplied for the maximum number of votes a player can receive for each player and a summation was applied, the total number of votes awarded for all the players can be unrealistic. 
- **Predicted Votes**: it's the number of votes each player receives considering the predicted share. To avoid the issue presented in the above metric, the maximum number of votes a player can receive is taken into account (currently 1010, and it can be adjusted through a function in the postprocessing module). It then assumes that there will only be 17 contenders with votes from the jury (average value from the past seasons), so votes are distributed among the 17 players with best voting share, using their predicted share as the wheight of the distribution.
- **Adjusted Predicted Share**: using the predicted votes calculated in the above metric, the predicted share is adjusted considering the maximum number of votes a player can get.
- **Predicted Rank**: it simply ranks all the players using the predicted share.

Data was also extracted from [Basketball Reference](https://www.basketball-reference.com) using the same custom module mentioned in [this section](#data-updater). The tracking of all the experiments' parameters and results have been done with MLFlow. The notebooks containing the modelling work done can be found in this [repo](https://github.com/Rodrixx05/nba-mvp-prediction-modelling).

In the future, a significant improvement is expected to be applied to the models. The idea is to take into account how the panel votes for the players. Each member votes 5 players with the following votes scoring:
- 10 points to the first place player
- 7 points to the second place player
- 5 points to the third place player
- 3 points to the fourth place player
- 1 point to the fifth place player

Once the predicted share is obtained, an experiment would be run for each member of the panel to check which 5 players are chosen, using the predicted share of the players as the weighted probability. 