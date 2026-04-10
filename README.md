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
"

```
COMBINATIONS = [
    # # --- Tower optimisation, starting from original IEA 15MW design ---
    # ("1", "A", "towr"),
    # ("1", "B", "towr"),
    # ("1", "C", "towr"),
    # # --- Tower + platform optimisation ---
    # ("1", "A", "tower_ptfm"),
    # ("1", "B", "tower_ptfm"),
    # ("1", "C", "tower_ptfm"),
    # --- Platform only, after tower optimisation (sequential) ---
    ("1A", "A", "ptfm"),
    ("1B", "B", "ptfm"),
    ("1C", "C", "ptfm"),
]
```
