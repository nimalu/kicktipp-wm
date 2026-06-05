from collections import namedtuple
from http.cookiejar import MozillaCookieJar
from urllib.parse import parse_qs, urlparse
from pathlib import Path
import time
import mechanicalsoup

Bet = namedtuple("Bet", "match_day match_id home_team away_team home_goals away_goals")


class KicktippApi:
    def __init__(
        self,
        username: str,
        password: str,
        community: str,
        session_path: str | Path | None = None,
    ):
        self.community = community
        self.session_path = (
            Path(session_path)
            if session_path
            else Path(__file__).with_name(".kicktipp_session")
        )
        self.browser = mechanicalsoup.StatefulBrowser()
        self._load_session()
        if not self.is_logged_in():
            self._login(username, password)

    def _load_session(self) -> None:
        cookiejar = MozillaCookieJar(str(self.session_path))
        if self.session_path.exists():
            try:
                cookiejar.load(ignore_discard=True, ignore_expires=True)
            except Exception:
                cookiejar = MozillaCookieJar(str(self.session_path))
        self.browser.set_cookiejar(cookiejar)

    def _save_session(self) -> None:
        cookiejar = self.browser.get_cookiejar()
        if isinstance(cookiejar, MozillaCookieJar):
            cookiejar.save(ignore_discard=True, ignore_expires=True)

    def is_logged_in(self) -> bool:
        self.browser.open("https://www.kicktipp.de/info/profil")
        return (
            self.browser.url is not None
            and "/login" not in self.browser.url
            and not self.browser.page.select('form[action*="login"]')
        )

    def _login(self, username: str, password: str) -> None:
        self.browser.open("https://www.kicktipp.de/info/profil/login")

        # 1. Select the form (usually the only one, or specify a selector like 'form')
        self.browser.select_form('form[action*="login"]')

        # 2. Assign values directly to the browser state
        self.browser["kennung"] = username
        self.browser["passwort"] = password

        # 3. Submit without needing to pass the form object manually
        self.browser.submit_selected()
        self._save_session()

    def _build_bet_url(self, matchday):
        return f"https://www.kicktipp.de/{self.community}/tippabgabe?&spieltagIndex={matchday}"

    def _get_matchdays_from_current_page(self) -> list[int]:
        page = self.browser.page
        if page is None:
            return []

        matchdays = set()
        for link in page.select('a[href*="spieltagIndex="]'):
            href = link.get("href")
            if not href:
                continue

            query = parse_qs(urlparse(href).query)
            for value in query.get("spieltagIndex", []):
                try:
                    matchdays.add(int(value))
                except ValueError:
                    continue

        return sorted(matchdays)

    def get_bets(self, matchday) -> list[Bet]:
        url = self._build_bet_url(matchday)
        self.browser.open(url)

        # Using self.browser.page gets you the BeautifulSoup object of the current page
        page = self.browser.page

        home_teams = [td.text.strip() for td in page.select("tr > td:nth-child(2)")]
        away_teams = [td.text.strip() for td in page.select("tr > td:nth-child(3)")]

        def value_default_0(inp):
            return int(inp.attrs["value"]) if "value" in inp.attrs else 0

        home_bets = [
            value_default_0(inp) for inp in page.select('input[id$="_heimTipp"]')
        ]
        away_bets = [
            value_default_0(inp) for inp in page.select('input[id$="_gastTipp"]')
        ]

        matches = []
        for i in range(len(home_teams)):
            try:
                matches.append(
                    Bet(
                        matchday,
                        i,
                        home_teams[i],
                        away_teams[i],
                        home_bets[i],
                        away_bets[i],
                    )
                )
            except Exception:
                continue
        return matches

    def get_bets_all(self) -> list[Bet]:
        self.browser.open(f"https://www.kicktipp.de/{self.community}/tippabgabe")

        bets = []
        for matchday in self._get_matchdays_from_current_page():
            bets.extend(self.get_bets(matchday))

        return bets

    def submit_bets(self, bets: list[Bet], friendly=True) -> None:
        bets_by_matchday: dict[str, list[Bet]] = {}
        for t in bets:
            match_day = str(t.match_day)
            if match_day not in bets_by_matchday:
                bets_by_matchday[match_day] = []
            bets_by_matchday[match_day].append(t)

        for match_day, matchday_bets in bets_by_matchday.items():
            if friendly:
                # wait a bit between requests
                time.sleep(5)

            self.browser.open(self._build_bet_url(match_day))
            print(f"Submitting bets for matchday {match_day}...")

            # Select the form first
            self.browser.select_form("form")

            page = self.browser.page
            field_home_tips = page.select('input[id$="_heimTipp"]')
            field_away_tips = page.select('input[id$="_gastTipp"]')

            for match in matchday_bets:
                print(
                    f"{match.home_team} vs {match.away_team}: {match.home_goals}:{match.away_goals}"
                )
                home_field = field_home_tips[match.match_id]
                away_field = field_away_tips[match.match_id]

                # Update values via the browser object using the field names
                self.browser[home_field.attrs["name"]] = str(match.home_goals)
                self.browser[away_field.attrs["name"]] = str(match.away_goals)

            # Submit the currently selected form
            self.browser.submit_selected()
