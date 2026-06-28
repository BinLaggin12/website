if __name__ == "__main__":
    from .database import Database
    from .api import create_fastapi_app

    database = Database()

    api = create_fastapi_app(database)

    import uvicorn

    uvicorn.run(api, host="127.0.0.1", port=8000)
