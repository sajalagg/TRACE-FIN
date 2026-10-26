from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from app.core.config import BASE_DIR, get_db_path
from app.services.evaluation import compute_evaluation_report
from scripts.seed_demo_data import seed_database


def run_and_export_evaluation(
    threshold: int = 60,
    reseed: bool = False,
    output_dir: Path | None = None,
) -> dict[str, Path]:
    """Run the reproducible Stage 10 evaluation, print paper-ready tables, and export JSON/CSV."""
    db_path = get_db_path()
    if reseed or not db_path.exists():
        seed_database(db_path=db_path, total_transactions=500, seed=42)

    report = compute_evaluation_report(
        threshold=threshold,
        use_user_preferences_threshold=False,
        db_path=db_path,
    )

    out_dir = output_dir or (BASE_DIR / "data")
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "evaluation_report.json"
    csv_path = out_dir / "evaluation_methods_summary.csv"

    json_path.write_text(
        json.dumps(report.model_dump(), indent=2),
        encoding="utf-8",
    )

    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "method",
                "threshold",
                "TP",
                "FP",
                "TN",
                "FN",
                "precision",
                "recall",
                "f1_score",
                "false_positive_rate",
                "flagged_count",
                "flagged_percentage",
                "ato_detection_rate",
                "bec_detection_rate",
                "structuring_detection_rate",
                "capex_false_positive_rate",
            ]
        )
        for m_name, m in report.methods_comparison.items():
            cm = m.confusion_matrix
            writer.writerow(
                [
                    m_name,
                    threshold,
                    cm.true_positives,
                    cm.false_positives,
                    cm.true_negatives,
                    cm.false_negatives,
                    m.precision,
                    m.recall,
                    m.f1_score,
                    m.false_positive_rate,
                    m.flagged_count,
                    m.flagged_percentage,
                    m.ato_scenario_detection_rate,
                    m.bec_scenario_detection_rate,
                    m.structuring_scenario_detection_rate,
                    m.capex_false_positive_rate,
                ]
            )

    print("=" * 88)
    print(f"TRACE-Fin Reproducible Evaluation Report (Fixed Threshold = {threshold})")
    print("=" * 88)
    print(f"\nDisclaimer: {report.evaluation_disclaimer}\n")
    print("1. Overall Scoring Approach Comparison:")
    print(
        f"{'Method':<16} | {'Prec':>6} | {'Recall':>6} | {'F1':>6} | {'FPR':>6} | "
        f"{'Flagged':>10} | {'ATO Rec':>7} | {'BEC Rec':>7} | {'CapEx FPR':>9}"
    )
    print("-" * 88)
    for m_name, m in report.methods_comparison.items():
        print(
            f"{m_name:<16} | {m.precision:>6.4f} | {m.recall:>6.4f} | {m.f1_score:>6.4f} | "
            f"{m.false_positive_rate:>6.4f} | {m.flagged_count:>3} ({m.flagged_percentage:>4.1f}%) | "
            f"{m.ato_scenario_detection_rate:>7.2%} | {m.bec_scenario_detection_rate:>7.2%} | "
            f"{m.capex_false_positive_rate:>9.2%}"
        )

    print("\n2. Per-Scenario Flagging Rates:")
    print(
        f"{'Scenario Archetype':<34} | {'GT Class':<10} | {'Cases':>5} | "
        f"{'Baseline':>10} | {'Contextual':>10} | {'Ctx + TI':>10}"
    )
    print("-" * 88)
    for s in report.per_scenario_breakdown:
        print(
            f"{s.scenario_label:<34} | {s.ground_truth_class:<10} | {s.total_cases:>5} | "
            f"{s.baseline_flagged_count:>3} ({s.baseline_flagged_rate * 100:>4.0f}%) | "
            f"{s.contextual_flagged_count:>3} ({s.contextual_flagged_rate * 100:>4.0f}%) | "
            f"{s.contextual_ti_flagged_count:>3} ({s.contextual_ti_flagged_rate * 100:>4.0f}%)"
        )

    print("\n3. Per-Expenditure-Model Breakdown (OpEx vs CapEx vs Personal):")
    print(
        f"{'Expenditure Model':<22} | {'Txs':>4} | {'Base F1':>7} | {'Base FPR':>8} | "
        f"{'Ctx F1':>7} | {'Ctx FPR':>7} | {'TI F1':>7} | {'TI FPR':>7}"
    )
    print("-" * 88)
    for em in report.per_expenditure_model_breakdown:
        print(
            f"{em.expenditure_model:<22} | {em.total_transactions:>4} | "
            f"{em.baseline_f1:>7.4f} | {em.baseline_fpr:>8.4f} | "
            f"{em.contextual_f1:>7.4f} | {em.contextual_fpr:>7.4f} | "
            f"{em.contextual_ti_f1:>7.4f} | {em.contextual_ti_fpr:>7.4f}"
        )

    print(f"\nExported JSON report to: {json_path}")
    print(f"Exported CSV summary to: {csv_path}")
    print("=" * 88)

    return {"json": json_path, "csv": csv_path}


def main() -> None:
    parser = argparse.ArgumentParser(description="Run TRACE-Fin Stage 10 reproducible evaluation.")
    parser.add_argument("--threshold", type=int, default=60, help="Fixed risk score threshold (default: 60).")
    parser.add_argument("--reseed", action="store_true", help="Reset and reseed database before evaluating.")
    args = parser.parse_args()
    run_and_export_evaluation(threshold=args.threshold, reseed=args.reseed)


if __name__ == "__main__":
    main()
