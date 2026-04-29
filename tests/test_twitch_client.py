"""Smoke tests for TwitchClient using mocked httpx responses."""

from __future__ import annotations

import time

import httpx
import pytest

from clipsmith import twitch_client as tc_mod
from clipsmith.twitch_client import TwitchClient


class _FakeResp:
    def __init__(self, json_data: dict, status: int = 200):
        self._json = json_data
        self.status_code = status

    def json(self) -> dict:
        return self._json

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("err", request=None, response=None)  # type: ignore[arg-type]


class _FakeHttp:
    def __init__(self):
        self.calls: list[tuple[str, str, dict | None]] = []
        self._responses: dict[str, _FakeResp] = {}

    def stub(self, key: str, resp: _FakeResp) -> None:
        self._responses[key] = resp

    def post(self, url, data=None, **kw):
        self.calls.append(("POST", url, data))
        return self._responses[url]

    def get(self, url, headers=None, params=None, **kw):
        self.calls.append(("GET", url, params))
        return self._responses[url]

    def close(self):
        pass


def _build(http: _FakeHttp) -> TwitchClient:
    c = TwitchClient("cid", "csecret")
    c._http = http  # type: ignore[assignment]
    return c


def test_requires_credentials():
    with pytest.raises(ValueError):
        TwitchClient("", "")


def test_token_fetched_and_cached():
    http = _FakeHttp()
    http.stub(
        tc_mod.OAUTH_TOKEN_URL,
        _FakeResp({"access_token": "tok", "expires_in": 3600}),
    )
    http.stub(
        f"{tc_mod.HELIX}/users",
        _FakeResp({"data": [{"id": "42", "login": "x"}]}),
    )
    c = _build(http)
    assert c.get_user_id("x") == "42"
    # Second call should reuse the cached token, not refetch.
    assert c.get_user_id("x") == "42"
    posts = [call for call in http.calls if call[0] == "POST"]
    assert len(posts) == 1


def test_get_user_id_missing_raises():
    http = _FakeHttp()
    http.stub(tc_mod.OAUTH_TOKEN_URL, _FakeResp({"access_token": "t", "expires_in": 60}))
    http.stub(f"{tc_mod.HELIX}/users", _FakeResp({"data": []}))
    c = _build(http)
    with pytest.raises(LookupError):
        c.get_user_id("nope")


def test_get_videos_parses_archive():
    http = _FakeHttp()
    http.stub(tc_mod.OAUTH_TOKEN_URL, _FakeResp({"access_token": "t", "expires_in": 60}))
    http.stub(
        f"{tc_mod.HELIX}/videos",
        _FakeResp(
            {
                "data": [
                    {
                        "id": "v1",
                        "user_id": "u1",
                        "user_login": "chuyelwuero",
                        "title": "stream",
                        "created_at": "2026-04-27T20:00:00Z",
                        "published_at": "2026-04-27T20:05:00Z",
                        "url": "https://twitch.tv/videos/v1",
                        "duration": "3h21m4s",
                        "type": "archive",
                    }
                ]
            }
        ),
    )
    c = _build(http)
    vids = c.get_videos("u1")
    assert len(vids) == 1
    assert vids[0].id == "v1"
    assert vids[0].duration == "3h21m4s"
    assert vids[0].type == "archive"


def test_get_clips_filters_by_video():
    http = _FakeHttp()
    http.stub(tc_mod.OAUTH_TOKEN_URL, _FakeResp({"access_token": "t", "expires_in": 60}))
    http.stub(
        f"{tc_mod.HELIX}/clips",
        _FakeResp(
            {
                "data": [
                    {
                        "id": "c1",
                        "url": "u",
                        "title": "t1",
                        "creator_name": "n",
                        "video_id": "v1",
                        "vod_offset": 1234,
                        "duration": 28.5,
                        "view_count": 500,
                        "created_at": "2026-04-27T20:30:00Z",
                    },
                    {
                        "id": "c2",
                        "url": "u",
                        "title": "t2",
                        "creator_name": "n",
                        "video_id": "vOTHER",
                        "vod_offset": 99,
                        "duration": 20.0,
                        "view_count": 50,
                        "created_at": "2026-04-27T20:30:00Z",
                    },
                ],
                "pagination": {},
            }
        ),
    )
    c = _build(http)
    clips = c.get_clips_for_vod("u1", "v1")
    assert [cl.id for cl in clips] == ["c1"]
    assert clips[0].vod_offset == 1234


def test_token_refreshes_when_expired(monkeypatch):
    http = _FakeHttp()
    http.stub(
        tc_mod.OAUTH_TOKEN_URL,
        _FakeResp({"access_token": "t1", "expires_in": 1}),
    )
    http.stub(f"{tc_mod.HELIX}/users", _FakeResp({"data": [{"id": "1"}]}))
    c = _build(http)
    c.get_user_id("a")
    # Force expiry.
    monkeypatch.setattr(time, "time", lambda: c._token_expires_at + 1)
    c.get_user_id("a")
    posts = [call for call in http.calls if call[0] == "POST"]
    assert len(posts) == 2
