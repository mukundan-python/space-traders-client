import tkinter as tk
from tkinter import ttk

from collections import defaultdict
from datetime import datetime
from itertools import zip_longest
from tkinter import messagebox
from utils import parse_datetime, format_datetime

import json
import os.path
import requests

import locale

locale.setlocale(locale.LC_ALL, "")  # Use '' for auto, or force e.g. to 'en_US.UTF-8'

AGENT_FILE = "agents.json"

API_STATUS = "https://api.spacetraders.io/v2/"
LIST_FACTIONS = "https://api.spacetraders.io/v2/factions"
CLAIM_USER = "https://api.spacetraders.io/v2/register"
MY_ACCOUNT = "https://api.spacetraders.io/v2/my/agent"
MY_CONTRACTS = "https://api.spacetraders.io/v2/my/contracts"
MY_SHIPS = "https://api.spacetraders.io/v2/my/ships"


FACTION_LOOKUPS = {}



def load_player_logins():
    known_agents = {}

    if os.path.exists(AGENT_FILE):
        with open(AGENT_FILE) as json_agents:
            known_agents = json.load(json_agents)

    return known_agents


def store_agent_login(json_result):
    known_agents = load_player_logins()
    known_agents[json_result["symbol"]] = json_result["token"]

    with open(AGENT_FILE, "w") as json_agents:
        json.dump(known_agents, json_agents)


def get_faction_lookups():
    global FACTION_LOOKUPS
    if len(FACTION_LOOKUPS) > 0:
        return FACTION_LOOKUPS

    try:
        response = requests.get(
            LIST_FACTIONS,
            params={"limit": 20},
        )

        if response.status_code == 200:
            faction_json = response.json()
            for faction in faction_json["data"]:
                FACTION_LOOKUPS[faction["symbol"]] = faction["name"]

        else:
            print("Failed:", response.status_code, response.reason, response.text)

    except ConnectionError as ce:
        print("Failed:", ce)

    return FACTION_LOOKUPS


def generate_faction_combobox():
    faction_combobox["values"] = sorted(get_faction_lookups().values())


def generate_login_combobox():
    known_agents = load_player_logins()
    agent_list = sorted(known_agents.keys(), key=str.casefold)

    id_login["values"] = agent_list


def show_agent_summary(json_result):
    global FACTION_LOOKUPS
    tabs.tab(0, state=tk.DISABLED)
    tabs.tab(1, state=tk.NORMAL)
    tabs.tab(2, state=tk.NORMAL)
    tabs.tab(3, state=tk.NORMAL)
    tabs.tab(4, state=tk.NORMAL)

    player_token.set(json_result["token"])
    player_login.set(json_result["symbol"])
    player_faction.set(get_faction_lookups()[json_result["startingFaction"]])
    player_worth.set(f"{json_result['credits']:n}")

    tabs.select(1)


def register_agent():
    try:
        username = agent_name.get()
        faction = next(
            iter(
                [
                    symbol
                    for symbol, name in get_faction_lookups().items()
                    if name == agent_faction.get()
                ]
            )
        )

        response = requests.post(
            CLAIM_USER,
            data={"faction": faction, "symbol": username},
        )
        if response.status_code < 400:
            result = response.json()
            # used to hold the token for later
            result["data"]["agent"]["token"] = result["data"]["token"]
            store_agent_login(result["data"]["agent"])
            show_agent_summary(result["data"]["agent"])
            agent_name.set("")
        else:
            print("Failed:", response.status_code, response.reason, response.text)

    except StopIteration:
        print("Did they pick a faction?")

    except ConnectionError as ce:
        print("Failed:", ce)


def login_agent():
    player_token.set(player_login.get())

    # -1 -> user entered a new token, so there won't be a name selected
    if id_login.current() != -1:
        known_agents = load_player_logins()
        player_token.set(known_agents[player_login.get()])

    try:
        response = requests.get(
            MY_ACCOUNT,
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {player_token.get()}",
            },
        )
        if response.status_code == 200:
            result = response.json()
            # used to hold the token for later
            result["data"]["token"] = player_token.get()
            show_agent_summary(result["data"])
            # print(result)

            # -1, so now store the agent name / token for future runs
            if id_login.current() == -1:
                store_agent_login(result["data"])

        else:
            print("Failed:", response.status_code, response.reason, response.text)

    except ConnectionError as ce:
        print("Failed:", ce)


def logout_agent():
    tabs.tab(0, state=tk.NORMAL)
    tabs.tab(1, state=tk.DISABLED)
    tabs.tab(2, state=tk.DISABLED)
    tabs.tab(3, state=tk.DISABLED)
    tabs.tab(4, state=tk.DISABLED)
    player_login.set("")
    player_token.set("")

    tabs.select(0)


def refresh_tabs(event):
    selected_index = tabs.index(tabs.select())
    if selected_index == 1:
        refresh_player_summary()

    elif selected_index == 2:
        refresh_leaderboard()


