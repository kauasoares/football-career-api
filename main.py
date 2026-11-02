"""Football Career API — modo carreira (técnico ou jogador) com partidas simuladas.

FastAPI + SQLite. Cada carreira tem o seu próprio "mundo": clubes, jogadores,
calendário, resultados e estatísticas.
"""
import math
import os
import random
import sqlite3
from contextlib import asynccontextmanager, contextmanager
from typing import Literal

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

DB_PATH = os.getenv("DB_PATH", "data/career.db")

Position = Literal["GK", "DEF", "MID", "ATT"]
Formation = Literal["4-4-2", "4-3-3", "3-5-2"]
Tactic = Literal["BALANCED", "ATTACK", "DEFENSE"]

FORMATIONS = {"4-4-2": (4, 4, 2), "4-3-3": (4, 3, 3), "3-5-2": (3, 5, 2)}  # DEF, MID, ATT
SQUAD_PLAN = {"GK": 2, "DEF": 6, "MID": 6, "ATT": 4}  # elenco inicial de 18
MIN_POS = {"GK": 1, "DEF": 4, "MID": 5, "ATT": 3}  # mínimo que preserva as três formações
MIN_SQUAD, MAX_SQUAD = 16, 25
TOTAL_ROUNDS = 14  # 8 clubes, turno e returno
MID_WINDOW_ROUND = 8  # janela de meio de temporada
FIRE_LIMIT = 15  # confiança da diretoria que leva à demissão

CLUBS = [
    ("Tigres do ABC", "Santo André", 74),
    ("Leões Paulistas", "São Paulo", 72),
    ("Águias do Sul", "Porto Alegre", 69),
    ("Tubarões FC", "Santos", 67),
    ("Dragões United", "Curitiba", 64),
    ("Falcões da Serra", "Belo Horizonte", 62),
    ("Lobos do Cerrado", "Brasília", 60),
    ("Fênix Carioca", "Rio de Janeiro", 58),
]
FIRST = ["Lucas", "Mateus", "Rafael", "Bruno", "Diego", "Caio", "Thiago", "Vitor", "Gabriel", "Felipe",
         "Pedro", "Henrique", "Leandro", "Rodrigo", "André", "Marcelo", "Fábio", "Igor", "Renan", "Davi"]
LAST = ["Silva", "Souza", "Costa", "Lima", "Rocha", "Alves", "Dias", "Melo", "Ramos", "Nunes",
        "Barros", "Freitas", "Teixeira", "Moreira", "Campos", "Pinto", "Araújo", "Cardoso", "Gomes", "Lopes"]

SCHEMA = """
CREATE TABLE IF NOT EXISTS careers (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    name             TEXT NOT NULL,
    mode             TEXT NOT NULL CHECK (mode IN ('MANAGER','PLAYER')),
    status           TEXT NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE','FIRED','RETIRED')),
    season           INTEGER NOT NULL DEFAULT 1,
    round            INTEGER NOT NULL DEFAULT 1,
    user_team_id     INTEGER,
    user_player_id   INTEGER,
    board_confidence INTEGER NOT NULL DEFAULT 60,
    target_position  INTEGER,
    created_at       TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS teams (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    career_id INTEGER NOT NULL REFERENCES careers(id) ON DELETE CASCADE,
    name      TEXT NOT NULL,
    city      TEXT NOT NULL,
    budget    REAL NOT NULL DEFAULT 30,
    formation TEXT NOT NULL DEFAULT '4-4-2',
    tactic    TEXT NOT NULL DEFAULT 'BALANCED' CHECK (tactic IN ('BALANCED','ATTACK','DEFENSE')),
    UNIQUE (career_id, name)
);
CREATE TABLE IF NOT EXISTS players (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    career_id INTEGER NOT NULL REFERENCES careers(id) ON DELETE CASCADE,
    team_id   INTEGER REFERENCES teams(id) ON DELETE SET NULL,
    name      TEXT NOT NULL,
    position  TEXT NOT NULL CHECK (position IN ('GK','DEF','MID','ATT')),
    age       INTEGER NOT NULL,
    rating    INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 99),
    potential INTEGER NOT NULL CHECK (potential BETWEEN 1 AND 99),
    starter   INTEGER NOT NULL DEFAULT 0,
    retired   INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS fixtures (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    career_id  INTEGER NOT NULL REFERENCES careers(id) ON DELETE CASCADE,
    season     INTEGER NOT NULL,
    round      INTEGER NOT NULL,
    home_id    INTEGER NOT NULL REFERENCES teams(id),
    away_id    INTEGER NOT NULL REFERENCES teams(id),
    played     INTEGER NOT NULL DEFAULT 0,
    home_goals INTEGER,
    away_goals INTEGER
);
CREATE INDEX IF NOT EXISTS idx_fixtures_round ON fixtures (career_id, season, round);
CREATE TABLE IF NOT EXISTS goals (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    fixture_id INTEGER NOT NULL REFERENCES fixtures(id) ON DELETE CASCADE,
    team_id    INTEGER NOT NULL REFERENCES teams(id),
    player_id  INTEGER NOT NULL REFERENCES players(id),
    assist_id  INTEGER REFERENCES players(id),
    minute     INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS season_stats (
    career_id  INTEGER NOT NULL REFERENCES careers(id) ON DELETE CASCADE,
    season     INTEGER NOT NULL,
    player_id  INTEGER NOT NULL REFERENCES players(id),
    games      INTEGER NOT NULL DEFAULT 0,
    goals      INTEGER NOT NULL DEFAULT 0,
    assists    INTEGER NOT NULL DEFAULT 0,
    rating_sum REAL NOT NULL DEFAULT 0,
    PRIMARY KEY (career_id, season, player_id)
);
CREATE TABLE IF NOT EXISTS offers (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    career_id     INTEGER NOT NULL REFERENCES careers(id) ON DELETE CASCADE,
    season        INTEGER NOT NULL,
    player_id     INTEGER NOT NULL REFERENCES players(id),
    team_id       INTEGER NOT NULL REFERENCES teams(id),
    role          TEXT NOT NULL CHECK (role IN ('TITULAR','RESERVA')),
    team_strength REAL NOT NULL,
    last_position INTEGER,
    status        TEXT NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING','ACCEPTED','REJECTED','EXPIRED'))
);
"""


@contextmanager
def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


@asynccontextmanager
async def lifespan(_: FastAPI):
    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
    with db() as conn:
        conn.executescript(SCHEMA)
    yield



