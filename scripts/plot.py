from ast import parse
from itertools import product
import argparse
from pathlib import Path
import yaml
import pandas as pd
import numpy as np
import getpass
import matplotlib.pyplot as plt
import sys
sys.path.append('.')
from ai4mat.data.data import StorageResolver, get_prediction_path, get_targets_path


def main():
    parser = argparse.ArgumentParser("Plots predictions")
    parser.add_argument("--experiments", type=str, nargs="+")
    parser.add_argument("--trials", type=str, nargs="+")
    parser.add_argument("--targets", type=str, nargs="+")
    parser.add_argument("--filetype", type=str, default="pdf")
    parser.add_argument("--units", type=str, default="eV")
    parser.add_argument("--limits", type=float, nargs=2)
    args = parser.parse_args()
    
    font = {
        'family': 'sans-serif',
        'weight': 'normal',
        'size'  : 12}

    plt.rc('font', **font)
    plot_kwargs = dict(
        s=40,
        facecolors='none',
        edgecolors='navy',
        alpha=0.3,
    )

    storage_resolver = StorageResolver()
    for experiment_name in args.experiments:
        experiment_path = storage_resolver["experiments"].joinpath(experiment_name)
        with open(experiment_path.joinpath("config.yaml")) as experiment_file:
            experiment = yaml.safe_load(experiment_file)
        folds = pd.read_csv(experiment_path.joinpath("folds.csv.gz"),
                            index_col="_id",
                            squeeze=True)
        true_targets = pd.concat([pd.read_csv(storage_resolver["processed"]/dataset/"targets.csv.gz", index_col="_id")
                                  for dataset in experiment["datasets"]], axis=0).reindex(
                                          index=folds.index)
        if args.targets:
            targets = args.targets
        else:
            targets = experiment["targets"]
        for target_name, this_trial_name in product(targets, args.trials):
            predictions = pd.read_csv(storage_resolver["predictions"].joinpath(
                                           get_prediction_path(
                                               experiment_name,
                                               target_name,
                                               this_trial_name
                                           )), index_col="_id", squeeze=True)
            assert predictions.index.equals(true_targets.index)
            mae = np.abs(predictions - true_targets.loc[:, target_name]).mean()
            fig, ax = plt.subplots()
            ax.scatter(true_targets.loc[:, target_name],
                       predictions,
                       label=f"$\mathrm{{MAE}}={mae:.4f}$",
                       **plot_kwargs)
            ax.set_xlabel(f"DFT {target_name}, {args.units}")
            ax.set_ylabel(f"Predicted {target_name}, {args.units}")
            ax.legend()
            if args.limits:
                lims = args.limits
            else:
                lims = [
                    np.min([ax.get_xlim(), ax.get_ylim()]),
                    np.max([ax.get_xlim(), ax.get_ylim()]),
                ]
            ax.plot(lims, lims, 'k-', alpha=0.75, zorder=0)
            ax.set_aspect('equal')
            ax.set_xlim(lims)
            ax.set_ylim(lims)

            plots_folder = storage_resolver["plots"].joinpath(
                                experiment_name,
                                target_name)
            plots_folder.mkdir(exist_ok=True, parents=True)
            if args.filetype == "pdf":
                dpi = None
                metadata = {
                    "Title": f"Predictions for {target_name} "
                            f"for experiment {experiment_name}",
                    "Keywords": "2D materials, machine learning, graph neural network, MEGNet"}
                try:
                    metadata["Author"] = getpass.getuser()
                except:
                    pass
            else:
                dpi = 300
                metadata = None
            fig.savefig(Path(plots_folder, f"{this_trial_name}.{args.filetype}"),
                        dpi=dpi, bbox_inches='tight', metadata=metadata)

if __name__ == "__main__":
    main()
