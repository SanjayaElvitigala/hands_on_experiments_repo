import numpy as np
import pandas as pd
import lightgbm as lgb
import multiprocessing
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
import time


# creating the synthetic data
row_count = 500
X_vars = [np.random.rand(row_count, 1) * np.random.randint(2, 10) for i in range(6)]
Y_vars = [x_var * (index + 2) for index, x_var in enumerate(X_vars)]

X_cols = [f"X{i}" for i in range(len(Y_vars))]
Y_cols = [f"Y{i}" for i in range(len(Y_vars))]
all_data = pd.DataFrame(
    np.concatenate(Y_vars + X_vars, axis=1), columns=Y_cols + X_cols
)


class ModelWrapper:

    def __init__(
        self, targets, features, data, is_parallel, executor, lgb_njobs
    ) -> None:
        self.targets = targets
        self.features = features
        self.models = {}
        self.data = data
        self.is_parallel = is_parallel
        self.total_time_taken = 0
        self.executor = executor
        self.lgb_njobs = lgb_njobs

    def train_inner_model(self, target):
        print(f"training inner target: {target}")

        self.models[target] = lgb.LGBMRegressor(verbose=-1, n_jobs=self.lgb_njobs)
        self.models[target].fit(X=self.data[self.features], y=self.data[target])

    def get_pool_executer(self):
        if self.executor == "threadpool":
            return ThreadPoolExecutor
        elif self.executor == "processpool":
            return ProcessPoolExecutor

    def train(self, n_threads):
        start_time = time.time()
        if self.is_parallel:
            with self.get_pool_executer()(max_workers=n_threads) as executor:
                for target in self.targets:
                    executor.submit(self.train_inner_model, target)
        else:
            for target in self.targets:
                self.train_inner_model(target)
        end_time = time.time()
        self.total_time_taken = end_time - start_time

        print(f"total time taken : {np.round(self.total_time_taken,4)} seconds")


if __name__ == "__main__":
    models_cluster = ModelWrapper(
        targets=Y_cols,
        features=X_cols,
        is_parallel=False,
        data=all_data,
        executor="processpool",
        lgb_njobs=None,
    )

    models_cluster.train(6)
