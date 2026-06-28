from typing import cast
from fastapi import FastAPI, Request, Path, Body, Depends, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.responses import JSONResponse, FileResponse
from starlette.staticfiles import StaticFiles
from pydantic import BaseModel
from uuid import UUID
import uuid
import os
from .database import Database, Rental


def create_fastapi_app(database: Database):
    def get_db(request: Request) -> Database:
        return cast(Database, request.app.state.database)

    app = FastAPI()
    app.state.database = database

    static_dir = os.path.join(os.path.dirname(__file__), "..", "static")
    if os.path.isdir(static_dir):
        app.mount("/static", StaticFiles(directory=static_dir), name="static")

        @app.get("/")
        async def index():
            return FileResponse(os.path.join(static_dir, "index.html"))

    def get_user_id_from_state(request: Request) -> UUID:
        user_id_str = request.cookies.get("user_id")
        if not user_id_str:
            raise HTTPException(status_code=401, detail="Unauthorized")
        try:
            return UUID(user_id_str)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid user_id")

    @app.post("/user/create")
    async def create_user():
        user_id = uuid.uuid4()
        return {"user_id": user_id}

    @app.post("/house/create")
    async def create_house():
        house_id = uuid.uuid4()
        return {"house_id": house_id}

    @app.post("/house/{house_id}/rent")
    async def rent_house(
        house_id: UUID = Path(...),
        payload: dict = Body(...),
        user_id: UUID | None = Depends(get_user_id_from_state),
        db: Database = Depends(get_db),
    ):
        rental_id = uuid.uuid4()
        if not await db.make_rental(
            rental_id=rental_id,
            user_id=user_id,
            house_id=house_id,
            data_object=payload,
        ):
            # already locked
            return JSONResponse(
                status_code=409, content={"detail": "House is already rented"}
            )
        return {"rental_id": rental_id}

    @app.get("/house/{house_id}/current_lock")
    async def get_current_lock(
        house_id: UUID = Path(...),
        db: Database = Depends(get_db),
    ):
        user_id = db.get_current_lock(house_id)
        if not user_id:
            return JSONResponse(status_code=404, content={"detail": "No active lock"})
        return {"user_id": user_id}

    @app.post("/rental/{rental_id}/update")
    async def update_rental(
        rental_id: UUID = Path(...),
        payload: dict = Body(...),
        user_id: UUID | None = Depends(get_user_id_from_state),
        db: Database = Depends(get_db),
    ):
        rental = db.get_rental(rental_id)
        if not rental:
            return JSONResponse(status_code=404, content={"detail": "Rental not found"})
        if rental.user_id != user_id:
            return JSONResponse(status_code=403, content={"detail": "Forbidden"})

        db.update_rental(
            rental_id=rental_id,
            user_id=user_id,
            house_id=rental.house_id,
            data_object=payload,
        )
        return {"detail": "Rental updated"}

    @app.get("/rental/{rental_id}", response_model=Rental)
    async def get_rental(
        rental_id: UUID = Path(...),
        user_id: UUID | None = Depends(get_user_id_from_state),
        db: Database = Depends(get_db),
    ):
        rental = db.get_rental(rental_id)
        forbidden = not (rental and rental.user_id == user_id)
        if forbidden:
            return JSONResponse(status_code=403, content={"detail": "Forbidden"})
        return rental

    @app.get("/user/rentals", response_model=list[Rental])
    async def get_user_rentals(
        db: Database = Depends(get_db),
        user_id: UUID | None = Depends(get_user_id_from_state),
    ):
        rentals = db.list_rentals_by_user(user_id)
        return rentals

    @app.post("/rental/{rental_id}/cancel")
    async def cancel_rental(
        rental_id: UUID = Path(...),
        user_id: UUID | None = Depends(get_user_id_from_state),
        db: Database = Depends(get_db),
    ):
        rental = db.get_rental(rental_id)
        forbidden = not (rental and rental.user_id == user_id)
        if forbidden:
            return JSONResponse(status_code=403, content={"detail": "Forbidden"})

        await db.cancel_rental(
            rental_id=rental_id,
            user_id=user_id,
            house_id=rental.house_id,
        )

    @app.post("/truncate_all")
    async def truncate_all(db: Database = Depends(get_db)):
        db.truncate_all()

    return app
