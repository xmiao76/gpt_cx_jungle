from __future__ import annotations

import random

from jungle.ai.core import (
    BLUE,
    EMPTY,
    LION,
    NO_SIDE,
    RED,
    TIGER,
    CompactPosition,
    RIVER_JUMPS,
    ZOBRIST_SIDE,
    compact_piece,
    compact_side,
    encode_piece,
    move_captured,
    move_destination,
    move_is_jump,
    move_origin,
    pack_move,
    piece_kind,
    piece_side,
    unpack_move,
)
from jungle.domain import (
    RED_DEN,
    BOARD_SIZE,
    GameState,
    Piece,
    PieceType,
    Position,
    Side,
    initial_state,
)
from jungle.engine import Game
from jungle.rules import evaluate_result, legal_moves


def make_state(pieces: dict[int, Piece], side_to_move: Side = Side.BLUE) -> GameState:
    board = [None] * BOARD_SIZE
    for square, piece in pieces.items():
        board[square] = piece
    return GameState(board=board, side_to_move=side_to_move)


def snapshot(position: CompactPosition) -> tuple[object, ...]:
    return (
        position.board.copy(),
        position.piece_squares.copy(),
        position.piece_counts.copy(),
        position.side_counts.copy(),
        position.side_to_move,
        position.total_piece_count,
        position.winner,
        position.zobrist_hash,
    )


def assert_matches_game_state(position: CompactPosition, state: GameState) -> None:
    expected_board = [EMPTY if piece is None else compact_piece(piece) for piece in state.board]
    assert position.board == expected_board
    assert position.side_to_move == compact_side(state.side_to_move)
    assert position.total_piece_count == sum(piece is not None for piece in state.board)
    assert position.zobrist_hash == position.recompute_zobrist()
    position.assert_consistent()


def test_piece_and_move_integer_encodings_round_trip() -> None:
    for side in (BLUE, RED):
        for kind in PieceType:
            code = encode_piece(side, kind)
            assert piece_side(code) == side
            assert piece_kind(code) == int(kind)

    move = pack_move(62, 0, encode_piece(RED, PieceType.ELEPHANT), is_jump=True)
    assert move_origin(move) == 62
    assert move_destination(move) == 0
    assert move_captured(move) == encode_piece(RED, PieceType.ELEPHANT)
    assert move_is_jump(move)
    assert unpack_move(move) == (62, 0, encode_piece(RED, PieceType.ELEPHANT), True)


def test_initial_position_conversion_tracks_board_counts_bitboards_and_hash() -> None:
    state = initial_state()
    position = CompactPosition.from_game_state(state)

    assert_matches_game_state(position, state)
    assert position.side_counts == [8, 8]
    assert position.total_piece_count == 16
    assert position.winner == NO_SIDE
    for side in (BLUE, RED):
        for kind in PieceType:
            code = encode_piece(side, kind)
            assert position.piece_counts[code] == 1
            assert position.piece_squares[code].bit_count() == 1

    red_to_move = state.copy()
    red_to_move.side_to_move = Side.RED
    red_position = CompactPosition.from_game_state(red_to_move)
    assert position.zobrist_hash ^ red_position.zobrist_hash == ZOBRIST_SIDE
    assert CompactPosition.from_game_state(state).zobrist_hash == position.zobrist_hash


def test_piece_bitboards_support_duplicate_types_in_synthetic_positions() -> None:
    state = make_state(
        {
            Position(6, 0).index: Piece(Side.BLUE, PieceType.CAT),
            Position(6, 2).index: Piece(Side.BLUE, PieceType.CAT),
            Position(2, 0).index: Piece(Side.RED, PieceType.RAT),
        }
    )
    position = CompactPosition.from_game_state(state)
    blue_cat = encode_piece(BLUE, PieceType.CAT)

    assert position.piece_counts[blue_cat] == 2
    assert position.piece_squares[blue_cat] == (
        (1 << Position(6, 0).index) | (1 << Position(6, 2).index)
    )
    assert_matches_game_state(position, state)


