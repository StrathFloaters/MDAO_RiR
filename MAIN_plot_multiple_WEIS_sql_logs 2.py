import os
import yaml
import openmdao.api as om
import matplotlib.pyplot as plt
import numpy as np

# ---------------------------------------------------------------------------
# Variable display configuration
# ---------------------------------------------------------------------------
VAR_DISPLAY = {
    # ── Objectives ──────────────────────────────────────────────────
    'floatingse.system_structural_mass': ('Floating support structure mass',     'Kg'),
    'towerse.tower_mass':       ('Tower structural mass',   'Kg'),
    'financese.lcoe':           ('LCOE',                    'USD/MWh'),
    'total_AEP':                ('Annual Energy Production', 'GWh'),
    
    # ── Design variables ────────────────────────────────────────────
    'chord':                    ('Blade Chord',              'm'),
    'spar_cap_ss':              ('Spar Cap SS Thickness',    'm'),
    'spar_cap_ps':              ('Spar Cap PS Thickness',    'm'),
    'twist':                    ('Blade Twist',              'deg'),
    'member_diameter':          ('Member Diameter',          'm'),
    'member_wall_thickness':    ('Member Wall Thickness',    'm'),
    'joint_position':           ('Joint Position',           'm'),
    'floating.jointdv_0':       ('Keel vert. pos. (draft)',  'm'),
    'floating.jointdv_1':       ('Center to outer column distance',     'm'),
    'floating.memgrp1.outer_diameter_in':   ('Outer column diameter',   'm'),
    'tower.diameter':           ('Tower diameters',         'm'),
    'tower.layer_thickness':    ('Tower thicknesses',       'm'),

    # ── Constraints ─────────────────────────────────────────────────
    'tip_deflection':           ('Tip Deflection Ratio',     ''),
    'freq_ratio':               ('Frequency Ratio',          ''),
    'rotor_overspeed':          ('Rotor Overspeed',          ''),
    'max_surge':                ('Max Surge',                'm'),
    'pitch_period':             ('Pitch Period',             's'),
    'heave_period':             ('Heave Period',             's'),
    'raft.Max_PtfmPitch':       ('Max ptfm pitch (raft)',    'deg'),
    'raft.max_nac_accel':       ('Max nacelle acceleration', 'm/s^2'),
    'floatingse.structural_frequencies':    ('Eigenfreq.s floating ptfm', 'Hz'),
    'towerse.tower.f1':         ('Tower 1st eigenfreq. AS CANTILEVER!',    'Hz'), # ONLY USE FOR BOTTOM FIXED TURBINE, cantilever beam hypothesis
    'towerse.tower.structural_frequencies': ('Tower struct. freq. AS CANTILEVER!', 'Hz'), # ONLY USE FOR BOTTOM FIXED TURBINE, cantilever beam hypothesis
    'floatingse.fore_aft_freqs':('1st F-A eigenfreq.', 'Hz'),
    'floatingse.side_side_freqs':('1st S-S eigenfreq.', 'Hz'),
    'towerse.post.constr_global_buckling':  ('Tower global buckling', ''),
    'towerse.post.constr_shell_buckling':   ('Tower (local) shell buckling', ''),

    # ── Extra (add your own) ────────────────────────────────────────
    # 'some.variable.path':     ('Pretty Name',             'unit'),
}


def _get_display(var_name):
    """
    Return (pretty_name, unit_str) for *var_name* by searching VAR_DISPLAY.
    Falls back to the last dot-separated token if no match is found.
    """
    var_lower = var_name.lower()
    for key, (pretty, unit) in VAR_DISPLAY.items():
        if key.lower() in var_lower:
            return pretty, unit
    return var_name.split('.')[-1], ''


