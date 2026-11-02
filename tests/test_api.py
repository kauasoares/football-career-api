from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from fastapi.testclient import TestClient

import main
from backup_db import create_backup


@pytest.fixture

def api_client(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "DB_PATH", str(tmp_path / "career.db"))
    with TestClient(main.app) as client:
        yield client


def create_manager(client: TestClient) -> int:
    response = client.post(
        "/careers",
        json={"name": "Carreira de teste", "mode": "MANAGER", "club": "Tigres do ABC"},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def create_player(client: TestClient) -> int:
    response = client.post(
        "/careers",
        json={
            "name": "Carreira de atleta",
            "mode": "PLAYER",
            "player": {"name": "Atleta Teste", "position": "ATT", "age": 18},
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_health_and_catalog(api_client):
    assert api_client.get("/health").json() == {"status": "ok"}
    clubs = api_client.get("/clubs")
    assert clubs.status_code == 200
    assert len(clubs.json()) == 8


def test_manager_and_player_careers_are_isolated(api_client):
    manager_id = create_manager(api_client)
    player_id = create_player(api_client)
    assert manager_id != player_id

    manager_teams = api_client.get(f"/careers/{manager_id}/teams").json()
    player_teams = api_client.get(f"/careers/{player_id}/teams").json()
    assert len(manager_teams) == len(player_teams) == 8
    assert manager_teams[0]["id"] != player_teams[0]["id"]

    foreign_team_id = player_teams[0]["id"]
    assert api_client.get(f"/careers/{manager_id}/teams/{foreign_team_id}").status_code == 404


def test_lineup_accepts_formation_and_rejects_incompatible_positions(api_client):
    career_id = create_manager(api_client)
    squad = api_client.get(f"/careers/{career_id}/squad").json()["squad"]
    selected = []
    for position, required in (("GK", 1), ("DEF", 3), ("MID", 5), ("ATT", 2)):
        selected.extend([p["id"] for p in squad if p["position"] == position][:required])

    valid = api_client.put(
        f"/careers/{career_id}/lineup",
        json={"formation": "3-5-2", "tactic": "BALANCED", "starters": selected},
    )
    assert valid.status_code == 200, valid.text
    assert len(valid.json()["starters"]) == 11

    invalid = api_client.put(
        f"/careers/{career_id}/lineup",
        json={"formation": "4-4-2", "tactic": "ATTACK", "starters": selected},
    )
    assert invalid.status_code == 400


def test_market_resale_does_not_create_artificial_profit(api_client):
    career_id = create_manager(api_client)
    market = api_client.get(f"/careers/{career_id}/market?limit=100").json()["players"]
    free_agent = next(p for p in market if p["club"] == "Livre (free agent)")

    bought = api_client.post(
        f"/careers/{career_id}/market/buy", json={"player_id": free_agent["id"]}
    )
    assert bought.status_code == 200, bought.text
    purchase_price = bought.json()["price_millions"]

    sold = api_client.post(
        f"/careers/{career_id}/market/sell", json={"player_id": free_agent["id"]}
    )
    assert sold.status_code == 200, sold.text
    sale_price = sold.json()["price_millions"]
    assert sale_price < purchase_price


def test_squad_retains_minimum_position_coverage(api_client):
    career_id = create_manager(api_client)
    squad = api_client.get(f"/careers/{career_id}/squad").json()["squad"]
    midfielders = [p for p in squad if p["position"] == "MID"]
    assert len(midfielders) == 6

    first_sale = api_client.post(
        f"/careers/{career_id}/market/sell", json={"player_id": midfielders[0]["id"]}
    )
    assert first_sale.status_code == 200

    second_sale = api_client.post(
        f"/careers/{career_id}/market/sell", json={"player_id": midfielders[1]["id"]}
    )
    assert second_sale.status_code == 409


def test_player_can_complete_season_and_progress(api_client):
    career_id = create_player(api_client)
    advance = api_client.post(f"/careers/{career_id}/advance?rounds=14")
    assert advance.status_code == 200, advance.text
    assert advance.json()["season_finished"] is True

    next_season = api_client.post(f"/careers/{career_id}/next-season")
    assert next_season.status_code == 200, next_season.text
    assert next_season.json()["next_season"] == 2
    overview = api_client.get(f"/careers/{career_id}").json()
    assert overview["season"] == 2
    assert overview["round"] == 1


def test_academic_api_is_accessible_without_authentication(api_client):
    # A atividade usa a API aberta para facilitar a avaliação pelo Swagger/Postman.
    assert api_client.get("/clubs").status_code == 200
    assert api_client.get("/docs").status_code == 200
    schema = api_client.get("/openapi.json").json()
    assert "security" not in schema
    assert "securitySchemes" not in schema.get("components", {})


def test_sqlite_backup_is_valid_and_restorable(tmp_path):
    source = tmp_path / "source.db"
    backups = tmp_path / "backups"
    with sqlite3.connect(source) as conn:
        conn.execute("CREATE TABLE sample (id INTEGER PRIMARY KEY, value TEXT NOT NULL)")
        conn.execute("INSERT INTO sample(value) VALUES ('persistido')")

    backup = create_backup(source, backups)
    assert backup.exists()
    with sqlite3.connect(backup) as conn:
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert conn.execute("SELECT value FROM sample").fetchone()[0] == "persistido"


def test_backup_fails_when_database_does_not_exist(tmp_path):
    with pytest.raises(FileNotFoundError):
        create_backup(tmp_path / "missing.db", tmp_path / "backups")
