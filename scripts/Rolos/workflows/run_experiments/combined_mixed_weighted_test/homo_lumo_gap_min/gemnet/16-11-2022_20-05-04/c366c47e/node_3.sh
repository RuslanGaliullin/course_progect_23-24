#!/bin/bash
cd ai4material_design
export WANDB_API_KEY=ae457f48d5eb86299f2fe9c18497a281b029a295
python run_experiments.py --n-jobs 8 --output-folder /output --gpus 0 --processes-per-unit 1 --wandb-entity hse_lambda --targets homo_lumo_gap_min --experiments combined_mixed_weighted_test --trials stability/gemnet/16-11-2022_20-05-04/c366c47e/3