def refresh_player_summary(*args):
    try:
        response = requests.get(
            MY_ACCOUNT,
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {player_token.get()}",
            },
            params={"limit":20},
        )
        if response.status_code == 200:
            result = response.json()

            player_worth.set(f"{result['data']['credits']:n}")

        response = requests.get(
            MY_CONTRACTS,
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {player_token.get()}",
            },
        )
        if response.status_code == 200:
            result = response.json()
            contract_view.delete(*contract_view.get_children())
            for row in result["data"]:
                if len(row["terms"]["deliver"]) > 0:
                    remaining = (
                        row["terms"]["deliver"][0]["unitsRequired"]
                        - row["terms"]["deliver"][0]["unitsFulfilled"]
                    )
                    contract_view.insert(
                        "",
                        "end",
                        iid=row["id"],
                        text="contract_values",
                        open=True,
                        values=(
                            get_faction_lookups()[row["factionSymbol"]],
                            row["type"],
                            format_datetime(row["terms"]["deadline"]),
                            row["terms"]["deliver"][0]["tradeSymbol"],
                            row["terms"]["deliver"][0]["destinationSymbol"],
                            f"{remaining:n}",
                        ),
                    )
                for subrow, item in enumerate(row["terms"]["deliver"][1:]):
                    contract_view.insert(
                        row["id"],
                        "end",
                        iid=f'{row["id"]}#{subrow}',
                        text="extra_items",
                        values=(
                            "",
                            "",
                            "",
                            item["tradeSymbol"],
                            item["destinationSymbol"],
                            f"{(item['unitsRequired']-item['unitsFulfilled']):n}",
                        ),
                    )

        else:
            print("Failed:", response.status_code, response.reason, response.text)

        response = requests.get(
            MY_SHIPS,
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {player_token.get()}",
            },
        )
        if response.status_code == 200:
            result = response.json()
            ship_view.delete(*ship_view.get_children())
            for row in result["data"]:
                modules_and_mounts = list(
                    zip_longest(
                        row["modules"], row["mounts"], fillvalue=defaultdict(str)
                    )
                )
                if len(modules_and_mounts) > 0:
                    module, mount = modules_and_mounts[0]
                else:
                    module = defaultdict(str)
                    mount = defaultdict(str)

                ship_view.insert(
                    "",
                    "end",
                    iid=row["symbol"],
                    text="ship_values",
                    open=True,
                    values=(
                        row["symbol"],
                        row["registration"]["role"],
                        row["frame"]["name"],
                        row["reactor"]["name"],
                        row["engine"]["name"],
                        module["name"],
                        mount["name"],
                        f'{row["fuel"]["current"]} / {row["fuel"]["capacity"]}',
                        f'{row["cargo"]["units"]} / {row["cargo"]["capacity"]}',
                    ),
                )
                for subrow, (module, mount) in enumerate(modules_and_mounts[1:]):
                    ship_view.insert(
                        row["symbol"],
                        "end",
                        iid=f'{row["symbol"]}#{subrow}',
                        text="modules_and_mounts",
                        values=(
                            "",
                            "",
                            "",
                            "",
                            "",
                            module["name"],
                            mount["name"],
                            "",
                            "",
                        ),
                    )

        else:
            print("Failed:", response.status_code, response.reason, response.text)

    except ConnectionError as ce:
        print("Failed:", ce)


def display_clicked_contract(*args):
    print(contract_view.index(contract_view.focus()), contract_view.focus())


def display_clicked_ship(*args):
    print(ship_view.index(ship_view.focus()), ship_view.focus())


def refresh_leaderboard(*args):
    try:
        response = requests.get(
            API_STATUS,
            params={"token": player_token.get()},
        )
        if response.status_code == 200:
            result = response.json()
            credits_leaderboard_view.delete(*credits_leaderboard_view.get_children())
            for rank, row in enumerate(result["leaderboards"]["mostCredits"]):
                credits_leaderboard_view.insert(
                    "",
                    "end",
                    text="values",
                    values=(rank + 1, row["agentSymbol"], f"{row['credits']:n}"),
                )

            charts_leaderboard_view.delete(*charts_leaderboard_view.get_children())
            for rank, row in enumerate(result["leaderboards"]["mostSubmittedCharts"]):
                charts_leaderboard_view.insert(
                    "",
                    "end",
                    text="values",
                    values=(rank + 1, row["agentSymbol"], f"{row['chartCount']:n}"),
                )

        else:
            print("Failed:", response.status_code, response.reason, response.text)

    except ConnectionError as ce:
        print("Failed:", ce)

# Marketplace finder function used to get the waypoints with Marketplace trait and display them 
def list_marketplaces():
    selected_ship = ship_control_var.get()

    if not selected_ship:
        messagebox.showerror("Error", "No ship selected.")
        return
    # Used the ship data to get current waypoint
    ship_response = requests.get(
        f"https://api.spacetraders.io/v2/my/ships/{selected_ship}",
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {player_token.get()}",
        },
    )
    # Stops if ship data cannot be loaded
    if ship_response.status_code != 200:
        messagebox.showerror("Error", "Could not load ship.")
        return
    # Used to get current waypoint
    waypoint = ship_response.json()["data"]["nav"]["waypointSymbol"]
    # Used to extract system symbol from waypoint
    system_symbol = "-".join(waypoint.split("-")[:2])
    # Used to sort out and return the waypoints that has marketplace trait
    waypoint_response = requests.get(
        f"https://api.spacetraders.io/v2/systems/{system_symbol}/waypoints",
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {player_token.get()}",
        },
        params={"traits": "MARKETPLACE"},
    )

    if waypoint_response.status_code == 200:
         # Used to extract marketplace symbols
        marketplaces = [wp["symbol"] for wp in waypoint_response.json()["data"]]
        # Used to show the results on the label
        marketplace_result.config(text="\n".join(marketplaces))
    else:
        messagebox.showerror("Error", "Could not load waypoints.")
        
