import numpy as np
import pandas as pd
from FaaSr_py.client.py_client_stubs import faasr_log


def more_imports():
    """
    This function is imported first during the directory walk, and should cause the
    execution of `02_less_imports.py` to fail due to the missing packages.
    """
    df = pd.DataFrame(
        {
            "A": [1, 2, 3],
            "B": [4, 5, 6],
        }
    )
    faasr_log(str(df))

    arr = np.array([1, 2, 3])
    faasr_log(str(arr))
