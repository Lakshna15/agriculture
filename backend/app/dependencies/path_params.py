from typing import Annotated

from fastapi import Path

# Primary keys are PostgreSQL integers. Bounding the path parameter turns an
# out-of-range id into a 422 instead of a database error.
ResourceId = Annotated[int, Path(ge=1, le=2_147_483_647)]