# Refuel function used to refuel the ship 
def refuel_ship():
    selected_ship = ship_control_var.get()

    if not selected_ship:
        messagebox.showerror("Error", "No ship selected.")
        return
    # Sends refuel request to the API
    response = requests.post(
        f"https://api.spacetraders.io/v2/my/ships/{selected_ship}/refuel",
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {player_token.get()}",
        },
    )

    if response.status_code == 200:
        refuel_status.config(text="Status: REFUELLED", fg="green")
        refresh_player_summary()
    else:
        messagebox.showerror("Error", response.text)
        
# Generate Waypoint function used to get the waypoints in the system of the ship that is selected and also to automatically update the data
def generate_waypoint_list():
    # Gets the currently selected ship from the treeview
    ship_symbol = ship_view.focus()  
    # Used to empty the dropdown before showing newer waypoints
    waypoint_dropdown["values"] = []   
    # Stops if no ship is selected
    if not ship_symbol:
        return  

    response = requests.get(
        f"https://api.spacetraders.io/v2/my/ships/{ship_symbol}",
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {player_token.get()}",
        },
    )

    if response.status_code == 200:
        ship_data = response.json()
        # Used to get the current waypoint
        waypoint = ship_data["data"]["nav"]["waypointSymbol"]  
        system_symbol = "-".join(waypoint.split("-")[:2])

        waypoint_response = requests.get(
            f"https://api.spacetraders.io/v2/systems/{system_symbol}/waypoints",
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {player_token.get()}",
            },
            params={"limit": 20},  # Limiting results to 20 waypoints
        )

        if waypoint_response.status_code == 200:
            data = waypoint_response.json()
            # Used to automatically updates the dropdown with waypoint symobls
            waypoint_dropdown["values"] = [wp["symbol"] for wp in data["data"]]
        else:
            print("Failed:", waypoint_response.status_code, waypoint_response.reason)
    else:
        print("Failed:", response.status_code, response.reason)
        
# Travel function used to travel the chosen waypoint
def travel_ship():
    selected_ship = ship_view.focus()
    destination = selected_waypoint.get()

    if not selected_ship:
        messagebox.showerror("Error", "No ship selected.") 
        return

    if not destination:
        messagebox.showerror("Error", "No destination selected.")    
        return

    response = requests.post(
        f"https://api.spacetraders.io/v2/my/ships/{selected_ship}/navigate",
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {player_token.get()}",
        },
        json={"waypointSymbol": destination},  
    )

    if response.status_code == 200:
        # Used to refresh all data after successful travel 
        refresh_player_summary()  
        messagebox.showinfo("Success", "Ship is travelling.")
        
    else:
        messagebox.showerror("Travel Failed", response.text)
        
# Deliver function used to deliver the goods to the contracts destination
def deliver_contract():
    # Used to get selected contract from treeview
    selected_contract = contract_view.focus() 
    # used to get selected ship from treeview
    selected_ship = ship_view.focus() 

    if not selected_contract or not selected_ship:
        messagebox.showerror("Error", "Select both a contract and a ship.")  
        return
    # Used to strip sub-item suffix to get real contract ID
    if "#" in selected_contract: 
        selected_contract = selected_contract.split("#")[0] 
    # Gets the needed trade good from contract row
    trade_symbol = contract_view.item(selected_contract)["values"][3] 

    # Gets the selected ship's full data including cargo
    cargo_response = requests.get(
        f"https://api.spacetraders.io/v2/my/ships/{selected_ship}",
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {player_token.get()}",
        },
    ) 

    if cargo_response.status_code != 200:
        # Stops if ship data cannot be loaded
        messagebox.showerror("Error", "Could not load cargo.") 
        return
    # Used to extract cargo inventory from response
    cargo = cargo_response.json()["data"]["cargo"]["inventory"]
    # Used to find how many units of the required good are there
    units = next((item["units"] for item in cargo if item["symbol"] == trade_symbol), 0) 

    if units == 0:
        # Stops if required good are not in cargo
        messagebox.showerror("Error", f"No {trade_symbol} in cargo.") 
        return
    # Used to send all available units to the contract destination
    response = requests.post(
        f"https://api.spacetraders.io/v2/my/contracts/{selected_contract}/deliver",
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {player_token.get()}",
        },
        json={
            "shipSymbol": selected_ship,
            "tradeSymbol": trade_symbol,
            "units": units 
        }
    )

    if response.status_code == 200:
        # Used to refresh contracts and cargo after delivery
        refresh_player_summary() 
        messagebox.showinfo("Success", f"Delivered {units} units of {trade_symbol}.")
    else:
        messagebox.showerror("Error", response.text)
        
