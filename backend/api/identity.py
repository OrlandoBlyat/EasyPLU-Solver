from fastapi import HTTPException

def run_owner(request):
    owner = request.headers.get("x-run-owner", "")
    if len(owner) != 64 or any(char not in "0123456789abcdef" for char in owner):
        raise HTTPException(403, "Prijavna seja ni veljavna.")
    return owner