# ---------------------------------------------------------------------------
# Parse bounds from a WEIS analysis YAML
# ---------------------------------------------------------------------------
# Mapping from WEIS analysis-YAML keys to the OpenMDAO variable name
# substrings used in the SQL log.  This is how the script knows which
# YAML bound belongs to which plotted variable.
#
# Format:  'yaml_section.yaml_key': 'openmdao_var_substring'
#
# For design variables the bounds are lower_bound / upper_bound.
# For constraints the bounds can be lower_bound / upper_bound or min / max.
#
# Only variables that appear here will have bounds drawn.
# Add or remove entries as needed.
# ---------------------------------------------------------------------------
YAML_TO_SQL = {
    # ── Design variables ────────────────────────────────────────────
    'design_variables.tower.outer_diameter':              'tower.diameter',
    'design_variables.tower.layer_thickness':             'tower.layer_thickness',
    'design_variables.floating.joints.z_coordinate':      'floating.jointdv_0',
    'design_variables.floating.joints.r_coordinate':      'floating.jointdv_1',
    'design_variables.floating.members.groups.diameter':  'floating.memgrp1.outer_diameter_in',

    # ── Constraints ─────────────────────────────────────────────────
    'constraints.tower.stress':                           'towerse.post.constr_stress',
    'constraints.tower.global_buckling':                  'towerse.post.constr_global_buckling',
    'constraints.tower.shell_buckling':                   'towerse.post.constr_shell_buckling',
    'constraints.tower.d_to_t':                           'towerse.constr_d_to_t',
    'constraints.tower.taper':                            'towerse.constr_taper',
    'constraints.tower.slope':                            'towerse.slope',
    'constraints.tower.frequency_1':                      'floatingse.structural_frequencies',
    'constraints.floating.Max_Offset':                    'raft.Max_Offset',
    'constraints.floating.freeboard_margin':              'floatingse.constr_freeboard_heel_margin',
    'constraints.floating.draft_margin':                  'floatingse.constr_draft_heel_margin',
    'constraints.floating.fairlead_depth':                'floatingse.constr_fairlead_wave',
    'constraints.floating.fixed_ballast_capacity':        'floatingse.constr_fixed_margin',
    'constraints.floating.variable_ballast_capacity':     'floatingse.constr_variable_margin',
    'constraints.control.rotor_overspeed':                'raft.rotor_overspeed',
    'constraints.control.Max_PtfmPitch':                  'raft.Max_PtfmPitch',
    'constraints.control.nacelle_acceleration':           'raft.max_nac_accel',
}


def _resolve_yaml_path(data, dotpath):
    """
    Walk a nested dict/list following a dot-separated path.
    Returns the sub-dict at the end, or None if the path does not exist.
    Handles list elements by checking each item.
    """
    keys = dotpath.split('.')
    node = data
    for key in keys:
        if isinstance(node, dict):
            if key in node:
                node = node[key]
            else:
                return None
        elif isinstance(node, list):
            # Search inside list items (e.g. groups or coordinate entries)
            found = None
            for item in node:
                if isinstance(item, dict):
                    if key in item:
                        found = item[key]
                        break
                    elif 'names' in item and key != 'names':
                        # keep going for items with sub-dicts
                        if key in item:
                            found = item[key]
                            break
            if found is not None:
                node = found
            else:
                # If key not found inside list items, try first item directly
                if len(node) > 0 and isinstance(node[0], dict):
                    node = node[0]
                    if key in node:
                        node = node[key]
                    else:
                        return None
                else:
                    return None
        else:
            return None
    return node


