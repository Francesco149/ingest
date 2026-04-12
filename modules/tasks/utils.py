import math
from typing import List, Any

def get_batches(items: List[Any], batch_size: int) -> List[List[Any]]:
    """
    Splits a list of items into batches of approximately equal size.
    """
    if not items:
        return []

    num_batches = math.ceil(len(items) / batch_size)
    batch_size_per_batch = len(items) // num_batches
    remainder = len(items) % num_batches

    batches = []
    current_idx = 0
    for i in range(num_batches):
        size = batch_size_per_batch + (1 if i < remainder else 0)
        batch_ids = items[current_idx : current_idx + size]
        batches.append(batch_ids)
        current_idx += size
    return batches