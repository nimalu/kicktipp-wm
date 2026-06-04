from collections import namedtuple
import mechanicalsoup

Bet = namedtuple("Bet", "match_day match_id home_team away_team home_goals away_goals")


class KicktippApi:
    def __init__(self):
        self.browser = mechanicalsoup.StatefulBrowser()

    def login(self, username: str, password: str) -> None:
        self.browser.open("https://www.kicktipp.de/info/profil/login")

        # 1. Select the form (usually the only one, or specify a selector like 'form')
        self.browser.select_form('form[action*="login"]')

        # 2. Assign values directly to the browser state
        self.browser["kennung"] = username
        self.browser["passwort"] = password

        # 3. Submit without needing to pass the form object manually
        self.browser.submit_selected()

    def _build_bet_url(self, community, matchday):
        return (
            f"https://www.kicktipp.de/{community}/tippabgabe?&spieltagIndex={matchday}"
        )

    def get_bets(self, community, matchday) -> list[Bet]:
        url = self._build_bet_url(community, matchday)
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

    def submit_bets(self, community: str, bets: list[Bet]) -> None:
        bets_by_matchday: dict[str, list[Bet]] = {}
        for t in bets:
            match_day = str(t.match_day)
            if match_day not in bets_by_matchday:
                bets_by_matchday[match_day] = []
            bets_by_matchday[match_day].append(t)

        for match_day, matchday_bets in bets_by_matchday.items():
            self.browser.open(self._build_bet_url(community, match_day))

            # Select the form first
            self.browser.select_form("form")

            page = self.browser.page
            field_home_tips = page.select('input[id$="_heimTipp"]')
            field_away_tips = page.select('input[id$="_gastTipp"]')

            for match in matchday_bets:
                home_field = field_home_tips[match.match_id]
                away_field = field_away_tips[match.match_id]

                # Update values via the browser object using the field names
                self.browser[home_field.attrs["name"]] = str(match.home_goals)
                self.browser[away_field.attrs["name"]] = str(match.away_goals)

            # Submit the currently selected form
            self.browser.submit_selected()
