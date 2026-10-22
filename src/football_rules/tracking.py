"""Project-local MLflow defaults; honor an explicitly configured destination."""

import os
from pathlib import Path

import mlflow


def configure_tracking() -> str:
    if not os.environ.get("MLFLOW_TRACKING_URI"):
        directory = Path("data/mlflow").resolve()
        directory.mkdir(parents=True, exist_ok=True)
        mlflow.set_tracking_uri("sqlite:///" + (directory / "mlflow.db").as_posix())

    experiment_id = os.environ.get("MLFLOW_EXPERIMENT_ID")

    if experiment_id:
        experiment = mlflow.set_experiment(experiment_id=experiment_id)
    else:
        experiment = mlflow.set_experiment("football-rules-retrieval")

    return experiment.experiment_id
