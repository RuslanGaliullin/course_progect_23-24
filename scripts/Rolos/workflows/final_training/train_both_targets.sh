#!/bin/bash
# Trains the sparse MegNet models with optimal parameters on all the data,
# saves the weights to datasets/checkpoints/combined_mixed_all_train
cd ai4material_design
if [ ! -f scripts/Rolos/dry-run ]; then
source scripts/Rolos/wandb_config.sh
parallel -j 2 python run_experiments.py --output-folder /output --targets {1} --trials {2} --experiments combined_mixed_all_train --gpus 0 --n-jobs 4 --save-checkpoints ::: formation_energy_per_site homo_lumo_gap_min :::+ megnet_pytorch/sparse/05-12-2022_19-50-53/d6b7ce45 megnet_pytorch/sparse/05-12-2022_19-50-53/831cc496
fi