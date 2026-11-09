"""Post-game walkthrough for Chess.com games.

Fetches games from the Chess.com public API, runs Stockfish over every ply,
picks the critical moments for the player, labels the thinking error behind
each one, and writes a Markdown walkthrough (plus JSON for other tools).

Usage:
    python coach/walkthrough.py jakem-r --latest 1
    python coach/walkthrough.py jakem-r --url https://www.chess.com/game/live/185860567340
    python coach/walkthrough.py jakem-r --latest 5 --out reviews/

Needs: python-chess, a `stockfish` binary on PATH.
"""
import argparse, io, json, math, os, re, sys, urllib.request
import chess, chess.engine, chess.pgn

UA = {"User-Agent": "chess-coach-walkthrough"}
VAL = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3, chess.ROOK: 5, chess.QUEEN: 9, chess.KING: 0}


def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
        return json.load(r)


def fetch_games(user, latest=None, url=None):
    archives = get(f"https://api.chess.com/pub/player/{user}/games/archives")["archives"]
    games = []
    for a in reversed(archives):
        games = get(a)["games"] + games
        if url and any(g["url"] == url for g in games):
            return [g for g in games if g["url"] == url]
        if latest and len(games) >= latest:
            break
    games.sort(key=lambda g: g["end_time"])
    return games[-latest:] if latest else []


def winpct(cp):
    return 50 + 50 * (2 / (1 + math.exp(-0.00368208 * cp)) - 1)


def material(board, color):
    return sum(VAL[p.piece_type] for p in board.piece_map().values() if p.color == color)


def is_forcing(board, move):
    return board.is_capture(move) or board.gives_check(move)


def phase(board, ply):
    if ply <= 24:
        return "opening"
    heavy = sum(len(board.pieces(p, c)) * v for p, v in
                [(chess.KNIGHT, 3), (chess.BISHOP, 3), (chess.ROOK, 5), (chess.QUEEN, 9)] for c in chess.COLORS)
    return "endgame" if heavy <= 26 else "middlegame"


def analyse_game(g, user, engine, depth=18):
    game = chess.pgn.read_game(io.StringIO(g["pgn"]))
    me = chess.WHITE if g["white"]["username"].lower() == user.lower() else chess.BLACK
    board = game.board()
    info = engine.analyse(board, chess.engine.Limit(depth=depth))
    plies, prev_clock = [], {chess.WHITE: None, chess.BLACK: None}
    for ply, node in enumerate(game.mainline(), start=1):
        mover, mv = board.turn, node.move
        before = info["score"].pov(chess.WHITE).score(mate_score=10000)
        best_pv = info.get("pv", [])[:8]
        best_san = board.san(best_pv[0]) if best_pv else None
        best_line = board.variation_san(best_pv) if best_pv else ""
        best_forcing = bool(best_pv) and is_forcing(board, best_pv[0])
        fen, san, ph = board.fen(), board.san(mv), phase(board, ply)
        played_forcing = is_forcing(board, mv)
        bal0 = material(board, mover) - material(board, not mover)
        board.push(mv)
        m = re.search(r"\[%clk (\d+):(\d+):([\d.]+)\]", node.comment or "")
        clock = int(m[1]) * 3600 + int(m[2]) * 60 + float(m[3]) if m else None
        spent = None
        if clock is not None:
            start = prev_clock[mover] if prev_clock[mover] is not None else float(g["time_control"].split("+")[0])
            spent = round(start - clock, 1)
            prev_clock[mover] = clock
        if board.is_game_over():
            o = board.outcome()
            after, reply_pv = (0 if o.winner is None else (10000 if o.winner == chess.WHITE else -10000)), []
        else:
            info = engine.analyse(board, chess.engine.Limit(depth=depth))
            after = info["score"].pov(chess.WHITE).score(mate_score=10000)
            reply_pv = info.get("pv", [])[:8]
        sign = 1 if mover == chess.WHITE else -1
        wb, wa = winpct(before * sign), winpct(after * sign)
        reply_san = board.san(reply_pv[0]) if reply_pv else None
        reply_line = board.variation_san(reply_pv) if reply_pv else ""
        tmp = board.copy()
        for x in reply_pv[:6]:
            tmp.push(x)
        mat_swing = (material(tmp, mover) - material(tmp, not mover)) - bal0
        mate_against = info["score"].pov(mover).mate() if not board.is_game_over() and info["score"].is_mate() else None
        plies.append(dict(ply=ply, move_no=(ply + 1) // 2, side="White" if mover == chess.WHITE else "Black",
                          mine=mover == me, san=san, fen=fen, phase=ph, clock=clock, spent=spent,
                          wp_before=round(wb, 1), wp_after=round(wa, 1), drop=round(wb - wa, 1),
                          best=best_san, best_line=best_line, best_forcing=best_forcing, played_forcing=played_forcing,
                          reply=reply_san, reply_line=reply_line, mat_swing=mat_swing,
                          mate_against=mate_against if mate_against is not None and mate_against < 0 else None))
    return dict(url=g["url"], date=game.headers.get("UTCDate"), white=g["white"], black=g["black"],
                me="White" if me == chess.WHITE else "Black", result=game.headers.get("Result"),
                termination=game.headers.get("Termination"), eco=g.get("eco", "").rsplit("/", 1)[-1].replace("-", " "),
                plies=plies)


