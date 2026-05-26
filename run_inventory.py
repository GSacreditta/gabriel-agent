"""
CLI runner for the Gmail Inventory Pass.

Usage:
    # Basic (no entity tagging):
    python run_inventory.py --bucket=my-bucket-name --skip-entity-tagging

    # With entity tagging via local Ollama:
    python run_inventory.py --bucket=my-bucket-name --ollama-url=http://localhost:11434

    # With entity tagging via Cloud Run Ollama:
    python run_inventory.py --bucket=my-bucket-name --ollama-url=https://ollama-xxxxx-uc.a.run.app

    # Resume a previous run:
    python run_inventory.py --bucket=my-bucket-name --run-id=20250510T120000Z

Scope: ONLY emails under the 'Finanzas' label in sternbergg@gmail.com.
All outputs go to GCS. No local data files are written.
LLM entity tagging uses a private Ollama instance — no data sent to public APIs.
"""

import argparse
import asyncio
import logging
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.inventory_service import InventoryService


def setup_logging(verbose: bool = False):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
        datefmt='%H:%M:%S'
    )
    # Quiet noisy libraries
    logging.getLogger('googleapiclient.discovery_cache').setLevel(logging.WARNING)
    logging.getLogger('google.auth.transport.requests').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('httpx').setLevel(logging.WARNING)


async def main():
    parser = argparse.ArgumentParser(
        description="Gmail Inventory Pass — Family Office (Finanzas label only)"
    )
    parser.add_argument('--bucket', required=True,
                        help='GCS bucket name for output')
    parser.add_argument('--entities', default='config/entities.txt',
                        help='Path to entities file')
    parser.add_argument('--queries', default='config/inventory_queries.yaml',
                        help='Path to queries YAML')
    parser.add_argument('--prompt', default='config/entity_prompt.txt',
                        help='Path to entity prompt template')
    parser.add_argument('--skip-entity-tagging', action='store_true',
                        help='Skip LLM entity tagging')
    parser.add_argument('--ollama-url', default='http://localhost:11434',
                        help='Ollama API URL (local or Cloud Run)')
    parser.add_argument('--ollama-model', default='phi3:mini',
                        help='Ollama model for entity tagging (default: phi3:mini)')
    parser.add_argument('--run-id',
                        help='Resume a specific run ID (otherwise generates new)')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Verbose logging')
    args = parser.parse_args()

    setup_logging(args.verbose)
    logger = logging.getLogger(__name__)

    logger.info("=" * 60)
    logger.info("  Gmail Inventory Pass — Family Office")
    logger.info("  Scope: label:Finanzas @ sternbergg@gmail.com")
    logger.info("=" * 60)
    logger.info(f"  Bucket:         {args.bucket}")
    logger.info(f"  Entities:       {args.entities}")
    logger.info(f"  Entity tagging: {'SKIP' if args.skip_entity_tagging else f'ON ({args.ollama_model} @ {args.ollama_url})'}")
    logger.info(f"  Privacy:        LLM is private (Ollama) — no public API calls")
    logger.info("=" * 60)

    # Initialize service
    service = InventoryService(
        bucket_name=args.bucket,
        entities_file=args.entities,
        queries_file=args.queries,
        prompt_file=args.prompt,
        ollama_url=args.ollama_url,
        ollama_model=args.ollama_model
    )

    # Override run_id for resume
    if args.run_id:
        service.run_id = args.run_id
        logger.info(f"  Resuming run: {args.run_id}")

    await service.initialize()

    # Execute
    summary = await service.run_inventory(skip_entity_tagging=args.skip_entity_tagging)

    # Print results
    logger.info("")
    logger.info("=" * 60)
    logger.info("  RESULTS")
    logger.info("=" * 60)
    logger.info(f"  Total messages:     {summary['total_messages']}")
    logger.info(f"  Unique senders:     {summary['unique_senders']}")
    logger.info(f"  With attachments:   {summary['messages_with_attachments']}")
    logger.info(f"  Entity-tagged:      {summary['entity_tagged']}")
    logger.info(f"  GCS output:         {summary['gcs_path']}")
    logger.info("=" * 60)
    logger.info("")
    logger.info("Next steps:")
    logger.info(f"  1. Review stats:    gsutil cat {summary['gcs_path']}stats.md")
    logger.info(f"  2. Review senders:  gsutil cat {summary['gcs_path']}senders_summary.csv")
    logger.info(f"  3. Fill config/entities.txt if entity tagging was skipped")
    logger.info(f"  4. Re-run with --ollama-url to tag entities privately")


if __name__ == '__main__':
    asyncio.run(main())
