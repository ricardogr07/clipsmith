"""VOD pipeline orchestration: download → transcribe → candidates → select → clip."""

from __future__ import annotations

import logging

from rich.console import Console
from rich.logging import RichHandler

from .candidates import CandidateMoment, build_candidates, save_candidates
from .chat import download_chat
from .clipper import cut_all_clips
from .downloader import download_vod
from .llm import get_provider
from .selector import build_stream_context, save_picks, select_clips
from .settings import AppConfig, Secrets
from .transcribe import transcribe
from .twitch_client import TwitchClient, Video

console = Console()
log = logging.getLogger(__name__)


def _setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(message)s",
        handlers=[RichHandler(console=console, rich_tracebacks=True, show_path=False)],
    )


def _process_vod(
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

    console.print(f"[cyan]transcribing[/cyan] {mp4_path.name} ...")
    transcript = transcribe(
        mp4_path,
        video_id,
        cfg.transcribe,
        overwrite=not skip_transcribe,
    )
    console.print(
        f"[green]transcript done[/green]: {len(transcript.segments)} segments, "
        f"language={transcript.language}"
    )

    console.print("[cyan]downloading chat...[/cyan]")
    chat = download_chat(video_id, work_dir, overwrite=not skip_chat)
    console.print(f"[green]chat loaded[/green]: {len(chat.messages)} messages")

    console.print("[cyan]scoring candidates...[/cyan]")
    candidates = build_candidates(chat, existing_clips, cfg.candidates)

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
            f"  #{i:2d}  t={c.t_center:7.1f}s  score={c.score:6.1f}  "
            f"signals={','.join(c.sources)}"
        )

    if skip_select:
        console.print("[yellow]LLM selection skipped (--skip-select)[/yellow]")
        return

    if provider:
        cfg.llm.provider = provider  # type: ignore[assignment]

    console.print(
        f"[cyan]selecting clips[/cyan] via {cfg.llm.provider} "
        f"(top {max_candidates} candidates)..."
    )
    picker = get_provider(cfg, secrets)
    stream_context = build_stream_context(
        channel=video.user_login,
        vod_title=video.title,
        vod_duration=video.duration,
    )
    picks = select_clips(
        candidates, transcript, picker, stream_context, cfg.clip,
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
