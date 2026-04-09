import requests

BASE_URL = "https://api.spacetraders.io/v2"

def get_account(token):
    return requests.get(
        f"{BASE_URL}/my/agent",
        headers={"Authorization": f"Bearer {token}"}
    )

def get_ships(token):
    return requests.get(
        f"{BASE_URL}/my/ships",
        headers={"Authorization": f"Bearer {token}"}
    )

def get_contracts(token):
    return requests.get(
        f"{BASE_URL}/my/contracts",
        headers={"Authorization": f"Bearer {token}"}
    )

def refuel_ship(token, ship):
    return requests.post(
        f"{BASE_URL}/my/ships/{ship}/refuel",
        headers={"Authorization": f"Bearer {token}"}
    )