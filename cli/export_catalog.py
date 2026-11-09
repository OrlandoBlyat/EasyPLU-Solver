"""Export the same catalogue handbook used by the web application."""
import argparse
import getpass
import os
import sys
import time
from pathlib import Path
from threading import Event
from backend.auth.easyplu import login
from backend.infrastructure.jobs import job_scope
from backend.catalog.collector import collect_products
from backend.catalog.cache import load_cache, save_cache, merge_cache, save_missing_names
from backend.catalog.pdf import make_pdf

ROOT = Path(__file__).resolve().parents[1]

def main():
    parser = argparse.ArgumentParser(description="Create a categorized EasyPLU training PDF.")
    parser.add_argument("--username", help="EasyPLU email or 8-digit Lidl SSO number")
    parser.add_argument("--login-method", choices=("easyplu", "sso"), default="easyplu")
    parser.add_argument("--output", type=Path, default=ROOT / "var/plu-catalog/plu-catalog.pdf")
    parser.add_argument("--cache", type=Path, default=ROOT / "var/plu-catalog/cache.json")
    parser.add_argument(
        "--missing-names",
        type=Path,
        default=ROOT / "var/plu-catalog/missing-names.json",
        help="JSON output for API items without a Slovenian name",
    )
    args = parser.parse_args()
    if os.geteuid() == 0:
        print(
            "Warning: do not run this exporter with sudo; generated cache and PDF files will be owned by root.",
            file=sys.stderr, flush=True,
        )
    username = (args.username or input("EasyPLU email / Lidl SSO number: ")).strip()
    password = getpass.getpass("Password: ")
    if not username or not password:
        parser.error("username and password are required")

    output = args.output.resolve()
    cache_path = args.cache.resolve()
    missing_names_path = args.missing_names.resolve()
    cache_dir = ROOT / "var/plu-catalog/images"
    missing_names = []
    catalogue_fetched = False
    try:
        cached_products = load_cache(cache_path)
        with job_scope(Event(), deadline=time.monotonic() + 1800):
            user_id = login(username, password, login_method=args.login_method)
            catalogue_fetched = True
            live_products = collect_products(user_id, missing_names)
            products = merge_cache(live_products, cached_products)
            save_cache(cache_path, products)
            print(f"Rendering {len(products)} products...", flush=True)
            make_pdf(products, output, cache_dir)
    except KeyboardInterrupt:
        print("Cancelled", file=sys.stderr)
        return 130
    except Exception as error:
        print(f"Export failed: {error}", file=sys.stderr)
        return 1
    finally:
        if catalogue_fetched:
            try:
                save_missing_names(missing_names_path, missing_names)
                if missing_names:
                    print(f"Missing-name items saved to {missing_names_path}", flush=True)
            except (OSError, TypeError, ValueError) as error:
                print(f"Could not save missing-name diagnostics: {error}", file=sys.stderr)
    print(f"Cache saved to {cache_path}", flush=True)
    print(f"Created {output}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
