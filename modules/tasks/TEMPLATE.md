# [TASK NAME]

[Brief description of what this task does]

## Pool
`POOL = "[pool_name]"` (e.g., "download", "cpu", "cuda", "vision")

## Schema
### Input
- `field_name` (type): description

### Output
- `field_name` (type): description

## Implementation Blueprint (Code Examples)

### 1. Skeleton Code (The Complete File Structure)
```python
"""
# Input
- url_slug (str): The unique identifier for the resource.
- [other_input] (type): description

# Output
- [other_output] (type): description

# Creates
- [child_task_type] (optional): description of child task
"""
from typing import Dict, Any
import logging
from modules.task_manager.task_manager import Task
from modules.tasks.utils import get_batches

log = logging.getLogger(__name__)

async def run(task: Task, context: Dict[str, Any], input_data: Dict[str, Any]) -> Dict[str, Any]:
    # 1. Access Core Objects
    config = context["config"]
    task_manager = context["task_manager"]
    
    # 2. Access Input Data
    url_slug = input_data["url_slug"] # Mandatory
    optional_param = input_data.get("optional_param", "default_value") # Optional
    
    log.info(f"Starting task {task.id} for slug: {url_slug}")

    # 3. Logic Implementation
    # ... your code here ...
    # Note: Raise exceptions for failures; don't return error statuses.

    # 4. Orchestration (if needed)
    # await task_manager.create_task("child_task", {"url_slug": url_slug}, dependencies=[task.id])

    return {
        "url_slug": url_slug,
        "result_key": "result_value"
    }
```

### 2. Accessing Dependencies (The Scanning Pattern)
The `task_manager` injects parent task outputs as `dep_{task_id}` keys. To find a specific piece of data from any parent, scan the input keys.
```python
# Search for a specific key (e.g., 'transcript') inside any parent dependency
target_data = None
for key, val in input_data.items():
    if key.startswith("dep_") and isinstance(val, dict) and "transcript" in val:
        target_data = val["transcript"]
        break

if not target_data:
    raise ValueError("Required dependency data not found in input_data")
```

### 3. Accessing Configuration
```python
# Accessing config values
chunk_duration = config["processing"]["chunk_duration"]
```

### 4. Balanced Batching (Using `utils.py`)
```python
from modules.tasks.utils import get_batches

# Split a list of IDs into approximately equal batches
batch_ids = get_batches(items_list, batch_size=5)

for batch in batch_ids:
    # Process batch (e.g., dispatching to sub-tasks)
    pass
```

### 5. Orchestration (Creating Child Tasks)
```python
# Create a child task and link it to the current task
await context["task_manager"].create_task(
    "child_task_type",
    {
        "url_slug": task.input_data.get("url_slug"),
        "batch": batch
    },
    dependencies=[task.id]
)
```

## Implementation Notes
- [Add specific constraints or logic requirements here]
