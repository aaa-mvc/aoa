"""Pluggable value functions for AOA.

Each model takes (files_or_commits, params) and returns a USD value.
"""


def compute(files, value_config):
    """Compute value using the configured model.

    Args:
        files: list of file dicts from scan_files
        value_config: dict with 'model' and 'params' keys

    Returns:
        float: estimated value in configured currency
    """
    model_name = value_config.get("model", "hourly_linear")
    params = value_config.get("params", {})

    models = {
        "hourly_linear": _hourly_linear,
    }

    model_fn = models.get(model_name, _hourly_linear)
    return model_fn(files, params)


def _hourly_linear(files, params):
    """Value = files × minutes_per_action / 60 × rate_per_hour"""
    mpa = params.get("minutes_per_action", 10)
    rate = params.get("rate_per_hour", 50)
    hours = len(files) * mpa / 60
    return hours * rate
