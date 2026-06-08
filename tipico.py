from dataclasses import dataclass

import json
import requests


@dataclass
class Match:
    id: str
    team1: str
    team2: str
    status: str
    eventStartTime: int


def _fetch_requests(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    }
    response = requests.get(url, headers=headers)
    return response.text


def fetch_matches() -> list[Match]:
    url = "https://sports.tipico.de/v1/tpapi/programgateway/program/events/selectedEvents/all/1710510?maxMarkets=1&competitionSort=TURNOVER&groupOutrightsByTeam=true&language=de&flattenNonOutrights=true"
    data = json.loads(_fetch_requests(url))
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
    data = _fetch_requests(url)
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
