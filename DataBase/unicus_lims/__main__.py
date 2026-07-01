import hashlib
import os

from pathlib import Path

DEFAULT_ADMIN_USER = "admin"
DEFAULT_ADMIN_PASS = "admin123"
OWNER_USER = "owner"
OWNER_PASS = "owner123"

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
    database.create_admin_user(OWNER_USER, _hash_password(OWNER_PASS), role="owner")
    api = create_fastapi_app(database)
    import uvicorn
    port = int(os.environ.get("PORT", 3000))
    print(f"Unicus Diagnostics + Admin running at http://localhost:{port}")
    uvicorn.run(api, host="0.0.0.0", port=port)