# Buy function used to purchase goods from the market
def buy_goods():
    # Used to get selected ship from market dropdown
    selected_ship = market_ship_var.get()
    # Used to get selected item from market table
    selected_goods = market_view.focus() 
    # Used to get quantity entered by player
    quantity = quantity_var.get()  

    if not selected_goods:
        # Validates goods are selected
        messagebox.showerror("Error", "No goods selected.")  
        return

    if not selected_ship:
        # Validates ship is selected
        messagebox.showerror("Error", "No ship selected.")  
        return
    # converting into integer
    try:
        quantity = int(quantity)  
    except:
        # Shows error if not a number
        messagebox.showerror("Error", "Invalid quantity.")  
        return

    response = requests.post(
        f"https://api.spacetraders.io/v2/my/ships/{selected_ship}/purchase",
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {player_token.get()}",
        },
        json={"symbol": selected_goods, "units": quantity} # Sends purchase request to API
    )

    if response.status_code == 200:
        # Used to refresh credits and cargo after purchase
        refresh_player_summary() 
        messagebox.showinfo("Success", "Purchase complete.")
    else:
        messagebox.showerror("Error", response.text)
        
#Sell function used to sell the selected goods from the ship to the market
def sell_goods():
    # Used to get selected ship from market dropdown
    selected_ship = market_ship_var.get()
    # Used to get selected item from market table
    selected_goods = market_view.focus()
    # Used to get quantity entered by player
    quantity = quantity_var.get()

    if not selected_goods:
        # Validates goods are selected
        messagebox.showerror("Error", "No goods selected.")
        return

    if not selected_ship:
        # Validates ship is selected
        messagebox.showerror("Error", "No ship selected.")
        return
    # converting into integers
    try:
        quantity = int(quantity)
    except:
        # shows error when not a number
        messagebox.showerror("Error", "Invalid quantity.")
        return

    response = requests.post(
        f"https://api.spacetraders.io/v2/my/ships/{selected_ship}/sell",
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {player_token.get()}",
        },
        json={"symbol": selected_goods, "units": quantity}
    )

    if response.status_code == 200:
        # Used to refresh the credits and cargo after sale
        refresh_player_summary()
        messagebox.showinfo("Success", "Sold successfully.")
    else:
        messagebox.showerror("Error", response.text)
        
# Market Function used to show all the available goods at the current marketplace using the waypoint
def load_market():
    selected_ship = market_ship_var.get()

    if not selected_ship:
        messagebox.showerror("Error", "No ship selected.")
        return
    # Used to get the waypoint from the ship data
    ship_response = requests.get(
        f"https://api.spacetraders.io/v2/my/ships/{selected_ship}",
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {player_token.get()}",
        },
    )

    if ship_response.status_code != 200:
        # Stops the process if the ship data isn't loaded
        messagebox.showerror("Error", "Could not load ship data.")
        return

    ship_data = ship_response.json()
    # Used to get the ship data
    waypoint = ship_data["data"]["nav"]["waypointSymbol"]
    system_symbol = "-".join(waypoint.split("-")[:2])  # [:2]- to get full symbol
    # Used to get the market data from the current waypoint of the ship
    market_response = requests.get(
        f"https://api.spacetraders.io/v2/systems/{system_symbol}/waypoints/{waypoint}/market",
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {player_token.get()}",
        },
    )

    if market_response.status_code == 200:
        market_data = market_response.json()

        market_view.delete(*market_view.get_children())
        # Used to add each trade goods to the market table
        for item in market_data["data"]["tradeGoods"]:
            market_view.insert(
                "",
                "end",
                iid=item["symbol"],
                values=(item["symbol"], item["purchasePrice"]),
            )

    else:
        messagebox.showerror("Error", "Could not load market.")
        
# Cargo function used to show the current items in the ship
def get_cargo():
    # Used to get the selected ship from dropdown
    selected_ship = ship_control_var.get() 
    # Used to validate a contract if it selected 
    if not selected_ship:
        messagebox.showerror("Error", "No ship selected.") 
        return
    # Used to get the ships data including cargo inventory
    response = requests.get(
        f"https://api.spacetraders.io/v2/my/ships/{selected_ship}",
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {player_token.get()}",
        },
    ) 
    if response.status_code == 200:
        # Used to extract cargo inventory
        cargo = response.json()["data"]["cargo"]["inventory"]  
        # Used to clear the table before automatically updating to prevent duplicates
        cargo_view.delete(*cargo_view.get_children()) 
        # Used to add each cargo item into the table
        for item in cargo:
            cargo_view.insert(
                "",
                "end",
                values=(item["symbol"], item["units"])
            ) 
    else:
        messagebox.showerror("Error", "Could not load cargo.")
        
# Orbit function used to orbit the ship in order to travel
def orbit_ship():
    selected_ship = ship_control_var.get()

    if not selected_ship:
        messagebox.showerror("Error", "No ship selected.")
        return

    response = requests.post(
        f"https://api.spacetraders.io/v2/my/ships/{selected_ship}/orbit",
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {player_token.get()}",
        },
    )

    if response.status_code == 200:
        orbit_status.config(text="Status: IN ORBIT", fg="green")
        refresh_player_summary()
    else:
        messagebox.showerror("Error", response.text)
        
# Dock function used to dock ship at current waypoint
def dock_ship():
    selected_ship = ship_control_var.get()

    if not selected_ship:
        messagebox.showerror("Error", "No ship selected.")
        return

    response = requests.post(
        f"https://api.spacetraders.io/v2/my/ships/{selected_ship}/dock",
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {player_token.get()}",
        },
    )

    if response.status_code == 200:
        dock_status.config(text="Status: DOCKED", fg="green")
        refresh_player_summary()
    else:
        messagebox.showerror("Error", response.text)
