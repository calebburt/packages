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
    pcks_json = requests.get(urljoin(SERVER, "packages.json")).text
    pcks_dict = json.loads(pcks_json)
    pcks = []
    for pck_dict in pcks_dict:
        pck = Package(pck_dict["name"], urljoin(SERVER, pck_dict["path"]), pck_dict["deps"], pck_dict["description"])
        pcks.append(pck)
    return pcks

def download_package(package: Package, path: str):
    with open(path, "wb") as f:
        f.write(requests.get(package.url).content)

packs = get_package_list()
print(packs)
download_package(packs[0], "pack.package")