def parse_bounds_from_yaml(yaml_path, yaml_to_sql=None):
    """
    Read a WEIS analysis YAML and extract upper/lower bounds for every
    variable that has a mapping in ``yaml_to_sql``.

    Parameters
    ----------
    yaml_path : str
        Path to the WEIS analysis YAML file.
    yaml_to_sql : dict or None
        Mapping ``{'dot.path.in.yaml': 'openmdao_var_substring'}``.
        If None, uses the module-level ``YAML_TO_SQL``.

    Returns
    -------
    bounds : dict
        ``{openmdao_var_substring: {'lower': float or None,
                                     'upper': float or None}}``
        Bounds of ±1e+30 (or absent) are stored as ``None``.
    """
    if yaml_to_sql is None:
        yaml_to_sql = YAML_TO_SQL

    with open(yaml_path, 'r') as f:
        cfg = yaml.safe_load(f)

    _BIG = 1e+29  # threshold: anything with abs > this is "no bound"

    bounds = {}
    for dotpath, sql_key in yaml_to_sql.items():
        node = _resolve_yaml_path(cfg, dotpath)
        if node is None or not isinstance(node, dict):
            continue

        lo = None
        up = None

        # Design-variable style: lower_bound / upper_bound
        if 'lower_bound' in node:
            val = float(node['lower_bound'])
            if abs(val) < _BIG:
                lo = val
        if 'upper_bound' in node:
            val = float(node['upper_bound'])
            if abs(val) < _BIG:
                up = val

        # Constraint style: min / max  (used by control constraints)
        if 'min' in node:
            val = float(node['min'])
            if abs(val) < _BIG:
                lo = val
        if 'max' in node:
            val = float(node['max'])
            if abs(val) < _BIG:
                up = val

        # Constraint style from problem_vars.yaml: lower / upper
        if 'lower' in node:
            try:
                val = float(node['lower'])
                if abs(val) < _BIG:
                    lo = val
            except (ValueError, TypeError):
                pass
        if 'upper' in node:
            try:
                val = float(node['upper'])
                if abs(val) < _BIG:
                    up = val
            except (ValueError, TypeError):
                pass

        if lo is not None or up is not None:
            bounds[sql_key] = {'lower': lo, 'upper': up}

    # Print summary
    print(f"\n===  Bounds parsed from: {yaml_path}  ===")
    for sql_key, bnd in bounds.items():
        pretty, unit = _get_display(sql_key)
        unit_str = f" [{unit}]" if unit else ""
        lo_str = f"{bnd['lower']}" if bnd['lower'] is not None else "—"
        up_str = f"{bnd['upper']}" if bnd['upper'] is not None else "—"
        print(f"  {sql_key:50s}  {lo_str:>12s} ≤ x ≤ {up_str:<12s}  ({pretty}{unit_str})")
    print("=" * 60 + "\n")

    return bounds


# ---------------------------------------------------------------------------
# Discover all variable names recorded in an SQL file
# ---------------------------------------------------------------------------
def list_recorded_variables(sql_path, output_file=None):
    """
    Open a WEIS / OpenMDAO SQL recorder file and return every variable
    name that was recorded.  Optionally write the list to a text file.
    """
    cr = om.CaseReader(sql_path)
    cases = cr.list_cases('driver', recurse=False, out_stream=None)
    if not cases:
        print(f"  WARNING: no driver cases found in {sql_path}")
        return []

    all_vars = set()
    first_case = cr.get_case(cases[0])
    all_vars.update(first_case.get_objectives().keys())
    all_vars.update(first_case.get_design_vars().keys())
    all_vars.update(first_case.get_constraints().keys())
    try:
        all_vars.update(first_case.outputs.keys())
    except Exception:
        pass
    all_vars = sorted(all_vars)

    print(f"\n===  Recorded variables in: {sql_path}  ===")
    print(f"  Total: {len(all_vars)} variables\n")
    for v in all_vars:
        pretty, unit = _get_display(v)
        unit_str = f"  [{unit}]" if unit else ""
        print(f"  {v}  ->  {pretty}{unit_str}")
    print("=" * 60 + "\n")

    if output_file:
        with open(output_file, 'w') as f:
            f.write(f"# Recorded variables in: {sql_path}\n")
            f.write(f"# Total: {len(all_vars)}\n")
            f.write(f"# Format:  openmdao_path  ->  pretty_name  [unit]\n#\n")
            for v in all_vars:
                pretty, unit = _get_display(v)
                unit_str = f"  [{unit}]" if unit else ""
                f.write(f"{v}  ->  {pretty}{unit_str}\n")
        print(f"  Variable list written to: {output_file}\n")

    return all_vars