# Accept function used to approve the contract 
def accept_contract():
    selected = contract_view.focus() 

    if not selected:
        messagebox.showerror("Error", "No contract selected.")
        return
    # Sending accept request to API
    response = requests.post(
        f"https://api.spacetraders.io/v2/my/contracts/{selected}/accept",
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {player_token.get()}",
        },
    )  

    if response.status_code == 200:
        refresh_player_summary()
        messagebox.showinfo("Success", "Contract accepted.")
        
    else:
        messagebox.showerror("Error", response.text)

# Submit function used to fulfill the contract after the delivery
def submit_contract():
    # Used to get the currently selected contract from the treeview
    selected = contract_view.focus()  

    if not selected:
        messagebox.showerror("Error", "No contract selected.")  
        return

    response = requests.post(
        f"https://api.spacetraders.io/v2/my/contracts/{selected}/fulfill",
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {player_token.get()}",
        },
    )

    if response.status_code == 200:
        # Used to refresh contracts and credits after submitting
        refresh_player_summary()  
        messagebox.showinfo("Success", "Contract completed.")
    else:
        messagebox.showerror("Error", response.text)

###
# Root window, with app title
#
root = tk.Tk()
root.title("Io Space Trading")

# Main themed frame, for all other widgets to rest upon
main = ttk.Frame(root, padding="3 3 12 12")
main.grid(sticky=tk.NSEW)

root.columnconfigure(0, weight=1)
root.rowconfigure(0, weight=1)

# Tabbed widget for rest of the app to run in
tabs = ttk.Notebook(main)
tabs.grid(sticky=tk.NSEW)
tabs.bind("<<NotebookTabChanged>>", refresh_tabs)

main.columnconfigure(0, weight=1)
main.rowconfigure(0, weight=1)

# setup the four main tabs
welcome = ttk.Frame(tabs)
summary = ttk.Frame(tabs)
leaderboard = ttk.Frame(tabs)
market_tab = ttk.Frame(tabs)
ship_control = ttk.Frame(tabs)
tabs.add(welcome, text="Welcome")
tabs.add(summary, text="Summary")
tabs.add(ship_control, text="Ship Control")
tabs.add(market_tab, text="Market")
tabs.add(leaderboard, text="Leaderboard")
tabs.tab(1, state=tk.DISABLED)
tabs.tab(2, state=tk.DISABLED)
tabs.tab(3, state=tk.DISABLED)
tabs.tab(4, state=tk.DISABLED)


##
# Ship control tab
#
# select ship
def populate_control_ships():
    # Reads all ship names from the Summary tab treeview
    known_ships = [ship_view.item(s)["values"][0] for s in ship_view.get_children()] 
    # Automatically updates the dropdown with ship names
    ship_control_dropdown["values"] = known_ships  
    # Gets currently selected ship
    selected_ship = ship_control_var.get() 
    if not selected_ship:
        return 
    # Fetches ship data from API
    response = requests.get(
        f"https://api.spacetraders.io/v2/my/ships/{selected_ship}",
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {player_token.get()}",
        },
    ) 
    if response.status_code == 200:
        data = response.json()["data"]
        # Gets current ship status
        status = data["nav"]["status"] 
        # Gets current ship location
        location = data["nav"]["waypointSymbol"] 
        # Updates location label
        ship_location_label.config(text=f"Location: {location}") 
        if status == "IN_ORBIT":
            # Updates orbit status to green
            orbit_status.config(text="Status: IN ORBIT", fg="green")  
            dock_status.config(text="Status: DOCKED", fg="black")
        elif status == "DOCKED":
            # Updates dock status to green
            dock_status.config(text="Status: DOCKED", fg="green") 
            orbit_status.config(text="Status: IN ORBIT", fg="black")
        elif status == "IN_TRANSIT":
            # Shows blue for in transit
            orbit_status.config(text="Status: IN TRANSIT", fg="blue") 
            dock_status.config(text="Status: IN TRANSIT", fg="blue")
            
ttk.Label(ship_control, text="Select Ship:").grid(row=0, column=0, sticky=tk.W, padx=10)
ship_control_var = tk.StringVar()
# Used to create the ship selector dropdown with postcommand to automatically show the ships
ship_control_dropdown = ttk.Combobox(ship_control, textvariable=ship_control_var, postcommand= populate_control_ships)
ship_control_dropdown.grid(row=1, column=0, columnspan=2, sticky=tk.EW, ipady=5, pady=5, padx=10)
# Used to bind selection so location and status updates immediately when a ship is chosen
#ship_control_dropdown.bind("<<ComboboxSelected>>", lambda e: populate_control_ships())
ship_control_dropdown.bind("<<ComboboxSelected>>", lambda e: populate_control_ships())
# Label used to show the ship's current waypoint and it updates automatically after selection
ship_location_label = tk.Label(ship_control, text="Location: -")
ship_location_label.grid(row=1,column=2,sticky = tk.W,padx=10)

            
# Orbit Control labelframe
orbit_frame = ttk.LabelFrame(ship_control, text="Orbit Control", padding=10)
orbit_frame.grid(row=2, column=0, padx=10, pady=10, sticky=tk.NSEW)

ttk.Button(orbit_frame, text="ORBIT SHIP", command=orbit_ship).grid(row=0, column=0, sticky=tk.EW)
#label used to show the orbit status
orbit_status = tk.Label(orbit_frame, text="Status: DOCKED")
orbit_status.grid(row=1, column=0)

