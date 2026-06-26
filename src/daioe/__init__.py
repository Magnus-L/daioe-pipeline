"""DAIOE pipeline: a faithful Python port of Erik Engberg's Stata construction of the
Dynamic AI Occupational Exposure index, with byte-near-exact validation against the
frozen Stata outputs and a config-driven annual-update path.

Stage modules (one per source do-file):
    stage1_onet         -> r_oj (element_impact) and S_o (social skills)
    stage2_ai_progress  -> Delta p_it (the only time-varying input)
    stage3_mapping      -> Felten x_ij mapping matrix
    stage4_index        -> the DAIOE index at O*NET-SOC level
    stage5_taxonomies   -> taxonomy translation + comparator merges + publication clean

Shared infrastructure:
    config              -> typed access to config.yaml
    stata_ops           -> Stata-idiom shims (cumsum_by, group_total, collapse_mean, pctl_rank)
    io                  -> readers/writers (one fixed Stata reader for inputs AND validation)
    validate            -> compare_to_dta against the Stata ground truth
"""

__version__ = "0.1.0"
