"""Structured result summary emitted by every ETL job."""

from dataclasses import dataclass, field


@dataclass
class JobSummary:
    """Outcome of one ETL job run, logged as a structured record.

    ``errors`` holds data-quality violations (distinct from ``rows_rejected``, which counts
    individual payloads dropped during validation). A non-empty ``errors`` marks the run failed.
    """

    job: str
    rows_processed: int = 0
    rows_rejected: int = 0
    duration_ms: int = 0
    errors: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, object]:
        return {
            "job": self.job,
            "rows_processed": self.rows_processed,
            "rows_rejected": self.rows_rejected,
            "duration_ms": self.duration_ms,
            "errors": self.errors,
        }
