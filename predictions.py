import numpy as np


def quotes_to_probs(quotes: dict[str, float]) -> dict[str, float]:
    implied_probs = {res: 1 / quote for res, quote in quotes.items()}
    total = sum(implied_probs.values())
    return {k: v / total for k, v in implied_probs.items()}


def probs_dict_to_matrix(probs: dict[str, float], max_goals=4) -> np.ndarray:
    matrix = np.zeros((max_goals + 1, max_goals + 1))
    for res, quote in probs.items():
        home, away = map(int, res.split(":"))
        if home <= max_goals and away <= max_goals:
            matrix[home, away] = quote
    return matrix


def kicktipp_scoring_rule(scoreline_actual, scoreline_pred):
    home_goals, away_goals = scoreline_actual
    pred_home, pred_away = scoreline_pred
    if home_goals == away_goals:
        # draw
        if pred_home == home_goals and pred_away == away_goals:
            return 4
        elif (pred_home - pred_away) == 0:
            return 2
        else:
            return 0
    else:
        # not a draw
        if pred_home == home_goals and pred_away == away_goals:
            return 4
        elif (pred_home - pred_away) == (home_goals - away_goals):
            return 3
        elif (pred_home > pred_away) == (home_goals > away_goals):
            return 2
        else:
            return 0


def generate_kicktipp_score_matrix(scoreline, max_goals=4):
    """Generate score matrix for a specific predicted scoreline."""
    scores = []
    for hg in range(max_goals + 1):
        for ag in range(max_goals + 1):
            scores.append(kicktipp_scoring_rule(scoreline, (hg, ag)))
    return np.array(scores).reshape((max_goals + 1, max_goals + 1))


def generate_kicktipp_score_matrices(max_goals=4):
    """Generate score matrices for all possible predictions."""
    matrices = []
    for hg in range(max_goals + 1):
        for ag in range(max_goals + 1):
            matrices.append(
                generate_kicktipp_score_matrix((hg, ag), max_goals=max_goals)
            )
    return np.array(matrices).reshape(
        max_goals + 1, max_goals + 1, max_goals + 1, max_goals + 1
    )


def expected_kicktipp_scores(probs: np.ndarray, score_matrices: np.ndarray):
    """Calculate expected scores for all predictions given the probabilities."""
    expected_scores = np.tensordot(probs, score_matrices, axes=([0, 1], [0, 1]))
    return expected_scores


def best_kicktipp_prediction(quotes: dict[str, float], max_goals=4, knockout=False):
    probs = quotes_to_probs(quotes)

    if knockout:
        # In knockout stages, draws are not possible, so we set their probabilities to zero
        for res in list(probs.keys()):
            if res.split(":")[0] == res.split(":")[1]:  # draw result
                probs[res] = 0

    probs = probs_dict_to_matrix(probs, max_goals=max_goals)

    score_matrices = generate_kicktipp_score_matrices(max_goals=max_goals)
    expected_scores = expected_kicktipp_scores(probs, score_matrices)
    best_idx = np.unravel_index(np.argmax(expected_scores), expected_scores.shape)
    return (int(best_idx[0]), int(best_idx[1])), expected_scores[best_idx]