def label(p):
    """The thinking error behind one of the player's bad moves."""
    if p["mate_against"]:
        return "Allowed a forced mate", "Before every move, look at every check your opponent has after it. One of them mates."
    r = p["reply"] or ""
    if "+" in r or "x" in r:
        kind = "check" if "+" in r else "capture"
        return ("Missed their " + kind,
                f"After {p['san']}, {r} is the reply. Before you let go of the piece, list each check and capture your opponent has.")
    if p["best_forcing"] and not p["played_forcing"]:
        return ("Missed your own forcing move",
                f"{p['best']} was there. When your opponent has just moved, look at your own checks and captures first.")
    if p["phase"] == "endgame":
        return "Endgame technique", f"{p['best']} was the move. In endings, count the moves of any race before you commit."
    return "Quiet move, wrong plan", f"{p['best']} kept the advantage. Ask what your opponent wants to do next before picking a plan."


def moments(a, limit=4):
    mine = [p for p in a["plies"] if p["mine"]]
    plies = a["plies"]
    out = []
    for i, p in enumerate(plies):
        if not p["mine"]:
            continue
        gift = i > 0 and not plies[i - 1]["mine"] and plies[i - 1]["drop"] >= 15
        if p["drop"] >= 10 or (gift and p["drop"] >= 5):
            kind, lesson = label(p)
            if gift and p["drop"] >= 5:
                kind, lesson = "Didn't punish their mistake", f"Your opponent's {plies[i - 1]['move_no']}{'.' if plies[i - 1]['side'] == 'White' else '…'}{plies[i - 1]['san']} was an error. {p['best']} punished it: {p['best_line']}."
            out.append(dict(p, kind=kind, lesson=lesson, gift=gift))
    out.sort(key=lambda m: -m["drop"])
    return sorted(out[:limit], key=lambda m: m["ply"])


def opening_exit(a, move_no=12):
    for p in a["plies"]:
        if p["mine"] and p["move_no"] >= move_no:
            return p["wp_before"]
    return None


def markdown(a, ms):
    opp = a["black"] if a["me"] == "White" else a["white"]
    me = a["white"] if a["me"] == "White" else a["black"]
    lines = [f"# {a['date']} · {a['me']} vs {opp['username']} ({opp['rating']})", "",
             f"{a['eco']}. {a['termination']}. Your rating after: {me['rating']}.", f"[Game on Chess.com]({a['url']})", ""]
    ex = opening_exit(a)
    if ex is not None:
        lines += [f"**Out of the opening (move 12):** {ex:.0f}% winning chance.", ""]
    peak = max((p["wp_before"] for p in a["plies"] if p["mine"]), default=50)
    lines += [f"**Best point in the game:** {peak:.0f}%.", ""]
    for n, m in enumerate(ms, 1):
        dots = "." if m["side"] == "White" else "…"
        t = f", {m['spent']:.0f}s on the move, {int(m['clock'] // 60)}:{int(m['clock'] % 60):02d} left" if m["clock"] is not None and m["spent"] is not None else ""
        lines += [f"## {n}. {m['move_no']}{dots}{m['san']} · {m['kind']}", "",
                  f"Winning chance {m['wp_before']:.0f}% → {m['wp_after']:.0f}% ({m['phase']}{t}).", "",
                  f"- Better: **{m['best']}**. Line: {m['best_line']}",
                  f"- After your move: {m['reply_line']}" if m["reply_line"] else "",
                  f"- FEN: `{m['fen']}`", "", m["lesson"], ""]
    lines += ["## Before the next game", "",
              "Set up each position above and find the better move without the engine. Then write one sentence on what you missed."]
    return "\n".join(x for x in lines if x is not None)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("user")
    ap.add_argument("--latest", type=int)
    ap.add_argument("--url")
    ap.add_argument("--depth", type=int, default=18)
    ap.add_argument("--out", default="reviews")
    args = ap.parse_args()
    if not (args.latest or args.url):
        args.latest = 1
    games = fetch_games(args.user, args.latest, args.url)
    if not games:
        sys.exit("No games found.")
    os.makedirs(args.out, exist_ok=True)
    engine = chess.engine.SimpleEngine.popen_uci("stockfish")
    try:
        for g in games:
            a = analyse_game(g, args.user, engine, args.depth)
            ms = moments(a)
            stem = os.path.join(args.out, f"{a['date'].replace('.', '-')}_{g['url'].rsplit('/', 1)[-1]}")
            json.dump(dict(a, moments=ms), open(stem + ".json", "w"), indent=1)
            open(stem + ".md", "w").write(markdown(a, ms))
            print(stem + ".md")
    finally:
        engine.quit()


if __name__ == "__main__":
    main()
