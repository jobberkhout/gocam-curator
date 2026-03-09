"""gocam run — execute the full pipeline in sequence."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import click

from gocam.utils.display import console, print_error, print_info, print_success, print_warning
from gocam.utils.process import resolve_process


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _run_step(
    ctx: click.Context,
    command: click.BaseCommand,
    step_name: str,
    log_lines: list[str],
    **kwargs,
) -> bool:
    """Invoke a Click command, catch any failure, return True on success."""
    console.rule(f"[bold]{step_name}[/bold]")
    log_lines.append(f"\n[{_now()}] START  {step_name}")
    try:
        ctx.invoke(command, **kwargs)
        log_lines.append(f"[{_now()}] OK     {step_name}")
        print_success(f"{step_name} completed")
        return True
    except SystemExit as exc:
        msg = f"exited with code {exc.code}"
        log_lines.append(f"[{_now()}] FAILED {step_name} — {msg}")
        print_warning(f"{step_name} failed ({msg}) — continuing")
        return False
    except Exception as exc:
        log_lines.append(f"[{_now()}] FAILED {step_name} — {exc}")
        print_warning(f"{step_name} failed ({exc}) — continuing")
        return False


@click.command("run")
@click.option(
    "--process", "-p",
    default=None,
    help="Process name. Auto-detected if there is exactly one process.",
)
@click.option(
    "--deep",
    is_flag=True,
    default=False,
    help="Include a deep second-pass extraction after the initial report.",
)
@click.pass_context
def run_command(ctx: click.Context, process: str | None, deep: bool) -> None:
    """Run the full GO-CAM curation pipeline for a process in one command.

    \b
    PIPELINE STEPS
      1. extract-all          Extract entities from all files in input/.
      2. report               Synthesize extractions into REPORT.md.
      3. extract-all --deep   Second-pass extraction for missed content.  [--deep only]
      4. report (post-deep)   Re-synthesize after deep pass.              [--deep only]
      5. translate            Map biology to GO terms and ECO codes.
      6. verify               Check all IDs against live databases.
      7. narrative            Generate expert-readable claims document.

    \b
    BEHAVIOR
      - Each step runs in sequence and its outcome is logged.
      - If a step fails, the pipeline continues to the next step where possible.
      - A timestamped pipeline_log.txt is saved in the process directory.

    \b
    OUTPUT  (all standard step outputs, plus)
      pipeline_log.txt    Timestamped record of each step's success or failure.

    \b
    EXAMPLES
      gocam run vesicle-fusion
      gocam run vesicle-fusion --deep
      gocam run --process ampa-endocytosis
    """
    # Lazy imports to avoid circular dependency at module load time
    from gocam.commands.extract_all import extract_all_command
    from gocam.commands.narrative import narrative_command
    from gocam.commands.report import report_command
    from gocam.commands.translate import translate_command
    from gocam.commands.verify import verify_command

    process_dir = resolve_process(process)
    process_name = process_dir.name

    log_lines: list[str] = [
        f"gocam pipeline run",
        f"Process:  {process_name}",
        f"Started:  {_now()}",
        f"Deep mode: {deep}",
    ]

    console.print(
        f"[bold]Process:[/bold] {process_name}  "
        f"[bold]Steps:[/bold] extract-all → report"
        + (" → deep" if deep else "")
        + " → translate → verify → narrative"
    )

    results: dict[str, bool] = {}

    # Step 1: extract-all
    results["extract-all"] = _run_step(
        ctx, extract_all_command, "extract-all", log_lines, process=process_name, deep=False
    )

    # Step 2: report
    results["report"] = _run_step(
        ctx, report_command, "report", log_lines, process=process_name
    )

    # Step 3 (optional): deep second pass
    if deep:
        results["extract-all --deep"] = _run_step(
            ctx, extract_all_command, "extract-all --deep", log_lines,
            process=process_name, deep=True
        )
        # Re-run report to incorporate deep-pass findings
        results["report (post-deep)"] = _run_step(
            ctx, report_command, "report (post-deep)", log_lines, process=process_name
        )

    # Step 4: translate
    results["translate"] = _run_step(
        ctx, translate_command, "translate", log_lines, process=process_name
    )

    # Step 5: verify
    results["verify"] = _run_step(
        ctx, verify_command, "verify", log_lines, process=process_name
    )

    # Step 6: narrative
    results["narrative"] = _run_step(
        ctx, narrative_command, "narrative", log_lines, process=process_name
    )

    # Summary
    console.rule("[bold]Pipeline Summary[/bold]")
    n_ok = sum(results.values())
    n_total = len(results)
    log_lines.append(f"\n[{_now()}] DONE   {n_ok}/{n_total} steps succeeded")

    for step, ok in results.items():
        status = "[green]OK[/green]" if ok else "[red]FAILED[/red]"
        console.print(f"  {status}  {step}")

    # Save log
    log_path = process_dir / "pipeline_log.txt"
    log_path.write_text("\n".join(log_lines) + "\n", encoding="utf-8")
    print_success(f"\nPipeline log → {log_path}")

    if n_ok == n_total:
        print_success(f"All {n_total} steps completed successfully.")
    else:
        print_warning(f"{n_total - n_ok} step(s) failed — see {log_path} for details.")