# ---------------------------------------------------------------------------
# Read history for an arbitrary set of variable names
# ---------------------------------------------------------------------------
def read_weis_opt(sql_path, all_requested_keys):
    """
    Read optimisation history from a WEIS SQL recorder file for an
    arbitrary set of variable names.
    """
    cr = om.CaseReader(sql_path)
    cases = cr.list_cases('driver', recurse=False, out_stream=None)
    if not cases:
        return {}

    first_case = cr.get_case(cases[0])
    available = set()
    available.update(first_case.get_objectives().keys())
    available.update(first_case.get_design_vars().keys())
    available.update(first_case.get_constraints().keys())
    try:
        available.update(first_case.outputs.keys())
    except Exception:
        pass
    available = sorted(available)

    resolved = []
    for req in all_requested_keys:
        req_lower = req.lower()
        found = False
        for av in available:
            if req_lower in av.lower():
                resolved.append(av)
                found = True
                break
        if not found:
            resolved.append(req)

    history = {}
    for case_name in cases:
        case = cr.get_case(case_name)
        pool = {}
        pool.update(case.get_objectives())
        pool.update(case.get_design_vars())
        pool.update(case.get_constraints())
        try:
            pool.update(dict(case.outputs))
        except Exception:
            pass

        for key in resolved:
            if key in pool:
                val = np.atleast_1d(pool[key]).flatten()
                history.setdefault(key, []).append(val)
            else:
                try:
                    val = np.atleast_1d(case[key]).flatten()
                    history.setdefault(key, []).append(val)
                except KeyError:
                    pass

    for key in history:
        history[key] = np.array(history[key])
    return history


def _match_vars(available, requested):
    """
    Given a list of available variable names and a list of requested
    (sub)strings, return only those available names that contain at least
    one of the requested substrings (case-insensitive).
    """
    if not requested:
        return available
    matched = []
    for var in available:
        var_lower = var.lower()
        for req in requested:
            if req.lower() in var_lower:
                matched.append(var)
                break
    if not matched:
        print(f"  WARNING: none of the requested names {requested} matched "
              f"any available variables. Available: {available}")
    return matched


def _find_bounds(var_name, bounds_dict):
    """
    Look up the bounds for *var_name* by substring matching against the
    keys in *bounds_dict*.  Returns (lower, upper) — each may be None.
    """
    if not bounds_dict:
        return None, None
    var_lower = var_name.lower()
    for bkey, bnd in bounds_dict.items():
        if bkey.lower() in var_lower:
            return bnd.get('lower'), bnd.get('upper')
    return None, None


