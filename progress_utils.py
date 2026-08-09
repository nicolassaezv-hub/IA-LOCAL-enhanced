# utils/progress_utils.py

from tqdm import tqdm
import time


def show_progress(task_name="Processing", duration=2):
    """
    Simple progress bar.

    Parameters:
        task_name (str): Description shown to the user.
        duration (int|float): Approximate duration in seconds.
    """

    print(f"\n[ASTRA PROCESS] {task_name}")

    for _ in tqdm(
        range(100),
        desc=task_name,
        ncols=80,
        leave=False
    ):
        time.sleep(duration / 100)


def progress_steps(task_name, steps):
    """
    Multi-step progress visualization.

    Example:
        progress_steps(
            "Analyzing CSV",
            [
                "Loading file",
                "Validating columns",
                "Computing indicators",
                "Saving results"
            ]
        )
    """

    print(f"\n[ASTRA] {task_name}")

    for step in steps:
        print(f" -> {step}")

        for _ in tqdm(
            range(100),
            desc=step,
            ncols=80,
            leave=False
        ):
            time.sleep(0.01)


def progress_iterator(iterable, description="Processing"):
    """
    Wraps an iterable with tqdm.

    Example:
        for row in progress_iterator(df.iterrows(), "Reading Rows"):
            ...
    """

    return tqdm(
        iterable,
        desc=description,
        ncols=80
    )
