import requests
from urllib.parse import urljoin
import json
from dataclasses import dataclass

SERVER = "http://localhost:8000"

@dataclass
class Package:
    name: str
    url: str
    deps: list[str]
    description: str

def get_package_list():
    print("Fetching package list...")
    pcks_json = requests.get(urljoin(SERVER, "packages.json")).text
    pcks_dict = json.loads(pcks_json)
    pcks = []
    for pck_dict in pcks_dict:
        pck = Package(pck_dict["name"], urljoin(SERVER, pck_dict["path"]), pck_dict["deps"], pck_dict["description"])
        pcks.append(pck)
    print("Found {} packages.".format(len(pcks)))
    return pcks

def download_package(package: Package, path: str):
    print("Downloading {}...".format(package.name))
    with open(path, "wb") as f:
        f.write(requests.get(package.url).content)

