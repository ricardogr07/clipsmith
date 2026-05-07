"""VOD pipeline orchestration: download → transcribe → candidates → select → clip."""

from __future__ import annotations

import logging

from rich.console import Console
from rich.logging import RichHandler

import json
from pathlib import Path

from .candidates import build_candidates, save_candidates
from .chat import download_chat
from .clipper import cut_all_clips
from .detect import load_or_detect_webcam_rect
from .downloader import download_vod
from .llm import get_provider
from .llm.prompts import build_stream_context
from .models.candidates import CandidateMoment
from .models.twitch import Video
from .selector import PickResult, select_clips
from .settings import AppConfig, Secrets
from .transcribe import transcribe
from .twitch_client import TwitchClient

console = Console()
log = logging.getLogger(__name__)


def save_picks(picks: list[PickResult], path: Path) -> None:
    """Serialize accepted picks to JSON."""
    path.write_text(
        json.dumps([p.to_dict() for p in picks], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(message)s",
        handlers=[RichHandler(console=console, rich_tracebacks=True, show_path=False)],
    )


def process_vod(
    video: Video,
    cfg: AppConfig,
    secrets: Secrets,
    *,
    skip_download: bool = False,
    skip_transcribe: bool = False,
    skip_chat: bool = False,
    skip_select: bool = False,
    skip_clip: bool = False,
    provider: str | None = None,
    max_candidates: int = 20,
    start_s: float = 0.0,
) -> None:
    """Run the full pipeline for one VOD: download → transcribe → candidates → select → clip."""
    video_id = video.id
    work_dir = cfg.work_dir.expanduser()
    vod_dir = work_dir / video_id
    vod_dir.mkdir(parents=True, exist_ok=True)

    if secrets.twitch_client_id and secrets.twitch_client_secret and video.user_id:
        with TwitchClient(secrets.twitch_client_id, secrets.twitch_client_secret) as tc:
            existing_clips = tc.get_clips_for_vod(video.user_id, video_id)
    else:
        existing_clips = []
        log.info("skipping existing-clips fetch (no Twitch credentials or local mode)")

    console.print(
        f"VOD [bold]{video_id}[/bold]: {video.title!r} by {video.user_login} "
        f"({video.duration}, type={video.type}) — {len(existing_clips)} existing clip(s)"
    )

    if not skip_download:
        console.print("[cyan]downloading...[/cyan]")
        result = download_vod(video_id, work_dir)
        mp4_path = result.mp4_path
    else:
        mp4_path = vod_dir / f"{video_id}.mp4"
        if not mp4_path.exists():
            raise FileNotFoundError(f"Expected MP4 not found: {mp4_path}")

    load_or_detect_webcam_rect(mp4_path, vod_dir, cfg.reframe)

    if start_s > 0:
        console.print(f"[dim]start offset:[/dim] {start_s:.0f}s — pregame content will be skipped")

    console.print(f"[cyan]transcribing[/cyan] {mp4_path.name} ...")
    transcript = transcribe(
        mp4_path,
        video_id,
        cfg.transcribe,
        overwrite=not skip_transcribe,
    )
    if start_s > 0:
        before = len(transcript.segments)
        transcript.segments = [s for s in transcript.segments if s.start >= start_s]
        log.info(
            "trimmed transcript: %d -> %d segments (start_s=%.0f)",
            before,
            len(transcript.segments),
            start_s,
        )
    console.print(
        f"[green]transcript done[/green]: {len(transcript.segments)} segments, "
        f"language={transcript.language}"
    )

    console.print("[cyan]downloading chat...[/cyan]")
    chat = download_chat(video_id, work_dir, overwrite=not skip_chat)
    if start_s > 0:
        before = len(chat.messages)
        chat.messages = [m for m in chat.messages if m.time_in_seconds >= start_s]
        log.info(
            "trimmed chat: %d -> %d messages (start_s=%.0f)", before, len(chat.messages), start_s
        )
    console.print(f"[green]chat loaded[/green]: {len(chat.messages)} messages")

    console.print("[cyan]scoring candidates...[/cyan]")
    candidates = build_candidates(
        chat, existing_clips, cfg.candidates, transcript=transcript, mp4_path=mp4_path
    )

    if not candidates:
        log.info("no chat signals — falling back to evenly-spaced transcript samples")
        duration = transcript.segments[-1].end if transcript.segments else 0.0
        interval = cfg.clip.max_seconds * 2
        t = interval / 2
        while t < duration:
            candidates.append(
                CandidateMoment(
                    t_center=t,
                    score=1.0,
                    sources=["transcript_sample"],
                    reasons=[f"evenly-spaced sample at t={t:.1f}s (no chat data)"],
                )
            )
            t += interval

    save_candidates(candidates, vod_dir / "candidates.json")
    console.print(f"[green]candidates[/green]: {len(candidates)} moments")
    for i, c in enumerate(candidates[:10], 1):
        console.print(
            f"  #{i:2d}  t={c.t_center:7.1f}s  score={c.score:6.1f}  signals={','.join(c.sources)}"
        )

    if skip_select:
        console.print("[yellow]LLM selection skipped (--skip-select)[/yellow]")
        return

    if provider:
        cfg.llm.provider = provider  # type: ignore[assignment]

    console.print(
        f"[cyan]selecting clips[/cyan] via {cfg.llm.provider} (top {max_candidates} candidates)..."
    )
    picker = get_provider(cfg, secrets)
    stream_context = build_stream_context(
        channel=video.user_login,
        vod_title=video.title,
        vod_duration=video.duration,
    )
    picks = select_clips(
        candidates,
        transcript,
        picker,
        stream_context,
        cfg.clip,
        max_candidates=max_candidates,
    )
    picks_path = vod_dir / "picks.json"
    save_picks(picks, picks_path)
    console.print(f"[green]picks[/green]: {len(picks)} accepted -> {picks_path}")
    for i, pr in enumerate(picks, 1):
        console.print(
            f"  #{i:2d}  [{pr.pick.start_offset_s:.1f}-{pr.pick.end_offset_s:.1f}s]  "
            f"{pr.pick.title_es!r}"
        )

    if skip_clip:
        console.print("[yellow]clipping skipped (--skip-clip)[/yellow]")
        return

    out_dir = cfg.out_dir.expanduser() / video_id
    console.print(f"[cyan]cutting clips[/cyan] -> {out_dir}")
    clip_paths = cut_all_clips(mp4_path, transcript, picks, out_dir, cfg)
    console.print(f"[green]done[/green]: {len(clip_paths)} clip(s) in {out_dir}")
