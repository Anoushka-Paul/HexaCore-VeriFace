"""
sketch_search.py

End-to-end pipeline: sketch image -> photo-realistic conversion ->
authenticated search against VeriFace's POST /search endpoint.

VeriFace's /search route requires a logged-in officer/admin (JWT bearer
auth, per auth_service). This script logs in first, then attaches the
token to the search request.

Usage:
    python sketch_search.py --sketch suspect_sketch.jpg \
        --username officer1 --password mypassword

    # Optional flags:
    python sketch_search.py --sketch suspect_sketch.jpg \
        --username officer1 --password mypassword \
        --url http://localhost:8000 --style cufs --keep-converted
"""

import argparse
import os
import sys
import tempfile

import requests

from sketch_to_photo import convert_sketch_to_photo


def login(base_url: str, username: str, password: str) -> str:
    """Logs into VeriFace's auth service and returns a bearer token."""
    try:
        response = requests.post(
            f"{base_url}/auth/login",
            data={"username": username, "password": password},
            timeout=10,
        )
    except requests.exceptions.ConnectionError as e:
        raise RuntimeError(
            f"Could not reach {base_url}. Is the VeriFace server running? "
            f"(uvicorn main:app --reload --host 0.0.0.0 --port 8000)"
        ) from e

    if response.status_code == 401:
        raise RuntimeError("Login failed: incorrect username or password.")
    response.raise_for_status()

    token = response.json().get("access_token")
    if not token:
        raise RuntimeError(f"Login succeeded but no access_token in response: {response.json()}")
    return token


def search_photo(base_url: str, photo_path: str, token: str) -> list[dict]:
    """Uploads the converted photo to /search and returns the match list."""
    with open(photo_path, "rb") as f:
        try:
            response = requests.post(
                f"{base_url}/search",
                files={"file": (os.path.basename(photo_path), f, "image/jpeg")},
                headers={"Authorization": f"Bearer {token}"},
                timeout=30,
            )
        except requests.exceptions.ConnectionError as e:
            raise RuntimeError(f"Could not reach {base_url}/search.") from e

    if response.status_code == 401:
        raise RuntimeError("Search failed: token was rejected (expired or invalid).")
    if response.status_code == 422:
        raise RuntimeError(f"Search failed: {response.json().get('detail', response.text)}")
    response.raise_for_status()
    return response.json()


def print_results(results: list[dict]) -> None:
    if not results:
        print("No matches returned.")
        return

    print(f"\n{len(results)} match(es) found:\n")
    for rank, person in enumerate(results, start=1):
        print(f"  #{rank}  {person.get('name', '?')}  (person_id={person.get('person_id', '?')})")
        print(f"       similarity: {person.get('similarity', '?')}   confidence: {person.get('confidence', '?')}")
        if "review_recommended" in person:
            print(f"       review recommended: {person['review_recommended']}")
        print()


def main():
    parser = argparse.ArgumentParser(description="Convert a sketch and search it against VeriFace.")
    parser.add_argument("--sketch", required=True, help="Path to the input sketch image")
    parser.add_argument("--username", required=True, help="VeriFace officer/admin username")
    parser.add_argument("--password", required=True, help="VeriFace password")
    parser.add_argument("--url", default="http://localhost:8000", help="Base URL of the VeriFace API")
    parser.add_argument("--style", default="cufs", choices=["cufs", "cufsf"], help="Sketch model style")
    parser.add_argument(
        "--keep-converted", action="store_true",
        help="Keep the intermediate converted photo instead of deleting it after search",
    )
    args = parser.parse_args()

    with tempfile.TemporaryDirectory() as tmp_dir:
        converted_path = os.path.join(tmp_dir, "converted.jpg")

        print(f"Converting sketch: {args.sketch}")
        try:
            convert_sketch_to_photo(args.sketch, converted_path, style=args.style)
        except (FileNotFoundError, ValueError) as e:
            print(f"Input error: {e}", file=sys.stderr)
            sys.exit(1)
        except RuntimeError as e:
            print(f"Model error: {e}", file=sys.stderr)
            sys.exit(1)

        if args.keep_converted:
            kept_path = os.path.splitext(args.sketch)[0] + "_converted.jpg"
            import shutil
            shutil.copy(converted_path, kept_path)
            print(f"Saved converted photo to: {kept_path}")

        print(f"Logging in as '{args.username}'...")
        try:
            token = login(args.url, args.username, args.password)
        except RuntimeError as e:
            print(f"Auth error: {e}", file=sys.stderr)
            sys.exit(1)

        print("Searching...")
        try:
            results = search_photo(args.url, converted_path, token)
        except RuntimeError as e:
            print(f"Search error: {e}", file=sys.stderr)
            sys.exit(1)

    print_results(results)


if __name__ == "__main__":
    main()
