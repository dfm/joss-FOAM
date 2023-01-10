""" Top level script to run the pipeline sequentially, copy this script with the config file to the folder where you want to run the analysis.
Comment certain imports if you don't want to repeat them on repeated runs."""
import importlib, sys, os
from pathlib import Path
import config
# Check for sensible input, so that you don't use observed periods whilst looking at the theoretical values as if they are frequencies, and vice versa.
match_obsAndTheory = False
for obs_list in config.observable_list:
    for obs in obs_list:
        if (config.periods_or_frequencies_observed) in obs:
            match_obsAndTheory = True
    if match_obsAndTheory is False:
        config.logger.error(f'The observables that are analysed {config.observable_list} do not all include the observational data that is used: {config.periods_or_frequencies_observed}')
        sys.exit()
    match_obsAndTheory = False
# Check if none of the fixed parameters are in the list of free parameters, and set name for nested grid
if config.fixed_parameters is not None:
    nested_grid_dir = 'Nested_grid_fix'
    for param in config.fixed_parameters.keys():
        nested_grid_dir = f'{nested_grid_dir}_{param}'
        if param in config.free_parameters:
            config.logger.error(f'The parameter {param} can not be both fixed and free.')
            sys.exit()

# Set the main top-level directory
config.main_directory = os.getcwd()
config.observations = f'{config.main_directory}/{config.observations}'

# Run the pipeline
importlib.import_module('foam.pipeline.pipe0_extract_puls_and_spectro')
importlib.import_module('foam.pipeline.pipe1_construct_pattern')

# Change the current working directory for nested grids
if config.fixed_parameters is not None:
    Path(nested_grid_dir).mkdir(parents=True, exist_ok=True)
    os.chdir(nested_grid_dir)

importlib.import_module('foam.pipeline.pipe2_calculate_likelihood')
importlib.import_module('foam.pipeline.pipe3_spectroClip_AICc')
importlib.import_module('foam.pipeline.pipe4_bestModel_errors')
importlib.import_module('foam.pipeline.pipe5_correlationPlots')
importlib.import_module('foam.pipeline.pipe6_table_bestModels')
