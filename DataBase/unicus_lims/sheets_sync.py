import os
from collections import OrderedDict
from typing import Any

import gspread

REGISTERED_SHEET_URL = (
    "https://docs.google.com/spreadsheets/d/"
    "1HlDpmVOlT_7l7haLcMSkvaymayi7QIogTVv4C1UaxCY"
)


def _get_creds_path() -> str:
    """
    Return the path to the Google service account JSON key.
    Checks the GOOGLE_SHEETS_CREDS_PATH environment variable first,
    then falls back to a well-known dev path.
    """
    env_path = os.environ.get("GOOGLE_SHEETS_CREDS_PATH")
    if env_path:
        return env_path
    dev_path = "/home/sofiyan/Desktop/algebraic-creek-288408-688a9c094efe.json"
    if os.path.isfile(dev_path):
        return dev_path
    raise FileNotFoundError(
        "Google Sheets credentials not found. "
        "Set GOOGLE_SHEETS_CREDS_PATH env var to the service account JSON file."
    )


def fetch_products() -> list[dict[str, Any]]:
    """
    Read the Health-Packages & Products worksheet, group rows by
    (product_name, price), and return a list of product dicts.

    Each row represents either a test included in a package or a
    sub-component of an individual product. Rows sharing the same
    product name and price are clubbed into a single product whose
    description lists all included components.

    Returns:
        list[dict]: Each dict has keys:
            - name (str): product name from column A
            - price (float): offer price from column B
            - description (str): comma-separated list of included tests
            - category (str): "Package" if >1 row, else "Individual"
    """
    creds_path = _get_creds_path()
    gc = gspread.service_account(filename=creds_path)
    sheet = gc.open_by_url(REGISTERED_SHEET_URL)
    worksheet = sheet.sheet1

    rows = worksheet.get_all_values()

    # Group rows by (product_name, price)
    groups: OrderedDict[tuple[str, str], list[str]] = OrderedDict()
    for row in rows[1:]:  # skip header
        name = row[0].strip()
        if not name:
            continue
        price = row[1].strip()
        test = row[2].strip()
        key = (name, price)
        if key not in groups:
            groups[key] = []
        groups[key].append(test)

    # Manual category overrides for products whose grouping does not
    # indicate their logical category. CBC is grouped as a single product
    # (sub-rows for different sample types) but is an Individual test,
    # not a Package.
    CATEGORY_OVERRIDE: dict[str, str] = {
        "CBC": "Individual",
        "HbA1c": "Individual",
    }

    products: list[dict[str, Any]] = []
    for (name, price_str), tests in groups.items():
        try:
            price_float = float(price_str.replace(",", "").replace("₹", ""))
        except ValueError:
            price_float = 0.0
        description = ", ".join(t for t in tests if t)
        category = CATEGORY_OVERRIDE.get(name, "Package" if len(tests) > 1 else "Individual")
        products.append({
            "name": name,
            "price": price_float,
            "description": description,
            "category": category,
        })

    return products
