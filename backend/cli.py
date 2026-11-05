import asyncio
import os

import typer
from backend.analytics import generate_coach_tips, run_anticheat_analysis
from backend.database import find_match_by_hash, get_connection, init_db, insert_parsed_demo
from backend.parser import get_file_hash, parse_demo
from rich.console import Console
from rich.table import Table

app = typer.Typer(help="Fragscope CS2 Demo Analyzer CLI")
console = Console()

@app.command()
def parse(demo_path: str):
    """Parse a CS2 demo file and save its data to the local SQLite database."""
    if not os.path.exists(demo_path):
        console.print(f"[red]Error: Demo file '{demo_path}' not found.[/red]")
        raise typer.Exit(code=1)

    console.print("[cyan]Initializing database...[/cyan]")
    asyncio.run(init_db())

    # Get file hash and size
    file_hash = get_file_hash(demo_path)
    file_size = os.path.getsize(demo_path)

    async def run_parse():
        async with get_connection() as conn:
            # Check for existing match
            existing = await find_match_by_hash(conn, file_hash)
            if existing:
                console.print(f"[yellow]Match already imported! ID: {existing['id']}, Map: {existing['map_name']}[/yellow]")
                return existing["id"]

            console.print("[cyan]Parsing demo (using demoparser2)...[/cyan]")
            parsed_data = parse_demo(demo_path, include_ticks=True)

            console.print("[cyan]Saving match data to SQLite...[/cyan]")
            match_id = await insert_parsed_demo(conn, parsed_data, demo_path, file_hash, file_size)

            console.print("[cyan]Running anticheat analysis...[/cyan]")
            await run_anticheat_analysis(match_id, parsed_data.get("ticks_df"))

            console.print("[cyan]Generating coaching tips...[/cyan]")
            await generate_coach_tips(match_id)

            console.print(f"[green]Successfully parsed and imported! Match ID: {match_id}[/green]")
            return match_id

    asyncio.run(run_parse())

@app.command()
def highlights(match_id: int, video: str = typer.Option(None, help="Path to video file (.mp4) to cut clips from")):
    """Show highlights (multi-kills, clutches) and optionally cut video clips using ffmpeg."""
    async def get_highlights():
        async with get_connection() as conn:
            # Fetch match header
            async with conn.execute("SELECT * FROM matches WHERE id = ?", (match_id,)) as cursor:
                match_row = await cursor.fetchone()
                if not match_row:
                    console.print(f"[red]Error: Match ID {match_id} not found.[/red]")
                    return

            # Fetch player stats to see multi-kills
            async with conn.execute(
                "SELECT player, team, rating, kills, multi_kills_3k, multi_kills_4k, multi_kills_5k "
                "FROM player_match_stats WHERE match_id = ? ORDER BY rating DESC",
                (match_id,)
            ) as cursor:
                stats_rows = await cursor.fetchall()

            # Fetch rounds winner / events
            async with conn.execute("SELECT * FROM rounds WHERE match_id = ? ORDER BY round_num ASC", (match_id,)) as cursor:
                round_rows = await cursor.fetchall()
                rounds_dict = {r["id"]: r for r in round_rows}

            # Fetch kills to locate tick numbers for multi-kills
            async with conn.execute(
                "SELECT tick, round_id, attacker, victim, weapon, headshot FROM kills WHERE match_id = ? ORDER BY tick ASC",
                (match_id,)
            ) as cursor:
                kill_rows = await cursor.fetchall()

            console.print(f"\n[bold green]=== HIGHLIGHTS FOR MATCH {match_id} ({match_row['map_name']}) ===[/bold green]")

            # Print multi-kill table
            table = Table(title="Top Performance / Multi-Kills")
            table.add_column("Player", style="cyan")
            table.add_column("Team", style="magenta")
            table.add_column("Kills", style="green")
            table.add_column("3K Rounds", style="yellow")
            table.add_column("4K Rounds", style="orange3")
            table.add_column("5K Rounds", style="red")
            table.add_column("Rating", style="bold green")

            for s in stats_rows:
                if s["multi_kills_3k"] > 0 or s["multi_kills_4k"] > 0 or s["multi_kills_5k"] > 0 or s["kills"] > 20:
                    table.add_row(
                        s["player"], s["team"], str(s["kills"]),
                        str(s["multi_kills_3k"]), str(s["multi_kills_4k"]), str(s["multi_kills_5k"]),
                        f"{s['rating']:.2f}"
                    )
            console.print(table)

            from backend.highlights import detect_highlights, cut_highlight_clips
            highlights_found = detect_highlights(match_id)

            if not highlights_found:
                console.print("[yellow]No significant highlights found (no 3K/4K/5K rounds).[/yellow]")
                return

            console.print("\n[bold]Detected Highlight Clips:[/bold]")
            for idx, h in enumerate(highlights_found):
                console.print(f"[{idx}] Round {h['round_num']}: [cyan]{h['description']}[/cyan] (ticks {h['start_tick']} - {h['end_tick']})")

            # Cut clips using ffmpeg if video is provided
            if video:
                if not os.path.exists(video):
                    console.print(f"[red]Error: Video file '{video}' not found.[/red]")
                    return

                console.print(f"\n[cyan]Cutting clips from '{video}' using ffmpeg...[/cyan]")
                try:
                    cut_clips = cut_highlight_clips(match_id, video)
                    for c in cut_clips:
                        console.print(f"[green]Saved clip: {os.path.join('output', c['clip_path'])}[/green]")
                except Exception as e:
                    console.print(f"[red]Failed to cut clips: {e}[/red]")

    asyncio.run(get_highlights())

if __name__ == "__main__":
    app()