app = FastAPI(
    title="Football Career API",
    description=(
        "Modo carreira de futebol (estilo FIFA) com partidas simuladas. "
        "Seja **técnico** de um clube ou **jogador** em ascensão: dispute temporadas, "
        "monte a escalação, negocie no mercado e receba propostas."
    ),
    version="2.1.0",
    lifespan=lifespan,
)


# ====================== Modelos ======================
class PlayerCreate(BaseModel):
    name: str = Field(min_length=2, max_length=40)
    position: Position
    age: int = Field(18, ge=16, le=21)


class CareerCreate(BaseModel):
    name: str = Field(min_length=2, max_length=40, description="Nome da carreira")
    mode: Literal["MANAGER", "PLAYER"]
    club: str | None = Field(None, description="Modo MANAGER: nome do clube (veja GET /clubs)")
    player: PlayerCreate | None = Field(None, description="Modo PLAYER: dados do seu jogador")


class LineupIn(BaseModel):
    formation: Formation
    tactic: Tactic = "BALANCED"
    starters: list[int] | None = Field(None, description="11 ids de jogadores; se omitido, a escalação é automática")


class TransferIn(BaseModel):
    player_id: int


# ====================== Utilidades ======================
def clamp(x, lo, hi):
    return max(lo, min(hi, x))


def poisson(lam: float) -> int:
    limit, k, p = math.exp(-lam), 0, 1.0
    while True:
        p *= random.random()
        if p <= limit:
            return k
        k += 1


def get_career(conn, cid: int) -> dict:
    row = conn.execute("SELECT * FROM careers WHERE id = ?", (cid,)).fetchone()
    if not row:
        raise HTTPException(404, "Carreira não encontrada")
    return dict(row)


def require_active(career: dict):
    if career["status"] != "ACTIVE":
        raise HTTPException(409, f"Carreira encerrada ({career['status']})")


def require_mode(career: dict, mode: str):
    if career["mode"] != mode:
        raise HTTPException(400, "Disponível apenas no modo " + ("TÉCNICO (MANAGER)" if mode == "MANAGER" else "JOGADOR (PLAYER)"))


def window_open(career: dict) -> bool:
    return career["status"] == "ACTIVE" and career["round"] in (1, MID_WINDOW_ROUND)


def require_window(career: dict):
    if not window_open(career):
        raise HTTPException(409, f"Janela de transferências fechada (abre antes das rodadas 1 e {MID_WINDOW_ROUND})")


def player_value(rating: int, age: int, potential: int) -> float:
    """Valor de mercado em milhões."""
    base = max(0.1, rating - 45) ** 2 / 40
    if age <= 21:
        factor = 1 + max(0, potential - rating) / 50
    elif age <= 29:
        factor = 1.0
    else:
        factor = max(0.2, 1 - (age - 29) * 0.15)
    return round(base * factor, 1)


def used_names(conn, cid: int) -> set:
    return {r[0] for r in conn.execute("SELECT name FROM players WHERE career_id = ?", (cid,))}


def new_name(used: set) -> str:
    for _ in range(200):
        n = f"{random.choice(FIRST)} {random.choice(LAST)}"
        if n not in used:
            used.add(n)
            return n
    n = f"{random.choice(FIRST)} {random.choice(LAST)} Jr."
    used.add(n)
    return n


def insert_player(conn, cid, team_id, name, pos, age, rating, potential) -> int:
    return conn.execute(
        "INSERT INTO players (career_id, team_id, name, position, age, rating, potential) VALUES (?,?,?,?,?,?,?)",
        (cid, team_id, name, pos, age, clamp(rating, 30, 95), clamp(max(potential, rating), 30, 99)),
    ).lastrowid


def squad_of(conn, team_id: int):
    return conn.execute("SELECT * FROM players WHERE team_id = ? AND retired = 0", (team_id,)).fetchall()


def auto_lineup(squad, formation: str):
    d, m, a = FORMATIONS[formation]
    picked, used = [], set()
    for pos, n in (("GK", 1), ("DEF", d), ("MID", m), ("ATT", a)):
        pool = sorted((p for p in squad if p["position"] == pos), key=lambda p: -p["rating"])[:n]
        picked += pool
        used |= {p["id"] for p in pool}
    if len(picked) < 11:  # faltou jogador em alguma posição: completa com os melhores de linha
        rest = sorted((p for p in squad if p["id"] not in used and p["position"] != "GK"), key=lambda p: -p["rating"])
        picked += rest[: 11 - len(picked)]
    return picked


def set_starters(conn, team_id: int, ids):
    conn.execute("UPDATE players SET starter = 0 WHERE team_id = ?", (team_id,))
    conn.executemany("UPDATE players SET starter = 1 WHERE id = ?", [(i,) for i in ids])


def lineup_for(conn, career: dict, team):
    """Titulares do time. Só o time do técnico usa a escalação escolhida por ele."""
    squad = squad_of(conn, team["id"])
    manual = career["mode"] == "MANAGER" and team["id"] == career["user_team_id"]
    if manual:
        flagged = [p for p in squad if p["starter"]]
        if len(flagged) == 11 and sum(p["position"] == "GK" for p in flagged) == 1:
            return flagged
    xi = auto_lineup(squad, team["formation"])
    if manual:
        set_starters(conn, team["id"], [p["id"] for p in xi])
    return xi


def team_strength(conn, team) -> float:
    xi = auto_lineup(squad_of(conn, team["id"]), team["formation"])
    return round(sum(p["rating"] for p in xi) / len(xi), 1) if xi else 0.0


def team_power(xi, tactic: str):
    att_n = att_d = def_n = def_d = 0.0
    for p in xi:
        r, pos = p["rating"], p["position"]
        if pos == "ATT":
            att_n += r; att_d += 1
        elif pos == "MID":
            att_n += 0.6 * r; att_d += 0.6; def_n += 0.4 * r; def_d += 0.4
        elif pos == "DEF":
            def_n += r; def_d += 1
        else:
            def_n += 1.4 * r; def_d += 1.4
    att = att_n / att_d if att_d else 50
    dfn = def_n / def_d if def_d else 50
    if tactic == "ATTACK":
        att, dfn = att * 1.04, dfn * 0.96
    elif tactic == "DEFENSE":
        att, dfn = att * 0.96, dfn * 1.04
    return att, dfn


