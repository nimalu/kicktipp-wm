from dataclasses import dataclass
from urllib.parse import parse_qs, urlparse
from pathlib import Path
import requests
import pickle
import bs4


@dataclass
class Bet:
    id: str
    time: str
    home_team: str
    away_team: str
    home_goals: int
    away_goals: int
    knockout: bool = False


class Session(requests.Session):
    def __init__(self):
        super().__init__()

    def save(self, session_path: str | Path) -> None:
        with open(session_path, "wb") as f:
            pickle.dump(self.cookies, f)

    def load(self, session_path: str | Path) -> None:
        with open(session_path, "rb") as f:
            cookies = pickle.load(f)
            self.cookies.update(cookies)


class KicktippApi:
    def __init__(self, session: Session | None = None):
        self.session = session or Session()

    def get_and_raise(self, url: str) -> requests.Response:
        res = self.session.get(url)
        if res.status_code != 200:
            raise ValueError("Request failed with status code: " + str(res.status_code))
        return res

    def is_logged_in(self) -> bool:
        res = self.session.get("https://www.kicktipp.de/info/profil")
        return "login" not in res.url

    def login(self, username: str, password: str) -> None:
        url = "https://www.kicktipp.de/info/profil/loginaction"
        data = {
            "kennung": username,
            "passwort": password,
        }
        res = self.session.post(url, data=data)
        if res.status_code != 200:
            raise ValueError("Login failed with status code: " + str(res.status_code))

    def open_league(self, league_id: str) -> None:
        res = self.get_and_raise(f"https://www.kicktipp.de/{league_id}/tippabgabe?")
        soup = bs4.BeautifulSoup(res.text, "html.parser")

        self.tipper_id = soup.find("input", {"name": "tipperId"})["value"]
        self.saison_id = soup.find("input", {"name": "tippsaisonId"})["value"]
        self.league_id = league_id

    def get_scoring_rules(self) -> dict:
        res = self.get_and_raise(
            f"https://www.kicktipp.de/{self.league_id}/spielregeln"
        )
        soup = bs4.BeautifulSoup(res.text, "html.parser")

        ktable = soup.find("table", class_="ktable")
        if not ktable:
            raise ValueError("Failed to find scoring rules table")

        tds = ktable.find_all("td")
        return {
            "win_tendency": int(tds[1].text),
            "win_goal_diff": int(tds[2].text),
            "win_exact": int(tds[3].text),
            "draw_tendency": int(tds[5].text),
            "draw_exact": int(tds[7].text),
        }

    def get_matchdays(self):
        res = self.get_and_raise(f"https://www.kicktipp.de/{self.league_id}/tippabgabe")
        soup = bs4.BeautifulSoup(res.text, "html.parser")

        matchday_anchors = soup.select(".spieltagsauswahl .dropdownoverlay a")
        ids: list[str] = []
        for anchor in matchday_anchors:
            href = anchor["href"]
            parsed_url = urlparse(href)
            query_params = parse_qs(parsed_url.query)
            id = query_params.get("spieltagIndex", [None])[0]
            if id and id not in ids:
                ids.append(id)
        return ids

    def get_bets(self, matchday_id: str):
        res = self.get_and_raise(
            f"https://www.kicktipp.de/{self.league_id}/tippabgabe?spieltagIndex={matchday_id}"
        )
        soup = bs4.BeautifulSoup(res.text, "html.parser")

        bet_table = soup.select_one("table#tippabgabeSpiele")

        bets: list[Bet] = []
        for datarow in bet_table.select("tbody tr"):
            tds = datarow.find_all("td")
            time = tds[0].text.strip()
            home_team = tds[1].text.strip()
            away_team = tds[2].text.strip()
            goals = tds[3]
            try:
                home_goals = goals.find(
                    "input", id=lambda x: x and x.endswith("_heimTipp")
                )["value"]
                home_goals = int(home_goals) if home_goals.isdigit() else 0
            except Exception:
                home_goals = 0
            try:
                away_goals = goals.find(
                    "input", id=lambda x: x and x.endswith("_gastTipp")
                )["value"]
                away_goals = int(away_goals) if away_goals.isdigit() else 0
            except Exception:
                away_goals = 0
            
            try:
                knockout = "n.E." in goals.text
            except Exception:
                knockout = False

            first_input = goals.find("input")
            id = first_input["id"].split("_")[1]

            bets.append(Bet(id, time, home_team, away_team, home_goals, away_goals, knockout))

        return bets

    def submit_bets(self, bets: list[Bet], matchday_id: str):
        if not bets:
            raise ValueError("No bets provided")

        payload: dict = {}
        payload["tipperId"] = self.tipper_id
        payload["spieltagIndex"] = matchday_id
        payload["tippsaisonId"] = self.saison_id

        for b in bets:
            payload[f"spieltippForms[{b.id}].tippAbgegeben"] = "true"
            payload[f"spieltippForms[{b.id}].heimTipp"] = str(b.home_goals)
            payload[f"spieltippForms[{b.id}].gastTipp"] = str(b.away_goals)

        res = self.session.post(
            f"https://www.kicktipp.de/{self.league_id}/tippabgabe", data=payload
        )
        if res.status_code not in (200, 302):
            raise ValueError(
                f"Submitting bets failed with status code: {res.status_code}"
            )

        return res