# Dock Control labelframe
dock_frame = ttk.LabelFrame(ship_control, text="Dock Control", padding=10)
dock_frame.grid(row=2, column=1, padx=10, pady=10, sticky=tk.NSEW)

ttk.Button(dock_frame, text="DOCK SHIP", command=dock_ship).grid(row=0, column=0, sticky=tk.EW)
# label used to show the dock status
dock_status = tk.Label(dock_frame, text="Status: IN ORBIT")
dock_status.grid(row=1, column=0)

# Refuel labelframe
refuel_frame = ttk.LabelFrame(ship_control, text="Refuel", padding=10)
refuel_frame.grid(row=2, column=2, padx=10, pady=10, sticky=tk.NSEW)

ttk.Button(refuel_frame, text="REFUEL SHIP", command=refuel_ship).grid(row=0, column=0, sticky=tk.EW)
# label used to show the fuel status
refuel_status = tk.Label(refuel_frame, text="")
refuel_status.grid(row=1, column=0)

refuel_frame.columnconfigure(0, weight=1)

# Marketplace Finder labelframe
marketplace_frame = ttk.LabelFrame(ship_control, text="Find Marketplace", padding=10)
marketplace_frame.grid(row=3, column=0, columnspan=3, padx=10, pady=10, sticky=tk.NSEW)

ttk.Button(marketplace_frame, text="List Marketplaces", command=list_marketplaces).grid(row=0, column=0, sticky=tk.EW)
# label used to show the list of marketplaces waypoints
marketplace_result = tk.Label(marketplace_frame, text="", wraplength=300)
marketplace_result.grid(row=1, column=0, sticky=tk.EW)

marketplace_frame.columnconfigure(0, weight=1)

# Cargo Info labelframe postitioned to the right of orbit, dock and refuel
cargo_frame = ttk.LabelFrame(ship_control,text = "Cargo info",padding = 10)
cargo_frame.grid(row=2,column=3,padx=10,pady=10,sticky= tk.NSEW)

# Treeview table used to display cargo items and units
cargo_view = ttk.Treeview(cargo_frame, columns=("Item","Units"), show="headings", height=5)
cargo_view.heading("Item", text="Item")
cargo_view.heading("Units", text="Units")
cargo_view.grid(row=0, column=0, sticky=tk.NSEW)
# Buttons used to call the function get_cargo and load the cargo to the table
ttk.Button(cargo_frame, text="Load Cargo", command=get_cargo).grid(row=1, column=0, sticky=tk.EW, pady=5)

cargo_frame.columnconfigure(0, weight=1)
cargo_frame.rowconfigure(0, weight=1)
###
# agent registration/login tab
#

welcome_frame = ttk.Frame(welcome)
welcome_frame.grid(row=0, column=0, columnspan=2, sticky=tk.NSEW)

# left hand frame will check/register new agents and return/store the UUID
register = ttk.LabelFrame(welcome_frame, text="Register", relief="groove", padding=5)
register.grid(sticky=tk.NSEW)

# widgets required on the left are a label, an entry, a dropdown, and a button
agent_name = tk.StringVar()
agent_faction = tk.StringVar()
ttk.Label(
    register, text="Enter a new agent name\nto start a new account", anchor=tk.CENTER
).grid(sticky=tk.EW)
faction_combobox = ttk.Combobox(
    register, textvariable=agent_faction, postcommand=generate_faction_combobox
)
faction_combobox.grid(row=1, column=0, sticky=tk.EW)
ttk.Entry(register, textvariable=agent_name).grid(row=2, column=0, sticky=tk.EW)
ttk.Button(register, text="Register new agent", command=register_agent).grid(
    row=3, column=0, columnspan=2, sticky=tk.EW
)

register.columnconfigure(0, weight=1)
register.rowconfigure(0, weight=1)

ttk.Label(welcome_frame, text="or", padding=10, anchor=tk.CENTER).grid(
    row=0, column=1, sticky=tk.EW
)

# right hand frame will allow to choose from known players and/or paste in existing
# UUID to login and play as that agent
login = ttk.LabelFrame(welcome_frame, text="Login", relief=tk.GROOVE, padding=5)
login.grid(row=0, column=2, sticky=tk.NSEW)

# widgets required on the right are a dropdown, and a button
player_login = tk.StringVar()
player_token = (
    tk.StringVar()
)  # going to use this to remember the currently logged in agent
ttk.Label(login, text="Choose the agent to play as\nor paste an existing id", anchor = tk.CENTER).grid(
    sticky=tk.EW
)
id_login = ttk.Combobox(
    login, textvariable=player_login, postcommand=generate_login_combobox
)
id_login.grid(row=1, column=0, sticky=tk.EW)
ttk.Button(login, text="Login agent", command=login_agent).grid(
    row=2, column=0, columnspan=2, sticky=tk.EW
)

login.columnconfigure(0, weight=1)
login.rowconfigure(0, weight=1)

welcome_frame.columnconfigure(0, weight=1)
welcome_frame.columnconfigure(2, weight=1)
welcome_frame.rowconfigure(0, weight=1)

welcome.columnconfigure(0, weight=1)
welcome.rowconfigure(0, weight=1)

###
# summary tab
#

player_summary = ttk.LabelFrame(summary, text="Agent", relief=tk.GROOVE, padding=5)

player_faction = tk.StringVar()
player_worth = tk.StringVar()

