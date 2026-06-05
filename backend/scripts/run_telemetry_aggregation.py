from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.services.telemetry_aggregation import run_aggregation


if __name__ == "__main__":
    run_aggregation(Path(r"D:\1 Ирито\5 WellInsight\telemetry"), 5, 10)
