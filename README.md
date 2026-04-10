# MDAO_RiR
Repository with the software tool developed for RIR 18221019-1 (MDAO for FOWT)

## Step 1: Install WEIS
This software tool needs WEIS by the National Lab of the Rockies.

You can follow the instructions on how to install WEIS here: [https://weis.readthedocs.io/en/latest/installation.html](https://weis.readthedocs.io/en/latest/installation.html)

For this code, the version of WEIS and of the dependencies that have been used can be found in the "environment.yml" file.

## Step 2: Copy the files n the right folder in WEIS
Once WEIS is installed, copy and paste in a desider folder the following folder:

WEIS/examples

Then, go to this folder, and create a folder titled "04_rir".

Then upload in this folder the files available in this repository.

## Step 3: Running the WEIS Multidisciplinary Design, Analysis, and Optimisation simulations (MDAO)

### File MAIN_run_weis_parallel.py
This file can be used to run multiple WEIS MDAO in parallel.

To set up which MDAO simulations to run in parallel, use the `COMBINATIONS = [...]` variable, where each triplet indicates one MDAO WEIS simulation:
("var1", "var2", "var3)

- var1 indicate the starting FOWT system to be considered:
  - "1" is the 15MW Umaine semisub
  - "1A' is the 15MW Umaine semisub, with the tower optimised for location A
  - "1B" is the 15MW Umaine semisub, with the tower optimised for location B
  - "1C" is the 15MW Umaine semisub, with the tower optimised for location C
 
- var2 is the location for which the system should be optimised (metocean conditions)
  - "A" for location A
  - "B" for location B
  - "C" for location C
 
For the definition of the locations, please see the following paper:
"Data-driven metocean conditions classification to unlock standardisation of FOWTs", K. Patryniak, M. Collu, A. C. Pillai, Torque 2026, Bruges, Belgium.

- var3 indicates the type of MDAO to be carried out:
  - "towr" to optimise ONLY the tower
  - "ptfm" to optimise ONLY the platform
  - "tower_ptfm" to optimise both the tower and the platform
 
NB The "pftm" MDAO should be done after the "towr" one, since the "pftm" takes the optimised tower as starting point.

Below the pre-prepared `COMBINATIONS` variable, with the first 6 MDAO simulations for "towr" and "tower_ptfm", to be run before the 3 MDAO simulations optimising the "ptfm".

```
COMBINATIONS = [
    # --- Tower optimisation, starting from original IEA 15MW design ---
    ("1", "A", "towr"),
    ("1", "B", "towr"),
    ("1", "C", "towr"),
    # --- Tower + platform optimisation ---
    ("1", "A", "tower_ptfm"),
    ("1", "B", "tower_ptfm"),
    ("1", "C", "tower_ptfm"),
    # --- Platform only, after tower optimisation (sequential) ---
    # ("1A", "A", "ptfm"),
    # ("1B", "B", "ptfm"),
    #v("1C", "C", "ptfm"),
]
```
### Output
Once the MDAO simulations have been run successfully, the results are in the `output` folder, and can be post-processed.

## Step 4: Plotting the results (MAIN_plot_multiple_WEIS_sql_logs 2.py)
This script read the `*.sql` output files, for each MDAO simulation, and plot the objectives, design variables, and constraint values vs the optimisation step.

The input section that needs to be specified is in the section below, variable "runs".

It can be commented or de-commented depending on which MDAO results should be postprocessed.

```
runs = {
    'A_ptfm_twr': os.path.join(
        "outputs",
        "inp1_modA_anatower_ptfm",
        "outputs",
        "log_opt_inp1_modA_anatower_ptfm.sql",
    ),
    'B_ptfm_twr': os.path.join(
        "outputs",
        "inp1_modB_anatower_ptfm",
        "outputs",
        "log_opt_inp1_modB_anatower_ptfm.sql",
    ),
    'C_ptfm_twr': os.path.join(
        "outputs",
        "inp1_modC_anatower_ptfm",
        "outputs",
        "log_opt_inp1_modC_anatower_ptfm.sql",
    ),
    # 'A_twr': os.path.join(
        # "outputs",
        # "inp1_modA_anatowr",
        # "outputs",
        # "log_opt_inp1_modA_anatowr.sql",
    # ),
    # 'B_twr': os.path.join(
        # "outputs",
        # "inp1_modB_anatowr",
        # "outputs",
        # "log_opt_inp1_modB_anatowr.sql",
    # ),
    # 'C_twr': os.path.join(
        # "outputs",
        # "inp1_modC_anatowr",
        # "outputs",
        # "log_opt_inp1_modC_anatowr.sql",
    # ),
    'A_ptfm': os.path.join(
        "outputs",
        "inp1A_modA_anaptfm",
        "outputs",
        "log_opt_inp1A_modA_anaptfm.sql",
    ),
    'B_ptfm': os.path.join(
        "outputs",
        "inp1B_modB_anaptfm",
        "outputs",
        "log_opt_inp1B_modB_anaptfm.sql",
    ),
    'C_ptfm': os.path.join(
        "outputs",
        "inp1C_modC_anaptfm",
        "outputs",
        "log_opt_inp1C_modC_anaptfm.sql",
    ),
}
```

## Step 5: Writing the main table comparing the results of the iterative optimisation (i.e., tower, then platform) VS the coupled iteration (tower AND platform)(MAIN_export_final_iteration_table 2.py)

This script takes the values of the objective, design variables, and constraints at the latest iteration of the "towr" and "tower_ptfm", and also perform a difference (absolute and in %age), saving the results in a spreadsheet titled `weis_final_iteration_comparison.xlsx`


