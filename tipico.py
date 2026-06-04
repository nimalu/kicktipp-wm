from util import fetch_with_cache
import json
import requests

from collections import namedtuple

Match = namedtuple("Match", "id team1 team2 status eventStartTime")


def _fetch_requests(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    response = requests.get(url, headers=headers)
    return response.text


def fetch_matches() -> list[Match]:
    url = "https://sports.tipico.de/v1/tpapi/programgateway/program/events/selectedEvents/all/1710510?maxMarkets=1&competitionSort=TURNOVER&groupOutrightsByTeam=true&language=de&flattenNonOutrights=true"
    json_raw = fetch_with_cache(url, _fetch_requests)
    data = json.loads(json_raw)
    events: dict = data["SELECTION"]["events"]

    matches = []
    for event in events.values():
        if event["type"] != "live":
            continue

        matches.append(
            Match(
                id=event["id"],
                team1=event["team1"],
                team2=event["team2"],
                status=event["status"],
                eventStartTime=event["eventStartTime"],
            )
        )

    return matches


def fetch_quotes(match_id: str) -> dict[str, float]:
    url = f"https://sports.tipico.de/v1/tpapi/programgateway/program/events/{match_id}"
    data = fetch_with_cache(url, _fetch_requests)
    data = json.loads(data)
    point_bet_id = next(
        (
            group["id"]
            for group in data["oddGroups"].values()
            if group["type"] == "point-bet"
        )
    )
    odd_ids = data["oddGroupResultsMap"][str(point_bet_id)]

    quotes = {}
    for odd_id in odd_ids:
        result = data["results"][str(odd_id)]
        if "X" in result["caption"]:
            continue
        quotes[result["caption"]] = result["quoteFloatValue"]

    return quotes


def find_match(matches: list[Match], team1: str, team2: str) -> Match:
    overwrites = {
        "Bosnien-Herzegowina": "Bosnien & Herzegowina",
        "Curaçao": "Curacao",
        "Saudi-Arabien": "Saudi Arabien",
    }
    if team1 in overwrites:
        team1 = overwrites[team1]
    if team2 in overwrites:
        team2 = overwrites[team2]

    for match in matches:
        if (match.team1 == team1 and match.team2 == team2) or (
            match.team1 == team2 and match.team2 == team1
        ):
            return match

    raise ValueError(f"Match not found for teams: {team1} vs {team2}")