# ---------------------------------------------------------------------------
# Main plotting function
# ---------------------------------------------------------------------------
def plot_comparison(
    run_dict,
    columns,
    vector_reduce='mean',
    list_variables=False,
    list_variables_file=None,
    bounds_yaml=None,
    yaml_to_sql=None,
):
    """
    Create:
      - one figure per WEIS optimisation (only that run plotted)
      - one additional figure with all runs overlaid.

    Parameters
    ----------
    run_dict : dict
        ``{'Run Label': 'path/to/log_opt.sql', ...}``
    columns : list of (str, list-of-str)
        Each element is a tuple ``(column_title, [var_substrings])``.
    vector_reduce : {'mean', 'max', 'min'}
        How to reduce vector variables to a single line in the multi-run
        comparison plot.
    list_variables : bool
        If True, print every recorded variable to the console.
    list_variables_file : str or None
        If given, write the full variable list to this text file.
    bounds_yaml : str or None
        Path to a WEIS analysis YAML file.  If given, upper/lower bounds
        for design variables and constraints are extracted and plotted as
        dashed horizontal lines on the relevant subplots.
    yaml_to_sql : dict or None
        Custom mapping ``{'dot.path.in.yaml': 'sql_var_substring'}``.
        If None, uses the module-level ``YAML_TO_SQL`` dictionary.
    """
    # Collect every requested variable across all columns
    all_requested = []
    for _title, var_list in columns:
        all_requested.extend(var_list)
    all_requested = list(dict.fromkeys(all_requested))

    # Optionally list available variables
    first_sql = list(run_dict.values())[0]
    if list_variables or list_variables_file:
        list_recorded_variables(first_sql, output_file=list_variables_file)

    # Parse bounds if a YAML was provided
    bounds = {}
    if bounds_yaml is not None:
        bounds = parse_bounds_from_yaml(bounds_yaml, yaml_to_sql=yaml_to_sql)

    # Read all histories
    all_histories = {}
    for label, path in run_dict.items():
        print(f"\nReading: {label}  ({path})")
        all_histories[label] = read_weis_opt(path, all_requested)

    # Resolve column variable lists
    ref_keys = list(all_histories[list(all_histories.keys())[0]].keys())

    resolved_columns = []
    for title, var_list in columns:
        matched = _match_vars(ref_keys, var_list)
        resolved_columns.append((title, matched))

    # Print summary
    print("\n===  Variables selected for plotting  ===")
    for title, var_list in resolved_columns:
        print(f"  {title} ({len(var_list)}):")
        for v in var_list:
            pretty, unit = _get_display(v)
            unit_str = f" [{unit}]" if unit else ""
            lo, up = _find_bounds(v, bounds)
            bnd_str = ""
            if lo is not None or up is not None:
                lo_s = f"{lo}" if lo is not None else "—"
                up_s = f"{up}" if up is not None else "—"
                bnd_str = f"  (bounds: {lo_s} .. {up_s})"
            print(f"    {v}  ->  {pretty}{unit_str}{bnd_str}")
    print("=========================================\n")

    # Reducers
    _REDUCERS = {
        'mean': (np.mean, 'mean'),
        'max':  (np.max,  'max'),
        'min':  (np.min,  'min'),
    }

    n_cols = len(resolved_columns)

    # ── Bound-line styling ──────────────────────────────────────────
    _BOUND_STYLE = dict(linestyle='--', linewidth=1.2, alpha=0.8)
    _UPPER_COLOR = 'red'
    _LOWER_COLOR = 'blue'

    def _plot_for_labels(labels, fig_suffix, single_run=False):
        col_lengths = [max(1, len(vl)) for (_t, vl) in resolved_columns]
        n_rows = max(col_lengths)

        fig, axes = plt.subplots(
            n_rows, n_cols,
            figsize=(5 * n_cols, 3 * n_rows),
            sharex=True,
        )
        if n_rows == 1 and n_cols == 1:
            axes = np.array([[axes]])
        elif n_rows == 1:
            axes = np.atleast_2d(axes)
        elif n_cols == 1:
            axes = axes[:, np.newaxis]

        def plot_var_list(var_list, col_idx):
            for i, var_name in enumerate(var_list):
                ax = axes[i, col_idx]
                max_iter = 0
                for label in labels:
                    hist = all_histories[label]
                    data = hist.get(var_name)
                    if data is None:
                        continue

                    iters = np.arange(data.shape[0])
                    max_iter = max(max_iter, len(iters))

                    if data.ndim == 2 and data.shape[1] > 1:
                        if single_run:
                            for comp in range(data.shape[1]):
                                ax.plot(
                                    iters, data[:, comp],
                                    label=f"{label} [{comp}]" if data.shape[1] <= 20 else None,
                                )
                        else:
                            reduce_fn, reduce_label = _REDUCERS.get(
                                vector_reduce, (np.mean, 'mean'))
                            summary = np.array([reduce_fn(row) for row in data])
                            ax.plot(iters, summary,
                                    label=f"{label} ({reduce_label})")
                    else:
                        ax.plot(iters, data.flatten(), label=label)

                # ── Draw bound lines ────────────────────────────────
                lo, up = _find_bounds(var_name, bounds)
                if lo is not None:
                    ax.axhline(lo, color=_LOWER_COLOR, **_BOUND_STYLE,
                               label='Lower bound')
                if up is not None:
                    ax.axhline(up, color=_UPPER_COLOR, **_BOUND_STYLE,
                               label='Upper bound')

                pretty, unit = _get_display(var_name)
                if unit:
                    ax.set_ylabel(f"{pretty} [{unit}]")
                else:
                    ax.set_ylabel(pretty)
                ax.grid(True, alpha=0.3)

        # Plot each column
        for col_idx, (title, var_list) in enumerate(resolved_columns):
            if var_list:
                plot_var_list(var_list, col_idx)
            axes[0, col_idx].set_title(title, fontweight='bold', fontsize=10)

        # Legends on top row
        for j in range(n_cols):
            axes[0, j].legend(fontsize=7)

        # X labels on bottom row
        for j in range(n_cols):
            axes[-1, j].set_xlabel('Iteration')

        # Hide unused axes
        for col_idx, (_t, vl) in enumerate(resolved_columns):
            for row_idx in range(len(vl), n_rows):
                axes[row_idx, col_idx].set_visible(False)

        # Figure title
        if len(labels) == 1:
            fig_title = f"WEIS Optimisation Comparison ({labels[0]})"
        else:
            fig_title = "Multi-Run WEIS Optimisation Comparison"
        fig.suptitle(fig_title, fontsize=13, fontweight='bold')

        plt.tight_layout()
        fname = f"weis_opt_comparison_{fig_suffix}.png"
        plt.savefig(fname, dpi=150)
        plt.close(fig)

    # 1) One figure per run
    for label in run_dict.keys():
        _plot_for_labels([label], fig_suffix=label, single_run=True)

    # 2) All runs overlaid
    _plot_for_labels(list(run_dict.keys()), fig_suffix="ALL", single_run=False)


