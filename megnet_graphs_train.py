import os
import itertools
import time
from operator import methodcaller
import numpy as np
import pandas as pd
import argparse
from multiprocessing import Pool
from pynvml import nvmlInit, nvmlDeviceGetHandleByIndex, nvmlDeviceGetMemoryInfo, nvmlDeviceGetCount
import wandb

from megnet.models import MEGNetModel
from megnet.utils.preprocessing import StandardScaler
from megnet.data.graph import GaussianDistance

from defect_representation import VacancyAwareStructureGraph, FlattenGaussianDistance

IS_INTENSIVE = {
    "homo": True,
    "formation_energy": False
}
CORE_PATH = r"datasets/{}_defects{}.pickle.gzip"
MODEL_PATH_ROOT = os.path.join("models", "MEGNet-defect-only")


def get_free_gpu():
    nvmlInit()
    return np.argmax([
        nvmlDeviceGetMemoryInfo(nvmlDeviceGetHandleByIndex(i)).free
        for i in range(nvmlDeviceGetCount())
    ])


class Experiment():
    def __init__(self,
                 target: str,
                 vacancy_only: bool,
                 atom_features: str,
                 add_bond_z_coord: bool,
                 epochs: int = 1000,
                 path_suffix: str = None,
                 learning_rate: float = 1e-3):
        if path_suffix is None:
            if vacancy_only:
                self.train_path = CORE_PATH.format("train", "_vac_only")
                self.test_path = CORE_PATH.format("test", "_vac_only")
                self.data_name = "vac_only"
            else:
                self.train_path = CORE_PATH.format("train", "")
                self.test_path = CORE_PATH.format("test", "")
                self.data_name = "full"
        else:
            self.data_name = path_suffix
            self.train_path = CORE_PATH.format("train", "_"+path_suffix)
            self.test_path = CORE_PATH.format("test", "_"+path_suffix)
        self.name = (f"{self.data_name}"
                     f"{'_bond_z' if add_bond_z_coord else ''}"
                     f"_{atom_features}"
                     f"_{epochs}")
        self.target = target
        self.epochs = epochs
        self.atom_features = atom_features
        self.add_bond_z_coord = add_bond_z_coord
        self.model_path = os.path.join(MODEL_PATH_ROOT, self.target, self.name)
        self.learning_rate = learning_rate
        # This parameter is not used in run(), but is saved for reference
        self.vacancy_only = vacancy_only


    def run(self, gpu=None):
        train = pd.read_pickle(self.train_path)
        test = pd.read_pickle(self.test_path)
        run = wandb.init(project='ai4material_design',
                         entity='kazeev',
                         config=self.__dict__,
                         reinit=True)
        nfeat_edge_per_dim = 10
        cutoff = 15
        if self.add_bond_z_coord:
            bond_converter = FlattenGaussianDistance(
                np.linspace(0, cutoff, nfeat_edge_per_dim), 0.5)
        else:
            bond_converter = GaussianDistance(
                np.linspace(0, cutoff, nfeat_edge_per_dim), 0.5)
        graph_converter = VacancyAwareStructureGraph(
            bond_converter=bond_converter,
            atom_features=self.atom_features,
            add_bond_z_coord=self.add_bond_z_coord,
            cutoff=cutoff)
        scaler = StandardScaler.from_training_data(train.defect_representation,
                                                   train[self.target],
                                                   is_intensive=IS_INTENSIVE[self.target])
        # TODO(kazeevn) elegant device configration and GPU distribution
        os.environ['CUDA_DEVICE_ORDER']='PCI_BUS_ID'
        os.environ['TF_FORCE_GPU_ALLOW_GROWTH'] = "true"
        if gpu is None:
            os.environ['CUDA_VISIBLE_DEVICES'] = str(get_free_gpu())
        else:
            os.environ['CUDA_VISIBLE_DEVICES'] = str(gpu)
        model = MEGNetModel(nfeat_edge=graph_converter.nfeat_edge*nfeat_edge_per_dim,
                            nfeat_node=graph_converter.nfeat_node,
                            nfeat_global=2,
                            graph_converter=graph_converter,
                            npass=2,
                            target_scaler=scaler,
                            metrics=["mae"],
                            lr=self.learning_rate)
        # We use the same test for monitoring, but do no early stopping
        model.train(train.defect_representation,
                    train[self.target],
                    test.defect_representation,
                    test[self.target],
                    epochs=self.epochs,
                    callbacks=[wandb.keras.WandbCallback(save_model=False)],
                    save_checkpoint=False,
                    verbose=1)
        model.save_model(self.model_path)
        run.finish()


# https://stackoverflow.com/questions/5228158/cartesian-product-of-a-dictionary-of-lists
def product_dict(**kwargs):
    keys = kwargs.keys()
    vals = kwargs.values()
    for instance in itertools.product(*vals):
        yield dict(zip(keys, instance))


TARGETS = ("homo", "formation_energy")
def generate_all_experiments():
    param_values = {
        "target": TARGETS,
        "vacancy_only": (True, False),
        "atom_features": ("Z", "embed", "werespecies"),
        "add_bond_z_coord": (True, False),
        "epochs": [1000],
    }    
    return [Experiment(**params) for params in product_dict(**param_values)]


def get_8x8_experiments():
    base_params = {
        "vacancy_only": True,
        "atom_features": "Z",
        "add_bond_z_coord": True,
        "learning_rate": 2e-4,
    }
    all_params = []
    for target in TARGETS:
        for split_method, epochs in (
                ("vac_only_8x8_split", 1000),
                ("vac_only_no_8x8_in_train", 400),
                ("vac_only_no_8x8_in_train", 1000)
        ):
            this_params = base_params.copy()
            this_params["path_suffix"] = split_method
            this_params["target"] = target
            this_params["epochs"] = epochs
            all_params.append(Experiment(**this_params))
    return all_params


def run_on_gpu(index_experiment):
    return index_experiment[1].run(gpu=str(1+index_experiment[0]%3))


def main():
    os.environ["WANDB_START_METHOD"] = "thread"
    os.environ["WANDB_RUN_GROUP"] = "Defect-only-MEGNet-" + wandb.util.generate_id()
    experiments = get_8x8_experiments()
    # We are light on GPU usage
    with Pool(12) as p:
        p.map(run_on_gpu, enumerate(experiments))


if __name__ == '__main__':
    main()