ttk.Label(player_summary, textvariable=player_login, anchor=tk.CENTER).grid(
    columnspan=2, sticky=tk.EW
)
ttk.Label(player_summary, text="Faction:").grid(row=1, column=0, sticky=tk.W)
ttk.Label(player_summary, textvariable=player_faction, anchor=tk.CENTER).grid(
    row=1, column=1, sticky=tk.EW
)
ttk.Label(player_summary, text="Credits:").grid(row=2, column=0, sticky=tk.W)
ttk.Label(player_summary, textvariable=player_worth, anchor=tk.CENTER).grid(
    row=2, column=1, sticky=tk.EW
)
ttk.Button(player_summary, text="Logout", command=logout_agent).grid(
    row=5, column=0, columnspan=2, sticky=tk.EW
)

player_summary.columnconfigure(0, weight=1)

contract_summary = ttk.LabelFrame(
    summary, text="Contracts", relief=tk.GROOVE, padding=5
)

contract_view = ttk.Treeview(
    contract_summary,
    height=3,
    columns=("Faction", "Type", "Deadline", "Goods", "Destination", "Owing"),
    show="headings",
)
contract_view.column("Faction", anchor=tk.W, width=20)
contract_view.column("Type", anchor=tk.W, width=20)
contract_view.column("Deadline", anchor=tk.W, width=20)
contract_view.column("Goods", anchor=tk.W, width=30)
contract_view.column("Destination", anchor=tk.W, width=20)
contract_view.column("Owing", anchor=tk.E, width=20)
contract_view.heading("#1", text="Faction")
contract_view.heading("#2", text="Type")
contract_view.heading("#3", text="Deadline")
contract_view.heading("#4", text="Goods")
contract_view.heading("#5", text="Destination")
contract_view.heading("#6", text="Owing")
contract_view.grid(sticky=tk.NSEW)
contract_scroll = ttk.Scrollbar(
    contract_summary, orient=tk.VERTICAL, command=contract_view.yview
)
contract_scroll.grid(column=1, row=0, sticky=tk.NS)
contract_view.config(yscrollcommand=contract_scroll.set)
contract_view.bind("<Double-1>", display_clicked_contract)

contract_summary.columnconfigure(0, weight=1)
contract_summary.rowconfigure(0, weight=1)

# Adding Accept, Submit and Deliver buttons 
ttk.Button(contract_summary, text="Accept", command=accept_contract).grid(row=1, column=0, sticky=tk.EW) 
ttk.Button(contract_summary, text="Submit", command=submit_contract).grid(row=2, column=0, sticky=tk.EW)
ttk.Button(contract_summary, text="Deliver", command=deliver_contract).grid(row=3, column=0, sticky=tk.EW)

ship_summary = ttk.LabelFrame(summary, text="Ships", relief=tk.GROOVE, padding=5)
ship_view = ttk.Treeview(
    ship_summary,
    height=3,
    columns=(
        "Registration",
        "Role",
        "Frame",
        "Reactor",
        "Engine",
        "Modules",
        "Mounts",
        "Fuel",
        "Cargo",
    ),
    show="headings",
)
ship_view.column("Registration", anchor=tk.W, width=30)
ship_view.column("Role", anchor=tk.W, width=30)
ship_view.column("Frame", anchor=tk.W, width=30)
ship_view.column("Reactor", anchor=tk.W, width=30)
ship_view.column("Engine", anchor=tk.W, width=30)
ship_view.column("Modules", anchor=tk.W, width=30)
ship_view.column("Mounts", anchor=tk.W, width=30)
ship_view.column("Fuel", anchor=tk.E, width=20)
ship_view.column("Cargo", anchor=tk.E, width=20)
ship_view.heading("#1", text="Registration")
ship_view.heading("#2", text="Role")
ship_view.heading("#3", text="Frame")
ship_view.heading("#4", text="Reactor")
ship_view.heading("#5", text="Engine")
ship_view.heading("#6", text="Modules")
ship_view.heading("#7", text="Mounts")
ship_view.heading("#8", text="Fuel")
ship_view.heading("#9", text="Cargo")
ship_view.grid(sticky=tk.NSEW)
ship_scroll = ttk.Scrollbar(ship_summary, orient=tk.VERTICAL, command=ship_view.yview)
ship_scroll.grid(column=1, row=0, sticky=tk.NS)
ship_view.config(yscrollcommand=ship_scroll.set)
ship_view.bind("<Double-1>", display_clicked_ship)

ship_summary.columnconfigure(0, weight=1)
ship_summary.rowconfigure(0, weight=1)


player_summary.grid(row=0, column=0, sticky=tk.NSEW)
contract_summary.grid(row=0, column=1, sticky=tk.NSEW)
ship_summary.grid(row=1, column=0, columnspan=2, sticky=tk.NSEW)

# Navigation Controls
# Creating the navigation labelframe below the ships table
navigation_frame = ttk.LabelFrame(ship_summary, text="Navigation", padding=5)
navigation_frame.grid(row=2, column=0, columnspan=2, sticky=tk.EW)
# Storing the selected waypoint using a variable
selected_waypoint = tk.StringVar()
#  Adding waypoints automatically to the dropdown using postcommand
waypoint_dropdown = ttk.Combobox(navigation_frame, textvariable=selected_waypoint, postcommand = generate_waypoint_list)
waypoint_dropdown.grid(row=0, column=0, sticky=tk.EW)
# Button that calls travel_ship() when pressed
ttk.Button(navigation_frame, text="Travel", command=travel_ship).grid(row=0, column=1, sticky=tk.EW)