# ---------------------------------------------------------------------------
# Usage
# ---------------------------------------------------------------------------
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

# ── Example: Discover available variables ────────────────────────────────
# list_recorded_variables(
#     list(runs.values())[0],
#     output_file='available_variables.txt',
# )

# ── Example: Plot with bounds from WEIS analysis YAML ────────────────────
plot_comparison(
    runs,
    columns=[
        ('Objectives', [
            'floatingse.system_structural_mass',
            'towerse.tower_mass',
        ]),
        ('Design Variables', [
            'floating.memgrp1.outer_diameter_in',
            'floating.jointdv_0',
            'floating.jointdv_1',
            'tower.diameter',
            'tower.layer_thickness',
        ]),
        ('Constraints', [
            'raft.Max_PtfmPitch',
            'raft.max_nac_accel',
            'raft.Max_Offset',
            'floatingse.structural_frequencies',
            'floatingse.fore_aft_freqs',
            'floatingse.side_side_freqs',
            'towerse.post.constr_global_buckling',
            'towerse.post.constr_shell_buckling',
        ]),
        # ('Performance', [
        #     'financese.lcoe',
        # ]),
    ],
    vector_reduce='min', # 'mean', 'max', 'min'

    list_variables=False,
    list_variables_file = None, # 'available_variables.txt',

    # ── Bounds ──────────────────────────────────────────────────────
    # Path to your WEIS analysis YAML.  Set to None to disable bounds.
    bounds_yaml='RiR_raft_opt_analysis_twr_ptfm.yaml',

    # Optional: override the default YAML→SQL mapping (if None, uses
    # the module-level YAML_TO_SQL dictionary defined above).
    yaml_to_sql=None,
)
