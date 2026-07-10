from __future__ import annotations

from jungle.domain import BLUE_TRAPS, GameState, Piece, PieceType, Position, Side


def make_state(pieces: dict[int, Piece], side_to_move: Side = Side.BLUE) -> GameState:
    board = [None] * 63
    for index, piece in pieces.items():
        board[index] = piece
    return GameState(board=board, side_to_move=side_to_move)


def full_options():
    from jungle.ai.evaluation import EvaluationOptions

    return EvaluationOptions(
        full=True,
        threat_weight=1,
        use_den_safety=True,
        use_den_race=True,
        repetition_penalty=320,
    )


def test_evaluation_is_antisymmetric() -> None:
    from jungle.ai.evaluation import evaluate_state

    state = make_state(
        {
            Position(6, 0).index: Piece(Side.BLUE, PieceType.CAT),
            Position(2, 6).index: Piece(Side.RED, PieceType.CAT),
            Position(6, 6).index: Piece(Side.BLUE, PieceType.RAT),
            Position(2, 0).index: Piece(Side.RED, PieceType.RAT),
        }
    )

    assert evaluate_state(state, Side.BLUE, full_options()) == -evaluate_state(state, Side.RED, full_options())


def test_evaluation_rewards_material_advantage() -> None:
    from jungle.ai.evaluation import evaluate_state

    state = make_state(
        {
            Position(6, 0).index: Piece(Side.BLUE, PieceType.ELEPHANT),
            Position(2, 6).index: Piece(Side.RED, PieceType.CAT),
        }
    )

    assert evaluate_state(state, Side.BLUE, full_options()) > 0


def test_evaluation_recognizes_enemy_piece_weakened_in_own_trap() -> None:
    from jungle.ai.evaluation import PIECE_VALUES, effective_material_value

    trap = next(iter(BLUE_TRAPS))
    elephant = Piece(Side.RED, PieceType.ELEPHANT)
    trapped = make_state({trap: elephant, Position(6, 0).index: Piece(Side.BLUE, PieceType.CAT)})

    assert effective_material_value(trapped, trap, elephant) < PIECE_VALUES[PieceType.ELEPHANT]


def test_evaluation_penalizes_an_enemy_close_to_own_den() -> None:
    from jungle.ai.evaluation import evaluate_state

    threatened = make_state(
        {
            Position(6, 0).index: Piece(Side.BLUE, PieceType.CAT),
            Position(7, 3).index: Piece(Side.RED, PieceType.DOG),
        }
    )
    distant = make_state(
        {
            Position(6, 0).index: Piece(Side.BLUE, PieceType.CAT),
            Position(2, 6).index: Piece(Side.RED, PieceType.DOG),
        }
    )

    assert evaluate_state(threatened, Side.BLUE, full_options()) < evaluate_state(distant, Side.BLUE, full_options())


def test_evaluation_rewards_rat_pressure_on_elephant() -> None:
    from jungle.ai.evaluation import evaluate_state

    attacking = make_state(
        {
            Position(2, 0).index: Piece(Side.BLUE, PieceType.RAT),
            Position(2, 1).index: Piece(Side.RED, PieceType.ELEPHANT),
            Position(8, 6).index: Piece(Side.RED, PieceType.CAT),
        }
    )
    distant = make_state(
        {
            Position(6, 0).index: Piece(Side.BLUE, PieceType.RAT),
            Position(2, 1).index: Piece(Side.RED, PieceType.ELEPHANT),
            Position(8, 6).index: Piece(Side.RED, PieceType.CAT),
        }
    )

    assert evaluate_state(attacking, Side.BLUE, full_options()) > evaluate_state(distant, Side.BLUE, full_options())
