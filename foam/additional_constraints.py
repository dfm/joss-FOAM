import sys
from functools import partial
import numpy as np
import pandas as pd
from pathlib import Path
################################################################################
def spectro_constraint(merit_values_file, observations_file=None, nsigma=3, spectro_companion=None, isocloud_grid_summary=None, spectroGrid_file=None):
    """
    Enforce an n-sigma constraint on the models based on the spectoscopic observations.
    Save this as a file with prefix indicating how many sigma the error box was.
    ------- Parameters -------
    merit_values_file: string
        Path to the hdf5 files with the merit funtion values and the spectroscopic info of the models in the grid.
    observations_file: string
        Path to the tsv file with observations, with a column for each observable and each set of errors.
        Column names specify the observable, and "_err" suffix denotes that it's the error.
    nsigma: int
        How many sigmas you want to make the interval to accept models.
    spectro_companion: dict
        Information on the companion star. Set to None to model single stars,
        or provide this to include binary constraints using isochrone-clouds.
    isocloud_grid_directory: string
        Directory holding the grid for the isochrone-cloud modelling.
    spectroGrid_file: string
        File with the spectroscopic info and ages of the model-grid.
    """
    Obs_dFrame = pd.read_table(observations_file, delim_whitespace=True, header=0)
    df_Theo = pd.read_hdf(merit_values_file)

    df_Theo = df_Theo[df_Theo.logTeff < np.log10(Obs_dFrame['Teff'][0]+nsigma*Obs_dFrame['Teff_err'][0])]
    df_Theo = df_Theo[df_Theo.logTeff > np.log10(Obs_dFrame['Teff'][0]-nsigma*Obs_dFrame['Teff_err'][0])]
    df_Theo = df_Theo[df_Theo.logg < Obs_dFrame['logg'][0]+nsigma*Obs_dFrame['logg_err'][0]]
    df_Theo = df_Theo[df_Theo.logg > Obs_dFrame['logg'][0]-nsigma*Obs_dFrame['logg_err'][0]]
    df_Theo = df_Theo[df_Theo.logL < Obs_dFrame['logL'][0]+nsigma*Obs_dFrame['logL_err'][0]]
    df_Theo = df_Theo[df_Theo.logL > Obs_dFrame['logL'][0]-nsigma*Obs_dFrame['logL_err'][0]]

    if spectro_companion is not None:
        if (isocloud_grid_summary is None) or (spectroGrid_file is None):
            logger.error('Please supply a directory for the isocloud grid and a path to the file with the grid spectroscopy and ages.')
            sys.exit()

        spectroGrid_dataFrame = pd.read_hdf(spectroGrid_file)

        func = partial(enforce_binary_constraints, spectro_companion=spectro_companion, isocloud_grid_summary=isocloud_grid_summary, nsigma=nsigma, spectroGrid_dataFrame=spectroGrid_dataFrame)
        indices_to_drop = df_Theo.apply(func, axis=1)
        for index_to_drop in indices_to_drop:
            if (index_to_drop is not None) and (index_to_drop==index_to_drop):
                df_Theo.drop(index_to_drop, inplace=True)

    outputFile = f'{nsigma}sigmaSpectro_{merit_values_file}'
    Path(outputFile).parent.mkdir(parents=True, exist_ok=True)
    df_Theo.to_hdf(f'{outputFile}', 'spectro_constrained_models', format='table', mode='w')

