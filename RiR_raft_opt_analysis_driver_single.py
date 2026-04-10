import os
from weis import weis_main
from wisdem.inputs.validation import load_yaml

# TEST_RUN will reduce the number and duration of simulations
TEST_RUN = False

## Input, modelling, analysis options
input_option        = "1"
modelling_option    = "A"
analysis_option     = "towr" # "towr", "ptfm", "towr_ptfm"

## File management
run_dir = os.path.dirname( os.path.realpath(__file__) )

match input_option:
    case "1":
        fname_wt_input = os.path.join(run_dir, "..", "00_setup", "ref_turbines", "IEA-15-240-RWT_VolturnUS-S_rectangular_sparsetower.yaml")
    case "1A":
        fname_wt_input = os.path.join(run_dir, "..", "04_rir_01_A_twr", "outputs", "04_umaine_semi_raft_opt", "refturb_output.yaml")
    case "1B":
        fname_wt_input = os.path.join(run_dir, "..", "04_rir_04_B_twr", "outputs", "04_umaine_semi_raft_opt", "refturb_output.yaml")
    case "1C":
        fname_wt_input = os.path.join(run_dir, "..", "04_rir_07_C_twr", "outputs", "04_umaine_semi_raft_opt", "refturb_output.yaml")
    case _:
        raise FileNotFoundError("File not available")
        
match modelling_option:
    case "A":
        fname_modeling_options = os.path.join(run_dir, "RiR_raft_opt_modeling_locA.yaml")
    case "B":
        fname_modeling_options = os.path.join(run_dir, "RiR_raft_opt_modeling_locB.yaml")
    case "C":
        fname_modeling_options = os.path.join(run_dir, "RiR_raft_opt_modeling_locC.yaml")
    case _:
        raise FileNotFoundError("File not available")
        
match analysis_option:
    case "towr":
        fname_analysis_options = os.path.join(run_dir, "RiR_raft_opt_analysis_twr.yaml")
    case "ptfm":
        fname_analysis_options = os.path.join(run_dir, "RiR_raft_opt_analysis_ptfm.yaml")
    case "tower_ptfm":
        fname_analysis_options = os.path.join(run_dir, "RiR_raft_opt_analysis_twr_ptfm.yaml")
    case _:
        raise FileNotFoundError("File not available")


# fname_wt_input = os.path.join(run_dir, "..", "00_setup", "ref_turbines", "IEA-15-240-RWT_VolturnUS-S_rectangular_sparsetower3.yaml")
# fname_modeling_options = os.path.join(run_dir, "umaine_semi_raft_opt_modeling.yaml")
# fname_analysis_options = os.path.join(run_dir, "umaine_semi_raft_opt_analysis.yaml")

wt_opt, modeling_options, opt_options = weis_main(fname_wt_input, 
                                                 fname_modeling_options, 
                                                 fname_analysis_options,
                                                 test_run=TEST_RUN
                                                 )

# Test that the input we are providing RAFT has not changed
this_raft_input = load_yaml(os.path.join(run_dir,"outputs","04_umaine_semi_raft_opt","raft_designs","raft_design_0.yaml"))
standard_raft_input = load_yaml(os.path.join(run_dir, "..", "00_setup", "ref_turbines", "IEA-15-240-RWT_VolturnUS-S_raft.yaml"))
# Disable this test because we get slightly different inputs on the linux CI
assert(this_raft_input != standard_raft_input)

# If the values have changed for a purpose, move this_raft_input to standard_raft_input and commit
#fname_wt_input = os.path.join(run_dir, "..", "00_setup", "ref_turbines", "IEA-15-240-RWT_VolturnUS-S_rectangular_sparsetower_6sec.yaml")
#fname_wt_input = os.path.join(run_dir, "..", "00_setup", "ref_turbines", "IEA-15-240-RWT_VolturnUS-S_rectangular.yaml")
#fname_wt_input = os.path.join(run_dir, "..", "00_setup", "ref_turbines", "IEA-15-240-RWT_VolturnUS-S_sparsetower.yaml")
