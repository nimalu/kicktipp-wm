import os
import time

from dotenv import load_dotenv

from kicktipp import KicktippApi, Bet
import tipico
from predictions import best_kicktipp_prediction


def main():
    load_dotenv()

    KICKTIPP_USERNAME = os.getenv("KICKTIPP_USERNAME")
    KICKTIPP_PASSWORD = os.getenv("KICKTIPP_PASSWORD")
    KICKTIPP_COMMUNITY = os.getenv("KICKTIPP_COMMUNITY")

    if not KICKTIPP_USERNAME or not KICKTIPP_PASSWORD or not KICKTIPP_COMMUNITY:
        raise ValueError(
            "Please set KICKTIPP_USERNAME, KICKTIPP_PASSWORD and "
            "KICKTIPP_COMMUNITY in your .env file"
        )

    # 0. login to kicktipp
    kicktipp = KicktippApi(KICKTIPP_USERNAME, KICKTIPP_PASSWORD, KICKTIPP_COMMUNITY)

    # 1. collect bets from kicktipp
    bets = kicktipp.get_bets_all()

    # 2. collect matches from tipico
    matches = tipico.fetch_matches()

    # 3. use tipico quotes to predict the best bet for each match
    submissions = []
    for bet in bets:
        try:
            match = tipico.find_match(matches, bet.home_team, bet.away_team)
        except ValueError:
            print(
                f"Match not found for bet: {bet.home_team} vs {bet.away_team}, skipping..."
            )
            continue

        print(f"{match.team1} vs {match.team2}")
        if match.status != "pre_match":
            print(f"  Match already started or finished, skipping: {match.status}")
            continue

        time.sleep(2)  # be nice to tipico and avoid too many requests in a short time
        quotes = tipico.fetch_quotes(match.id)

        is_knockout = bet.match_day >= 11
        res, expected_score = best_kicktipp_prediction(
            quotes, max_goals=4, knockout=is_knockout
        )
        print(f"  Current bet: {bet.home_goals}:{bet.away_goals}")
        print(f"  Best prediction: {res[0]}:{res[1]}")
        print(f"  Expected score: {expected_score:.2f}")

        if bet.home_goals != res[0] or bet.away_goals != res[1]:
            submissions.append(
                Bet(
                    bet.match_day,
                    bet.match_id,
                    bet.home_team,
                    bet.away_team,
                    res[0],
                    res[1],
                )
            )

    # 4. submit bets to kicktipp
    kicktipp.submit_bets(submissions)


if __name__ == "__main__":
    main()
