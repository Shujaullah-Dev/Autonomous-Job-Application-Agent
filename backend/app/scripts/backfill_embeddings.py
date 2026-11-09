
"""Generate and store embeddings for active jobs."""

import argparse
import sys

from sqlalchemy.exc import SQLAlchemyError

from app.db.session import SessionLocal
from app.services.semantic_embeddings import (
    EmbeddingError,
    embed_texts,
)
from app.services.vector_store import (
    scan_jobs,
    store_embeddings,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Backfill job semantic embeddings"
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=100,
    )

    parser.add_argument(
        "--after-id",
        type=int,
        default=0,
    )

    parser.add_argument(
        "--batch-size",
        type=int,
        default=8,
    )

    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write embeddings; default is dry-run",
    )

    args = parser.parse_args(argv)

    if not 1 <= args.limit <= 500:
        parser.error("--limit must be between 1 and 500")

    if args.after_id < 0:
        parser.error("--after-id cannot be negative")

    if not 1 <= args.batch_size <= 32:
        parser.error(
            "--batch-size must be between 1 and 32"
        )

    mode = "APPLY" if args.apply else "DRY RUN"

    try:
        with SessionLocal() as db:
            scan = scan_jobs(
                db,
                limit=args.limit,
                after_id=args.after_id,
            )

            print(f"Mode: {mode}")
            print(f"Scanned jobs: {scan.scanned}")
            print(f"Unchanged embeddings: {scan.unchanged}")
            print(f"Embeddings needed: {len(scan.pending)}")

            if args.apply:
                for start in range(
                    0,
                    len(scan.pending),
                    args.batch_size,
                ):
                    batch = scan.pending[
                        start : start + args.batch_size
                    ]

                    documents = [
                        item.document
                        for item in batch
                    ]

                    vectors = embed_texts(documents)

                    try:
                        store_embeddings(
                            db,
                            list(zip(batch, vectors, strict=True)),
                        )
                        db.commit()

                    except Exception:
                        db.rollback()
                        raise

                print(
                    "Embeddings stored successfully."
                )
            else:
                print(
                    "Dry-run only. No embeddings written."
                )

            print(
                f"Last scanned job ID: {scan.last_job_id}"
            )

            if scan.scanned == args.limit:
                print(
                    "More jobs may remain. "
                    "Use --after-id with the last scanned ID."
                )

    except (
        EmbeddingError,
        SQLAlchemyError,
        RuntimeError,
        ValueError,
    ) as exc:
        print(
            f"Embedding backfill failed: {exc}",
            file=sys.stderr,
        )
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
