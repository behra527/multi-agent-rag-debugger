from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="Demo users API")


class User(BaseModel):
    id: int
    name: str
    email: str


USERS = {
    1: {"id": 1, "name": "Ada", "email": "ada@example.test"},
    2: {"id": 2, "name": "Grace", "email": "grace@example.test"},
}


@app.get("/users/{user_id}", response_model=User)
def get_user(user_id: int) -> dict:
    user = USERS.get(user_id)
    if user is None:
        return {"id": user_id, "name": "missing"}
    # Intentional defect: drop email so response_model validation fails with HTTP 500.
    return {"id": user["id"], "name": user["name"]}
