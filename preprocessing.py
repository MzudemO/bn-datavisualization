from typing import Tuple, Dict

from bs4 import BeautifulSoup, NavigableString
import re
from dateutil.parser import parse
from datetime import datetime

import pandas as pd


def set_host(tag) -> bool:
    pattern = re.compile("(Beatmap by|Mapped by)")
    return (
        isinstance(tag.previous_element, NavigableString)
        and re.search(pattern, tag.previous_element) is not None
    )


def nomination(tag) -> bool:
    pattern = re.compile("thought_balloon")

    # current formatting has the emoji in text before the user
    if (
        isinstance(tag.previous_sibling, NavigableString)
        and re.search(pattern, tag.previous_element) is not None
    ):
        return True
    # old formatting has the emoji in a link with a whitespace in between. we search for the first previous link to avoid putting three .previous_element
    else:
        return re.search(pattern, tag.find_previous("a").string) is not None


def qualification(tag) -> bool:
    pattern = re.compile("heart")

    if (
        isinstance(tag.previous_sibling, NavigableString)
        and re.search(pattern, tag.previous_element) is not None
    ):
        return True
    else:
        return re.search(pattern, tag.find_previous("a").string) is not None


def nomination_reset(tag) -> bool:
    pattern = re.compile("anger_right")

    if (
        isinstance(tag.previous_sibling, NavigableString)
        and re.search(pattern, tag.previous_element) is not None
    ):
        return True
    else:
        return re.search(pattern, tag.find_previous("a").string) is not None


def disqualification(tag) -> bool:
    pattern = re.compile("broken_heart")

    if (
        isinstance(tag.previous_sibling, NavigableString)
        and re.search(pattern, tag.previous_element) is not None
    ):
        return True
    else:
        return re.search(pattern, tag.find_previous("a").string) is not None


# Returns trailing id from osu website url
def id_from_url(url: str) -> str:
    return url.split("/")[-1]


# Input string should be in the format **Artist - Title**
# Returns Tuple[Artist, Title]
def extract_artist_title(metadata: str) -> tuple:
    pattern = re.compile("\*\*(.*?)\*\*")
    match = pattern.match(metadata).group(1)
    return match.split(
        " - ", 1
    )  # hopefully no Artists have this in their name, because there are Titles with it (Gravity - Zero)


# Parses the html at filepath, extracts list of maps, mappers, nominators
# Returns Dict{"mapsets": pd.DataFrame, "mappers": pd.DataFrame, "nominators": pd.DataFrame}
# Should probably be rewritten
def parse_html_to_df(filepath: str) -> dict:
    with open(filepath, encoding="utf8") as f:
        soup = BeautifulSoup(f, "lxml")

    distinct_messages = soup.find_all("div", class_="chatlog__messages")

    mappers = {"user_id": [], "usernames": []}
    nominators = {"user_id": [], "usernames": []}
    # only saves the last 2 bns, the last pop and the last dq for now until I think of how to do this
    mapsets = {
        "set_id": [],
        "date": [],
        "artist": [],
        "title": [],
        "host_id": [],
        "first_nominator": [],
        "second_nominator": [],
        "nomination_reset": [],
        "disqualification": [],
    }

    for dm in distinct_messages:

        timestamp = dm.find("span", class_="chatlog__timestamp")
        timestamp = parse(timestamp.string, fuzzy=True)
        timestamp = datetime.date(timestamp)

        grouped_messages = dm.find_all("div", class_="chatlog__message")

        for msg in grouped_messages:
            # skip loved maps
            if msg.find_all(string=re.compile("gift_heart")):
                continue

            # skip hybrid sets
            if msg.find_all(string=re.compile("\]\[")):
                continue

            content = msg.find("div", class_="chatlog__embed-field-value")

            # extract mapset link and artist - title
            mapset = content.find(href=re.compile("/s/"))
            set_id = int(id_from_url(mapset.get("href")))
            artist, title = extract_artist_title(mapset.string)
            mapsets["set_id"].append(set_id)
            mapsets["date"].append(timestamp)
            mapsets["artist"].append(artist)
            mapsets["title"].append(title)

            # extract set host link and username
            host = content.find(set_host)
            host_id = int(id_from_url(host.get("href")))
            host_name = host.string
            mapsets["host_id"].append(host_id)
            if host_id not in mappers["user_id"]:
                mappers["user_id"].append(host_id)
                mappers["usernames"].append(host_name)

            # extract all nomination/reset events (contains duplicates), but only save one (the last)
            noms = content.find_all(nomination)
            if noms:
                user_id = int(id_from_url(noms[-1].get("href")))
                mapsets["first_nominator"].append(user_id)
                if user_id not in nominators["user_id"]:
                    nominators["user_id"].append(user_id)
                    nominators["usernames"].append(noms[-1].string)
            else:
                mapsets["first_nominator"].append(None)

            qfs = content.find_all(qualification)
            if qfs:
                user_id = int(id_from_url(qfs[-1].get("href")))
                mapsets["second_nominator"].append(user_id)
                if user_id not in nominators["user_id"]:
                    nominators["user_id"].append(user_id)
                    nominators["usernames"].append(qfs[-1].string)
            else:
                mapsets["second_nominator"].append(None)

            pops = content.find_all(nomination_reset)
            if pops:
                user_id = int(id_from_url(pops[-1].get("href")))
                mapsets["nomination_reset"].append(user_id)
                if user_id not in nominators["user_id"]:
                    nominators["user_id"].append(user_id)
                    nominators["usernames"].append(pops[-1].string)
            else:
                mapsets["nomination_reset"].append(None)

            dqs = content.find_all(disqualification)
            if dqs:
                user_id = int(id_from_url(dqs[-1].get("href")))
                mapsets["disqualification"].append(user_id)
                if user_id not in nominators["user_id"]:
                    nominators["user_id"].append(user_id)
                    nominators["usernames"].append(dqs[-1].string)
            else:
                mapsets["disqualification"].append(None)

    mapsets_df = pd.DataFrame(mapsets)
    mappers_df = pd.DataFrame(mappers)
    nominators_df = pd.DataFrame(nominators)

    return {"mapsets": mapsets_df, "mappers": mappers_df, "nominators": nominators_df}


"""
Message structure:
div class="chatlog__messages"

    span class="chatlog__timestamp"

    div class="chatlog__message "
        div class="chatlog__embed-field-value"

    div class="chatlog__message "
        div class="chatlog__embed-field-value"


Message info:
<div class="chatlog__embed-field-value">
 <div class="markdown">
  <a href="https://osu.ppy.sh/s/685558">
   **zts - lastendconductor**
  </a>
  Beatmap by
  <a href="https://osu.ppy.sh/u/4075595">
   Yohanes
  </a>
  [
  <strong>
   osu
  </strong>
  ]
  <a href="https://osu.ppy.sh/forum/p/6487333">
   :thought_balloon:
  </a>
  <a href="https://osu.ppy.sh/u/2849992">
   Garden
  </a>
  <a href="https://osu.ppy.sh/forum/p/6488714">
   :anger_right:
  </a>
  <a href="https://osu.ppy.sh/u/1603923">
   Delis
  </a>
  <a href="https://osu.ppy.sh/forum/p/6620309">
   :thought_balloon:
  </a>
  <a href="https://osu.ppy.sh/u/3376777">
   Kalibe
  </a>
  <a href="https://osu.ppy.sh/forum/p/6621807">
   :heart:
  </a>
  <a href="https://osu.ppy.sh/u/2849992">
   Garden
  </a>
 </div>
</div>
"""