def round_robin(ids):
    ids, n, rounds = ids[:], len(ids), []
    for r in range(n - 1):
        pairs = []
        for i in range(n // 2):
            a, b = ids[i], ids[n - 1 - i]
            pairs.append((a, b) if (i + r) % 2 == 0 else (b, a))
        rounds.append(pairs)
        ids = [ids[0]] + [ids[-1]] + ids[1:-1]
    return rounds + [[(b, a) for a, b in rd] for rd in rounds]


def make_fixtures(conn, cid: int, season: int):
    ids = [r[0] for r in conn.execute("SELECT id FROM teams WHERE career_id = ? ORDER BY id", (cid,))]
    for rnd, pairs in enumerate(round_robin(ids), start=1):
        conn.executemany(
            "INSERT INTO fixtures (career_id, season, round, home_id, away_id) VALUES (?,?,?,?,?)",
            [(cid, season, rnd, h, a) for h, a in pairs],
        )


def compute_standings(conn, cid: int, season: int):
    rows = conn.execute(
        """
        SELECT t.id AS team_id, t.name,
          COUNT(f.id) AS played,
          COALESCE(SUM(CASE WHEN (f.home_id=t.id AND f.home_goals>f.away_goals)
                             OR (f.away_id=t.id AND f.away_goals>f.home_goals) THEN 1 ELSE 0 END),0) AS wins,
          COALESCE(SUM(CASE WHEN f.home_goals=f.away_goals THEN 1 ELSE 0 END),0) AS draws,
          COALESCE(SUM(CASE WHEN f.home_id=t.id THEN f.home_goals
                            WHEN f.away_id=t.id THEN f.away_goals ELSE 0 END),0) AS goals_for,
          COALESCE(SUM(CASE WHEN f.home_id=t.id THEN f.away_goals
                            WHEN f.away_id=t.id THEN f.home_goals ELSE 0 END),0) AS goals_against
        FROM teams t
        LEFT JOIN fixtures f ON (f.home_id=t.id OR f.away_id=t.id)
                             AND f.career_id=? AND f.season=? AND f.played=1
        WHERE t.career_id=? GROUP BY t.id
        """,
        (cid, season, cid),
    ).fetchall()
    table = []
    for r in rows:
        d = dict(r)
        d["losses"] = d["played"] - d["wins"] - d["draws"]
        d["points"] = d["wins"] * 3 + d["draws"]
        d["goal_diff"] = d["goals_for"] - d["goals_against"]
        table.append(d)
    table.sort(key=lambda r: (-r["points"], -r["goal_diff"], -r["goals_for"], r["name"]))
    for i, r in enumerate(table, start=1):
        r["position"] = i
    return table


def strength_rank(conn, cid: int, team_id: int) -> int:
    teams = conn.execute("SELECT * FROM teams WHERE career_id = ?", (cid,)).fetchall()
    ranked = sorted(teams, key=lambda t: -team_strength(conn, t))
    return [t["id"] for t in ranked].index(team_id) + 1


# ====================== Simulação da partida ======================
def simulate_fixture(conn, career: dict, fx) -> dict:
    home = conn.execute("SELECT * FROM teams WHERE id = ?", (fx["home_id"],)).fetchone()
    away = conn.execute("SELECT * FROM teams WHERE id = ?", (fx["away_id"],)).fetchone()
    xi_h, xi_a = lineup_for(conn, career, home), lineup_for(conn, career, away)
    (ah, dh), (aa, da) = team_power(xi_h, home["tactic"]), team_power(xi_a, away["tactic"])

    xg_h = clamp(1.15 * (ah / da) ** 2.2 * 1.1, 0.15, 4.5)  # 1.1 = mando de campo
    xg_a = clamp(1.15 * (aa / dh) ** 2.2, 0.15, 4.5)
    hg, ag = poisson(xg_h), poisson(xg_a)

    scorer_w = {"ATT": 6, "MID": 2.5, "DEF": 0.8, "GK": 0.02}
    assist_w = {"ATT": 3, "MID": 4, "DEF": 1}
    stats, events = {}, []
    for team, xi, n_goals in ((home, xi_h, hg), (away, xi_a, ag)):
        for _ in range(n_goals):
            scorer = random.choices(xi, [scorer_w[p["position"]] * (p["rating"] / 70) ** 3 for p in xi])[0]
            assist = None
            if random.random() < 0.7:
                others = [p for p in xi if p["id"] != scorer["id"] and p["position"] != "GK"]
                assist = random.choices(others, [assist_w[p["position"]] for p in others])[0]
            minute = random.randint(1, 90)
            stats.setdefault(scorer["id"], {"g": 0, "a": 0})["g"] += 1
            if assist:
                stats.setdefault(assist["id"], {"g": 0, "a": 0})["a"] += 1
            conn.execute(
                "INSERT INTO goals (fixture_id, team_id, player_id, assist_id, minute) VALUES (?,?,?,?,?)",
                (fx["id"], team["id"], scorer["id"], assist["id"] if assist else None, minute),
            )
            events.append({"minute": minute, "team": team["name"], "scorer": scorer["name"],
                           "assist": assist["name"] if assist else None})

    perf = {}
    for xi, gf, ga in ((xi_h, hg, ag), (xi_a, ag, hg)):
        res = (gf > ga) - (gf < ga)
        for p in xi:
            s = stats.get(p["id"], {"g": 0, "a": 0})
            note = 6.0 + 0.3 * res + random.gauss(0, 0.5) + s["g"] + 0.5 * s["a"]
            if ga == 0 and p["position"] in ("GK", "DEF"):
                note += 0.5
            note = round(clamp(note, 3.0, 10.0), 1)
            perf[p["id"]] = {"goals": s["g"], "assists": s["a"], "match_rating": note}
            conn.execute(
                """INSERT INTO season_stats (career_id, season, player_id, games, goals, assists, rating_sum)
                   VALUES (?,?,?,1,?,?,?)
                   ON CONFLICT (career_id, season, player_id) DO UPDATE SET
                     games = games + 1, goals = goals + excluded.goals,
                     assists = assists + excluded.assists, rating_sum = rating_sum + excluded.rating_sum""",
                (career["id"], career["season"], p["id"], s["g"], s["a"], note),
            )
    conn.execute("UPDATE fixtures SET played = 1, home_goals = ?, away_goals = ? WHERE id = ?", (hg, ag, fx["id"]))
    events.sort(key=lambda e: e["minute"])
    return {"fixture_id": fx["id"], "round": fx["round"], "home": home["name"], "away": away["name"],
            "home_goals": hg, "away_goals": ag, "score": f"{hg} x {ag}", "goals": events, "perf": perf}


# ====================== Visão geral ======================
def career_overview(conn, cid: int) -> dict:
    c = get_career(conn, cid)
    out = {
        "id": c["id"], "name": c["name"], "mode": c["mode"], "status": c["status"],
        "season": c["season"], "round": min(c["round"], TOTAL_ROUNDS), "total_rounds": TOTAL_ROUNDS,
        "season_finished": c["round"] > TOTAL_ROUNDS, "transfer_window": window_open(c),
    }
    team = conn.execute("SELECT * FROM teams WHERE id = ?", (c["user_team_id"],)).fetchone()
    if team:
        table = compute_standings(conn, cid, c["season"])
        out["team"] = {"id": team["id"], "name": team["name"], "formation": team["formation"],
                       "tactic": team["tactic"], "budget_millions": round(team["budget"], 1),
                       "strength": team_strength(conn, team),
                       "league_position": next((r["position"] for r in table if r["team_id"] == team["id"] and r["played"] > 0), None)}
        nxt = conn.execute(
            """SELECT f.round, h.name AS home, a.name AS away FROM fixtures f
               JOIN teams h ON h.id = f.home_id JOIN teams a ON a.id = f.away_id
               WHERE f.career_id = ? AND f.season = ? AND f.played = 0 AND (f.home_id = ? OR f.away_id = ?)
               ORDER BY f.round LIMIT 1""", (cid, c["season"], team["id"], team["id"])).fetchone()
        out["next_fixture"] = dict(nxt) if nxt else None
    if c["mode"] == "MANAGER":
        out["board_confidence"] = c["board_confidence"]
        out["target_position"] = c["target_position"]
    else:
        p = conn.execute("SELECT * FROM players WHERE id = ?", (c["user_player_id"],)).fetchone()
        if p:
            out["player"] = {"id": p["id"], "name": p["name"], "position": p["position"], "age": p["age"],
                             "rating": p["rating"], "potential": p["potential"],
                             "value_millions": player_value(p["rating"], p["age"], p["potential"])}
    return out


# ====================== Endpoints: sistema e catálogo ======================
@app.get("/health", tags=["Sistema"])
def health():
    return {"status": "ok"}


@app.get("/clubs", tags=["Carreira"])
def list_clubs():
    """Clubes disponíveis para o modo técnico (força inicial aproximada)."""
    return [{"name": n, "city": c, "strength": s} for n, c, s in CLUBS]


# ====================== Endpoints: carreira ======================
@app.post("/careers", status_code=201, tags=["Carreira"])
def create_career(body: CareerCreate):
    clubs = {n.casefold(): n for n, _, _ in CLUBS}
    if body.mode == "MANAGER":
        if not body.club:
            raise HTTPException(422, "No modo MANAGER informe o clube (veja GET /clubs)")
        if body.club.casefold() not in clubs:
            raise HTTPException(400, f"Clube inválido. Opções: {', '.join(clubs.values())}")
    elif not body.player:
        raise HTTPException(422, "No modo PLAYER informe os dados do jogador (name, position, age)")

    with db() as conn:
        cid = conn.execute("INSERT INTO careers (name, mode) VALUES (?, ?)", (body.name, body.mode)).lastrowid

        used = set()
        for name, city, base in CLUBS:
            tid = conn.execute(
                "INSERT INTO teams (career_id, name, city, formation) VALUES (?,?,?,?)",
                (cid, name, city, random.choice(list(FORMATIONS))),
            ).lastrowid
            for pos, n in SQUAD_PLAN.items():
                for _ in range(n):
                    rating = clamp(base + random.randint(-7, 7), 40, 92)
                    age = random.randint(18, 34)
                    pot = rating + (random.randint(0, 12) if age < 24 else random.randint(0, 2))
                    insert_player(conn, cid, tid, new_name(used), pos, age, rating, pot)
        top_up_free_agents(conn, cid)
        make_fixtures(conn, cid, 1)

        if body.mode == "MANAGER":
            team = conn.execute("SELECT * FROM teams WHERE career_id = ? AND name = ?",
                                (cid, clubs[body.club.casefold()])).fetchone()
            xi = auto_lineup(squad_of(conn, team["id"]), team["formation"])
            set_starters(conn, team["id"], [p["id"] for p in xi])
            conn.execute("UPDATE careers SET user_team_id = ?, target_position = ? WHERE id = ?",
                         (team["id"], strength_rank(conn, cid, team["id"]), cid))
        else:
            teams = conn.execute("SELECT * FROM teams WHERE career_id = ?", (cid,)).fetchall()
            team = min(teams, key=lambda t: team_strength(conn, t))  # começa no clube mais fraco
            d, m, a = FORMATIONS[team["formation"]]
            slots = {"GK": 1, "DEF": d, "MID": m, "ATT": a}[body.player.position]
            ratings = sorted((p["rating"] for p in squad_of(conn, team["id"])
                              if p["position"] == body.player.position), reverse=True)
            start_rating = clamp(ratings[min(slots, len(ratings)) - 1] + 1, 48, 70)  # entra como titular
            pid = insert_player(conn, cid, team["id"], body.player.name, body.player.position,
                                body.player.age, start_rating, random.randint(78, 92))
            conn.execute("UPDATE careers SET user_team_id = ?, user_player_id = ? WHERE id = ?", (team["id"], pid, cid))
        return career_overview(conn, cid)


def top_up_free_agents(conn, cid: int, target: int = 10):
    have = conn.execute("SELECT COUNT(*) FROM players WHERE career_id = ? AND team_id IS NULL AND retired = 0",
                        (cid,)).fetchone()[0]
    used = used_names(conn, cid)
    for _ in range(max(0, target - have)):
        rating = random.randint(50, 66)
        insert_player(conn, cid, None, new_name(used), random.choice(["GK", "DEF", "MID", "MID", "ATT"]),
                      random.randint(24, 33), rating, rating + random.randint(0, 3))


@app.get("/careers", tags=["Carreira"])
def list_careers():
    with db() as conn:
        rows = conn.execute(
            """SELECT c.id, c.name, c.mode, c.status, c.season, c.round, t.name AS team
               FROM careers c LEFT JOIN teams t ON t.id = c.user_team_id ORDER BY c.id DESC"""
        ).fetchall()
        return [dict(r) for r in rows]


@app.get("/careers/{cid}", tags=["Carreira"])
def get_career_overview(cid: int):
    with db() as conn:
        return career_overview(conn, cid)


@app.delete("/careers/{cid}", status_code=204, tags=["Carreira"])
def delete_career(cid: int):
    with db() as conn:
        get_career(conn, cid)
        conn.execute("DELETE FROM careers WHERE id = ?", (cid,))


# ====================== Endpoints: liga ======================
@app.get("/careers/{cid}/standings", tags=["Liga"])
def standings(cid: int, season: int | None = None):
    with db() as conn:
        c = get_career(conn, cid)
        return compute_standings(conn, cid, season or c["season"])


@app.get("/careers/{cid}/fixtures", tags=["Liga"])
def fixtures(cid: int, round: int | None = None, mine: bool = False, season: int | None = None):
    with db() as conn:
        c = get_career(conn, cid)
        sql = ("SELECT f.round, h.name AS home, a.name AS away, f.played, f.home_goals, f.away_goals "
               "FROM fixtures f JOIN teams h ON h.id = f.home_id JOIN teams a ON a.id = f.away_id "
               "WHERE f.career_id = ? AND f.season = ?")
        params: list = [cid, season or c["season"]]
        if round:
            sql += " AND f.round = ?"
            params.append(round)
        if mine:
            sql += " AND (f.home_id = ? OR f.away_id = ?)"
            params += [c["user_team_id"]] * 2
        return [dict(r) for r in conn.execute(sql + " ORDER BY f.round, f.id", params)]


@app.get("/careers/{cid}/teams", tags=["Liga"])
def list_teams(cid: int):
    with db() as conn:
        get_career(conn, cid)
        teams = conn.execute("SELECT * FROM teams WHERE career_id = ? ORDER BY name", (cid,)).fetchall()
        return [{"id": t["id"], "name": t["name"], "city": t["city"], "formation": t["formation"],
                 "tactic": t["tactic"], "budget_millions": round(t["budget"], 1),
                 "strength": team_strength(conn, t)} for t in teams]


@app.get("/careers/{cid}/teams/{team_id}", tags=["Liga"])
def get_team(cid: int, team_id: int):
    with db() as conn:
        get_career(conn, cid)
        t = conn.execute("SELECT * FROM teams WHERE id = ? AND career_id = ?", (team_id, cid)).fetchone()
        if not t:
            raise HTTPException(404, "Time não encontrado nesta carreira")
        squad = sorted(squad_of(conn, team_id), key=lambda p: -p["rating"])
        return {"id": t["id"], "name": t["name"], "formation": t["formation"], "tactic": t["tactic"],
                "strength": team_strength(conn, t),
                "squad": [{"id": p["id"], "name": p["name"], "position": p["position"], "age": p["age"],
                           "rating": p["rating"]} for p in squad]}


@app.get("/careers/{cid}/top-scorers", tags=["Liga"])
def top_scorers(cid: int, season: int | None = None, limit: int = Query(10, ge=1, le=50)):
    with db() as conn:
        c = get_career(conn, cid)
        rows = conn.execute(
            """SELECT p.name AS player, t.name AS team, ss.goals, ss.assists, ss.games,
                      ROUND(ss.rating_sum / ss.games, 2) AS avg_rating
               FROM season_stats ss JOIN players p ON p.id = ss.player_id LEFT JOIN teams t ON t.id = p.team_id
               WHERE ss.career_id = ? AND ss.season = ? AND ss.goals > 0
               ORDER BY ss.goals DESC, ss.assists DESC LIMIT ?""",
            (cid, season or c["season"], limit))
        return [dict(r) for r in rows]


@app.get("/careers/{cid}/squad", tags=["Liga"])
def my_squad(cid: int):
    """Elenco do seu clube (no modo PLAYER, são os seus companheiros de time)."""
    with db() as conn:
        c = get_career(conn, cid)
        team = conn.execute("SELECT * FROM teams WHERE id = ?", (c["user_team_id"],)).fetchone()
        xi_ids = {p["id"] for p in lineup_for(conn, c, team)}
        rows = conn.execute(
            """SELECT p.*, COALESCE(ss.games,0) AS games, COALESCE(ss.goals,0) AS goals,
                      COALESCE(ss.assists,0) AS assists,
                      CASE WHEN ss.games > 0 THEN ROUND(ss.rating_sum / ss.games, 2) END AS avg_rating
               FROM players p LEFT JOIN season_stats ss
                 ON ss.player_id = p.id AND ss.career_id = ? AND ss.season = ?
               WHERE p.team_id = ? AND p.retired = 0 ORDER BY p.rating DESC""",
            (cid, c["season"], team["id"])).fetchall()
        return {"team": team["name"], "formation": team["formation"], "tactic": team["tactic"],
                "squad": [{"id": r["id"], "name": r["name"], "position": r["position"], "age": r["age"],
                           "rating": r["rating"], "starter": r["id"] in xi_ids,
                           "is_you": r["id"] == c["user_player_id"], "games": r["games"],
                           "goals": r["goals"], "assists": r["assists"], "avg_rating": r["avg_rating"]}
                          for r in rows]}


# ====================== Endpoints: jogo ======================
@app.post("/careers/{cid}/advance", tags=["Jogo"])
def advance(cid: int, rounds: int = Query(1, ge=1, le=TOTAL_ROUNDS)):
    """Simula a(s) próxima(s) rodada(s) da temporada."""
    with db() as conn:
        career = get_career(conn, cid)
        require_active(career)
        if career["round"] > TOTAL_ROUNDS:
            raise HTTPException(409, f"Temporada encerrada. Use POST /careers/{cid}/next-season")
        played, my_matches, fired = [], [], False
        for _ in range(rounds):
            if career["round"] > TOTAL_ROUNDS:
                break
            fxs = conn.execute("SELECT * FROM fixtures WHERE career_id = ? AND season = ? AND round = ?",
                               (cid, career["season"], career["round"])).fetchall()
            results = []
            for fx in fxs:
                r = simulate_fixture(conn, career, fx)
                mine = career["user_team_id"] in (fx["home_id"], fx["away_id"])
                results.append({"home": r["home"], "score": r["score"], "away": r["away"], "mine": mine})
                if not mine:
                    continue
                detail = {k: r[k] for k in ("round", "home", "away", "score", "goals")}
                if career["mode"] == "MANAGER":
                    gf, ga = ((r["home_goals"], r["away_goals"]) if fx["home_id"] == career["user_team_id"]
                              else (r["away_goals"], r["home_goals"]))
                    career["board_confidence"] = clamp(career["board_confidence"] + (gf > ga) * 4 - (gf < ga) * 4, 0, 100)
                else:
                    pp = r["perf"].get(career["user_player_id"])
                    detail["my_player"] = ({"in_starting_xi": True, **pp} if pp else {"in_starting_xi": False})
                my_matches.append(detail)
            played.append({"round": career["round"], "results": results})
            career["round"] += 1
            conn.execute("UPDATE careers SET round = ?, board_confidence = ? WHERE id = ?",
                         (career["round"], career["board_confidence"], cid))
            if career["mode"] == "MANAGER" and career["board_confidence"] <= FIRE_LIMIT:
                conn.execute("UPDATE careers SET status = 'FIRED' WHERE id = ?", (cid,))
                fired = True
                break
        out = {"season": career["season"], "rounds": played, "my_matches": my_matches,
               "season_finished": career["round"] > TOTAL_ROUNDS}
        if career["mode"] == "MANAGER":
            out["board_confidence"] = career["board_confidence"]
        if fired:
            out["status"] = "FIRED"
            out["message"] = "A diretoria perdeu a confiança e demitiu você. Fim da carreira."
        elif out["season_finished"]:
            out["message"] = f"Temporada encerrada! Use POST /careers/{cid}/next-season"
        return out


@app.post("/careers/{cid}/next-season", tags=["Jogo"])
def next_season(cid: int):
    """Encerra a temporada: avalia o desempenho, evolui/envelhece jogadores e inicia a próxima."""
    with db() as conn:
        c = get_career(conn, cid)
        require_active(c)
        if c["round"] <= TOTAL_ROUNDS:
            raise HTTPException(409, f"A temporada só termina após a rodada {TOTAL_ROUNDS} (faltam {TOTAL_ROUNDS - c['round'] + 1})")
        table = compute_standings(conn, cid, c["season"])
        pos_map = {r["team_id"]: r["position"] for r in table}
        summary = {"season": c["season"], "champion": table[0]["name"]}
        user_team = conn.execute("SELECT * FROM teams WHERE id = ?", (c["user_team_id"],)).fetchone()
        summary["your_final_position"] = pos_map[user_team["id"]]

        perf_bonus = 0
        if c["mode"] == "MANAGER":
            final_pos = pos_map[user_team["id"]]
            conf = clamp(c["board_confidence"] + (c["target_position"] - final_pos) * 5, 0, 100)
            revenue = round(10 + (len(table) - final_pos) * 1.5, 1)
            conn.execute("UPDATE teams SET budget = budget + ? WHERE id = ?", (revenue, user_team["id"]))
            conn.execute("UPDATE careers SET board_confidence = ? WHERE id = ?", (conf, cid))
            summary["board"] = {"target_position": c["target_position"], "board_confidence": conf, "revenue_millions": revenue}
            if conf <= FIRE_LIMIT:
                conn.execute("UPDATE careers SET status = 'FIRED' WHERE id = ?", (cid,))
                summary["status"] = "FIRED"
                summary["message"] = "Resultado abaixo do esperado: a diretoria demitiu você. Fim da carreira."
                return summary
        else:
            st = conn.execute("SELECT games, goals, assists, rating_sum FROM season_stats "
                              "WHERE career_id = ? AND season = ? AND player_id = ?",
                              (cid, c["season"], c["user_player_id"])).fetchone()
            games = st["games"] if st else 0
            avg = st["rating_sum"] / games if games else 0
            perf_bonus = 2 if avg >= 7.6 else 1 if avg >= 7.0 else -1 if games >= 5 and avg < 6.0 else 0
            summary["your_season"] = {"games": games, "goals": st["goals"] if st else 0,
                                      "assists": st["assists"] if st else 0, "avg_rating": round(avg, 2)}

        # evolução e envelhecimento
        retired_from_your_team, user_change = [], None
        for p in conn.execute("SELECT * FROM players WHERE career_id = ? AND retired = 0", (cid,)).fetchall():
            age, r, pot = p["age"], p["rating"], p["potential"]
            if age < 24:
                delta = random.randint(1, 5)
            elif age < 30:
                delta = random.randint(-1, 1)
            elif age < 34:
                delta = random.randint(-3, 0)
            else:
                delta = random.randint(-4, -1)
            if p["id"] == c["user_player_id"]:
                delta += perf_bonus
            new_r = clamp(r + delta, 35, 95)
            if age < 24 and new_r > pot:
                new_r = max(r, pot)
            new_pot = max(pot, new_r)
            retire = (p["id"] != c["user_player_id"] and age + 1 >= 35
                      and random.random() < {35: 0.5, 36: 0.8}.get(age + 1, 1.0))
            if retire:
                conn.execute("UPDATE players SET age=?, rating=?, retired=1, team_id=NULL, starter=0 WHERE id=?",
                             (age + 1, new_r, p["id"]))
                if p["team_id"] == user_team["id"]:
                    retired_from_your_team.append(p["name"])
            else:
                conn.execute("UPDATE players SET age=?, rating=?, potential=? WHERE id=?",
                             (age + 1, new_r, new_pot, p["id"]))
            if p["id"] == c["user_player_id"]:
                user_change = {"age": age + 1, "rating_before": r, "rating_after": new_r, "potential": new_pot}

        if c["mode"] == "PLAYER":
            summary["progression"] = user_change
            if user_change["age"] >= 36:
                conn.execute("UPDATE careers SET status = 'RETIRED' WHERE id = ?", (cid,))
                summary["status"] = "RETIRED"
                summary["message"] = "Você se aposentou aos 36 anos. Fim da carreira!"
                return summary
        else:
            summary["retired_from_your_squad"] = retired_from_your_team

        # regens (jovens) para repor o elenco e free agents
        used = used_names(conn, cid)
        for t in conn.execute("SELECT * FROM teams WHERE career_id = ?", (cid,)).fetchall():
            counts = {pos: 0 for pos in SQUAD_PLAN}
            for p in squad_of(conn, t["id"]):
                counts[p["position"]] += 1
            for pos, plan in SQUAD_PLAN.items():
                for _ in range(max(0, plan - counts[pos])):
                    rating = random.randint(42, 58)
                    insert_player(conn, cid, t["id"], new_name(used), pos, random.randint(17, 19),
                                  rating, rating + random.randint(10, 28))
        top_up_free_agents(conn, cid)

        # nova temporada
        new_season = c["season"] + 1
        make_fixtures(conn, cid, new_season)
        conn.execute("UPDATE careers SET season = ?, round = 1 WHERE id = ?", (new_season, cid))
        c.update(season=new_season, round=1)
        if c["mode"] == "MANAGER":
            conn.execute("UPDATE careers SET target_position = ? WHERE id = ?",
                         (strength_rank(conn, cid, user_team["id"]), cid))
            team_row = conn.execute("SELECT * FROM teams WHERE id = ?", (user_team["id"],)).fetchone()
            flagged = [p for p in squad_of(conn, team_row["id"]) if p["starter"]]
            valid = len(flagged) == 11 and sum(p["position"] == "GK" for p in flagged) == 1
            lineup_for(conn, c, team_row)  # refaz a escalação automaticamente se ficou inválida
            summary["lineup_reset"] = not valid
        else:
            summary["new_offers"] = generate_offers(conn, c, pos_map)
        summary["next_season"] = new_season
        return summary


def generate_offers(conn, career: dict, pos_map: dict) -> int:
    conn.execute("UPDATE offers SET status = 'EXPIRED' WHERE career_id = ? AND status = 'PENDING'", (career["id"],))
    p = conn.execute("SELECT * FROM players WHERE id = ?", (career["user_player_id"],)).fetchone()
    options = []
    for t in conn.execute("SELECT * FROM teams WHERE career_id = ? AND id != ?", (career["id"], p["team_id"])).fetchall():
        xi = auto_lineup(squad_of(conn, t["id"]), t["formation"])
        slots = [x["rating"] for x in xi if x["position"] == p["position"]]
        if not slots:
            continue
        threshold = min(slots)
        if p["rating"] + 2 >= threshold:
            strength = round(sum(x["rating"] for x in xi) / len(xi), 1)
            options.append((strength, t, "TITULAR" if p["rating"] >= threshold else "RESERVA"))
    options.sort(key=lambda o: -o[0] + random.uniform(-2, 2))  # prefere clubes maiores, com um pouco de sorte
    for strength, t, role in options[:3]:
        conn.execute(
            "INSERT INTO offers (career_id, season, player_id, team_id, role, team_strength, last_position) VALUES (?,?,?,?,?,?,?)",
            (career["id"], career["season"], p["id"], t["id"], role, strength, pos_map.get(t["id"])))
    return min(3, len(options))


# ====================== Modo técnico ======================
@app.put("/careers/{cid}/lineup", tags=["Modo técnico"])
def set_lineup(cid: int, body: LineupIn):
    with db() as conn:
        c = get_career(conn, cid)
        require_mode(c, "MANAGER")
        require_active(c)
        d, m, a = FORMATIONS[body.formation]
        team = conn.execute("SELECT * FROM teams WHERE id = ?", (c["user_team_id"],)).fetchone()
        squad = squad_of(conn, team["id"])
        if body.starters is None:
            xi = auto_lineup(squad, body.formation)
        else:
            ids = body.starters
            if len(ids) != 11 or len(set(ids)) != 11:
                raise HTTPException(400, "Informe exatamente 11 jogadores diferentes")
            by_id = {p["id"]: p for p in squad}
            if any(i not in by_id for i in ids):
                raise HTTPException(400, "Há jogadores que não pertencem ao seu elenco")
            xi = [by_id[i] for i in ids]

        counts = {pos: sum(p["position"] == pos for p in xi) for pos in SQUAD_PLAN}
        if len(xi) != 11 or (counts["GK"], counts["DEF"], counts["MID"], counts["ATT"]) != (1, d, m, a):
            raise HTTPException(
                409 if body.starters is None else 400,
                f"A formação {body.formation} exige exatamente 1 GK, {d} DEF, {m} MID e {a} ATT. "
                "O elenco atual não possui jogadores suficientes ou a escalação informada é incompatível.",
            )

        conn.execute("UPDATE teams SET formation = ?, tactic = ? WHERE id = ?", (body.formation, body.tactic, c["user_team_id"]))
        set_starters(conn, team["id"], [p["id"] for p in xi])
        return {"formation": body.formation, "tactic": body.tactic,
                "starters": [{"id": p["id"], "name": p["name"], "position": p["position"], "rating": p["rating"]}
                             for p in sorted(xi, key=lambda p: (list(SQUAD_PLAN).index(p["position"]), -p["rating"]))]}


@app.get("/careers/{cid}/market", tags=["Modo técnico"])
def market(cid: int, position: Position | None = None, max_price: float | None = None,
           limit: int = Query(20, ge=1, le=100)):
    """Jogadores de outros clubes e free agents, com o preço de compra (em milhões)."""
    with db() as conn:
        c = get_career(conn, cid)
        require_mode(c, "MANAGER")
        sql = ("SELECT p.*, t.name AS team_name FROM players p LEFT JOIN teams t ON t.id = p.team_id "
               "WHERE p.career_id = ? AND p.retired = 0 AND (p.team_id IS NULL OR p.team_id != ?)")
        params: list = [cid, c["user_team_id"]]
        if position:
            sql += " AND p.position = ?"
            params.append(position)
        out = []
        for p in conn.execute(sql + " ORDER BY p.rating DESC LIMIT 300", params):
            price = buy_price(p)
            if max_price is None or price <= max_price:
                out.append({"id": p["id"], "name": p["name"], "position": p["position"], "age": p["age"],
                            "rating": p["rating"], "potential": p["potential"],
                            "club": p["team_name"] or "Livre (free agent)", "price_millions": price})
        return {"transfer_window": window_open(c), "players": out[:limit]}


def buy_price(p) -> float:
    v = player_value(p["rating"], p["age"], p["potential"])
    return round(v * (0.9 if p["team_id"] is None else 1.2), 1)


@app.post("/careers/{cid}/market/buy", tags=["Modo técnico"])
def buy_player(cid: int, body: TransferIn):
    with db() as conn:
        c = get_career(conn, cid)
        require_mode(c, "MANAGER")
        require_active(c)
        require_window(c)
        p = conn.execute("SELECT * FROM players WHERE id = ? AND career_id = ? AND retired = 0", (body.player_id, cid)).fetchone()
        if not p:
            raise HTTPException(404, "Jogador não encontrado")
        if p["team_id"] == c["user_team_id"]:
            raise HTTPException(400, "Esse jogador já é do seu clube")
        me = conn.execute("SELECT * FROM teams WHERE id = ?", (c["user_team_id"],)).fetchone()
        price = buy_price(p)
        if me["budget"] < price:
            raise HTTPException(409, f"Orçamento insuficiente: preço {price} M, você tem {round(me['budget'], 1)} M")
        if len(squad_of(conn, me["id"])) >= MAX_SQUAD:
            raise HTTPException(409, f"Elenco cheio (máximo {MAX_SQUAD} jogadores)")
        if p["team_id"] is not None:
            seller = squad_of(conn, p["team_id"])
            if len(seller) <= MIN_SQUAD or sum(x["position"] == p["position"] for x in seller) <= MIN_POS[p["position"]]:
                raise HTTPException(409, "O clube vendedor recusou: o elenco ficaria sem a quantidade mínima para as formações")
            conn.execute("UPDATE teams SET budget = budget + ? WHERE id = ?", (price, p["team_id"]))
        conn.execute("UPDATE teams SET budget = budget - ? WHERE id = ?", (price, me["id"]))
        conn.execute("UPDATE players SET team_id = ?, starter = 0 WHERE id = ?", (me["id"], p["id"]))
        return {"bought": p["name"], "price_millions": price, "budget_millions": round(me["budget"] - price, 1)}


@app.post("/careers/{cid}/market/sell", tags=["Modo técnico"])
def sell_player(cid: int, body: TransferIn):
    with db() as conn:
        c = get_career(conn, cid)
        require_mode(c, "MANAGER")
        require_active(c)
        require_window(c)
        p = conn.execute("SELECT * FROM players WHERE id = ? AND team_id = ? AND retired = 0",
                         (body.player_id, c["user_team_id"])).fetchone()
        if not p:
            raise HTTPException(404, "Esse jogador não está no seu elenco")
        squad = squad_of(conn, c["user_team_id"])
        if len(squad) <= MIN_SQUAD or sum(x["position"] == p["position"] for x in squad) <= MIN_POS[p["position"]]:
            raise HTTPException(409, f"Venda bloqueada: o elenco precisa ter ao menos {MIN_SQUAD} jogadores e manter GK≥1, DEF≥4, MID≥5 e ATT≥3")
        price = round(player_value(p["rating"], p["age"], p["potential"]) * 0.7, 1)
        buyers = [t for t in conn.execute("SELECT * FROM teams WHERE career_id = ? AND id != ?", (cid, c["user_team_id"]))
                  if t["budget"] >= price and len(squad_of(conn, t["id"])) < MAX_SQUAD]
        buyer = random.choice(buyers) if buyers else None
        if buyer:
            conn.execute("UPDATE teams SET budget = budget - ? WHERE id = ?", (price, buyer["id"]))
        conn.execute("UPDATE players SET team_id = ?, starter = 0 WHERE id = ?", (buyer["id"] if buyer else None, p["id"]))
        conn.execute("UPDATE teams SET budget = budget + ? WHERE id = ?", (price, c["user_team_id"]))
        return {"sold": p["name"], "price_millions": price, "to": buyer["name"] if buyer else "Free agent (sem clube)"}


# ====================== Modo jogador ======================
@app.get("/careers/{cid}/player", tags=["Modo jogador"])
def my_player(cid: int):
    with db() as conn:
        c = get_career(conn, cid)
        require_mode(c, "PLAYER")
        p = conn.execute("SELECT p.*, t.name AS team_name FROM players p LEFT JOIN teams t ON t.id = p.team_id "
                         "WHERE p.id = ?", (c["user_player_id"],)).fetchone()
        history = [dict(r) for r in conn.execute(
            """SELECT season, games, goals, assists, ROUND(rating_sum / games, 2) AS avg_rating
               FROM season_stats WHERE career_id = ? AND player_id = ? AND games > 0 ORDER BY season""",
            (cid, p["id"]))]
        return {"id": p["id"], "name": p["name"], "position": p["position"], "age": p["age"], "rating": p["rating"],
                "potential": p["potential"], "club": p["team_name"],
                "value_millions": player_value(p["rating"], p["age"], p["potential"]),
                "history": history,
                "career_totals": {"games": sum(h["games"] for h in history), "goals": sum(h["goals"] for h in history),
                                  "assists": sum(h["assists"] for h in history)}}


@app.get("/careers/{cid}/offers", tags=["Modo jogador"])
def list_offers(cid: int):
    with db() as conn:
        c = get_career(conn, cid)
        require_mode(c, "PLAYER")
        rows = conn.execute(
            """SELECT o.id, t.name AS club, o.role, o.team_strength, o.last_position, o.status
               FROM offers o JOIN teams t ON t.id = o.team_id
               WHERE o.career_id = ? AND o.season = ? ORDER BY o.id""", (cid, c["season"])).fetchall()
        return {"transfer_window": window_open(c), "offers": [dict(r) for r in rows]}


@app.post("/careers/{cid}/offers/{offer_id}/accept", tags=["Modo jogador"])
def accept_offer(cid: int, offer_id: int):
    with db() as conn:
        c = get_career(conn, cid)
        require_mode(c, "PLAYER")
        require_active(c)
        require_window(c)
        o = conn.execute("SELECT * FROM offers WHERE id = ? AND career_id = ? AND season = ? AND status = 'PENDING'",
                         (offer_id, cid, c["season"])).fetchone()
        if not o:
            raise HTTPException(404, "Proposta não encontrada ou já respondida")
        conn.execute("UPDATE players SET team_id = ?, starter = 0 WHERE id = ?", (o["team_id"], c["user_player_id"]))
        conn.execute("UPDATE careers SET user_team_id = ? WHERE id = ?", (o["team_id"], cid))
        conn.execute("UPDATE offers SET status = CASE WHEN id = ? THEN 'ACCEPTED' ELSE 'REJECTED' END "
                     "WHERE career_id = ? AND season = ? AND status = 'PENDING'", (offer_id, cid, c["season"]))
        team = conn.execute("SELECT name FROM teams WHERE id = ?", (o["team_id"],)).fetchone()
        return {"message": f"Transferência concluída: você agora joga no {team['name']}", "role": o["role"]}


@app.post("/careers/{cid}/retire", tags=["Modo jogador"])
def retire(cid: int):
    """Encerra a carreira do jogador e mostra o balanço final."""
    with db() as conn:
        c = get_career(conn, cid)
        require_mode(c, "PLAYER")
        require_active(c)
        conn.execute("UPDATE careers SET status = 'RETIRED' WHERE id = ?", (cid,))
    return my_player(cid) | {"status": "RETIRED"}
