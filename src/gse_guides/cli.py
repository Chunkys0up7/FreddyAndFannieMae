"""CLI entry point for the GSE Guide Scraper."""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

import click

from gse_guides.base_scraper import BaseScraper
from gse_guides.config import ScraperConfig


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    # Quiet noisy libraries
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("playwright").setLevel(logging.WARNING)


@click.group()
def cli():
    """GSE Guide Scraper - Extract Fannie Mae & Freddie Mac guidelines."""
    pass


@cli.command()
@click.argument("source", type=click.Choice(["fannie-mae", "freddie-mac", "all"]))
@click.option("--section", help="Scrape a single section by code (e.g. B3-3.1-01)")
@click.option("--output", type=click.Path(), default="output", help="Output directory")
@click.option("--delay", type=float, help="Override request delay (seconds)")
@click.option("--no-resume", is_flag=True, help="Re-scrape all sections")
@click.option("--max-sections", type=int, help="Limit sections to scrape (for testing)")
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose logging")
def scrape(source, section, output, delay, no_resume, max_sections, verbose):
    """Scrape guide sections and save as markdown."""
    _setup_logging(verbose)

    config = ScraperConfig(output_dir=Path(output))
    if delay is not None:
        config.fannie_request_delay_seconds = delay
        config.freddie_request_delay_seconds = delay
    if no_resume:
        config.skip_existing = False
    if max_sections:
        config.max_sections = max_sections

    scrapers = _create_scrapers(source, config)

    for scraper in scrapers:
        click.echo(f"\n{'='*60}")
        click.echo(f"Scraping: {scraper.source.value}")
        click.echo(f"{'='*60}")

        if section:
            result = scraper.scrape_single(section)
            if result:
                click.echo(f"Successfully scraped {result.section_code}: {result.title}")
                click.echo(f"  Words: {result.word_count}")
                click.echo(f"  Subsections: {len(result.subsections)}")
                click.echo(f"  Tables: {result.table_count}")
            else:
                click.echo(f"Failed to scrape section {section}", err=True)
                sys.exit(1)
        else:
            manifest = scraper.scrape_all()
            click.echo(f"\nResults:")
            click.echo(f"  Discovered: {manifest.total_discovered}")
            click.echo(f"  Scraped:    {manifest.total_scraped}")
            click.echo(f"  Skipped:    {manifest.total_skipped}")
            click.echo(f"  Failed:     {manifest.total_failed}")

            if manifest.errors:
                click.echo(f"\nErrors ({len(manifest.errors)}):")
                for err in manifest.errors[:10]:
                    click.echo(f"  {err.section_code}: {err.error_type} - {err.error_message[:80]}")


@cli.command()
@click.option("--output", type=click.Path(), default="output")
def status(output):
    """Show scraping progress and statistics."""
    output_dir = Path(output)

    for source_dir in ["fannie_mae", "freddie_mac"]:
        manifest_path = output_dir / source_dir / "manifest.json"
        if not manifest_path.exists():
            click.echo(f"\n{source_dir}: No manifest found (not yet scraped)")
            continue

        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        click.echo(f"\n{'='*40}")
        click.echo(f"Source: {source_dir}")
        click.echo(f"{'='*40}")
        click.echo(f"  Discovered: {data.get('total_discovered', 0)}")
        click.echo(f"  Scraped:    {data.get('total_scraped', 0)}")
        click.echo(f"  Skipped:    {data.get('total_skipped', 0)}")
        click.echo(f"  Failed:     {data.get('total_failed', 0)}")
        click.echo(f"  Started:    {data.get('started_at', 'N/A')}")
        click.echo(f"  Updated:    {data.get('last_updated', 'N/A')}")

        # Count files on disk
        source_path = output_dir / source_dir
        md_files = list(source_path.rglob("*.md"))
        click.echo(f"  Files:      {len(md_files)}")

        # Show errors summary
        errors = data.get("errors", [])
        if errors:
            click.echo(f"\n  Recent Errors ({len(errors)}):")
            for err in errors[:5]:
                click.echo(
                    f"    {err.get('section_code', '?')}: "
                    f"{err.get('error_type', '?')} - "
                    f"{err.get('error_message', '?')[:60]}"
                )


@cli.command()
@click.argument("source", type=click.Choice(["fannie-mae", "freddie-mac"]))
@click.option("--verbose", "-v", is_flag=True)
def discover(source, verbose):
    """Discover and list all section URLs without scraping."""
    _setup_logging(verbose)
    config = ScraperConfig()

    if source == "fannie-mae":
        from gse_guides.fannie_mae.discovery import FannieMaeDiscovery

        disc = FannieMaeDiscovery(config)
    else:
        from gse_guides.freddie_mac.discovery import FreddieMacDiscovery

        disc = FreddieMacDiscovery(config)

    urls = disc.discover()

    click.echo(f"\nDiscovered {len(urls)} sections:\n")
    click.echo(f"{'Code':<20} {'Last Modified':<15} URL")
    click.echo("-" * 80)

    for u in urls:
        click.echo(f"{u.section_code:<20} {u.last_modified or 'N/A':<15} {u.url}")


@cli.command()
@click.option("--output", type=click.Path(), default="output", help="Scraped output directory")
@click.option("--enriched", type=click.Path(), default="enriched", help="Enriched output directory")
@click.option("--source", type=click.Choice(["fannie-mae", "freddie-mac"]), help="Only enrich one source")
@click.option("--stats", is_flag=True, help="Print enrichment statistics")
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose logging")
def enrich(output, enriched, source, stats, verbose):
    """Enrich scraped sections with domain tags, MISMO metadata, and adaptive chunks."""
    _setup_logging(verbose)

    from gse_guides.enrichment.pipeline import EnrichmentPipeline

    config = ScraperConfig(output_dir=Path(output), enriched_dir=Path(enriched))
    pipeline = EnrichmentPipeline(config)

    normalized_source = source.replace("-", "_") if source else None
    result = pipeline.run(normalized_source)

    click.echo(f"\nEnrichment Complete:")
    click.echo(f"  Sections processed: {result.total_sections}")
    click.echo(f"  Chunks produced:    {result.total_chunks}")
    click.echo(f"  Avg chunk words:    {result.avg_chunk_words}")
    click.echo(f"  Cross-source links: {result.cross_source_link_count}")

    if result.errors:
        click.echo(f"\n  Errors ({len(result.errors)}):")
        for err in result.errors[:10]:
            click.echo(f"    {err[:80]}")

    if stats:
        click.echo(f"\n  Domain Distribution:")
        for domain, count in sorted(result.domain_distribution.items(), key=lambda x: -x[1]):
            click.echo(f"    {domain:<40} {count}")

        click.echo(f"\n  Content Type Distribution:")
        for ctype, count in sorted(result.content_type_distribution.items(), key=lambda x: -x[1]):
            click.echo(f"    {ctype:<25} {count}")


def _create_scrapers(source: str, config: ScraperConfig) -> list[BaseScraper]:
    """Create appropriate scraper instances."""
    scrapers = []

    if source in ("fannie-mae", "all"):
        from gse_guides.fannie_mae.scraper import FannieMaeScraper

        scrapers.append(FannieMaeScraper(config))

    if source in ("freddie-mac", "all"):
        from gse_guides.freddie_mac.scraper import FreddieMacScraper

        scrapers.append(FreddieMacScraper(config))

    return scrapers


if __name__ == "__main__":
    cli()