navigation_frame.columnconfigure(0, weight=1)

summary.columnconfigure(0, weight=1)
summary.columnconfigure(1, weight=3)
summary.rowconfigure(0, weight=2)
summary.rowconfigure(1, weight=3)

###
# leaderboard tab
#

credits_leaderboard_view = ttk.Treeview(
    leaderboard, height=6, columns=("Rank", "Agent", "Credits"), show="headings"
)
credits_leaderboard_view.column("Rank", anchor=tk.CENTER, width=10)
credits_leaderboard_view.column("Agent", anchor=tk.W, width=100)
credits_leaderboard_view.column("Credits", anchor=tk.E, width=100)
credits_leaderboard_view.heading("#1", text="Rank")
credits_leaderboard_view.heading("#2", text="Agent")
credits_leaderboard_view.heading("#3", text="Credits")
credits_leaderboard_view.grid(sticky=tk.NSEW)
credits_scroll = ttk.Scrollbar(
    leaderboard, orient=tk.VERTICAL, command=credits_leaderboard_view.yview
)
credits_scroll.grid(column=1, row=0, sticky=tk.NS)
credits_leaderboard_view.config(yscrollcommand=credits_scroll.set)

charts_leaderboard_view = ttk.Treeview(
    leaderboard, height=6, columns=("Rank", "Agent", "Chart Count"), show="headings"
)
charts_leaderboard_view.column("Rank", anchor=tk.CENTER, width=10)
charts_leaderboard_view.column("Agent", anchor=tk.W, width=100)
charts_leaderboard_view.column("Chart Count", anchor=tk.E, width=100)
charts_leaderboard_view.heading("#1", text="Rank")
charts_leaderboard_view.heading("#2", text="Agent")
charts_leaderboard_view.heading("#3", text="Chart Count")
charts_leaderboard_view.grid(sticky=tk.NSEW)
charts_scroll = ttk.Scrollbar(
    leaderboard, orient=tk.VERTICAL, command=charts_leaderboard_view.yview
)
charts_scroll.grid(column=1, row=1, sticky=tk.NS)
charts_leaderboard_view.config(yscrollcommand=charts_scroll.set)
refresh = ttk.Button(leaderboard, text="Refresh", command=refresh_leaderboard)
refresh.grid(column=0, row=2, sticky=tk.EW)

leaderboard.columnconfigure(0, weight=1)
leaderboard.rowconfigure((0, 1), weight=1)

#Market tab
# Treeview table for the available goods and prices at the selected waypoint
market_view = ttk.Treeview(
    market_tab,
    columns=("Symbol", "Price"),
    show="headings"
)
market_view.heading("Symbol", text="Goods")
market_view.heading("Price", text="Price")


market_view.grid(row=0, column=0, columnspan=2, sticky=tk.NSEW)

# Creating the trade labelframe for the entry bar and also the buy and sell buttons
trade_frame = ttk.LabelFrame(market_tab, text="Trade", padding=10)
trade_frame.grid(row=1, column=0, sticky=tk.NSEW, padx=5, pady=5)

ttk.Label(trade_frame, text="Quantity:").grid(row=0, column=0, sticky=tk.W)
# Storing the quantity entered using a variable
quantity_var = tk.StringVar()
ttk.Entry(trade_frame, textvariable=quantity_var).grid(row=0, column=1, sticky=tk.EW, ipady=5)
# Buy and Sell buttons 
ttk.Button(trade_frame, text="Buy", command=buy_goods).grid(row=1, column=0, sticky=tk.EW, ipady=10, padx=5, pady=5)
ttk.Button(trade_frame, text="Sell", command=sell_goods).grid(row=1, column=1, sticky=tk.EW, ipady=10, padx=5, pady=5)

trade_frame.columnconfigure(0, weight=1)
trade_frame.columnconfigure(1, weight=1)
# Creating the labelframe for the select ship using dropdown and also for the load market button
ship_frame = ttk.LabelFrame(market_tab, text="Ship", padding=10)
ship_frame.grid(row=1, column=1, sticky=tk.NSEW, padx=5, pady=5)

ttk.Label(ship_frame, text="Select Ship:").grid(row=0, column=0, sticky=tk.W)
market_ship_var = tk.StringVar()
market_ship_dropdown = ttk.Combobox(ship_frame, textvariable=market_ship_var)
market_ship_dropdown.grid(row=1, column=0, sticky=tk.EW, ipady=5, pady=5)
# buttons used to load the waypoint of the ship
ttk.Button(ship_frame, text="Load Market", command=load_market).grid(row=2, column=0, sticky=tk.EW, ipady=10, padx=5, pady=5)

ship_frame.columnconfigure(0, weight=1)

market_tab.columnconfigure(0, weight=1)
market_tab.columnconfigure(1, weight=1)
market_tab.rowconfigure(0, weight=1)

# Load ships into dropdown
def populate_market_ships():
    known_ships = [ship_view.item(s)["values"][0] for s in ship_view.get_children()]
    market_ship_dropdown["values"] = known_ships

market_ship_dropdown.config(postcommand=populate_market_ships)

market_tab.columnconfigure(0, weight=1)
market_tab.rowconfigure(0, weight=1)

def start_app():
    root.mainloop()
