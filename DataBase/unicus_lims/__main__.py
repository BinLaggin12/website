import hashlib

from pathlib import Path

DEFAULT_ADMIN_USER = "admin"
DEFAULT_ADMIN_PASS = "admin123"

# Ensure the generated_reports directory exists
HERE = Path(__file__).resolve().parent
REPORTS_DIR = HERE / "generated_reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


if __name__ == "__main__":
    from .database import Database
    from .api import create_fastapi_app

    database = Database()
    database.seed_doctors()
    database.seed_tests()
    database.create_admin_user(DEFAULT_ADMIN_USER, _hash_password(DEFAULT_ADMIN_PASS))
    api = create_fastapi_app(database)
    import uvicorn
    print(f"Unicus Diagnostics + Admin running at http://localhost:3000")
    uvicorn.run(api, host="0.0.0.0", port=3000)