################################################################################
def get_age(model, df):
    """
    Get the age of the models one step older and younger than the provided model.
    ------- Parameters -------
        model: pandas series
            Parameters of the model.
        df: pandas dataframe
            Dataframe with the model parameters and age (and spectroscopic info) of the theoretical models.

    ------- Returns -------
    min_age, max_age: tuple of integers
        Age of the model one sep younger and older than the procided model,
        these are the minimum and maximum age to accept models in the isochrone-cloud.
    """
    unique_xc=pd.unique(df[ np.isclose(df.Z, model.Z) ].Xc)

    if abs(model.Xc-max(unique_xc))<1E-4:
        min_age = 0
        max_age = int(df.loc[np.isclose(df.Z, model.Z) & np.isclose(df.M, model.M) & np.isclose(df.logD, model.logD) & np.isclose(df.aov, model.aov) & np.isclose(df.fov, model.fov) & np.isclose(df.Xc, round(model.Xc-0.01, 2))].age)
    elif abs(model.Xc-min(unique_xc))<1E-4:
        min_age = int(df.loc[np.isclose(df.Z, model.Z) & np.isclose(df.M, model.M) & np.isclose(df.logD, model.logD) & np.isclose(df.aov, model.aov) & np.isclose(df.fov, model.fov) & np.isclose(df.Xc, round(model.Xc+0.01, 2))].age)
        age     = int(df.loc[np.isclose(df.Z, model.Z) & np.isclose(df.M, model.M) & np.isclose(df.logD, model.logD) & np.isclose(df.aov, model.aov) & np.isclose(df.fov, model.fov) & np.isclose(df.Xc, round(model.Xc, 2))].age)
        max_age = age+age-min_age
    else:
        min_age = int(df.loc[np.isclose(df.Z, model.Z) & np.isclose(df.M, model.M) & np.isclose(df.logD, model.logD) & np.isclose(df.aov, model.aov) & np.isclose(df.fov, model.fov) & np.isclose(df.Xc, round(model.Xc+0.01, 2))].age)
        max_age = int(df.loc[np.isclose(df.Z, model.Z) & np.isclose(df.M, model.M) & np.isclose(df.logD, model.logD) & np.isclose(df.aov, model.aov) & np.isclose(df.fov, model.fov) & np.isclose(df.Xc, round(model.Xc-0.01, 2))].age)
    return min_age, max_age

################################################################################
def enforce_binary_constraints(df_Theo_row, spectro_companion=None, isocloud_grid_summary=None, nsigma=3, spectroGrid_dataFrame=None):
    """
    Enforce an n-sigma constraint on the models based on spectoscopic observations of the binary companion employing isochrone-clouds.
    ------- Parameters -------
    df_Theo_row: tuple, made of (int, pandas series)
        tuple retruned from pandas.iterrows(), first tuple entry is the row index of the pandas dataFrame
        second tuple entry is a pandas series, containing a row from the pandas dataFrame.
        (This row holds model parameters, the meritfunction value, and spectroscopic information.)
    spectro_companion: dict
        Information on the companion star, including spectroscopic parameters, mass ratio (q), the errors,
        and a boolean indicating whether the primary or secondary star is assumed pulsating and hence being modelled.
    isocloud_grid_directory: string
        Directory holding the grid for the isochrone-cloud modelling.
    nsigma: int
        How many sigmas you want to make the interval to accept models.
    spectroGrid_dataFrame: pandas DataFrame
        DataFrame with the spectroscopic info and ages of the model-grid.
    ------- Returns -------
    index: int or None
        Index of the dataframe that needs to be removed if binary constraints do not allow the model to remain.
        Returns None if the binary constraints do not discard the model.
    """
    model = df_Theo_row
    min_age, max_age = get_age(model, spectroGrid_dataFrame)
    q= spectro_companion['q']
    q_err= spectro_companion['q_err']
    if spectro_companion['primary_pulsates']:
        M2_min = round(model.M*(q-q_err), 1)
        M2_max = round(model.M*(q+q_err), 1)
    else:
        M2_min = round(model.M/(q+q_err), 1)
        M2_max = round(model.M/(q-q_err), 1)

    isocloud_dict = isocloud_grid_summary[model.Z]

    for key_Mass, df in zip(isocloud_dict.keys(), isocloud_dict.values()):
        if key_Mass < M2_min or key_Mass > M2_max:
            continue    # Only keep models that fall within mass range
        else:
            df = df[(df.star_age < max_age) & (df.star_age > min_age)]

            if df.shape[0] == 0:
                continue

            # Check for all provided constraints if the track passes through the uncertainty region
            if spectro_companion['Teff'] is not None:
                df=df[df.log_Teff < np.log10(spectro_companion['Teff']+nsigma*spectro_companion['Teff_err'])]
                df=df[df.log_Teff > np.log10(spectro_companion['Teff']-nsigma*spectro_companion['Teff_err'])]
            if spectro_companion['logg'] is not None:
                df=df[df.log_g < spectro_companion['logg']+nsigma*spectro_companion['logg_err']]
                df=df[df.log_g > spectro_companion['logg']-nsigma*spectro_companion['logg_err']]
            if spectro_companion['logL'] is not None:
                df=df[df.log_L < spectro_companion['logL']+nsigma*spectro_companion['logL_err']]
                df=df[df.log_L > spectro_companion['logL']-nsigma*spectro_companion['logL_err']]
            if df.shape[0] > 0: #If some models fall within the constraints, return None to not remove the model.
                return None

    return model.name