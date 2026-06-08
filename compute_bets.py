import functools
import os
import time

from dotenv import load_dotenv

from kicktipp import KicktippApi, Bet, Session
import tipico
from predictions import best_kicktipp_prediction


def prepare_session(username: str, password: str) -> Session:
    session = Session()
    if os.path.exists(".kicktipp_session"):
        session.load(".kicktipp_session")

    api = KicktippApi(session)
    if not api.is_logged_in():
        api.login(username, password)
        session.save(".kicktipp_session")

    return session


def find_tipico_match(
    home_team: str, away_team: str, tipico_matches: list[tipico.Match]
) -> tipico.Match:
    overwrites = {
        "Bosnien-Herzegowina": "Bosnien & Herzegowina",
        "Curaçao": "Curacao",
        "Saudi-Arabien": "Saudi Arabien",
    }
    if home_team in overwrites:
        home_team = overwrites[home_team]
    if away_team in overwrites:
        away_team = overwrites[away_team]

    for match in tipico_matches:
        if match.team1 == home_team and match.team2 == away_team:
            return match

    raise ValueError(f"No tipico match found for {home_team} vs {away_team}")


@functools.cache
def fetch_quotes_cached(match_id: str):
    sleep_time = 2
    for i in range(5):
        try:
            time.sleep(sleep_time)
            return tipico.fetch_quotes(match_id)
        except Exception as e:
            print(f"Error fetching quotes for match {match_id}: {e}")
            if i < 4:
                print(f"Retrying in {sleep_time} seconds...")
                time.sleep(sleep_time)
                sleep_time ^= 2
            else:
                print(f"Failed to fetch quotes for match {match_id} after 5 attempts.")
                return {}
    try:
        return tipico.fetch_quotes(match_id)
    except Exception as e:
        print(f"Error fetching quotes for match {match_id}: {e}")
        return {}


def load_params():
    load_dotenv()
    KICKTIPP_USERNAME = os.getenv("KICKTIPP_USERNAME")
    KICKTIPP_PASSWORD = os.getenv("KICKTIPP_PASSWORD")
    KICKTIPP_COMMUNITIES = os.getenv("KICKTIPP_COMMUNITIES")

    if not KICKTIPP_USERNAME or not KICKTIPP_PASSWORD or not KICKTIPP_COMMUNITIES:
        raise ValueError(
            "Please set KICKTIPP_USERNAME, KICKTIPP_PASSWORD and "
            "KICKTIPP_COMMUNITIES in your .env file"
        )
    return KICKTIPP_USERNAME, KICKTIPP_PASSWORD, KICKTIPP_COMMUNITIES


def is_past(bet: Bet) -> bool:
    try:
        time_struct = time.strptime(bet.time, "%d.%m.%y %H:%M")
        return time.mktime(time_struct) < time.time()
    except Exception:
        print(f"Error parsing time for bet {bet}")
        return False


def main():
    kicktipp_username, kicktipp_password, communities = load_params()

    tipico_matches = tipico.fetch_matches()

    session = prepare_session(kicktipp_username, kicktipp_password)
    api = KicktippApi(session)

    for community in communities.split(","):
        print(f"Processing community: {community.strip()}")
        api.open_league(community.strip())
        scoring_rules = api.get_scoring_rules()

        for matchday in api.get_matchdays():
            print(f"Processing matchday: {matchday}")
            bets = api.get_bets(matchday)
            changed_bets = []

            for bet in bets:
                print(f"Processing bet: {bet.home_team} vs {bet.away_team}")
                print(f"  Bef.: {bet.home_goals}:{bet.away_goals}")
                if is_past(bet):
                    print(f"  Skipping passed bet ({bet.time})")
                    continue

                try:
                    tipico_match = find_tipico_match(
                        bet.home_team, bet.away_team, tipico_matches
                    )
                except ValueError as e:
                    print(f"  {e}")
                    continue

                quotes = fetch_quotes_cached(tipico_match.id)

                (home_goals, away_goals), exp_points = best_kicktipp_prediction(
                    quotes, scoring_rules=scoring_rules, knockout=bet.knockout
                )
                print(
                    f"  Pred: {home_goals}:{away_goals} (expected points: {exp_points:.2f})"
                )
                if (home_goals, away_goals) != (bet.home_goals, bet.away_goals):
                    bet.home_goals = home_goals
                    bet.away_goals = away_goals
                    changed_bets.append(bet)

            if changed_bets:
                print(
                    f"Submitting {len(changed_bets)} changed bets for matchday {matchday}..."
                )
                api.submit_bets(changed_bets, matchday)


if __name__ == "__main__":
    main()