def test_precomputed_jumps_match_explicit_lion_and_tiger_rules() -> None:
    vertical_origin = Position(2, 1).index
    vertical_landing = Position(6, 1).index
    horizontal_origin = Position(3, 0).index
    horizontal_landing = Position(3, 3).index

    vertical = next(jump for jump in RIVER_JUMPS[vertical_origin] if jump.destination == vertical_landing)
    horizontal = next(jump for jump in RIVER_JUMPS[horizontal_origin] if jump.destination == horizontal_landing)
    assert not vertical.tiger_allowed
    assert vertical.path_mask.bit_count() == 3
    assert horizontal.tiger_allowed
    assert horizontal.path_mask.bit_count() == 2

    pieces = {
        vertical_origin: Piece(Side.BLUE, PieceType.LION),
        horizontal_origin: Piece(Side.BLUE, PieceType.TIGER),
        Position(0, 6).index: Piece(Side.RED, PieceType.CAT),
    }
    state = make_state(pieces)
    position = CompactPosition.from_game_state(state)
    assert position.to_public_move(
        next(
            move
            for move in position.generate_moves()
            if move_origin(move) == vertical_origin and move_destination(move) == vertical_landing
        )
    ) in legal_moves(state)
    assert position.to_public_move(
        next(
            move
            for move in position.generate_moves()
            if move_origin(move) == horizontal_origin and move_destination(move) == horizontal_landing
        )
    ) in legal_moves(state)

    tiger_vertical_state = make_state(
        {
            vertical_origin: Piece(Side.BLUE, PieceType.TIGER),
            Position(0, 6).index: Piece(Side.RED, PieceType.CAT),
        }
    )
    tiger_vertical = CompactPosition.from_game_state(tiger_vertical_state)
    assert not any(
        move_destination(move) == vertical_landing for move in tiger_vertical.generate_moves()
    )

    blocked_state = make_state(
        {
            vertical_origin: Piece(Side.BLUE, PieceType.LION),
            Position(4, 1).index: Piece(Side.RED, PieceType.RAT),
        }
    )
    blocked = CompactPosition.from_game_state(blocked_state)
    assert not any(move_destination(move) == vertical_landing for move in blocked.generate_moves())


def test_move_generation_for_either_side_does_not_mutate_position() -> None:
    state = initial_state()
    position = CompactPosition.from_game_state(state)
    before = snapshot(position)

    for side, public in ((BLUE, Side.BLUE), (RED, Side.RED)):
        comparison = state.copy()
        comparison.side_to_move = public
        expected = legal_moves(comparison)
        actual = [position.to_public_move(move) for move in position.generate_moves_for(side)]
        assert actual == expected
        assert snapshot(position) == before


def test_make_unmake_restores_capture_counts_winner_and_incremental_hash() -> None:
    blue_cat = Piece(Side.BLUE, PieceType.CAT)
    red_rat = Piece(Side.RED, PieceType.RAT)
    capture_state = make_state(
        {
            Position(2, 0).index: blue_cat,
            Position(2, 1).index: red_rat,
        }
    )
    position = CompactPosition.from_game_state(capture_state)
    move = next(move for move in position.generate_moves() if move_destination(move) == Position(2, 1).index)
    before = snapshot(position)

    undo = position.make_move(move)

    assert position.winner == BLUE
    assert position.side_to_move == RED
    assert position.side_counts == [1, 0]
    assert position.total_piece_count == 1
    assert position.zobrist_hash == position.recompute_zobrist()
    position.assert_consistent()

    position.unmake_move(move, undo)
    assert snapshot(position) == before
    position.assert_consistent()

    den_state = make_state(
        {
            Position(1, 3).index: blue_cat,
            Position(8, 6).index: red_rat,
        }
    )
    den_position = CompactPosition.from_game_state(den_state)
    den_move = next(
        move for move in den_position.generate_moves() if move_destination(move) == Position(0, 3).index
    )
    den_before = snapshot(den_position)
    den_undo = den_position.make_move(den_move)
    assert den_position.winner == BLUE
    assert den_position.generate_moves() == []
    den_position.unmake_move(den_move, den_undo)
    assert snapshot(den_position) == den_before


def test_terminal_detection_includes_no_legal_moves() -> None:
    # This intentionally synthetic full board mirrors the search regression
    # fixture: the lone red rat in its own den cannot be captured by elephants.
    board = [Piece(Side.BLUE, PieceType.ELEPHANT) for _ in range(BOARD_SIZE)]
    board[RED_DEN] = Piece(Side.RED, PieceType.RAT)
    state = GameState(board=board, side_to_move=Side.BLUE)
    position = CompactPosition.from_game_state(state)

    assert legal_moves(state) == []
    assert position.generate_moves() == []
    assert position.terminal_winner() == RED
    assert evaluate_result(state).winner is Side.RED


def test_random_reachable_positions_match_rules_and_restore_exactly() -> None:
    rng = random.Random(0xC0DEC0DE)
    checked_positions = 0

    for _ in range(10):
        game = Game()
        position = CompactPosition.from_game_state(game.state)
        for _ply in range(50):
            expected_moves = legal_moves(game.state)
            packed_moves = position.generate_moves()
            converted_moves = [position.to_public_move(move) for move in packed_moves]

            # Ordering parity is useful to deterministic search as well as set parity.
            assert converted_moves == expected_moves
            assert_matches_game_state(position, game.state)
            checked_positions += 1
            if not expected_moves:
                assert position.terminal_winner(packed_moves) == compact_side(game.state.side_to_move.opponent)
                break

            selected_index = rng.randrange(len(expected_moves))
            public_move = expected_moves[selected_index]
            packed_move = packed_moves[selected_index]
            before = snapshot(position)

            undo = position.make_move(packed_move)
            assert position.zobrist_hash == position.recompute_zobrist()
            position.assert_consistent()
            position.unmake_move(packed_move, undo)
            assert snapshot(position) == before

            position.make_move(packed_move)
            game.apply_move(public_move)
            assert_matches_game_state(position, game.state)
            if game.state.winner is not None:
                assert position.terminal_winner() == compact_side(game.state.winner)
                break

    assert checked_positions >= 100
